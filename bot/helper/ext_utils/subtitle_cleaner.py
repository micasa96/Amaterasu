"""Strip known spam from subtitle cues and track titles without re-encoding A/V."""

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

_LANGUAGE_NAMES = {
    "spa": "Español Latino Americano",
    "eng": "Inglés",
    "por": "Portugués",
    "fra": "Francés",
    "fre": "Francés",
    "deu": "Alemán",
    "ger": "Alemán",
    "ita": "Italiano",
    "jpn": "Japonés",
    "kor": "Coreano",
    "zho": "Chino",
    "chi": "Chino",
    "rus": "Ruso",
    "ara": "Árabe",
    "hin": "Hindi",
    "tur": "Turco",
    "pol": "Polaco",
    "nld": "Neerlandés",
    "dut": "Neerlandés",
    "swe": "Sueco",
    "nor": "Noruego",
    "dan": "Danés",
    "fin": "Finés",
    "ces": "Checo",
    "cze": "Checo",
    "ell": "Griego",
    "gre": "Griego",
    "heb": "Hebreo",
    "tha": "Tailandés",
    "vie": "Vietnamita",
    "ind": "Indonesio",
    "ukr": "Ucraniano",
    "ron": "Rumano",
    "rum": "Rumano",
    "hun": "Húngaro",
    "cat": "Catalán",
    "eus": "Vasco",
    "baq": "Vasco",
    "glg": "Gallego",
}


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
    cleaned = re.sub(r"\bwww\.?\s*", "", cleaned, flags=re.IGNORECASE)
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


def _audio_label(stream):
    language = str(_tag(stream.get("tags"), "language") or "").strip().casefold()
    if language and language != "und":
        return _LANGUAGE_NAMES.get(language, language.upper())
    return "Audio"


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
        [
            "ffprobe", "-v", "error", "-show_streams", "-show_format",
            "-of", "json", path,
        ],
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
    separator, global_title="",
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
    mapped = []
    counters = {"video": 0, "audio": 0, "subtitle": 0, "data": 0}
    for stream in streams:
        kind = stream.get("codec_type")
        if kind == "attachment":
            continue
        index = stream.get("index")
        if kind == "subtitle":
            if index in dropped:
                continue
            command += [
                "-map", f"{positions[index]}:0" if index in positions else f"0:{index}",
            ]
        else:
            command += ["-map", f"0:{index}"]
        number = counters.get(kind)
        if number is not None:
            counters[kind] = number + 1
        mapped.append((stream, kind, number, index in positions))
    if suffix == ".mkv":
        command += ["-map", "0:t?"]
    command += ["-c", "copy"]
    for stream, kind, number, is_cleaned in mapped:
        if number is None:
            continue
        prefix = f"-metadata:s:{kind[0]}:{number}"
        title = _tag(stream.get("tags"), "title")
        handler = _tag(stream.get("tags"), "handler_name")
        if kind == "audio":
            desired_title = _audio_label(stream)
            if desired_title != title:
                command += [prefix, f"title={desired_title}"]
            cleaned_handler = clean_title(handler, patterns)
            if handler and cleaned_handler != handler:
                command += [prefix, f"handler_name={cleaned_handler}"]
            continue
        cleaned_title = clean_title(title, patterns)
        cleaned_handler = clean_title(handler, patterns)
        if kind == "subtitle" and is_cleaned:
            command += [
                f"-c:s:{number}", _output_subtitle_codec(suffix, stream),
                f"-disposition:s:{number}", _disposition(stream, separator),
            ]
            language = _tag(stream.get("tags"), "language")
            if language:
                command += [prefix, f"language={language}"]
            command += [prefix, f"title={cleaned_title}"]
            if handler:
                command += [prefix, f"handler_name={cleaned_handler}"]
        else:
            if cleaned_title != title:
                command += [prefix, f"title={cleaned_title}"]
            if handler and cleaned_handler != handler:
                command += [prefix, f"handler_name={cleaned_handler}"]
    cleaned_global = clean_title(global_title, patterns)
    if cleaned_global != global_title:
        command += ["-metadata", f"title={cleaned_global}"]
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
        if not streams:
            return path
        global_title = _tag((probe.get("format") or {}).get("tags"), "title")
        subtitles = [s for s in streams if s.get("codec_type") == "subtitle"]
        working = tempfile.mkdtemp(
            prefix=".subclean-", dir=os.path.dirname(path) or "."
        )
        cleaned = {}
        dropped = set()
        metadata_changed = clean_title(global_title, normalized) != global_title
        for stream in streams:
            kind = stream.get("codec_type")
            if kind not in {"video", "audio", "subtitle"}:
                continue
            title = _tag(stream.get("tags"), "title")
            handler = _tag(stream.get("tags"), "handler_name")
            if kind == "audio":
                if _audio_label(stream) != title or (
                    handler and clean_title(handler, normalized) != handler
                ):
                    metadata_changed = True
                    break
                continue
            if clean_title(title, normalized) != title or (
                handler and clean_title(handler, normalized) != handler
            ):
                metadata_changed = True
                break
        for stream in subtitles:
            index = stream["index"]
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
        if not cleaned and not dropped and not metadata_changed:
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
                        global_title,
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
            "Track cleanup applied: %s | rewritten=%d dropped=%d titles=%s",
            os.path.basename(path),
            len(cleaned),
            len(dropped),
            "cleaned" if metadata_changed else "unchanged",
        )
    except _Cancelled:
        return path
    except Exception:
        LOGGER.exception("Automatic subtitle cleanup failed for %s", path)
    finally:
        if working is not None:
            shutil.rmtree(working, ignore_errors=True)
    return path
