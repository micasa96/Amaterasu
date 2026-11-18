import importlib.util
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest


def load_bridge():
    path = Path(__file__).parents[1] / "bot/helper/ext_utils/go_bridge.py"
    spec = importlib.util.spec_from_file_location("go_bridge_fixture", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_go_bridge_uses_explicit_task_lifecycle(monkeypatch):
    bridge = load_bridge()
    paths = []
    task_id = None
    progress = []

    def request(req):
        nonlocal task_id
        paths.append((req.method, req.url.path))
        if req.method == "POST":
            task_id = req.headers["X-Amaterasu-Task-ID"]
            return httpx.Response(202, json={"id": task_id})
        if req.method == "DELETE":
            assert req.url.path == f"/v1/tasks/{task_id}"
            return httpx.Response(204)
        assert req.url.path == f"/v1/tasks/{task_id}/events"
        return httpx.Response(200, text=(
            'data: {"status":"running","processed_bytes":2,"total_bytes":3}\n\n'
            'data: {"status":"complete","result":3}\n\n'
        ))

    def client(_timeout):
        return httpx.AsyncClient(base_url="http://sidecar", transport=httpx.MockTransport(request))

    async def report(current, total):
        progress.append((current, total))

    monkeypatch.setattr(bridge, "go_client", client)
    assert await bridge.run_task("hyperdl", {}, report) == 3
    assert progress == [(2, 3)]
    assert [method for method, _ in paths] == ["POST", "GET", "DELETE"]


def test_go_bridge_keeps_unsupported_proxies_on_python():
    bridge = load_bridge()
    client = SimpleNamespace(bot_token="1:fixture", api_id=1, api_hash="hash",
                             proxy={"scheme": "socks5", "hostname": "localhost", "port": 1080})
    assert bridge.bot_auth(client)["proxy"]["host"] == "localhost"
    client.proxy["scheme"] = "http"
    assert bridge.bot_auth(client) is None


@pytest.mark.asyncio
async def test_go_bridge_preserves_small_upload_checksum(monkeypatch, tmp_path):
    bridge = load_bridge()
    client = SimpleNamespace(bot_token="1:fixture", api_id=1, api_hash="hash", proxy=None)
    source = tmp_path / "small.txt"
    source.write_text("fixture", encoding="utf-8")

    async def run_task(task, payload, progress):
        assert task == "hyperul"
        assert Path(payload["path"]) == source
        return {"id": 1, "parts": 1, "name": source.name, "md5_checksum": "fixture-checksum"}

    monkeypatch.setattr(bridge, "run_task", run_task)
    receipt = await bridge.upload_parts(client, str(source), None)
    assert isinstance(receipt, bridge.InputFile)
    assert receipt.md5_checksum == "fixture-checksum"
