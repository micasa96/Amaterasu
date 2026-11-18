from os import getenv

try:
    import amaterasu_rs as _native
except ImportError:
    _native = None


def rust_core():
    if getenv("USE_RUST_CORE", "true").strip().lower() not in {"0", "false", "no", "off"}:
        return _native
    return None


def probe_document_type(path):
    native = rust_core()
    if native is None:
        return None
    try:
        with open(path, "rb") as file:
            result = native.probe_container_header(file.read(64 * 1024))
    except OSError:
        return None
    if result is None:
        return None
    _, tracks = result
    video_codecs = {
        "avc1", "avc3", "hvc1", "hev1", "av01", "vp09",
        "V_MPEG4/ISO/AVC", "V_MPEGH/ISO/HEVC", "V_AV1", "V_VP8", "V_VP9",
    }
    if any(kind == "video" and codec not in video_codecs for kind, codec in tracks):
        return None
    kinds = {kind for kind, _ in tracks}
    return "video" in kinds, "audio" in kinds, False
