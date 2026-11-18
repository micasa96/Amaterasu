from .. import bot_cache, task_dict, task_dict_lock
from ..helper.ext_utils.bot_utils import (
    arg_parser,
    new_task,
    sync_to_async,
)
from ..helper.ext_utils.links_utils import is_gdrive_link
from ..helper.ext_utils.status_utils import (
    MirrorStatus,
    get_task_by_gid,
)
from ..helper.mirror_leech_utils.gdrive_utils.helper import GoogleDriveHelper
from ..helper.telegram_helper.filters import CustomFilters
from ..helper.telegram_helper.message_utils import (
    drive_category_prompt,
    edit_message,
    open_category_btns,
    send_message,
)


async def change_category(client, message):
    if not message.from_user:
        return
    user_id = message.from_user.id

    text = message.text.split("\n")
    input_list = text[0].split()

    arg_base = {"link": "", "-id": "", "-index": ""}
    arg_parser(input_list[1:], arg_base)

    drive_id = arg_base["-id"]
    index_link = arg_base["-index"]

    if drive_id and is_gdrive_link(drive_id):
        drive_id = GoogleDriveHelper().get_id_from_url(drive_id)

    dl = None
    if gid := arg_base["link"]:
        dl = await get_task_by_gid(gid)
        if not dl:
            await send_message(message, f"GID: <code>{gid}</code> Not Found.")
            return
    if reply_to := message.reply_to_message:
        async with task_dict_lock:
            dl = task_dict.get(reply_to.id, None)
        if not dl:
            await send_message(message, "This is not an active task!")
            return
    if not dl:
        await send_message(message, "Provide a task GID or reply to an active task.")
        return
    if (
        not await CustomFilters.sudo("", message)
        and dl.listener.message.from_user.id != user_id
    ):
        await send_message(message, "This task is not for you!")
        return
    if dl.status() not in [
        MirrorStatus.STATUS_DOWNLOAD,
        MirrorStatus.STATUS_PAUSED,
        MirrorStatus.STATUS_QUEUEDL,
    ]:
        await send_message(
            message,
            f"Task should be on {MirrorStatus.STATUS_DOWNLOAD} or "
            f"{MirrorStatus.STATUS_PAUSED} or {MirrorStatus.STATUS_QUEUEDL}",
        )
        return
    listener = dl.listener if hasattr(dl, "listener") else None
    if listener and not listener.is_leech:
        if not index_link and not drive_id:
            try:
                drive_id, index_link, is_cancelled = await open_category_btns(message)
            except ValueError as error:
                return await send_message(message, str(error))
            if is_cancelled:
                listener.is_cancelled = True
                return
        if not index_link and not drive_id:
            return await send_message(message, "Time out")
        msg = "<b>Task has been Updated Successfully!</b>"
        if drive_id:
            if not (
                folder_meta := await sync_to_async(
                    GoogleDriveHelper().get_file_metadata, drive_id
                )
            ):
                return await send_message(
                    message, "Google Drive id validation failed!!"
                )
            if listener.drive_id and listener.drive_id == drive_id:
                msg += (
                    f"\n\n<b>Folder name</b> : {folder_meta['name']} Already selected"
                )
            else:
                msg += f"\n\n<b>Folder name</b> : {folder_meta['name']}"
            listener.drive_id = drive_id
        if index_link:
            listener.index_link = index_link
            msg += f"\n\n<b>Index Link</b> : <code>{index_link}</code>"
        return await send_message(message, msg)
    else:
        await send_message(message, "Can not change Category for this task!")


@new_task
async def confirm_category(client, query):
    parts = query.data.split(maxsplit=2)
    if len(parts) != 3:
        return await query.answer()
    _, picker_id, action = parts
    state = bot_cache.get(("drive_category", picker_id))
    if (
        not state
        or state["chat_id"] != query.message.chat.id
        or state["finished"].is_set()
    ):
        return await query.answer(text="This picker has expired.", show_alert=True)
    if query.from_user.id != state["user_id"] and not await CustomFilters.sudo("", query):
        return await query.answer(text="This task is not for you!", show_alert=True)
    if state["finished"].is_set():
        return await query.answer(text="This picker has expired.", show_alert=True)
    if action in ("done", "cancel"):
        state["cancelled"] = action == "cancel"
        if state["selected"] is None:
            state["selected"] = 0
        state["finished"].set()
        return await query.answer()
    if not (
        action.isascii() and action.isdecimal() and int(action) < len(state["categories"])
    ):
        return await query.answer(text="Invalid category.", show_alert=True)
    state["selected"] = int(action)
    await query.answer()
    if not state["finished"].is_set():
        await edit_message(query.message, *drive_category_prompt(picker_id, state))


