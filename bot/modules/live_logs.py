"""Private links to the web live-log viewer (/app/logs).

A signed link is a bearer credential, so it is never posted in a group:
the "LIVE LOGS" buttons on /log and /status deliver it to the requesting
owner/sudo user's private chat instead.
"""

from urllib.parse import urlencode

from pyrogram.enums import ChatType

from web.security import make_signed_token

from ..core.config_manager import Config
from ..helper.ext_utils.bot_utils import get_web_secret
from ..helper.telegram_helper.button_build import ButtonMaker
from ..helper.telegram_helper.filters import CustomFilters
from ..helper.telegram_helper.message_utils import send_message

LIVE_LOGS_PURPOSE = "live-logs"  # must match web/wserver.py
LIVE_LOGS_TTL_SECONDS = 3600
LIVE_LOGS_BUTTON = "◉ LIVE LOGS"


def live_logs_url(user_id: int) -> str:
    token = make_signed_token(
        get_web_secret(), LIVE_LOGS_PURPOSE, user_id, ttl=LIVE_LOGS_TTL_SECONDS
    )
    query = urlencode({"user_id": user_id, "token": token})
    return f"{Config.BASE_URL.rstrip('/')}/app/logs?{query}"


async def send_live_logs_link(client, query) -> None:
    """Handle a LIVE LOGS button press: DM a private link to owner/sudo."""
    user = query.from_user
    if user is None or not await CustomFilters.sudo(client, query):
        await query.answer("Live logs are for the owner and sudo users.", show_alert=True)
        return
    if not Config.BASE_URL:
        await query.answer(
            "Live logs need BASE_URL configured with the bot's public address.",
            show_alert=True,
        )
        return
    buttons = ButtonMaker()
    buttons.url_button("OPEN LIVE LOGS", live_logs_url(user.id))
    text = (
        "<b>✦ LIVE LOGS</b>\n"
        "Watch the bot's log in real time: pause, search, copy and download.\n"
        "<i>This private link expires in one hour. Anyone holding it can read "
        "the (redacted) log, so do not forward it.</i>"
    )
    result = await send_message(user.id, text, buttons.build_menu(1))
    if isinstance(result, str):
        # The user never started a private chat with the bot.
        await query.answer(
            "Start a private chat with the bot first, then press LIVE LOGS again.",
            show_alert=True,
        )
        return
    in_private = getattr(getattr(query.message, "chat", None), "type", None) == ChatType.PRIVATE
    await query.answer(
        "Link sent below." if in_private else "Sent the live-log link to your private chat.",
        show_alert=not in_private,
    )
