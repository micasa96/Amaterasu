import ast
import asyncio
import importlib.util
import sys
from pathlib import Path
from types import MethodType, ModuleType, SimpleNamespace

import pytest

MODULE_PATH = (
    Path(__file__).parents[1]
    / "bot"
    / "helper"
    / "telegram_helper"
    / "tg_stream.py"
)
WSERVER_PATH = Path(__file__).parents[1] / "web" / "wserver.py"


@pytest.fixture
def go_bridge():
    path = MODULE_PATH.parents[1] / "ext_utils" / "go_bridge.py"
    spec = importlib.util.spec_from_file_location("amaterasu_go_bridge_test", path)
    bridge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bridge)
    return bridge


@pytest.mark.asyncio
async def test_go_range_resumes_at_first_missing_byte(monkeypatch, go_bridge):
    import httpx

    bridge = go_bridge
    client = SimpleNamespace()
    monkeypatch.setattr(bridge, "media_request", lambda *args: {})

    class InterruptedRange(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"a"
            raise httpx.ReadError("interrupted")

    def fake_client(response):
        return httpx.AsyncClient(
            base_url="http://sidecar", transport=httpx.MockTransport(lambda _req: response)
        )

    monkeypatch.setattr(bridge, "go_client", lambda: fake_client(httpx.Response(503)))
    assert [part async for part in bridge.stream_range(client, "id", 10, 2, 4)] == []

    response = httpx.Response(
        206,
        headers={"Content-Range": "bytes 2-4/10", "Content-Length": "3"},
        stream=InterruptedRange(),
    )
    def go_client():
        def handle(request):
            if request.url.path == "/v1/cooldown":
                return httpx.Response(429, headers={"Retry-After": "60"})
            return response

        return httpx.AsyncClient(base_url="http://sidecar", transport=httpx.MockTransport(handle))

    monkeypatch.setattr(bridge, "go_client", go_client)
    offsets = []

    async def resume(offset):
        assert offset == 3
        assert client._amaterasu_go_flood_until > bridge.monotonic()
        yield b"bc"

    stream = bridge.stream_range(client, "id", 10, 2, 4)
    first = await anext(stream)
    resumed = bridge.recover_go_range(stream, first, 2, 4, resume, offsets.append)
    assert b"".join([part async for part in resumed]) == b"abc"
    assert offsets == [3]


@pytest.mark.asyncio
async def test_stalled_hoster_task_cancels_without_progress(monkeypatch, go_bridge):
    started = asyncio.Event()
    closed = asyncio.Event()

    async def stalled(*args, **kwargs):
        started.set()
        try:
            await asyncio.Future()
        finally:
            closed.set()

    monkeypatch.setenv("USE_GO_ENGINE", "true")
    monkeypatch.setattr(go_bridge, "run_task", stalled)
    uploader = SimpleNamespace(listener=SimpleNamespace(is_cancelled=False))
    pending = asyncio.create_task(
        go_bridge.upload_hoster("pixeldrain", "https://pixeldrain.com/", "unused", uploader, lambda _: None)
    )
    await asyncio.wait_for(started.wait(), 1)
    uploader.listener.is_cancelled = True
    await asyncio.wait_for(go_bridge.cancel_hoster(uploader), 1)
    with pytest.raises(asyncio.CancelledError):
        await pending
    assert closed.is_set() and uploader._go_hoster_task is None


def test_host_accepted_but_unreadable_receipt_is_not_retried(go_bridge):
    with pytest.raises(go_bridge.HostUploadUncertain) as error:
        with go_bridge.hoster_receipt(201):
            raise ValueError("invalid JSON")
    assert not go_bridge.retry_hoster_error(error.value)
    assert go_bridge.retry_hoster_error(OSError("rejected"))


@pytest.mark.asyncio
async def test_go_wait_event_updates_account_before_upload_fallback(go_bridge, tmp_path, monkeypatch):
    import httpx

    client = SimpleNamespace(bot_token="fixture", api_id=1, api_hash="fixture")
    file = tmp_path / "file"
    with file.open("wb") as data:
        data.truncate(11 * 1024**2)

    def sidecar(_timeout=15):
        response = httpx.Response(
            200, text='data: {"status":"cooldown","retry_after":62,"source":-1}\n\n'
        )
        return httpx.AsyncClient(
            base_url="http://sidecar", transport=httpx.MockTransport(lambda _request: response),
        )

    monkeypatch.setattr(go_bridge, "go_client", sidecar)
    start = go_bridge.monotonic()
    assert await go_bridge.upload_parts(client, str(file), None) is None
    assert client._amaterasu_send_flood_until >= start + 62


def load_stream_module():
    name = "amaterasu_adaptive_tg_stream_test"
    sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location(name, MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_wserver_functions(names, namespace):
    tree = ast.parse(WSERVER_PATH.read_text(encoding="utf-8"))
    wanted = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in names
    ]
    exec(
        compile(ast.Module(wanted, type_ignores=[]), str(WSERVER_PATH), "exec"),
        namespace,
    )
    return namespace


@pytest.mark.asyncio
async def test_adaptive_fetch_reuses_only_complete_versioned_edge_chunks(tmp_path):
    from web.filetolink_cache import EdgeCache

    stream = load_stream_module()
    cache = EdgeCache(tmp_path, 1024**2, lambda needed: None)
    engine = stream.AdaptiveTelegramStream(
        chat_id=-1001, message_id=7, clients={1: object()}, primary_client_id=1,
        primary_message=object(), profile=stream.build_profile('bulk', concurrency=1, prefetch=1),
        edge_cache=cache,
    )
    engine.unique_id = 'first-media'
    engine.file_size = 20 * 1024**2
    calls = []

    async def pull(state, offset, limit):
        calls.append((offset, limit))
        return b'x' * limit

    engine._pull = pull
    assert await engine._fetch(None, 0, 4) == b'xxxx'
    assert await engine._fetch(None, 0, 4) == b'xxxx'
    assert len(calls) == 1
    engine.unique_id = 'replacement-media'
    assert await engine._fetch(None, 0, 4) == b'xxxx'
    assert len(calls) == 2


def test_playback_profile_ramps_from_a_small_aligned_first_chunk():
    stream = load_stream_module()
    profile = stream.build_profile("playback", concurrency=8, prefetch=4)

    plan = stream.plan_chunks(1, 2 * 1024 * 1024 + 17, profile)

    assert profile.client_count == 1
    assert profile.first_chunk == 32 * 1024
    assert profile.max_chunk == 512 * 1024
    assert plan[0] == (0, 32 * 1024)
    assert all(offset % stream.MIN_ALIGN == 0 for offset, _ in plan)
    assert all(size % stream.MIN_ALIGN == 0 for _, size in plan)
    assert plan[-1][0] + plan[-1][1] >= 2 * 1024 * 1024 + 17


def test_bulk_profile_can_spread_a_download_across_four_clients():
    stream = load_stream_module()
    profile = stream.build_profile("bulk", concurrency=8, prefetch=4)

    assert profile.client_count == 4
    assert profile.first_chunk == 1024 * 1024
    assert profile.max_chunk == 1024 * 1024
    assert profile.window == 8
    assert profile.max_window == 8


@pytest.mark.asyncio
async def test_adaptive_pipeline_yields_ordered_exact_range_and_grows_window():
    stream = load_stream_module()
    profile = stream.build_profile("playback", concurrency=8, prefetch=4)
    engine = stream.AdaptiveTelegramStream(
        chat_id=-1001,
        message_id=7,
        clients={1: object()},
        primary_client_id=1,
        primary_message=object(),
        profile=profile,
    )
    engine._states = [SimpleNamespace(client_id=1)]
    engine.unique_id = "same-file"
    calls = []

    async def fake_fetch(self, state, offset, limit):
        calls.append((state.client_id, offset, limit))
        if offset == 0:
            await asyncio.sleep(0.02)
        return bytes((offset // stream.MIN_ALIGN) % 251 for _ in range(limit))

    engine._fetch = MethodType(fake_fetch, engine)
    start = 17
    end = 3_000_123
    received = b"".join([piece async for piece in engine.iter_range(start, end)])

    expected = bytearray()
    for offset, limit in stream.plan_chunks(start, end + 1, profile):
        data = bytes((offset // stream.MIN_ALIGN) % 251 for _ in range(limit))
        left = max(start, offset) - offset
        right = min(end + 1, offset + limit) - offset
        expected.extend(data[left:right])

    assert received == bytes(expected)
    assert len(received) == end - start + 1
    assert calls[0][2] == 32 * 1024
    assert engine.peak_window > profile.window


@pytest.mark.asyncio
async def test_duplicate_chunk_requests_are_coalesced_across_viewers():
    stream = load_stream_module()
    profile = stream.build_profile("playback", concurrency=4, prefetch=4)
    engines = [
        stream.AdaptiveTelegramStream(
            chat_id=-1001,
            message_id=8,
            clients={1: object()},
            primary_client_id=1,
            primary_message=object(),
            profile=profile,
        )
        for _ in range(2)
    ]
    calls = 0

    async def fake_pull(self, state, offset, limit):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.02)
        return b"x" * limit

    state = SimpleNamespace(client_id=1)
    for engine in engines:
        engine.unique_id = "coalesced-file"
        engine._pull = MethodType(fake_pull, engine)

    chunks = await asyncio.gather(
        engines[0]._fetch(state, 0, 32 * 1024),
        engines[1]._fetch(state, 0, 32 * 1024),
    )

    assert chunks == [b"x" * (32 * 1024)] * 2
    assert calls == 1
    assert not stream.inflight_chunk_count()


@pytest.mark.asyncio
async def test_pull_fails_over_to_another_reserved_client():
    stream = load_stream_module()
    failures = []
    profile = stream.build_profile("bulk", concurrency=4, prefetch=4)
    engine = stream.AdaptiveTelegramStream(
        chat_id=-1001,
        message_id=9,
        clients={1: object(), 2: object()},
        primary_client_id=1,
        primary_message=object(),
        profile=profile,
        on_failure=lambda client_id, reason, cooldown: failures.append(
            (client_id, reason, cooldown)
        ),
    )
    first = SimpleNamespace(client_id=1)
    second = SimpleNamespace(client_id=2)
    engine._states = [first, second]

    async def fake_pull_from_state(self, state, _offset, limit):
        if state.client_id == 1:
            raise ConnectionError("media DC disconnected")
        return b"z" * limit

    engine._pull_from_state = MethodType(fake_pull_from_state, engine)
    result = await engine._pull(first, 0, 4096)

    assert result == b"z" * 4096
    assert engine.used_client_ids == {2}
    assert engine.failed_client_ids == {1}
    assert failures and failures[0][0] == 1


@pytest.mark.asyncio
async def test_direct_getfile_request_uses_wzgram_310_safe_parameters():
    stream = load_stream_module()
    requests = []

    class Session:
        async def invoke(self, query, **kwargs):
            requests.append((query, kwargs))
            return stream.raw.types.upload.File(
                type=stream.raw.types.storage.FileUnknown(),
                mtime=0,
                bytes=b"d" * stream.MIN_ALIGN,
            )

    profile = stream.build_profile("playback", concurrency=4, prefetch=4)
    engine = stream.AdaptiveTelegramStream(
        chat_id=-1001,
        message_id=10,
        clients={1: object()},
        primary_client_id=1,
        primary_message=object(),
        profile=profile,
    )
    state = SimpleNamespace(
        client_id=1,
        sessions=[Session()],
        session_cursor=0,
        location=object(),
        dc_id=2,
    )

    result = await engine._pull_from_state(state, 4096, stream.MIN_ALIGN)

    query, kwargs = requests[0]
    assert result == b"d" * stream.MIN_ALIGN
    assert query.offset == 4096
    assert query.limit == stream.MIN_ALIGN
    assert query.precise is True
    assert query.cdn_supported is False
    assert kwargs == {"timeout": 8.0, "sleep_threshold": 0}


def test_web_stream_keeps_native_fallback_and_existing_cache_layer():
    source = WSERVER_PATH.read_text(encoding="utf-8")

    assert "FILETOLINK_ADAPTIVE_STREAMING" in source
    assert "AdaptiveTelegramStream" in source
    assert "Adaptive streaming unavailable" in source
    assert "_iter_telegram_range(" in source
    assert "_begin_progressive_cache(" in source
    assert "_existing_cached_media(" in source
    adaptive_setup = source[
        source.index("if go_first is None and FILETOLINK_ADAPTIVE_STREAMING:") : source.index(
            "transfer_source = ("
        )
    ]
    assert adaptive_setup.index("try:") < adaptive_setup.index(
        "from bot.helper.telegram_helper.tg_stream import"
    )


def test_reserved_adaptive_workers_are_all_released(monkeypatch):
    primary = object()
    secondary = object()
    loads = {1: 1, 2: 0}
    tg_client_module = ModuleType("bot.core.tg_client")
    tg_client_module.TgClient = SimpleNamespace(stream_loads=loads)
    monkeypatch.setitem(sys.modules, "bot.core.tg_client", tg_client_module)

    namespace = {
        "MAX_CONCURRENT_PER_CLIENT": 8,
        "_stream_client_choices": lambda: [(1, primary), (2, secondary)],
        "_stream_client_available": lambda _client_id: True,
    }
    load_wserver_functions(
        {
            "_acquire_stream_client",
            "_release_stream_load",
            "_reserve_stream_clients",
            "_release_reserved_stream_clients",
        },
        namespace,
    )

    reserved = namespace["_reserve_stream_clients"](1, primary, 2)
    assert reserved == {1: primary, 2: secondary}
    assert loads == {1: 1, 2: 1}

    namespace["_release_reserved_stream_clients"](reserved)
    assert loads == {1: 0, 2: 0}
