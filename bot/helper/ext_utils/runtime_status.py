"""Bot runtime status shared with the web process.

The web UI runs in a separate gunicorn process (see bot/core/startup.py), so
it cannot read the bot's in-memory ``task_dict``. The bot publishes a tiny
JSON snapshot to a temp file every couple of seconds; the web server reads it
for ``/api/status`` and ``/metrics``. A missing or stale snapshot means the
bot is not reporting, and readers must say so instead of showing zero.

The reader has no ``bot`` imports so the web process can use it cheaply.
"""

from __future__ import annotations

from json import dumps, loads
from os import environ, replace
from pathlib import Path
from time import time

BOT_STATUS_FILE = environ.get(
    "AMATERASU_BOT_STATUS_FILE", "/tmp/amaterasu-bot-status.json"
)
PUBLISH_INTERVAL_SECONDS = 2.0
# Several missed publishes in a row: treat the bot as not reporting.
STALE_AFTER_SECONDS = 15.0


def write_bot_status(
    active_tasks: int,
    started_at: float,
    path: str | Path = BOT_STATUS_FILE,
    now: float | None = None,
) -> None:
    """Atomically write one snapshot (write a temp file, then rename)."""
    target = Path(path)
    payload = {
        "active_tasks": int(active_tasks),
        "started_at": float(started_at),
        "updated_at": float(time() if now is None else now),
    }
    tmp = target.with_name(f".{target.name}.tmp")
    tmp.write_text(dumps(payload), encoding="utf-8")
    replace(tmp, target)


def read_bot_status(
    path: str | Path = BOT_STATUS_FILE,
    now: float | None = None,
    stale_after: float = STALE_AFTER_SECONDS,
) -> dict | None:
    """Return the latest fresh snapshot, or None when missing, invalid or stale."""
    try:
        data = loads(Path(path).read_text(encoding="utf-8"))
        active = int(data["active_tasks"])
        started = float(data["started_at"])
        updated = float(data["updated_at"])
    except (OSError, ValueError, TypeError, KeyError):
        return None
    current = time() if now is None else now
    if active < 0 or current - updated > stale_after or updated + 1 < started:
        return None
    return {"active_tasks": active, "started_at": started, "updated_at": updated}


async def publish_bot_status(interval: float = PUBLISH_INTERVAL_SECONDS) -> None:
    """Bot-side loop: publish the live task count until cancelled."""
    from asyncio import sleep, to_thread

    from bot import LOGGER, bot_start_time, task_dict

    warned = False
    while True:
        try:
            await to_thread(write_bot_status, len(task_dict), bot_start_time)
            warned = False
        except Exception as exc:  # never let status publishing hurt the bot
            if not warned:
                LOGGER.warning(f"Could not publish bot status for the web UI: {exc}")
                warned = True
        await sleep(interval)
