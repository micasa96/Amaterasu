"""Strip known spam text from text subtitle tracks without re-encoding A/V."""

import asyncio
import json
import os
import re
import shutil
import tempfile
from logging import getLogger
from pathlib import Path

from ...core.config_manager import BinConfig
from .merge_subtitles import join_documents, read_document

LOGGER = getLogger(__name__)

_TEXT_CODECS = {"subrip", "ass", "ssa", "mov_text", "webvtt"}
_FILTERED_SUFFIXES = {".mkv", ".mp4", ".m4v", ".mov"}
_MP4_SUFFIXES = {".mp4", ".m4v", ".mov"}
_ASS_CODECS = {"ass", "ssa"}


class _Cancelled(Exception):
    """Raised internally when the owning task is cancelled mid-cleanup."""


def normalize_patterns(patterns):
    if isinstance(patterns, str):
        patterns = [patterns]
    normalized = []
    for pattern in patterns or ():
        text = str(pattern).strip().casefold()
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def clean_title(title, patterns):
    cleaned = str(title or "")
    for pattern in patterns:
        cleaned = re.sub(re.escape(pattern), "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[\[\(\{]\s*[\]\)\}]", "", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return re.sub(r"^[\s\-–—_|,:;./\\]+|[\s\-–—_|,:;./\\]+$", "", cleaned)


def filter_subtitle_text(text, codec, patterns):
    """Return cleaned subtitle text, the original text, or None to drop the track."""
    document = read_document(text, codec)
    events = document["events"]
    kept = [
        event
        for event in events
        if not any(pattern in _cue_text(event, codec).casefold() for pattern in patterns)
    ]
    if len(kept) == len(events):
        return text
    if not kept:
        return None
    document["events"] = kept
    return join_documents([document])


def _cue_text(event, codec):
    return event[3] if codec == "subrip" else event["Text"]


def _tag(tags, name):
    for key, value in (tags or {}).items():
        if key.casefold() == name:
            return value
    return ""


def _output_subtitle_codec(suffix, stream):
    if suffix in _MP4_SUFFIXES:
        return "mov_text"
    return "ass" if stream.get("codec_name") in _ASS_CODECS else "srt"


def _disposition(stream, separator):
    active = [
        name for name, enabled in (stream.get("disposition") or {}).items() if enabled
    ]
    return separator.join(active) if active else "0"


async def _run(arguments, listener, timeout):
    process = await asyncio.create_subprocess_exec(
        *map(str, arguments),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    if listener is not None:
        listener.subproc = process
    communication = asyncio.create_task(process.communicate())
    elapsed = 0
    try:
        while not communication.done():
            if listener is not None and listener.is_cancelled:
                process.kill()
                await communication
                raise _Cancelled
            if elapsed >= timeout:
                process.kill()
                await communication
                raise ValueError("Subtitle cleanup timed out.")
            try:
                await asyncio.wait_for(asyncio.shield(communication), 1)
            except TimeoutError:
                elapsed += 1
        stdout, stderr = await communication
    finally:
        if listener is not None and listener.subproc is process:
            listener.subproc = None
    if process.returncode:
        diagnostic = (stderr or stdout).decode(errors="replace")[-4000:].strip()
        raise ValueError(diagnostic or f"ffmpeg exited with {process.returncode}.")
    return stdout


async def _probe(path, listener):
    output = await _run(
        ["ffprobe", "-v", "error", "-show_streams", "-of", "json", path],
        listener,
        120,
    )
    return json.loads(output.decode(errors="replace"))


async def _extract_track(ffmpeg, path, stream, target, listener):
    command = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
        "-i", path, "-map", f"0:{stream['index']}",
    ]
    if stream.get("codec_name") in _ASS_CODECS:
        command += ["-c:s", "copy", target]
    else:
        command += ["-c:s", "srt", target]
    await _run(command, listener, 600)


def _build_remux_command(
    ffmpeg, path, suffix, streams, subtitles, cleaned, dropped, patterns, output,
    separator,
):
    command = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", path,
    ]
    positions = {}
    for stream in subtitles:
        target = cleaned.get(stream["index"])
        if target is None:
            continue
        command += ["-i", target]
        positions[stream["index"]] = len(positions) + 1
    command += ["-map_chapters", "0"]
    for stream in streams:
        if stream.get("codec_type") == "attachment":
            continue
        index = stream.get("index")
        if stream.get("codec_type") == "subtitle":
            if index in dropped:
                continue
            command += ["-map", f"{positions[index]}:0" if index in positions else f"0:{index}"]
        else:
            command += ["-map", f"0:{index}"]
    if suffix == ".mkv":
        command += ["-map", "0:t?"]
    command += ["-c", "copy"]
    subtitle_index = 0
    for stream in subtitles:
        if stream["index"] in dropped:
            continue
        number = subtitle_index
        subtitle_index += 1
        title = _tag(stream.get("tags"), "title")
        handler = _tag(stream.get("tags"), "handler_name")
        if stream["index"] in positions:
            command += [
                f"-c:s:{number}", _output_subtitle_codec(suffix, stream),
                f"-disposition:s:{number}", _disposition(stream, separator),
            ]
            language = _tag(stream.get("tags"), "language")
            if language:
                command += [f"-metadata:s:s:{number}", f"language={language}"]
            command += [
                f"-metadata:s:s:{number}", f"title={clean_title(title, patterns)}",
            ]
            if handler:
                command += [
                    f"-metadata:s:s:{number}", f"handler_name={clean_title(handler, patterns)}",
                ]
        else:
            if clean_title(title, patterns) != title:
                command += [
                    f"-metadata:s:s:{number}", f"title={clean_title(title, patterns)}",
                ]
            if handler and clean_title(handler, patterns) != handler:
                command += [
                    f"-metadata:s:s:{number}",
                    f"handler_name={clean_title(handler, patterns)}",
                ]
    command += [output]
    return command


async def clean_subtitles(listener, path, patterns):
    """Remove matching cues and title fragments in place; return the final path."""
    normalized = normalize_patterns(patterns)
    suffix = Path(path).suffix.lower()
    if not normalized or suffix not in _FILTERED_SUFFIXES:
        return path
    working = None
    try:
        probe = await _probe(path, listener)
        streams = probe.get("streams") or []
        subtitles = [s for s in streams if s.get("codec_type") == "subtitle"]
        if not subtitles:
            return path
        working = tempfile.mkdtemp(
            prefix=".subclean-", dir=os.path.dirname(path) or "."
        )
        cleaned = {}
        dropped = set()
        title_changed = False
        for stream in subtitles:
            index = stream["index"]
            title = _tag(stream.get("tags"), "title")
            title_changed = title_changed or clean_title(title, normalized) != title
            if stream.get("codec_name") not in _TEXT_CODECS:
                continue
            extension = "ass" if stream.get("codec_name") in _ASS_CODECS else "srt"
            target = os.path.join(working, f"{index}.{extension}")
            try:
                await _extract_track(
                    BinConfig.FFMPEG_NAME, path, stream, target, listener
                )
                raw = Path(target).read_text(encoding="utf-8", errors="replace")
                codec = "ass" if extension == "ass" else "subrip"
                filtered = filter_subtitle_text(raw, codec, normalized)
            except _Cancelled:
                raise
            except Exception:
                LOGGER.warning(
                    "Skipping subtitle track %s: it could not be cleaned",
                    index,
                    exc_info=True,
                )
                continue
            if filtered is None:
                dropped.add(index)
            elif filtered != raw:
                Path(target).write_text(filtered, encoding="utf-8")
                cleaned[index] = target
        if not cleaned and not dropped and not title_changed:
            return path
        output = os.path.join(working, f"cleaned{suffix}")
        for separator in ("+", ","):
            try:
                await _run(
                    _build_remux_command(
                        BinConfig.FFMPEG_NAME,
                        path,
                        suffix,
                        streams,
                        subtitles,
                        cleaned,
                        dropped,
                        normalized,
                        output,
                        separator,
                    ),
                    listener,
                    1800,
                )
                break
            except ValueError as error:
                if "disposition" not in str(error).casefold():
                    raise
                if separator == ",":
                    raise
        os.replace(output, path)
        LOGGER.info(
            "Subtitle cleanup applied: %s | rewritten=%d dropped=%d title=%s",
            os.path.basename(path),
            len(cleaned),
            len(dropped),
            "cleaned" if title_changed else "unchanged",
        )
    except _Cancelled:
        return path
    except Exception:
        LOGGER.exception("Automatic subtitle cleanup failed for %s", path)
    finally:
        if working is not None:
            shutil.rmtree(working, ignore_errors=True)
    return path
