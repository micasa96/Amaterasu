import assert from "node:assert/strict";
import { test } from "node:test";

globalThis.location = { search: "" };
const { applyPreset, containerError, formFromProfile, getFFmpegCmd, getProfileJSON, QUICK_PRESETS } = await import(
  "../web/ui/src/pages/encode-profiles/profile.ts"
);

const profile = {
  video_codec: "libsvtav1",
  svtav1_variant: "5fish",
  audio_codec: "copy",
  subtitle_mode: "copy",
  video_params: {
    preset: 4,
    crf: 28,
    keyint_seconds: 2,
    fast_decode: false,
    extra_params: "preset=6:crf=32: keyint = 240 :min-keyint=129:fast-decode=1",
  },
};

test("5fish survives import and export while an invalid variant is rejected", () => {
  const saved = getProfileJSON(formFromProfile(profile));
  assert.equal(saved.svtav1_variant, "5fish");
  assert.equal(saved.video_params.preset, 4);
  assert.equal(formFromProfile({
    ...profile, video_params: { ...profile.video_params, fast_decode: "false" },
  }).fastDecode, false);
  assert.throws(() => formFromProfile({ ...profile, svtav1_variant: "5Fish" }), /must be 5fish/);
  assert.throws(() => formFromProfile({ ...profile, video_codec: "libx264" }), /requires the SVT-AV1/);
});

test("5fish preview keeps MKV tracks and gives the form controls priority", () => {
  const command = getFFmpegCmd(getProfileJSON(formFromProfile(profile)));
  assert.match(command, /^\/opt\/amaterasu-5fish\/bin\/ffmpeg/);
  for (const flag of ["-map '0:v:0?'", "-map '0:a?'", "-map '0:s?'", "-map '0:t?' -c:t copy"]) {
    assert.ok(command.includes(flag), flag);
  }
  assert.match(command, /-preset 4 -crf 28/);
  assert.match(command, /\bkeyint=33\b/);
  assert.match(command, /\bmin-keyint=33\b/);
  assert.match(command, /\bfast-decode=0\b/);
  assert.doesNotMatch(command, /preset=6|crf=32|keyint=240|fast-decode=1/);
});

test("the subtitle burn-in preview selects the requested track", () => {
  const command = getFFmpegCmd({
    ...profile, subtitle_mode: "burn", metadata: { a_track: "1,0?", s_track: "2,0" },
  });
  assert.match(command, /-map '0:a:1\?'/);
  assert.match(command, /-map '0:a:0\?'/);
  assert.match(command, /subtitles=input\.mkv:si=2/);
  assert.doesNotMatch(command, /-map '0:s/);
});

test("the selected output container survives a preset and controls the preview", () => {
  const form = formFromProfile({ ...profile, container: "MP4" });
  applyPreset(form, QUICK_PRESETS[0]);
  const saved = getProfileJSON(form);
  assert.equal(saved.container, "mp4");
  const command = getFFmpegCmd(saved);
  assert.match(command, /-movflags \+faststart -tag:v:0 hvc1/);
  assert.match(command, /output\.mp4$/);
  assert.doesNotMatch(command, /-c:t copy|-cluster_time_limit/);

  assert.equal(getProfileJSON(formFromProfile(profile)).container, undefined);
  assert.equal(containerError({ ...profile, container: "webm" }), "");
  assert.match(containerError({ ...profile, container: "mov" }), /MOV requires/);
  assert.throws(() => formFromProfile({ ...profile, container: "unknown" }), /output container/);
});
