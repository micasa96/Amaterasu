import importlib.util
from pathlib import Path
from types import SimpleNamespace


def test_rust_bridge_disable_and_probe_fallback(monkeypatch, tmp_path):
    path = Path(__file__).parents[1] / "bot/helper/ext_utils/rust_bridge.py"
    spec = importlib.util.spec_from_file_location("rust_bridge_fixture", path)
    bridge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bridge)
    media = tmp_path / "sample.mp4"
    media.write_bytes(b"fixture")
    native = SimpleNamespace(probe_container_header=lambda _: ("mp4", [("video", "avc1")]))
    monkeypatch.setattr(bridge, "_native", native)
    monkeypatch.setenv("USE_RUST_CORE", "false")
    assert bridge.probe_document_type(media) is None
    monkeypatch.setenv("USE_RUST_CORE", "true")
    assert bridge.probe_document_type(media) == (True, False, False)
    native.probe_container_header = lambda _: None
    assert bridge.probe_document_type(media) is None
