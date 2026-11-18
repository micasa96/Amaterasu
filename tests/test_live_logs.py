"""Live-log tailing: backlog, partial lines, rotation, resume, redaction, access."""

import asyncio
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name, rel):
    spec = spec_from_file_location(name, ROOT / rel)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


redact = _load("amaterasu_log_redact", "bot/helper/ext_utils/log_redact.py")
live = _load("amaterasu_live_logs", "web/live_logs.py")
# Use the real redaction rules without importing the bot package.
live.redact_log_text = redact.redact_log_text


def _append(path, data: bytes):
    with open(path, "ab") as fh:
        fh.write(data)


def test_crlf_logs_do_not_leak_carriage_returns(tmp_path):
    log = tmp_path / "log.txt"
    log.write_bytes(b"one\r\ntwo\r\n")
    lines, _ = live.read_backlog(str(log))
    assert lines == ["one", "two"]


def test_backlog_returns_complete_lines_and_a_resume_cursor(tmp_path):
    log = tmp_path / "log.txt"
    log.write_bytes(b"one\ntwo\nthree\npartial")
    lines, (_inode, offset) = live.read_backlog(str(log), max_lines=2)
    assert lines == ["two", "three"]
    assert offset == len(b"one\ntwo\nthree\n")  # stops before the partial line


def test_follow_waits_for_newline_then_emits_appended_lines(tmp_path):
    log = tmp_path / "log.txt"
    log.write_bytes(b"a\n")
    _, pos = live.read_backlog(str(log))
    _append(log, b"half")
    lines, pos2, rotated = live.read_from(str(log), pos)
    assert (lines, pos2, rotated) == ([], pos, False)
    _append(log, b" done\nnext\n")
    lines, pos3, rotated = live.read_from(str(log), pos2)
    assert lines == ["half done", "next"] and not rotated
    assert pos3[1] == log.stat().st_size


def test_rotation_restarts_from_the_top_of_the_new_file(tmp_path):
    log = tmp_path / "log.txt"
    log.write_bytes(b"x" * 50 + b"\n")
    _, pos = live.read_backlog(str(log))
    log.write_bytes(b"fresh\n")  # truncated: smaller than the cursor
    lines, _, rotated = live.read_from(str(log), pos)
    assert rotated and lines == ["fresh"]


def test_lines_are_redacted_before_they_leave_the_server(tmp_path):
    log = tmp_path / "log.txt"
    log.write_bytes(
        b"GET /qbit/?pass=hunter2\n"
        b"mongodb://user:secret@db/app\n"
        b"token 123456789:AAFabcdefghijklmnopqrstuvwxyz0123456\n"
    )
    lines, _ = live.read_backlog(str(log))
    joined = "\n".join(lines) + live.read_redacted_log(str(log))
    for secret in ("hunter2", "secret@", "AAFabcdefghijklmnopqrstuvwxyz0123456"):
        assert secret not in joined
    assert "123456789:[REDACTED]" in joined


def test_cursor_round_trip_and_follow_resumes_without_backlog(tmp_path):
    assert live.parse_cursor("12:345") == (12, 345)
    assert live.parse_cursor("garbage") is None and live.parse_cursor(None) is None
    log = tmp_path / "log.txt"
    log.write_bytes(b"old\n")
    _, pos = live.read_backlog(str(log))
    _append(log, b"new\n")

    async def first_batch():
        gen = live.follow(str(log), cursor=pos)
        batch = await gen.__anext__()
        await gen.aclose()
        return batch

    lines, cursor, _ = asyncio.run(first_batch())
    assert lines == ["new"]  # resumed: no repeated backlog
    assert live.parse_cursor(cursor)[1] == log.stat().st_size


def test_log_routes_are_private_and_bot_links_are_sent_privately():
    source = (ROOT / "web" / "wserver.py").read_text(encoding="utf-8")
    for route in ("/app/logs", "/api/logs/stream", "/api/logs/download"):
        handler = source.split(f'@app.get("{route}"', 1)[1].split("\n@app", 1)[0]
        assert "_live_logs_viewer(request)" in handler
    gate = source.split("def _live_logs_viewer", 1)[1].split("\ndef ", 1)[0]
    # Never public: there is no "allow when LOGIN_PASS is unset" branch.
    assert "if not _login_pass_configured()" not in gate
    bot = (ROOT / "bot" / "modules" / "live_logs.py").read_text(encoding="utf-8")
    assert "CustomFilters.sudo" in bot
    assert "send_message(user.id" in bot  # delivered to the user's private chat
