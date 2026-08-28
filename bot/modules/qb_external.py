# ruff: noqa: F403, F405
"""
Phase 6.9 — External qBittorrent integration.

This module lets Amaterasu leech torrents that already live in an
EXTERNALLY-MANAGED qBittorrent (USE_EXTERNAL_QBITTORRENT=True). It does
NOT re-download anything: it reuses the files already present on disk at
the torrent's content_path and feeds them straight into the leech upload
pipeline.

Commands:
  /leechhash <hash> [hash2 ...]   Upload one or more already-completed
                                  torrents from your external qBittorrent
                                  to Telegram (force, ignores the store).
  /leechhash <name>               Upload by torrent name (first match).
  /qbautowatch on|off             Toggle auto-upload of newly completed
                                  torrents.
  /qbautowatch status             Show state + how many hashes recorded.
  /qbautowatch reset              Forget all recorded hashes (next run
                                  re-uploads everything as "new").

The auto-watch loop only acts on torrents whose completion state is
"complete for upload" AND whose hash is NOT already in the Mongo store.
Hash recording survives bot restarts.
"""
from asyncio import sleep

from pyrogram.filters import command
from pyrogram.handlers import MessageHandler

from .. import (
    DOWNLOAD_DIR,
    LOGGER,
    bot_loop,
    task_dict,
    task_dict_lock,
)
from ..core.config_manager import Config
from ..core.torrent_manager import TorrentManager
from ..helper.ext_utils.bot_utils import new_task
from ..helper.ext_utils.db_handler import database
from ..helper.telegram_helper.bot_commands import BotCommands
from ..helper.telegram_helper.filters import CustomFilters
from ..helper.telegram_helper.message_utils import (
    delete_links,
    delete_message,
    send_message,
)
from ..helper.mirror_leech_utils.qbit_compat import (
    is_complete_for_upload,
    is_download_state,
    is_metadata_state,
)
from ..helper.mirror_leech_utils.status_utils.qbit_status import (
    QbittorrentStatus,
)


async def _resolve_torrents(identifiers):
    """Resolve a list of hashes/names to torrent info objects.

    Returns (resolved_list, errors_list). Each resolved entry is the
    aioqbt torrent info object.
    """
    if TorrentManager.qbittorrent is None:
        await TorrentManager.ensure_qbit()
    if TorrentManager.qbittorrent is None:
        return [], ["qBittorrent is not connected."]
    try:
        all_torrents = await TorrentManager.qbittorrent.torrents.info()
    except Exception as e:
        return [], [f"Failed to list torrents: {e}"]
    by_hash = {t.hash.lower(): t for t in all_torrents}
    resolved = []
    errors = []
    for ident in identifiers:
        key = ident.strip().lower()
        if key in by_hash:
            resolved.append(by_hash[key])
            continue
        # Try by exact (case-insensitive) name
        matches = [t for t in all_torrents if t.name.lower() == key]
        if len(matches) == 1:
            resolved.append(matches[0])
            continue
        # Try by substring (case-insensitive) — single match only
        sub = [t for t in all_torrents if key in t.name.lower()]
        if len(sub) == 1:
            resolved.append(sub[0])
            continue
        if len(sub) > 1:
            errors.append(
                f"'{ident}' matches {len(sub)} torrents by name — be more specific."
            )
            continue
        errors.append(f"'{ident}' not found in your qBittorrent.")
    return resolved, errors


class _ExternalQbStatus(QbittorrentStatus):
    """Minimal status shim so on_download_complete() can read name/gid.

    The real QbittorrentStatus pulls from live qBittorrent; here we just
    expose the already-known torrent name and hash so the upload pipeline
    proceeds without re-querying (and without re-downloading).
    """

    def __init__(self, listener, tor_info):
        # QbittorrentStatus.__init__ signature varies; build our own attrs.
        self.listener = listener
        self.message = getattr(listener, "message", None)
        self._name = tor_info.name
        self._hash = tor_info.hash

    def name(self):
        return self._name

    def gid(self):
        return self._hash[:12]

    def progress(self):
        return "100.0"


async def _leech_external_torrent(listener, tor_info):
    """Run the leech upload for an already-completed external torrent.

    Reuses TaskListener.on_download_complete() logic by preparing a
    listener whose dir points at a symlink to the torrent's content_path
    on disk. No qBittorrent re-download occurs.
    """
    from aiofiles.os import path as aiopath, symlink, makedirs

    content_path = getattr(tor_info, "content_path", None)
    if not content_path or not await aiopath.exists(content_path):
        save_path = getattr(tor_info, "save_path", "") or ""
        content_path = f"{save_path.rstrip('/')}/{tor_info.name}"
    if not await aiopath.exists(content_path):
        await listener.on_download_error(
            f"Torrent files not found on disk at: {content_path}\n"
            "Make sure Amaterasu runs on the same host/filesystem as "
            "your external qBittorrent."
        )
        return

    listener.is_qbit = True
    listener.is_torrent = True
    listener.is_leech = True
    listener.seed = False
    listener.name = tor_info.name
    listener.dir = f"{DOWNLOAD_DIR}{listener.mid}"
    await makedirs(listener.dir, exist_ok=True)
    link_name = f"{listener.dir}/{tor_info.name}"
    if not await aiopath.exists(link_name):
        try:
            await symlink(content_path, link_name)
        except Exception as e:
            await listener.on_download_error(f"Failed to link torrent files: {e}")
            return

    # Register a minimal status entry so on_download_complete() finds it.
    async with task_dict_lock:
        task_dict[listener.mid] = _ExternalQbStatus(listener, tor_info)

    # Mark done -> triggers the upload pipeline (leeches to Telegram).
    await listener.on_download_complete()


@new_task
async def leechhash(client, message):
    if not Config.USE_EXTERNAL_QBITTORRENT:
        await send_message(
            message,
            "External qBittorrent is not enabled.\n"
            "Set USE_EXTERNAL_QBITTORRENT=True in config.py first.",
        )
        return
    if Config.DISABLE_LEECH:
        await send_message(message, "Leech is currently disabled.")
        return

    parts = message.text.split()
    if len(parts) < 2:
        await send_message(
            message,
            "Usage:\n"
            "<code>/leechhash &lt;hash or name&gt;</code>  (space-separated, multiple allowed)\n"
            "Uploads already-completed torrents from your external qBittorrent to Telegram.",
        )
        return

    await delete_links(message)
    wait = await send_message(message, "<b>Resolving torrent(s)...</b>")
    resolved, errors = await _resolve_torrents(parts[1:])
    if errors:
        await send_message(message, "\n".join(errors))
    if not resolved:
        await delete_message(wait)
        return

    sent = 0
    for tor in resolved:
        if is_metadata_state(tor.state):
            await send_message(
                message, f"⚠️ <code>{tor.name}</code> still fetching metadata, skip."
            )
            continue
        if is_download_state(tor.state):
            await send_message(
                message,
                f"⚠️ <code>{tor.name}</code> is still downloading "
                f"({int(tor.progress * 100)}%), skip.",
            )
            continue
        # Build a real Mirror listener (sets mid/dir/name from message),
        # then drive the upload directly (no new_event -> no re-download).
        from ..modules.mirror_leech import Mirror

        listener = Mirror(client, message, is_qbit=True, is_leech=True)
        listener.is_torrent = True
        try:
            await _leech_external_torrent(listener, tor)
            sent += 1
        except Exception as e:
            LOGGER.error(f"leechhash upload failed for {tor.hash}: {e}")
            await send_message(
                message, f"❌ Error uploading <code>{tor.name}</code>: {e}"
            )
    await delete_message(wait)
    if sent:
        # Record hashes so auto-watch won't re-upload these later.
        await database.add_qb_external_leeched([t.hash for t in resolved])


# ---------------------------------------------------------------------------
# Auto-watch loop
# ---------------------------------------------------------------------------
_autowatch_task = None


async def _autowatch_loop():
    while Config.QB_EXTERNAL_AUTOWATCH and Config.USE_EXTERNAL_QBITTORRENT:
        try:
            if TorrentManager.qbittorrent is None:
                await TorrentManager.ensure_qbit()
            if TorrentManager.qbittorrent is None:
                await sleep(Config.QB_EXTERNAL_AUTOWATCH_INTERVAL)
                continue
            torrents = await TorrentManager.qbittorrent.torrents.info()
            recorded = await database.get_qb_external_leeched()
            new_hashes = []
            for tor in torrents:
                if not is_complete_for_upload(tor):
                    continue
                if tor.hash in recorded:
                    continue
                # New completed torrent -> auto leech to owner.
                from ..core.tg_client import TgClient
                from ..modules.mirror_leech import Mirror

                owner_msg = await TgClient.bot.send_message(
                    Config.OWNER_ID,
                    f"<b>Auto-watch:</b> uploading <code>{tor.name}</code> to Telegram...",
                )
                listener = Mirror(
                    TgClient.bot, owner_msg, is_qbit=True, is_leech=True
                )
                listener.is_torrent = True
                try:
                    await _leech_external_torrent(listener, tor)
                    new_hashes.append(tor.hash)
                except Exception as e:
                    LOGGER.error(f"autowatch upload failed for {tor.hash}: {e}")
            if new_hashes:
                await database.add_qb_external_leeched(new_hashes)
                LOGGER.info("Auto-watch uploaded %d new torrent(s).", len(new_hashes))
        except Exception as e:
            LOGGER.error(f"autowatch loop error: {e}")
        await sleep(Config.QB_EXTERNAL_AUTOWATCH_INTERVAL)


@new_task
async def qbautowatch(client, message):
    if not Config.USE_EXTERNAL_QBITTORRENT:
        await send_message(
            message,
            "External qBittorrent is not enabled.\n"
            "Set USE_EXTERNAL_QBITTORRENT=True in config.py first.",
        )
        return
    parts = message.text.split()
    sub = parts[1].lower() if len(parts) > 1 else ""
    global _autowatch_task
    if sub == "on":
        if Config.QB_EXTERNAL_AUTOWATCH:
            await send_message(message, "Auto-watch is already ON.")
            return
        Config.QB_EXTERNAL_AUTOWATCH = True
        if _autowatch_task is None or _autowatch_task.done():
            _autowatch_task = bot_loop.create_task(_autowatch_loop())
        await send_message(
            message,
            f"✅ Auto-watch ON. New completed torrents will be uploaded every "
            f"{Config.QB_EXTERNAL_AUTOWATCH_INTERVAL}s.",
        )
    elif sub == "off":
        Config.QB_EXTERNAL_AUTOWATCH = False
        await send_message(message, "⏹️ Auto-watch OFF.")
    elif sub == "reset":
        await database.reset_qb_external_leeched()
        await send_message(
            message,
            "🗑️ Recorded hashes cleared. Next auto-watch run treats all "
            "completed torrents as new.",
        )
    elif sub == "status":
        recorded = await database.get_qb_external_leeched()
        state = "ON" if Config.QB_EXTERNAL_AUTOWATCH else "OFF"
        await send_message(
            message,
            f"<b>Auto-watch:</b> {state}\n"
            f"<b>Recorded hashes:</b> {len(recorded)}",
        )
    else:
        await send_message(
            message,
            "Usage:\n"
            "<code>/qbautowatch on</code> — start auto-uploading new torrents\n"
            "<code>/qbautowatch off</code> — stop\n"
            "<code>/qbautowatch status</code> — show state & recorded count\n"
            "<code>/qbautowatch reset</code> — forget recorded hashes",
        )


def register_qb_external_handlers():
    """Wire up handlers. Called from core.handlers.add_handlers()."""
    from ..core.tg_client import TgClient

    if TgClient.bot is None:
        LOGGER.warning("TgClient.bot is None; skipping qb_external handlers.")
        return
    TgClient.bot.add_handler(
        MessageHandler(
            leechhash,
            filters=command(BotCommands.LeechHashCommand, case_sensitive=True)
            & CustomFilters.authorized,
        )
    )
    TgClient.bot.add_handler(
        MessageHandler(
            qbautowatch,
            filters=command(BotCommands.QbAutoWatchCommand, case_sensitive=True)
            & CustomFilters.sudo,
        )
    )


async def maybe_start_autowatch():
    """Start the loop at boot if auto-watch is enabled in config."""
    global _autowatch_task
    if Config.USE_EXTERNAL_QBITTORRENT and Config.QB_EXTERNAL_AUTOWATCH:
        if _autowatch_task is None or _autowatch_task.done():
            _autowatch_task = bot_loop.create_task(_autowatch_loop())
            LOGGER.info("External qBittorrent auto-watch started.")


async def stop_autowatch():
    global _autowatch_task
    Config.QB_EXTERNAL_AUTOWATCH = False
    if _autowatch_task is not None and not _autowatch_task.done():
        _autowatch_task.cancel()
