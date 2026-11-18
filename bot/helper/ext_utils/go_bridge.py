from asyncio import CancelledError, create_task, gather, sleep, wait_for
from base64 import b64decode, b64encode
from contextlib import AsyncExitStack, contextmanager, suppress
from json import loads
from os import getenv
from pathlib import Path
from struct import error as StructError
from time import monotonic
from uuid import uuid4

from httpx import AsyncClient, AsyncHTTPTransport, ConnectError, ConnectTimeout, HTTPError, Timeout
from pyrogram.raw.types import InputFile, InputFileBig
from pyrogram.file_id import FileId, FileType


class HostUploadUncertain(RuntimeError):
    pass


class GoStreamInterrupted(OSError):
    pass


class GoFloodWait(Exception):
    def __init__(self, seconds, source):
        super().__init__(f"Telegram cooldown ({seconds}s)")
        self.seconds = seconds
        self.source = source


def record_go_flood(client, seconds):
    if not isinstance(seconds, int) or seconds <= 0:
        return
    until = monotonic() + seconds
    client._amaterasu_go_flood_until = max(
        until, getattr(client, "_amaterasu_go_flood_until", 0),
    )
    client._amaterasu_send_flood_until = max(
        until, getattr(client, "_amaterasu_send_flood_until", 0),
    )
    for name in ("_amaterasu_download_pacer", "_amaterasu_upload_pacer"):
        if (pacer := getattr(client, name, None)) is not None:
            pacer.flood_until = max(until, pacer.flood_until)


async def wait_go_cooldown(client):
    while (delay := getattr(client, "_amaterasu_go_flood_until", 0) - monotonic()) > 0:
        await sleep(delay)


def retry_hoster_error(error):
    return isinstance(error, Exception) and not isinstance(error, HostUploadUncertain)


@contextmanager
def hoster_receipt(status):
    try:
        yield
    except Exception as error:
        if 200 <= status < 300:
            raise HostUploadUncertain(
                f"Hoster accepted the upload (HTTP {status}), but its result could not be confirmed"
            ) from error
        raise


async def cancel_hoster(uploader):
    if task := getattr(uploader, "_go_hoster_task", None):
        task.cancel()
        await gather(task, return_exceptions=True)


def bot_auth(client):
    token = getattr(client, "bot_token", None)
    if not token:
        return None
    auth = {"app_id": client.api_id, "app_hash": client.api_hash, "token": token}
    if proxy := getattr(client, "proxy", None):
        if not isinstance(proxy, dict) or str(proxy.get("scheme", "")).lower() not in {"socks5", "socks5h"}:
            return None
        try:
            host, port = proxy["hostname"], int(proxy["port"])
        except (KeyError, ValueError, TypeError):
            return None
        if not isinstance(host, str) or not host or not 0 < port <= 65535:
            return None
        auth["proxy"] = {
            "scheme": "socks5", "host": host, "port": port,
            "username": proxy.get("username") or "", "password": proxy.get("password") or "",
        }
    return auth


def media_request(client, file_id, size, start, end):
    auth = bot_auth(client)
    if auth is None:
        return None
    location = FileId.decode(file_id) if isinstance(file_id, str) else file_id
    if location.file_type == FileType.CHAT_PHOTO:
        return None
    return {
        **auth,
        "dc": location.dc_id,
        "kind": "photo" if location.file_type == FileType.PHOTO else "document",
        "id": location.media_id,
        "access_hash": location.access_hash,
        "file_reference": b64encode(location.file_reference or b"").decode("ascii"),
        "thumb_size": location.thumbnail_size or "",
        "size": size,
        "start": start,
        "end": end,
    }


def go_client(read_timeout=15):
    socket = getenv("AMATERASU_GO_SOCKET", "/tmp/amaterasu_go.sock")
    return AsyncClient(
        transport=AsyncHTTPTransport(uds=socket),
        base_url="http://amaterasu-go",
        timeout=Timeout(read_timeout, connect=1),
    )


async def register_go_tokens(config, *, stream=None, health=False):
    if not getenv("AMATERASU_GO_SOCKET"):
        return False
    from bot.core.tg_client import TgClient

    helper_tokens = config.helper_bot_tokens()
    proxies = TgClient._parse_proxies(config.HELPER_BOT_PROXIES)
    proxied = {token for token, proxy in zip(helper_tokens, proxies) if proxy}
    tokens = [] if config.TG_PROXY else [
        token for token in dict.fromkeys([
            config.BOT_TOKEN, *helper_tokens, *config.stream_bot_tokens(),
        ]) if token and token not in proxied
    ]
    try:
        async with go_client(2) as sidecar:
            if health:
                (await sidecar.get("/v1/health")).raise_for_status()
            result = await sidecar.post("/v1/mtproto/register-tokens", json={
                "app_id": config.TELEGRAM_API, "app_hash": config.TELEGRAM_HASH,
                "tokens": tokens, "stream": stream,
            })
            return result.status_code == 204
    except HTTPError:
        return False


async def publish_go_metadata(client, chat_id, message_id, media, filename, mime_type=None):
    if not getenv("AMATERASU_GO_SOCKET") or client is None or media is None:
        return
    from pymongo.errors import PyMongoError
    from bot.helper.ext_utils.db_handler import database

    size = getattr(media, "file_size", 0) or 0
    if size <= 0 or not getattr(media, "file_id", None) or database.db is None:
        return
    try:
        payload = media_request(client, media.file_id, size, 0, size - 1)
        if payload is None or "proxy" in payload:
            return
        bot_id = payload.pop("token").split(":", 1)[0]
        del payload["app_id"], payload["app_hash"], payload["start"], payload["end"]
        payload["file_reference"] = b64decode(payload["file_reference"])
        await wait_for(database.filetolink_collection("streams").update_one(
            {"_id": f"{int(chat_id)}:{int(message_id)}"},
            {"$set": {
                "bot_id": bot_id, "media": payload, "filename": str(filename),
                "mime_type": mime_type or getattr(media, "mime_type", None) or "application/octet-stream",
                "unique_id": getattr(media, "file_unique_id", "") or "",
            }},
            upsert=True,
        ), timeout=2)
    except (RuntimeError, PyMongoError, OSError, ValueError, StructError):
        # Python FileToLink can still serve an authorized link when Mongo is unavailable.
        return


async def stream_range(client, file_id, size, start, end):
    remaining = end - start + 1
    sent = 0
    try:
        if getattr(client, "_amaterasu_go_flood_until", 0) > monotonic():
            return
        payload = media_request(client, file_id, size, start, end)
        if payload is None:
            return
        async with go_client() as sidecar:
            async with sidecar.stream("POST", "/v1/stream", json=payload) as response:
                if response.status_code == 429:
                    record_go_flood(client, int(response.headers.get("retry-after", "0")))
                    return
                if (
                    response.status_code != 206
                    or response.headers.get("content-range") != f"bytes {start}-{end}/{size}"
                    or response.headers.get("content-length") != str(remaining)
                ):
                    return
                async for chunk in response.aiter_bytes():
                    if len(chunk) > remaining - sent:
                        raise OSError("Go sent bytes beyond the requested range")
                    sent += len(chunk)
                    yield chunk
                if sent != remaining:
                    raise OSError("Go ended the range early")
    except (HTTPError, OSError, ValueError, StructError) as error:
        if 0 < sent < remaining:
            # The range may have failed after its HTTP headers were committed.
            try:
                async with go_client() as sidecar:
                    status = await sidecar.post("/v1/cooldown", json=payload, timeout=1)
                if status.status_code == 429:
                    record_go_flood(client, int(status.headers.get("retry-after", "0")))
            except (HTTPError, OSError, ValueError):
                pass
            raise GoStreamInterrupted("Go range interrupted") from error


async def recover_go_range(source, first, start, end, resume, on_failure):
    offset = start + len(first)
    yield first
    try:
        async for chunk in source:
            offset += len(chunk)
            yield chunk
    except GoStreamInterrupted:
        if offset <= end:
            on_failure(offset)
            async for chunk in resume(offset):
                yield chunk


async def run_task(task, payload, progress, *, nonrepeatable=False):
    task_id = uuid4().hex
    task_path = f"/v1/tasks/{task_id}"
    accepted = False
    try:
        async with go_client(3600 if nonrepeatable else 30) as sidecar:
            try:
                async with AsyncExitStack() as connection:
                    response = await connection.enter_async_context(sidecar.stream(
                        "POST", f"/v1/tasks/{task}", json=payload,
                        headers={"Accept": "application/json", "X-Amaterasu-Task-ID": task_id},
                    ))
                    if response.status_code == 202:
                        accepted = True
                        await response.aread()
                        if response.json().get("id") != task_id:
                            raise ValueError("unexpected task ID")
                        response = await connection.enter_async_context(
                            sidecar.stream("GET", f"{task_path}/events"),
                        )
                    if response.status_code != 200:
                        if not nonrepeatable or (not accepted and response.status_code in {400, 404}):
                            return None
                    else:
                        async for line in response.aiter_lines():
                            if not line.startswith("data: "):
                                continue
                            event = loads(line[6:])
                            status = event.get("status")
                            if status == "running":
                                await progress(event["processed_bytes"], event["total_bytes"])
                            elif status == "complete":
                                return event["result"]
                            elif status == "cooldown":
                                raise GoFloodWait(event["retry_after"], event["source"])
                            elif status == "rejected":
                                return None
                            elif status == "failed":
                                break
            finally:
                if accepted:
                    with suppress(HTTPError):
                        await sidecar.delete(task_path, timeout=3)
    except (ConnectError, ConnectTimeout):
        if not accepted or not nonrepeatable:
            return None
    except (HTTPError, OSError, ValueError, KeyError):
        if nonrepeatable:
            raise HostUploadUncertain("Go hoster upload outcome is unknown") from None
    if nonrepeatable:
        raise HostUploadUncertain("Go hoster upload did not complete")
    return None


async def upload_parts(client, filename, progress):
    auth = bot_auth(client)
    if not auth or not isinstance(filename, str):
        return None
    if getattr(client, "_amaterasu_go_flood_until", 0) > monotonic():
        return None
    path = Path(filename).absolute()
    try:
        if not path.is_file() or not 0 < path.stat().st_size <= 2 * 1024**3:
            return None
    except OSError:
        return None
    try:
        result = await run_task("hyperul", {**auth, "path": str(path)}, progress)
    except GoFloodWait as wait:
        record_go_flood(client, wait.seconds)
        return None
    if result is not None:
        fields = {key: result[key] for key in ("id", "parts", "name")}
        if "md5_checksum" in result:
            return InputFile(**fields, md5_checksum=result["md5_checksum"])
        return InputFileBig(**fields)
    return None


async def upload_hoster(provider, url, path, uploader, callback, *,
                        field="", filename="", fields=None, authorization=""):
    if getenv("USE_GO_ENGINE", "true").strip().lower() not in {"1", "true", "yes", "on"}:
        return None

    async def report(current, _total):
        if uploader.listener.is_cancelled:
            raise CancelledError()
        callback(current)

    file = Path(path).absolute()
    if uploader.listener.is_cancelled:
        raise CancelledError()
    transfer = create_task(run_task("uphoster", {
        "provider": provider, "url": url, "path": str(file), "field": field,
        "filename": filename, "fields": fields, "authorization": authorization,
    }, report, nonrepeatable=True))
    uploader._go_hoster_task = transfer
    try:
        result = await transfer
    finally:
        uploader._go_hoster_task = None
    if uploader.listener.is_cancelled:
        raise CancelledError()
    if result is not None and 200 <= result["code"] < 300:
        try:
            callback(file.stat().st_size)
        except OSError:
            pass
    return result
