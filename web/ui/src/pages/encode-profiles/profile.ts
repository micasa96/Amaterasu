// Encoding profile model for the Encode Profiles page.
//
// Ported from the former web/static/js/encode.js. Payload shapes, defaults,
// codec rules and the FFmpeg preview are unchanged: the bot's
// normalize_encode_profile() and the FFmpeg builder in bot/ read the same
// JSON this module writes.

/* eslint-disable @typescript-eslint/no-explicit-any */
export type Profile = Record<string, any>;
export interface Option {
  value: string;
  label: string;
}
export interface Tag {
  key: string;
  value: string;
}

// ── Presets & options ───────────────────────────────────────────────
export const QUICK_PRESETS: Profile[] = [
  {
    name: "H.265 Balanced",
    video_codec: "libx265", audio_codec: "aac", subtitle_mode: "copy",
    metadata: {},
    video_params: { crf: 23, preset: "medium", pix_fmt: "yuv420p" },
    audio_params: { bitrate: "192k" },
  },
  {
    name: "H.265 High Quality",
    video_codec: "libx265", audio_codec: "flac", subtitle_mode: "copy",
    metadata: {},
    video_params: { crf: 18, preset: "slow", pix_fmt: "yuv420p10le" },
    audio_params: {},
  },
  {
    name: "H.264 Fast Encode",
    video_codec: "libx264", audio_codec: "aac", subtitle_mode: "copy",
    metadata: {},
    video_params: { crf: 20, preset: "veryfast", pix_fmt: "yuv420p" },
    audio_params: { bitrate: "192k" },
  },
  {
    name: "AV1 Balanced",
    video_codec: "libsvtav1", audio_codec: "libopus", subtitle_mode: "copy",
    metadata: {},
    video_params: { crf: 30, preset: 6, pix_fmt: "yuv420p10le", keyint_seconds: 10, fast_decode: true },
    audio_params: { bitrate: "128k", vbr: true },
  },
  {
    name: "Anime Encode",
    video_codec: "libx265", audio_codec: "libopus", subtitle_mode: "copy",
    metadata: {},
    video_params: { crf: 20, preset: "slow", pix_fmt: "yuv420p10le", extra_params: "tune=animation" },
    audio_params: { bitrate: "192k" },
  },
  {
    name: "Web Streaming",
    video_codec: "libx264", audio_codec: "aac", subtitle_mode: "copy",
    metadata: {},
    video_params: { crf: 23, preset: "fast", pix_fmt: "yuv420p", profile: "high", level: "4.1", extra_params: "tune=zerolatency" },
    audio_params: { bitrate: "128k" },
  },
];

export const OUTPUT_CONTAINERS: Option[] = [
  { value: "auto", label: "Auto (use source when compatible)" },
  { value: "mkv", label: "Matroska (.mkv)" },
  { value: "mp4", label: "MP4 (.mp4)" },
  { value: "mov", label: "QuickTime (.mov)" },
  { value: "webm", label: "WebM (.webm)" },
];

export const VIDEO_CODECS: Option[] = [
  { value: "libsvtav1", label: "AV1 (SVT-AV1)" },
  { value: "libx265", label: "H.265 / HEVC (Best for 1080p)" },
  { value: "libx264", label: "H.264 / AVC (Most Compatible)" },
  { value: "libvpx-vp9", label: "VP9 (YouTube format)" },
  { value: "mpeg4", label: "MPEG-4 (Legacy)" },
  { value: "copy", label: "Copy (No re-encode)" },
];

export const AUDIO_CODECS: Option[] = [
  { value: "libopus", label: "Opus (Best Quality/Size)" },
  { value: "aac", label: "AAC (Most Compatible)" },
  { value: "flac", label: "FLAC (Lossless)" },
  { value: "libmp3lame", label: "MP3" },
  { value: "ac3", label: "AC-3 (Dolby Digital)" },
  { value: "copy", label: "Copy (No re-encode)" },
];

export const AUDIO_BITRATES: Option[] = [
  { value: "64k", label: "64 kbps (Low)" },
  { value: "96k", label: "96 kbps" },
  { value: "128k", label: "128 kbps (Standard)" },
  { value: "192k", label: "192 kbps (High)" },
  { value: "256k", label: "256 kbps" },
  { value: "320k", label: "320 kbps (Maximum)" },
];

export const AUDIO_CHANNELS: Option[] = [
  { value: "0", label: "Keep Original" },
  { value: "1", label: "Mono (1.0)" },
  { value: "2", label: "Stereo (2.0)" },
  { value: "6", label: "Surround (5.1)" },
  { value: "8", label: "Surround (7.1)" },
];

export const SUBTITLE_MODES: Option[] = [
  { value: "copy", label: "Copy original subtitles" },
  { value: "none", label: "Remove subtitles" },
  { value: "burn", label: "Burn-in (Hardsubs)" },
];

export const KEYINT_SECONDS: Option[] = [
  { value: "2", label: "2 seconds (Smooth seeking)" },
  { value: "5", label: "5 seconds (Faster seeking)" },
  { value: "10", label: "10 seconds (Balanced)" },
  { value: "15", label: "15 seconds (Smaller file)" },
];

export const LEVELS: Option[] = [
  { value: "", label: "Default / Auto" },
  ...["3.0", "3.1"].map((v) => ({ value: v, label: v })),
  { value: "4.0", label: "4.0 (1080p30)" },
  { value: "4.1", label: "4.1 (1080p60)" },
  { value: "5.0", label: "5.0" },
  { value: "5.1", label: "5.1 (4K)" },
  { value: "5.2", label: "5.2" },
  { value: "6.0", label: "6.0 (8K)" },
  { value: "6.1", label: "6.1" },
  { value: "6.2", label: "6.2" },
];

export const FPS_MODES: Option[] = [
  { value: "vfr", label: "Variable (Preserve timing)" },
  { value: "cfr", label: "Constant frame rate" },
  { value: "passthrough", label: "Timestamp passthrough" },
  { value: "auto", label: "FFmpeg automatic" },
];

const COLOR_BASE: Option[] = [
  { value: "", label: "Default / Auto" },
  { value: "bt709", label: "BT.709 (HD/SDR)" },
  { value: "bt2020", label: "BT.2020 (HDR/UHD)" },
  { value: "smpte170m", label: "SMPTE 170M (SD/NTSC)" },
  { value: "smpte240m", label: "SMPTE 240M" },
  { value: "bt470bg", label: "BT.470 BG (SD/PAL)" },
];
export const COLOR_PRIMARIES = COLOR_BASE;
export const COLOR_TRC = COLOR_BASE;
export const COLORSPACES: Option[] = COLOR_BASE.map((o) =>
  o.value === "bt2020" ? { value: "bt2020nc", label: "BT.2020 NC (HDR/UHD)" } : o,
);

export const TRACK_CHOICES: Option[] = [
  { value: "?", label: "Keep all tracks (?)" },
  { value: "0", label: "Track 1 only (0)" },
  { value: "1", label: "Track 2 only (1)" },
  { value: "0,1", label: "Tracks 1 & 2 (0,1)" },
  { value: "1,0", label: "Tracks 2 & 1 (1,0)" },
  { value: "custom", label: "Custom mapping…" },
];

export const TAG_TRACKS: Option[] = [
  { value: "0", label: "Track 1" },
  { value: "1", label: "Track 2" },
  { value: "2", label: "Track 3" },
  { value: "3", label: "Track 4" },
  { value: "?", label: "All (?)" },
];

export const TAG_TYPES: Option[] = [
  { value: "title", label: "Title" },
  { value: "language", label: "Language" },
  { value: "handler_name", label: "Handler" },
  { value: "custom", label: "Custom" },
];

export const RENAME_TOKENS = [
  "{title}", "{episode}", "{quality}", "{resolution}", "{source}", "{audio}",
  "{codec}", "{basename}", "{filename}", "{year}", "{audiolang}", "{sublang}",
];
export const TITLE_TOKENS = ["{title}", "{episode}", "{quality}", "{basename}", "{filename}", "{year}"];

export const SVT_AV1_PRESETS: Option[] = Array.from({ length: 14 }, (_, i) => ({
  value: String(i),
  label: `Preset ${i} ${i < 4 ? "(Slowest)" : i > 9 ? "(Fastest)" : ""}`.trim(),
}));

export const X264_X265_PRESETS: Option[] = [
  { value: "veryslow", label: "Very Slow" },
  { value: "slower", label: "Slower" },
  { value: "slow", label: "Slow" },
  { value: "medium", label: "Medium" },
  { value: "fast", label: "Fast" },
  { value: "faster", label: "Faster" },
  { value: "veryfast", label: "Very Fast" },
  { value: "superfast", label: "Super Fast" },
  { value: "ultrafast", label: "Ultra Fast" },
];

export const VIDEO_PROFILE_OPTIONS: Record<string, Option[]> = {
  libsvtav1: [{ value: "0", label: "Main (4:2:0)" }],
  libx264: [
    { value: "baseline", label: "Baseline" },
    { value: "main", label: "Main" },
    { value: "high", label: "High" },
    { value: "high10", label: "High 10" },
  ],
  libx265: [
    { value: "main", label: "Main" },
    { value: "main10", label: "Main 10" },
  ],
};

export const PIXEL_FORMAT_OPTIONS: Record<string, Option[]> = {
  libsvtav1: [
    { value: "yuv420p10le", label: "10-bit YUV 4:2:0 (Recommended)" },
    { value: "yuv420p", label: "8-bit YUV 4:2:0 (Standard)" },
  ],
  libx264: [
    { value: "yuv420p", label: "8-bit YUV 4:2:0 (Most compatible)" },
    { value: "yuv420p10le", label: "10-bit YUV 4:2:0" },
    { value: "yuv422p", label: "8-bit YUV 4:2:2" },
    { value: "yuv444p", label: "8-bit YUV 4:4:4" },
  ],
  libx265: [
    { value: "yuv420p10le", label: "10-bit YUV 4:2:0 (Recommended)" },
    { value: "yuv420p", label: "8-bit YUV 4:2:0 (Standard)" },
    { value: "yuv422p", label: "8-bit YUV 4:2:2" },
    { value: "yuv444p", label: "8-bit YUV 4:4:4" },
  ],
  "libvpx-vp9": [
    { value: "yuv420p10le", label: "10-bit YUV 4:2:0" },
    { value: "yuv420p", label: "8-bit YUV 4:2:0" },
    { value: "yuv422p", label: "8-bit YUV 4:2:2" },
    { value: "yuv444p", label: "8-bit YUV 4:4:4" },
  ],
  mpeg4: [{ value: "yuv420p", label: "8-bit YUV 4:2:0" }],
  copy: [],
};

export const DISPOSITION_OPTIONS: Option[] = [
  { label: "0 (Remove all flags)", value: "0" },
  { label: "default (Mark as default)", value: "default" },
  { label: "forced (Mark as forced)", value: "forced" },
  { label: "default+forced", value: "default+forced" },
  { label: "dub (Dub track)", value: "dub" },
  { label: "comment (Commentary)", value: "comment" },
  { label: "hearing_impaired", value: "hearing_impaired" },
  { label: "visual_impaired", value: "visual_impaired" },
  { label: "captions", value: "captions" },
];

export const LANGUAGES: Option[] = [
  { value: "eng", label: "English (eng)" },
  { value: "jpn", label: "Japanese (jpn)" },
  { value: "spa", label: "Spanish (spa)" },
  { value: "fra", label: "French (fra)" },
  { value: "ger", label: "German (ger)" },
  { value: "ita", label: "Italian (ita)" },
  { value: "kor", label: "Korean (kor)" },
  { value: "chi", label: "Chinese (chi)" },
  { value: "rus", label: "Russian (rus)" },
  { value: "ara", label: "Arabic (ara)" },
  { value: "hin", label: "Hindi (hin)" },
  { value: "por", label: "Portuguese (por)" },
  { value: "und", label: "Undefined (und)" },
];

export const standardMetadataKeys = ["title", "v_track", "a_track", "s_track"];

export function presetOptions(codec: string): Option[] {
  if (codec === "libsvtav1") return SVT_AV1_PRESETS;
  if (codec === "libx264" || codec === "libx265") return X264_X265_PRESETS;
  return [];
}

export function hasPreset(codec: string): boolean {
  return codec === "libsvtav1" || codec === "libx264" || codec === "libx265";
}

/** A <select> only keeps a value that is one of its options. */
export function coerce(value: unknown, options: Option[]): string {
  const v = value === undefined || value === null ? "" : String(value);
  return options.some((o) => o.value === v) ? v : "";
}

export function crfHint(val: number): string {
  if (val < 18) return "Near lossless — very large file size";
  if (val <= 22) return "High quality — larger file size";
  if (val <= 28) return "Good balance of quality and size";
  if (val <= 35) return "Smaller file — some quality loss";
  return "Low quality — small file size";
}

/** Stream-scoped keys look like `s:v:0` (metadata) or `v:0` (disposition). */
export function matchesPrefix(key: string, prefix: string): boolean {
  const trimmed = key.trim();
  if (!trimmed.startsWith(prefix)) return false;
  return /^[\d?]+$/.test(trimmed.slice(prefix.length));
}

// ── Editor form state ───────────────────────────────────────────────
export interface Form {
  name: string;
  container: string;
  vCodec: string;
  svtVariant: string;
  pixFmt: string;
  crf: number;
  preset: string;
  keyint: string;
  fastDecode: boolean;
  vProfile: string;
  level: string;
  fpsMode: string;
  colorPrim: string;
  colorTrc: string;
  colorspace: string;
  extra: string;
  aCodec: string;
  aBitrate: string;
  aChannels: string;
  aVbr: boolean;
  sMode: string;
  tracks: Record<"v" | "a" | "s", { sel: string; custom: string }>;
  rename: string;
  title: string;
  cover: string;
  meta: Tag[];
  disp: Tag[];
}

export function defaultForm(): Form {
  return {
    name: "Custom Profile",
    container: "auto",
    vCodec: "libx264",
    svtVariant: "standard",
    pixFmt: "yuv420p",
    crf: 23,
    preset: "medium",
    keyint: "10",
    fastDecode: true,
    vProfile: "",
    level: "",
    fpsMode: "vfr",
    colorPrim: "",
    colorTrc: "",
    colorspace: "",
    extra: "",
    aCodec: "aac",
    aBitrate: "192k",
    aChannels: "2",
    aVbr: false,
    sMode: "copy",
    tracks: { v: { sel: "?", custom: "" }, a: { sel: "?", custom: "" }, s: { sel: "?", custom: "" } },
    rename: "",
    title: "",
    cover: "",
    meta: [],
    disp: [],
  };
}

/** Codec change: reset preset to the codec default, keep compatible pix_fmt/profile. */
export function applyVideoCodec(f: Form, codec: string) {
  if (f.svtVariant === "5fish") f.extra = "";
  f.vCodec = codec;
  f.svtVariant = "standard";
  f.preset = codec === "libsvtav1" ? "6" : hasPreset(codec) ? "medium" : "";
  const pix = PIXEL_FORMAT_OPTIONS[codec] || [];
  if (pix.length) f.pixFmt = pix.some((o) => o.value === f.pixFmt) ? f.pixFmt : pix[0].value;
  else f.pixFmt = "";
  const profiles = VIDEO_PROFILE_OPTIONS[codec] || [];
  f.vProfile = profiles.some((o) => o.value === f.vProfile) ? f.vProfile : "";
}

export function applySvtVariant(f: Form, variant: string) {
  const anime = variant === "5fish";
  f.svtVariant = variant;
  f.preset = anime ? "2" : "6";
  f.crf = anime ? 26 : 30;
  f.fastDecode = !anime;
  f.extra = "";
  if (anime) f.pixFmt = "yuv420p10le";
}

export function profileChoices(codec: string): Option[] {
  return [{ value: "", label: "Default / Auto" }, ...(VIDEO_PROFILE_OPTIONS[codec] || [])];
}

export function alignPixelFormatForProfile(f: Form) {
  if (f.vCodec === "libx264" && f.vProfile) f.pixFmt = f.vProfile === "high10" ? "yuv420p10le" : "yuv420p";
  else if (f.vCodec === "libx265" && f.vProfile) f.pixFmt = f.vProfile === "main10" ? "yuv420p10le" : "yuv420p";
}

function setTrack(f: Form, stream: "v" | "a" | "s", value: string) {
  if (!value || value === "?") f.tracks[stream] = { sel: "?", custom: "" };
  else if (TRACK_CHOICES.some((o) => o.value === value && o.value !== "custom"))
    f.tracks[stream] = { sel: value, custom: "" };
  else f.tracks[stream] = { sel: "custom", custom: value };
}

function trackValue(f: Form, stream: "v" | "a" | "s"): string {
  const t = f.tracks[stream];
  if (t.sel === "custom") return t.custom || "";
  if (t.sel === "?") return "";
  return t.sel;
}

/** Quick preset: every codec-specific field resets so nothing leaks across. */
export function applyPreset(f: Form, preset: Profile) {
  applyVideoCodec(f, preset.video_codec);
  f.aCodec = preset.audio_codec;
  f.sMode = preset.subtitle_mode;
  const vp = preset.video_params || {};
  const av1 = preset.video_codec === "libsvtav1";
  f.crf = vp.crf ?? 23;
  f.preset = coerce(vp.preset ?? (av1 ? 6 : "medium"), presetOptions(f.vCodec));
  f.pixFmt = coerce(vp.pix_fmt || (av1 ? "yuv420p10le" : "yuv420p"), PIXEL_FORMAT_OPTIONS[f.vCodec] || []);
  f.vProfile = coerce(vp.profile ?? "", profileChoices(f.vCodec));
  f.level = coerce(vp.level || "", LEVELS);
  f.colorPrim = coerce(vp.color_primaries || "", COLOR_PRIMARIES);
  f.colorTrc = coerce(vp.color_trc || "", COLOR_TRC);
  f.colorspace = coerce(vp.colorspace || "", COLORSPACES);
  f.fpsMode = coerce(vp.fps_mode || "vfr", FPS_MODES);
  f.extra = vp.extra_params || "";
  f.keyint = coerce(vp.keyint_seconds || 10, KEYINT_SECONDS);
  alignPixelFormatForProfile(f);
  f.fastDecode = vp.fast_decode !== false;
  const ap = preset.audio_params || {};
  f.aBitrate = coerce(ap.bitrate || (preset.audio_codec === "libopus" ? "128k" : "192k"), AUDIO_BITRATES);
  f.aChannels = coerce(ap.channels ?? 2, AUDIO_CHANNELS);
  f.aVbr = preset.audio_codec === "libopus" && Boolean(ap.vbr);
  f.meta = [];
  f.disp = [];
  Object.entries(preset.metadata || {}).forEach(([k, v]) => {
    if (!standardMetadataKeys.includes(k.trim())) f.meta.push({ key: k, value: String(v) });
  });
}

/** Load a saved or imported profile into the editor. */
export function formFromProfile(data: Profile): Form {
  const f = defaultForm();
  f.container = coerce(String(data.container ?? "auto").trim().toLowerCase(), OUTPUT_CONTAINERS);
  if (!f.container) throw new Error("Choose Auto, MKV, MP4, MOV, or WebM as the output container.");
  f.name = data.name || "Custom Profile";
  f.rename = data.rename || "";
  f.cover = data.cover_image || "";
  const vCodec = coerce(String(data.video_codec || "libx264").trim().toLowerCase(), VIDEO_CODECS);
  if (data.svtav1_variant != null && (data.svtav1_variant !== "5fish" || vCodec !== "libsvtav1")) {
    throw new Error("The SVT-AV1 variant must be 5fish and requires the SVT-AV1 video codec.");
  }
  f.aCodec = coerce(data.audio_codec || "aac", AUDIO_CODECS);
  f.sMode = coerce(data.subtitle_mode || "copy", SUBTITLE_MODES);
  const vp = data.video_params || {};
  const isAv1 = vCodec === "libsvtav1";
  const isAnime = isAv1 && data.svtav1_variant === "5fish";
  const isHevc = vCodec === "libx265";
  applyVideoCodec(f, vCodec);
  if (isAnime) applySvtVariant(f, "5fish");
  f.crf = Number(vp.crf ?? (isAnime ? 26 : isAv1 ? 30 : isHevc ? 24 : 23));
  f.preset = coerce(vp.preset ?? (isAv1 ? f.preset : "medium"), presetOptions(vCodec));
  f.pixFmt = coerce(vp.pix_fmt || (isAv1 || isHevc ? "yuv420p10le" : "yuv420p"), PIXEL_FORMAT_OPTIONS[vCodec] || []);
  f.vProfile = coerce(vp.profile ?? "", profileChoices(vCodec));
  f.level = coerce(vp.level || "", LEVELS);
  f.colorPrim = coerce(vp.color_primaries || "", COLOR_PRIMARIES);
  f.colorTrc = coerce(vp.color_trc || "", COLOR_TRC);
  f.colorspace = coerce(vp.colorspace || "", COLORSPACES);
  f.fpsMode = coerce(vp.fps_mode || "vfr", FPS_MODES);
  f.extra = vp.extra_params || "";
  f.keyint = coerce(vp.keyint_seconds || 10, KEYINT_SECONDS);
  alignPixelFormatForProfile(f);
  const legacyTuneZero = String(vp.extra_params || "")
    .split(":")
    .some((part) => part.trim() === "tune=0");
  const fastDecode = vp.fast_decode;
  if (typeof fastDecode === "string") {
    const value = fastDecode.trim().toLowerCase();
    f.fastDecode = ["1", "true", "yes", "on"].includes(value)
      || (!isAnime && !["0", "false", "no", "off"].includes(value));
  } else if (typeof fastDecode === "boolean" || typeof fastDecode === "number") {
    f.fastDecode = Boolean(fastDecode);
  } else {
    f.fastDecode = !isAnime && !legacyTuneZero;
  }
  const ap = data.audio_params || {};
  const isOpus = f.aCodec === "libopus";
  f.aBitrate = coerce(ap.bitrate || (isOpus ? "128k" : "192k"), AUDIO_BITRATES);
  f.aChannels = coerce(ap.channels ?? 2, AUDIO_CHANNELS);
  f.aVbr = isOpus && ap.vbr !== false;
  const md = data.metadata || {};
  f.title = md.title || "";
  setTrack(f, "v", md.v_track || "");
  setTrack(f, "a", md.a_track || "");
  setTrack(f, "s", md.s_track || "");
  Object.entries(md).forEach(([k, v]) => {
    if (!standardMetadataKeys.includes(k.trim())) f.meta.push({ key: k, value: String(v) });
  });
  Object.entries(data.disposition || {}).forEach(([k, v]) => f.disp.push({ key: k, value: String(v) }));
  return f;
}

// ── Profile JSON ────────────────────────────────────────────────────
export function getProfileJSON(f: Form): Profile {
  const vCodec = f.vCodec;
  const aCodec = f.aCodec;
  const isAnime = vCodec === "libsvtav1" && f.svtVariant === "5fish";

  const metadata: Record<string, string> = {};
  if (f.title) metadata.title = f.title;
  const vTrack = trackValue(f, "v");
  const aTrack = trackValue(f, "a");
  const sTrack = trackValue(f, "s");
  if (vTrack) metadata.v_track = vTrack;
  if (aTrack) metadata.a_track = aTrack;
  if (sTrack) metadata.s_track = sTrack;

  // Stream-scoped metadata tags; duplicate keys get trailing spaces, which
  // the bot trims, so several tags can target the same stream.
  f.meta.forEach((item) => {
    if (item.key && item.value) {
      let uniqueKey = item.key.trim();
      while (metadata[uniqueKey] !== undefined) uniqueKey += " ";
      metadata[uniqueKey] = item.value;
    }
  });

  const disposition: Record<string, string> = {};
  f.disp.forEach((item) => {
    if (item.key && item.value) disposition[item.key.trim()] = item.value;
  });

  const profile: Profile = {
    name: f.name || "Custom Profile",
    rename: f.rename || "",
    cover_image: f.cover || "",
    video_codec: vCodec || "libx264",
    ...(f.container !== "auto" ? { container: f.container } : {}),
    ...(isAnime ? { svtav1_variant: "5fish" } : {}),
    audio_codec: aCodec || "aac",
    subtitle_mode: f.sMode || "copy",
    metadata,
    video_params: {
      crf: parseInt(String(f.crf ?? "23")),
      preset: vCodec === "libsvtav1" ? parseInt(f.preset || (isAnime ? "2" : "6")) : f.preset || "medium",
      pix_fmt: f.pixFmt || "yuv420p",
      profile: f.vProfile || "",
      level: f.level || "",
      color_primaries: f.colorPrim || "",
      color_trc: f.colorTrc || "",
      colorspace: f.colorspace || "",
      extra_params: f.extra || "",
      keyint_seconds: vCodec === "libsvtav1" ? parseInt(f.keyint || "10") : undefined,
      fast_decode: vCodec === "libsvtav1" ? f.fastDecode !== false : undefined,
      fps_mode: f.fpsMode || "vfr",
    },
    audio_params: {
      bitrate: f.aBitrate || (aCodec === "libopus" ? "128k" : "192k"),
      channels: parseInt(f.aChannels || "2"),
      vbr: aCodec === "libopus" && (f.aVbr || false),
    },
  };

  if (Object.keys(disposition).length > 0) profile.disposition = disposition;

  Object.keys(profile.video_params).forEach((k) => {
    if (profile.video_params[k] === "") delete profile.video_params[k];
  });
  if (!profile.rename) delete profile.rename;
  if (!profile.cover_image) delete profile.cover_image;
  return profile;
}

/** JSON as shown and copied: without is_default and undefined fields. */
export function exportJSON(profile: Profile, indent = 2): string {
  const exportData = { ...profile };
  delete exportData.is_default;
  return JSON.stringify(exportData, null, indent);
}

export function containerError(profile: Profile): string {
  const { container, video_codec, audio_codec, subtitle_mode } = profile;
  if (container === "mov") {
    if (!["libx264", "libx265", "mpeg4", "copy"].includes(video_codec)) {
      return "MOV requires H.264, H.265, MPEG-4, or compatible copied video.";
    }
    if (!["aac", "ac3", "libmp3lame", "copy"].includes(audio_codec)) {
      return "MOV requires AAC, AC-3, MP3, or compatible copied audio.";
    }
  }
  if (container === "webm") {
    if (!["libsvtav1", "libvpx-vp9", "copy"].includes(video_codec) ||
        (video_codec === "copy" && subtitle_mode === "burn")) {
      return "WebM requires AV1, VP9, or compatible copied video without subtitle burn-in.";
    }
    if (!["libopus", "copy"].includes(audio_codec)) {
      return "WebM requires Opus or compatible copied audio.";
    }
  }
  return "";
}

// ── FFmpeg command preview ──────────────────────────────────────────
export function getFFmpegCmd(profile: Profile): string {
  const container = coerce(profile.container, OUTPUT_CONTAINERS);
  const extension = !container || container === "auto" ? "mkv" : container;
  const isMkv = extension === "mkv";
  const isMp4OrMov = extension === "mp4" || extension === "mov";
  const useAutomaticTimestamps = isMkv && profile.audio_codec === 'copy';
  if (profile.video_codec === "copy" && profile.subtitle_mode === "burn") {
    profile = { ...profile, video_codec: "libx264" };
  }
  const isAnime = profile.video_codec === "libsvtav1" && profile.svtav1_variant === "5fish";
  const binary = isAnime ? "/opt/amaterasu-5fish/bin/ffmpeg" : "ffmpeg";
  const useLegacySvtParams = useAutomaticTimestamps && !isAnime;
  let cmd = `${binary} -y -nostdin${useAutomaticTimestamps ? '' : ' -fflags +genpts'} -i input.mkv \\\n`;

  // Track mapping
  const tracks = [
    ["v", profile.metadata?.v_track ?? "0"],
    ["a", profile.metadata?.a_track ?? "?"],
    ["s", profile.subtitle_mode === "copy" ? profile.metadata?.s_track ?? "?" : ""],
  ];
  for (const [type, selection] of tracks) {
    for (const track of String(selection).split(",").map((value) => value.trim()).filter(Boolean)) {
      const stream = ["?", "*", "all"].includes(track) ? type : `${type}:${track.replace(/\?$/, "")}`;
      cmd += `  -map '0:${stream.replaceAll("'", "'\"'\"'")}?' \\\n`;
    }
  }
  if (isMkv) cmd += `  -map '0:t?' -c:t copy \\\n`;

  // Video
  cmd += `  -c:v ${profile.video_codec}`;
  if (profile.video_codec !== 'copy') {
    if (profile.video_params?.pix_fmt) cmd += ` -pix_fmt ${profile.video_params.pix_fmt}`;
    if (profile.video_codec === 'libsvtav1') {
      const svtParts: string[] = [];
      if (useLegacySvtParams) {
        if (profile.video_params?.preset !== undefined) svtParts.push(`preset=${profile.video_params.preset}`);
        if (profile.video_params?.crf !== undefined) svtParts.push(`crf=${profile.video_params.crf}`);
      } else {
        if (profile.video_params?.preset !== undefined) cmd += ` -preset ${profile.video_params.preset}`;
        if (profile.video_params?.crf !== undefined) cmd += ` -crf ${profile.video_params.crf}`;
      }
      const svtParams = new Map<string, string>();
      for (const part of String(profile.video_params?.extra_params || '').split(':')) {
        const separator = part.indexOf("=");
        if (separator < 0) continue;
        const key = part.slice(0, separator).trim();
        const value = part.slice(separator + 1).trim();
        if (/^[A-Za-z0-9_-]+$/.test(key) && value) svtParams.set(key, value);
      }
      for (const key of ['preset', 'crf', 'profile', 'level']) svtParams.delete(key);
      const seekSeconds = Number(profile.video_params?.keyint_seconds);
      const alignAnimeKeyint = (frames: number) => Math.max(1, Math.floor((frames + 15) / 32)) * 32 + 1;
      if (Number.isFinite(seekSeconds)) {
        svtParams.set('keyint', String(Math.max(24, Math.min(1800, Math.round(seekSeconds * 24)))));
      }
      if (isAnime) {
        cmd += ' -err_detect:v +explode';
        for (const key of ['lineart-psy-bias', 'texture-psy-bias']) {
          if (!svtParams.has(key)) svtParams.set(key, '3');
        }
        const keyint = alignAnimeKeyint(Math.min(1800, Number(svtParams.get('keyint')) || 240));
        svtParams.set('keyint', String(keyint));
        const minimum = svtParams.get('min-keyint') ?? '-1';
        if (minimum === '-1' && keyint < 129) {
          svtParams.set('min-keyint', '33');
        } else if (/^\+?\d+$/.test(minimum)) {
          const frames = Math.min(keyint, Number(minimum));
          svtParams.set('min-keyint', String(frames > 1 ? alignAnimeKeyint(frames) : frames));
        }
      }
      const fastDecode = profile.video_params?.fast_decode;
      if (typeof fastDecode === 'boolean') {
        if (useLegacySvtParams && !fastDecode) svtParams.delete('fast-decode');
        else svtParams.set('fast-decode', fastDecode ? '1' : '0');
      }
      if (profile.video_params?.profile !== undefined && profile.video_params.profile !== '') {
        svtParams.set('profile', String(profile.video_params.profile));
      }
      if (profile.video_params?.level) {
        svtParams.set('level', String(profile.video_params.level).replace('.', ''));
      }
      for (const [key, value] of svtParams) svtParts.push(`${key}=${value}`);
      if (svtParts.length) cmd += ` -svtav1-params "${svtParts.join(':')}"`;
    } else {
      if (profile.video_params?.crf !== undefined) cmd += ` -crf ${profile.video_params.crf}`;
      if (profile.video_params?.preset !== undefined && ['libx264', 'libx265'].includes(profile.video_codec)) {
        cmd += ` -preset ${profile.video_params.preset}`;
      }
      if (profile.video_codec === 'libvpx-vp9') cmd += ` -b:v 0`;
      if (profile.video_params?.extra_params && ['libx264', 'libx265'].includes(profile.video_codec)) {
        const codecParam = profile.video_codec === 'libx265' ? 'x265' : 'x264';
        cmd += ` -${codecParam}-params "${profile.video_params.extra_params}"`;
      }
    }
    if (profile.video_codec !== 'libsvtav1' && profile.video_params?.profile) {
      cmd += ` -profile:v ${profile.video_params.profile}`;
    }
    if (profile.video_codec !== 'libsvtav1' && profile.video_params?.level) {
      cmd += ` -level ${profile.video_params.level}`;
    }
    if (profile.video_params?.color_primaries) cmd += ` \\\n  -color_primaries ${profile.video_params.color_primaries}`;
    if (profile.video_params?.color_trc) cmd += ` -color_trc ${profile.video_params.color_trc}`;
    if (profile.video_params?.colorspace) cmd += ` -colorspace ${profile.video_params.colorspace}`;
    const fpsMode = profile.video_params?.fps_mode || 'vfr';
    if (!(useAutomaticTimestamps && ['auto', 'vfr'].includes(fpsMode))) {
      cmd += ` -fps_mode:v:0 ${fpsMode}`;
    }
  }
  cmd += ` \\\n`;

  // Audio
  cmd += `  -c:a ${profile.audio_codec}`;
  if (profile.audio_codec !== 'copy' && profile.audio_codec !== 'flac') {
    if (profile.audio_params?.bitrate) cmd += ` -b:a ${profile.audio_params.bitrate}`;
  }
  if (profile.audio_codec !== 'copy' && profile.audio_params?.channels) {
    cmd += ` -ac ${profile.audio_params.channels}`;
  }
  if (profile.audio_codec === 'libopus' && profile.audio_params?.vbr) {
    cmd += ` -vbr on`;
  }
  cmd += ` \\\n`;

  // Subtitles
  if (profile.subtitle_mode === 'none') {
    cmd += `  -sn \\\n`;
  } else if (profile.subtitle_mode === 'burn') {
    const track = String(profile.metadata?.s_track ?? "").split(",")
      .map((value) => value.trim().replace(/\?$/, "")).find((value) => /^[0-9]+$/.test(value)) ?? "0";
    cmd += `  -vf subtitles=input.mkv:si=${track} \\\n`;
  } else {
    cmd += `  -c:s copy \\\n`;
  }

  // Global metadata
  if (profile.metadata?.title) {
    cmd += `  -metadata title="${profile.metadata.title}" \\\n`;
  }

  // Stream metadata tags
  if (profile.metadata) {
    Object.entries(profile.metadata).forEach(([k, v]) => {
      if (!standardMetadataKeys.includes(k.trim())) {
        if (k.includes(':')) {
          cmd += `  -metadata:${k.trim()} "${v}" \\\n`;
        } else {
          cmd += `  -metadata "${k}=${v}" \\\n`;
        }
      }
    });
  }

  // Disposition flags
  if (profile.disposition) {
    Object.entries(profile.disposition).forEach(([k, v]) => {
      cmd += `  -disposition:${k.trim()} ${v} \\\n`;
    });
  }

  cmd += `  -max_muxing_queue_size 4096`;
  if (!useAutomaticTimestamps) cmd += ` -avoid_negative_ts make_zero`;
  if (isMkv && !useAutomaticTimestamps) cmd += ` -cluster_time_limit 5000`;
  if (isMp4OrMov) {
    cmd += ` -movflags +faststart`;
    if (profile.video_codec === "libx265") cmd += ` -tag:v:0 hvc1`;
  }
  cmd += ` \\\n`;
  cmd += `  output.${extension}`;
  return cmd;
}

// ── Storage: the bot's database when linked, this browser otherwise ──
const LOCAL_STORAGE_KEY = "amaterasu_encoding_profiles";
const params = new URLSearchParams(location.search);
const userId = params.get("user_id") || "";
const token = params.get("token") || "";
/** Opened without a signed link from the bot: profiles live in localStorage. */
export const isOfflineMode = !userId || !token;

const generateId = () => Math.random().toString(36).substring(2, 10);
const apiPath = (path: string) =>
  `${path}?user_id=${encodeURIComponent(userId)}&token=${encodeURIComponent(token)}`;

async function responseError(response: Response, action: string): Promise<Error> {
  let detail = "";
  try {
    const body = await response.clone().json();
    detail = body.detail || body.error || "";
  } catch {
    detail = await response.text().catch(() => "");
    // Proxies and servers answer errors with HTML pages; never show markup.
    if (/^\s*</.test(detail) || detail.length > 300) detail = "";
  }
  return new Error(detail || `${action} failed with HTTP ${response.status}`);
}

function readLocal(): Record<string, Profile> {
  const stored = localStorage.getItem(LOCAL_STORAGE_KEY);
  return stored ? JSON.parse(stored) : {};
}

export const profileApi = {
  async list(): Promise<Record<string, Profile>> {
    if (!isOfflineMode) {
      try {
        const res = await fetch(apiPath("/api/profiles"));
        if (res.ok) return await res.json();
      } catch (e) {
        console.error("API error, falling back to local", e);
      }
    }
    return readLocal();
  },
  async save(id: string | null, data: Profile): Promise<string> {
    if (!isOfflineMode) {
      const res = await fetch(apiPath(id ? `/api/profiles/${id}` : "/api/profiles"), {
        method: id ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (res.ok) {
        const result = await res.json();
        return result.id || id;
      }
      throw await responseError(res, "Saving profile");
    }
    const profiles = readLocal();
    const newId = id || generateId();
    profiles[newId] = { ...data, updatedAt: new Date().toISOString() };
    localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(profiles));
    return newId;
  },
  async delete(id: string): Promise<void> {
    if (!isOfflineMode) {
      const res = await fetch(apiPath(`/api/profiles/${id}`), { method: "DELETE" });
      if (res.ok) return;
      throw await responseError(res, "Deleting profile");
    }
    const profiles = readLocal();
    delete profiles[id];
    localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(profiles));
  },
  async setDefault(id: string): Promise<void> {
    if (!isOfflineMode) {
      const res = await fetch(apiPath(`/api/profiles/${id}/default`), { method: "POST" });
      if (res.ok) return;
      throw await responseError(res, "Setting default profile");
    }
    const profiles = readLocal();
    Object.keys(profiles).forEach((k) => (profiles[k].is_default = false));
    if (profiles[id]) profiles[id].is_default = true;
    localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(profiles));
  },
};

/** Drop Mongo's _id and anything that is not a profile object. */
export function cleanProfiles(loaded: Record<string, unknown> | null): Record<string, Profile> {
  return Object.fromEntries(
    Object.entries(loaded || {}).filter(
      ([id, p]) => id !== "_id" && p && typeof p === "object" && !Array.isArray(p),
    ),
  ) as Record<string, Profile>;
}
