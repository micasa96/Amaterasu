import ast
from asyncio import Event, Lock, wait_for
from html import escape
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
from urllib.parse import quote

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ID = "a" * 33
CATEGORY_ID = "b" * 33


def load_functions(namespace, path, *names, class_name=None):
    source = ROOT / path
    nodes = ast.parse(source.read_bytes()).body
    if class_name:
        nodes = next(node.body for node in nodes if getattr(node, "name", None) == class_name)
    functions = [node for node in nodes if getattr(node, "name", None) in names]
    for function in functions:
        function.decorator_list = []
    exec(compile(ast.Module(functions, type_ignores=[]), str(source), "exec"), namespace)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "source,enabled,destination,category,expected,prompt",
    [
        ("https://example.test/file.zip", True, "", "", CATEGORY_ID, True),
        ("", True, "", "", CATEGORY_ID, True),
        ("", False, "", "", "remote:folder", False),
        ("", True, "gd", "", DEFAULT_ID, False),
        ("", True, "", "TV_Shows", CATEGORY_ID, False),
    ],
)
async def test_mirror_destination(source, enabled, destination, category, expected, prompt):
    settings = {
        "drive_cat_mode": enabled,
        "DRIVE_CAT": {"TV_Shows": {"drive_id": CATEGORY_ID, "index_link": "category-index"}},
    }
    config = NS(
        DRIVE_CATEGORY_MODE=True,
        NAME_SWAP="",
        RCLONE_FLAGS="",
        TRANSMISSION_MODE="",
        UPLOAD_PATHS={},
        GDRIVE_ID=DEFAULT_ID,
        INDEX_URL="",
        STOP_DUPLICATE=False,
        DEFAULT_UPLOAD="rc",
        RCLONE_PATH="remote:folder",
        _normalize_default_upload=str,
    )
    picker = AsyncMock(return_value=(CATEGORY_ID, "category-index", False))
    namespace = dict(
        Config=config,
        user_data={17: settings},
        categories_dict={},
        excluded_extensions=[],
        is_gdrive_id=lambda value: value in {DEFAULT_ID, CATEGORY_ID},
        is_rclone_path=lambda value: value.startswith("remote:"),
        is_gdrive_link=lambda value: False,
        aiopath=NS(exists=AsyncMock(return_value=False)),
        open_category_btns=picker,
    )
    load_functions(namespace, "bot/helper/ext_utils/bot_utils.py", "fetch_drive_cat")
    load_functions(namespace, "bot/helper/telegram_helper/message_utils.py", "get_drive_categories")
    load_functions(namespace, "bot/helper/common.py", "before_start", class_name="TaskConfig")
    task = NS(
        user_id=17,
        user_dict=settings,
        message=object(),
        link=source,
        up_dest=destination,
        category=category,
        upload_index_url=None,
        is_leech=False,
        is_jd=False,
        is_uphoster=False,
        is_clone=False,
        name_swap="",
        rc_flags="",
        ffmpeg_cmds=None,
        _prepare_leech_dumps=AsyncMock(),
        is_token_exists=AsyncMock(),
    )

    await namespace["before_start"](task, auto_drive_category=True)

    assert picker.await_count == int(prompt)
    assert task.up_dest == expected
    assert task.upload_index_url == ("category-index" if expected == CATEGORY_ID else None)


class Buttons:
    def __init__(self):
        self.items = []

    def data_button(self, label, callback, *_args, **_kwargs):
        self.items.append((label, callback))

    url_button = data_button

    def build_menu(self, _columns):
        return self.items


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "actions,expected",
    [
        (["done"], (DEFAULT_ID, "default-index", False)),
        (["1", "done"], (CATEGORY_ID, "category-index", False)),
        (["cancel"], (None, None, True)),
        ([], (DEFAULT_ID, "default-index", False)),
    ],
)
async def test_drive_picker(actions, expected):
    message = NS(from_user=NS(id=17), chat=NS(id=12))

    def get_categories(_user_id):
        return {
            "Default": {"drive_id": DEFAULT_ID, "index_link": "default-index"},
            "TV_Shows & Movies": {"drive_id": CATEGORY_ID, "index_link": "category-index"},
        }

    async def send_prompt(_message, _text, buttons):
        callbacks = [data for _, data in buttons]
        assert all(len(data.encode()) <= 64 for data in callbacks)
        confirm = namespace["confirm_category"]
        unauthorized = NS(
            from_user=NS(id=18), message=message, data=callbacks[-1], answer=AsyncMock()
        )
        await confirm(None, unauthorized)
        assert unauthorized.answer.await_args.kwargs["show_alert"]
        for action in actions:
            data = next(data for data in callbacks if data.endswith(f" {action}"))
            await confirm(
                None,
                NS(from_user=message.from_user, message=message, data=data, answer=AsyncMock()),
            )
        return message

    async def wait_for_action(coroutine, timeout):
        assert timeout == 60
        await wait_for(coroutine, timeout=0.01)

    namespace = dict(
        Event=Event,
        wait_for=wait_for_action,
        token_hex=lambda _size: "picker",
        bot_cache={},
        ButtonMaker=Buttons,
        ButtonStyle=NS(DANGER=1, SUCCESS=2),
        Message=NS,
        get_drive_categories=get_categories,
        html_escape=escape,
        CustomFilters=NS(sudo=AsyncMock(return_value=False)),
        send_message=send_prompt,
        delete_message=AsyncMock(),
        edit_message=AsyncMock(),
    )
    load_functions(
        namespace,
        "bot/helper/telegram_helper/message_utils.py",
        "drive_category_prompt",
        "open_category_btns",
    )
    load_functions(namespace, "bot/modules/category_select.py", "confirm_category")

    assert await namespace["open_category_btns"](message, use_default_on_timeout=True) == expected
    assert not namespace["bot_cache"]
    if actions == ["1", "done"]:
        assert "TV_Shows &amp; Movies" in namespace["edit_message"].await_args.args[1]


@pytest.mark.asyncio
async def test_file_completion_uses_selected_category_index():
    config = NS(INCOMPLETE_TASK_NOTIFIER=False, INC_TASK_RESUME=False, SHOW_CLOUD_LINK=True)
    send = AsyncMock()
    namespace = dict(
        Config=config,
        LOGGER=NS(info=lambda *_args: None),
        send_message=send,
        ButtonMaker=Buttons,
        ButtonStyle=NS(PRIMARY=1),
        rutils=NS(quote=quote),
        escape=escape,
        _completion_header=lambda *_args: "",
        _premium_row=lambda *_args, **_kwargs: "",
        get_readable_file_size=str,
        get_readable_time=str,
        time=lambda: 0,
        clean_target=AsyncMock(),
        queue_dict_lock=Lock(),
        non_queued_up=set(),
        start_from_queued=AsyncMock(),
    )
    load_functions(
        namespace,
        "bot/helper/listeners/task_listener.py",
        "on_upload_complete",
        class_name="TaskListener",
    )
    task = NS(
        is_yt=False,
        is_leech=False,
        is_merge=False,
        name="Example File.mp4",
        size=1,
        message=NS(date=NS(timestamp=lambda: 0)),
        mode=("Telegram", "Drive"),
        tag="user",
        upload_index_url="https://index.example.test/movies/",
        bot_pm=False,
        thumb=None,
        seed=True,
        mid=14,
        up_dir="",
    )

    await namespace["on_upload_complete"](
        task, "https://drive.google.com/file/d/mock", 1, 0, "video/mp4"
    )

    urls = [url for _, url in send.await_args.args[2]]
    assert "https://index.example.test/movies/Example%20File.mp4" in urls
    assert "https://index.example.test/movies/Example%20File.mp4?a=view" in urls
