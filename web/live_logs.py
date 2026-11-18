"""Tail the bot's log file for the live-log viewer.

The bot writes ``log.txt`` (rotated at 10 MB by RotatingFileHandler) in the
working directory shared with the web process. This module reads a recent
backlog and then follows the file:

* only complete lines are emitted (a half-written line waits for its newline);
* rotation is detected (new inode, or the file shrank) and reading restarts
  at the top of the new file;
* each batch carries a cursor ``"<inode>:<offset>"`` so a reconnecting
  browser resumes exactly where it stopped (SSE ``Last-Event-ID``).

Every line passes through the same redaction as the Telegram /log command.
"""

from __future__ import annotations

from asyncio import sleep, to_thread
from os import environ, stat
from pathlib import Path


def redact_log_text(text: str) -> str:
    # Imported lazily, like the rest of wserver's bot imports: importing the
    # bot package at module load would run its startup side effects.
    from bot.helper.ext_utils.log_redact import redact_log_text as _redact

    return _redact(text)

LOG_FILE = environ.get("AMATERASU_LOG_FILE", "log.txt")
BACKLOG_LINES = 500
BACKLOG_BYTES = 512 * 1024
POLL_SECONDS = 0.5
MAX_BATCH_BYTES = 256 * 1024


def _decode_lines(chunk: bytes) -> list[str]:
    text = chunk.decode("utf-8", errors="replace")
    # rstrip("\r"): tolerate CRLF logs (e.g. a Windows development checkout).
    return [redact_log_text(line.rstrip("\r")) for line in text.split("\n") if line.strip()]


def _identity(path: str) -> tuple[int, int] | None:
    try:
        st = stat(path)
    except OSError:
        return None
    # st_ino is 0 on some Windows filesystems; size still detects truncation.
    return st.st_ino, st.st_size


def parse_cursor(cursor: str | None) -> tuple[int, int] | None:
    try:
        inode, offset = (int(part) for part in (cursor or "").split(":", 1))
    except ValueError:
        return None
    return (inode, offset) if offset >= 0 else None


def read_backlog(
    path: str = LOG_FILE, max_lines: int = BACKLOG_LINES
) -> tuple[list[str], tuple[int, int]]:
    """The last ``max_lines`` complete lines and the cursor after them."""
    ident = _identity(path)
    if ident is None:
        return [], (0, 0)
    inode, size = ident
    start = max(0, size - BACKLOG_BYTES)
    with open(path, "rb") as fh:
        fh.seek(start)
        chunk = fh.read(size - start)
    end = chunk.rfind(b"\n") + 1  # stop after the last complete line
    body = chunk[:end]
    if start > 0:  # drop the partial first line of the window
        body = body[body.find(b"\n") + 1 :]
    return _decode_lines(body)[-max_lines:], (inode, start + end)


def read_from(path: str, cursor: tuple[int, int]) -> tuple[list[str], tuple[int, int], bool]:
    """New complete lines since ``cursor``; returns (lines, new cursor, rotated)."""
    ident = _identity(path)
    if ident is None:
        return [], cursor, False
    inode, size = ident
    old_inode, offset = cursor
    rotated = (old_inode and inode and inode != old_inode) or size < offset
    if rotated:
        offset = 0
    if size <= offset:
        return [], (inode, offset), bool(rotated)
    with open(path, "rb") as fh:
        fh.seek(offset)
        chunk = fh.read(min(size - offset, MAX_BATCH_BYTES))
    end = chunk.rfind(b"\n") + 1
    if end == 0:
        if len(chunk) >= MAX_BATCH_BYTES:  # one huge line: emit it anyway
            end = len(chunk)
        else:
            return [], (inode, offset), bool(rotated)
    return _decode_lines(chunk[:end]), (inode, offset + end), bool(rotated)


def read_redacted_log(path: str = LOG_FILE) -> str:
    """The whole current log file, redacted, for download."""
    return redact_log_text(Path(path).read_text(encoding="utf-8", errors="replace"))


async def follow(path: str = LOG_FILE, cursor: tuple[int, int] | None = None):
    """Async generator of ``(lines, cursor_str, rotated)`` batches, forever.

    Starts with the backlog unless resuming from a valid ``cursor``.
    Yields an empty batch roughly every poll so callers can heartbeat and
    notice disconnected clients.
    """
    if cursor is None:
        lines, pos = await to_thread(read_backlog, path)
        yield lines, f"{pos[0]}:{pos[1]}", False
    else:
        pos = cursor
    while True:
        lines, pos, rotated = await to_thread(read_from, path, pos)
        yield lines, f"{pos[0]}:{pos[1]}", rotated
        if not lines:
            await sleep(POLL_SECONDS)
