from bot.helper.ext_utils.subtitle_cleaner import (
    _audio_label,
    _build_remux_command,
    clean_title,
    filter_subtitle_text,
    normalize_patterns,
)


SRT = """1
00:00:00,500 --> 00:00:01,500
Subtitulos por sitiospam.com

2
00:00:02,000 --> 00:00:03,000
Hola mundo
"""

ASS = """[Script Info]
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.50,0:00:01.50,Default,,0,0,0,,www.sitiospam.com
Dialogue: 0,0:00:02.00,0:00:03.00,Default,,0,0,0,,Hola mundo
"""


def test_normalize_patterns_is_case_insensitive_and_deduplicated():
    assert normalize_patterns([" Sitiospam.com ", "sitiospam.com", "", None]) == [
        "sitiospam.com"
    ]
    assert normalize_patterns("sitiospam.com") == ["sitiospam.com"]


def test_clean_title_removes_matching_fragment_and_keeps_the_rest():
    assert clean_title("Subtitulos por sitiospam.com", ["sitiospam.com"]) == (
        "Subtitulos por"
    )
    assert clean_title("sitiospam.com", ["sitiospam.com"]) == ""
    assert clean_title("www.sitiospam.com", ["sitiospam.com"]) == ""
    assert clean_title("Forzados www.sitiospam.com", ["sitiospam.com"]) == "Forzados"
    assert clean_title(
        "Spanish, Mexico (Forced) [sitiospam.com]", ["sitiospam.com"]
    ) == "Spanish, Mexico (Forced)"


def test_filter_subtitle_text_drops_only_matching_srt_cues_and_renumbers():
    cleaned = filter_subtitle_text(SRT, "subrip", ["sitiospam.com"])

    assert "sitiospam" not in cleaned
    assert "Hola mundo" in cleaned
    assert cleaned.startswith("1\n00:00:02,000 --> 00:00:03,000")


def test_filter_subtitle_text_drops_matching_ass_dialogue_and_keeps_styles():
    cleaned = filter_subtitle_text(ASS, "ass", ["sitiospam.com"])

    assert "sitiospam" not in cleaned
    assert "Hola mundo" in cleaned
    assert "Style: Part1_Default" in cleaned


def test_filter_subtitle_text_returns_original_when_nothing_matches():
    assert filter_subtitle_text(SRT, "subrip", ["otro-sitio.com"]) == SRT


def test_filter_subtitle_text_returns_none_when_every_cue_matches():
    single = """1
00:00:00,500 --> 00:00:01,500
www.sitiospam.com
"""
    assert filter_subtitle_text(single, "subrip", ["sitiospam.com"]) is None


def test_audio_label_uses_track_language():
    spa = {"codec_name": "eac3", "tags": {"language": "spa"}}
    eng = {"codec_name": "eac3", "tags": {"language": "eng"}}

    assert _audio_label(spa) == "Español Latino Americano"
    assert _audio_label(eng) == "Inglés"
    assert _audio_label({"tags": {}}) == "Audio"


def test_remux_command_clears_matching_global_title():
    command = _build_remux_command(
        "ffmpeg",
        "input.mkv",
        ".mkv",
        [],
        [],
        {},
        set(),
        ["sitiospam.com"],
        "output.mkv",
        "+",
        "www.sitiospam.com",
    )

    assert "-metadata" in command
    assert "title=" in command


def test_remux_command_cleans_audio_and_video_titles_without_reencoding():
    streams = [
        {
            "index": 0,
            "codec_type": "video",
            "codec_name": "h264",
            "tags": {"title": "www.sitiospam.com"},
        },
        {
            "index": 1,
            "codec_type": "audio",
            "codec_name": "eac3",
            "tags": {"language": "spa", "title": "www.sitiospam.com"},
        },
    ]

    command = _build_remux_command(
        "ffmpeg",
        "input.mkv",
        ".mkv",
        streams,
        [],
        {},
        set(),
        ["sitiospam.com"],
        "output.mkv",
        "+",
    )

    assert "-metadata:s:v:0" in command
    assert "-metadata:s:a:0" in command
    assert command.count("title=") == 2
    assert command.count("copy") == 1


def test_remux_command_replaces_only_cleaned_subtitle_tracks():
    streams = [
        {"index": 0, "codec_type": "video"},
        {"index": 1, "codec_type": "audio"},
        {
            "index": 2,
            "codec_type": "subtitle",
            "codec_name": "subrip",
            "tags": {"language": "spa", "title": "Subtitulos por sitiospam.com"},
        },
        {
            "index": 3,
            "codec_type": "subtitle",
            "codec_name": "subrip",
            "tags": {"language": "eng", "title": "English"},
        },
    ]
    subtitles = [stream for stream in streams if stream["codec_type"] == "subtitle"]

    command = _build_remux_command(
        "ffmpeg",
        "input.mkv",
        ".mkv",
        streams,
        subtitles,
        {2: "2.srt"},
        set(),
        ["sitiospam.com"],
        "output.mkv",
        "+",
    )

    assert command.count("-map") == 4
    assert "1:0" in command
    assert "-c:s:0" in command and "srt" in command
    assert "title=Subtitulos por" in command
    assert "language=spa" in command
    assert "-c:s:1" not in command
