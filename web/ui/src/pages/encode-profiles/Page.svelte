<script lang="ts">
  import { onMount, tick } from "svelte";
  import Shell, { type NavGroup } from "../../ui/Shell.svelte";
  import Select from "../../ui/Select.svelte";
  import Modal from "../../ui/Modal.svelte";
  import Feedback from "../../ui/Feedback.svelte";
  import Icon from "../../ui/Icon.svelte";
  import CopyButton from "../../ui/CopyButton.svelte";
  import EmptyState from "../../ui/EmptyState.svelte";
  import { toast } from "../../lib/toast.svelte";
  import TagBuilder from "./TagBuilder.svelte";
  import Star from "@lucide/svelte/icons/star";
  import CopyPlus from "@lucide/svelte/icons/copy-plus";
  import Code from "@lucide/svelte/icons/code";
  import Film from "@lucide/svelte/icons/film";
  import Music from "@lucide/svelte/icons/music";
  import Captions from "@lucide/svelte/icons/captions";
  import Tag from "@lucide/svelte/icons/tag";
  import IdCard from "@lucide/svelte/icons/id-card";
  import RotateCcw from "@lucide/svelte/icons/rotate-ccw";
  import ClipboardPaste from "@lucide/svelte/icons/clipboard-paste";
  import Sparkles from "@lucide/svelte/icons/sparkles";
  import FolderOpen from "@lucide/svelte/icons/folder-open";
  import {
    AUDIO_BITRATES,
    AUDIO_CHANNELS,
    AUDIO_CODECS,
    COLORSPACES,
    COLOR_PRIMARIES,
    COLOR_TRC,
    FPS_MODES,
    KEYINT_SECONDS,
    LEVELS,
    OUTPUT_CONTAINERS,
    PIXEL_FORMAT_OPTIONS,
    QUICK_PRESETS,
    RENAME_TOKENS,
    SUBTITLE_MODES,
    TITLE_TOKENS,
    TRACK_CHOICES,
    VIDEO_CODECS,
    alignPixelFormatForProfile,
    applyPreset,
    applySvtVariant,
    applyVideoCodec,
    cleanProfiles,
    containerError,
    crfHint,
    defaultForm,
    exportJSON,
    formFromProfile,
    getFFmpegCmd,
    getProfileJSON,
    hasPreset,
    isOfflineMode,
    presetOptions,
    profileApi,
    profileChoices,
    type Profile,
  } from "./profile";

  let { data }: { data: Record<string, unknown> } = $props();

  let form = $state(defaultForm());
  let currentProfileId = $state<string | null>(null);
  let profiles = $state<Record<string, Profile>>({});
  let listState = $state<"loading" | "ready" | "error">("loading");
  let expanded = $state<Record<string, boolean>>({});
  let busy = $state<Record<string, boolean>>({});
  let saving = $state(false);
  let error = $state("");
  let mode = $state<"json" | "ffmpeg">("json");

  let confirmDelete = $state<{ id: string; name: string } | null>(null);
  let deleting = $state(false);
  let confirmReset = $state(false);
  let importOpen = $state(false);
  let importText = $state("");
  let importError = $state("");

  const profile = $derived(getProfileJSON(form));
  const containerProblem = $derived(containerError(profile));
  const previewText = $derived(mode === "json" ? exportJSON(profile) : getFFmpegCmd(profile));
  const ids = $derived(Object.keys(profiles));
  const editingName = $derived(currentProfileId ? (profiles[currentProfileId]?.name ?? form.name) : null);

  const isVideoCopy = $derived(form.vCodec === "copy");
  const pixOptions = $derived(PIXEL_FORMAT_OPTIONS[form.vCodec] || []);

  const nav: NavGroup[] = [
    {
      label: "Profiles",
      items: [{ label: "Saved profiles", href: "#profiles", glyph: FolderOpen, current: true }],
    },
    {
      label: "Editor",
      items: [
        { label: "Container", href: "#container", glyph: Film },
        { label: "Presets", href: "#presets", glyph: Sparkles },
        { label: "Identity", href: "#identity", glyph: IdCard },
        { label: "Video", href: "#video", glyph: Film },
        { label: "Audio", href: "#audio", glyph: Music },
        { label: "Subtitles", href: "#subtitles", glyph: Captions },
        { label: "Output", href: "#output", glyph: Tag },
      ],
    },
  ];

  async function loadProfiles() {
    listState = "loading";
    try {
      profiles = cleanProfiles(await profileApi.list());
      listState = "ready";
    } catch (err) {
      console.error("Unable to load encoding profiles", err);
      listState = "error";
    }
  }

  onMount(loadProfiles);

  function fail(action: string, err: unknown) {
    const message = err instanceof Error && err.message ? err.message : "Try again.";
    error = `${action}: ${message}`;
  }

  async function save() {
    if (saving) return;
    if (containerProblem) {
      error = containerProblem;
      return;
    }
    saving = true;
    error = "";
    try {
      currentProfileId = await profileApi.save(currentProfileId, getProfileJSON(form));
      toast.show(`Saved “${form.name || "Custom Profile"}”`);
      await loadProfiles();
    } catch (err) {
      fail("Could not save the profile", err);
    } finally {
      saving = false;
    }
  }

  async function goToEditor() {
    await tick();
    const heading = document.getElementById("editor-title");
    heading?.scrollIntoView({
      behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
      block: "start",
    });
    heading?.focus({ preventScroll: true });
  }

  function edit(id: string) {
    try {
      form = formFromProfile(profiles[id]);
    } catch (err) {
      fail("Could not open the profile", err);
      return;
    }
    currentProfileId = id;
    error = "";
    toast.show(`Editing “${profiles[id].name || "Unnamed profile"}”`);
    void goToEditor();
  }

  async function run(id: string, action: string, work: () => Promise<void>, done: string) {
    busy[id] = true;
    error = "";
    try {
      await work();
      toast.show(done);
    } catch (err) {
      console.error(`Profile action '${action}' failed`, err);
      fail(action, err);
    } finally {
      busy[id] = false;
    }
  }

  function makeDefault(id: string) {
    void run(
      id,
      "Could not set the default profile",
      async () => {
        await profileApi.setDefault(id);
        await loadProfiles();
      },
      "Default profile updated",
    );
  }

  function duplicate(id: string) {
    const original = profiles[id];
    if (!original) return;
    void run(
      id,
      "Could not duplicate the profile",
      async () => {
        const copy = { ...JSON.parse(JSON.stringify(original)), name: `${original.name} (Copy)`, is_default: false };
        await profileApi.save(null, copy);
        await loadProfiles();
      },
      "Profile duplicated",
    );
  }

  async function doDelete() {
    if (!confirmDelete) return;
    const { id, name } = confirmDelete;
    deleting = true;
    error = "";
    try {
      await profileApi.delete(id);
      if (currentProfileId === id) currentProfileId = null;
      confirmDelete = null;
      toast.show(`Deleted “${name}”`);
      await loadProfiles();
    } catch (err) {
      confirmDelete = null;
      fail("Could not delete the profile", err);
    } finally {
      deleting = false;
    }
  }

  function doReset() {
    form = defaultForm();
    currentProfileId = null;
    confirmReset = false;
    error = "";
    toast.show("Editor reset to defaults");
  }

  async function openImport() {
    importError = "";
    importText = "";
    importOpen = true;
    try {
      const text = await navigator.clipboard.readText();
      if (text.trim().startsWith("{")) importText = text;
    } catch {
      /* clipboard not readable: the person pastes instead */
    }
  }

  function doImport(e: SubmitEvent) {
    e.preventDefault();
    try {
      const parsed = JSON.parse(importText);
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new SyntaxError();
      form = formFromProfile(parsed);
      currentProfileId = null;
      importOpen = false;
      toast.show("Profile imported into the editor");
      void goToEditor();
    } catch (err) {
      importError = err instanceof Error && !(err instanceof SyntaxError)
        ? err.message
        : "That is not valid profile JSON. Paste the JSON copied from a saved profile.";
    }
  }

  function insertToken(field: "rename" | "title", token: string) {
    form[field] = form[field] + token;
  }

  function setChannels(v: string) {
    form.aChannels = v;
    if (v === "0") form.aVbr = false;
  }
</script>

{#snippet field(id: string, label: string, hint?: string)}
  <label for={id}>{label}</label>
  {#if hint}<p class="note" id="{id}-hint">{hint}</p>{/if}
{/snippet}

{#snippet trackPicker(stream: "v" | "a" | "s", label: string)}
  <div class="field">
    <label for="track-{stream}">{label}</label>
    <Select
      id="track-{stream}"
      value={form.tracks[stream].sel}
      options={TRACK_CHOICES}
      onchange={(v) => {
        form.tracks[stream] = { sel: v, custom: "" };
        if (v === "custom") tick().then(() => document.getElementById(`track-${stream}-custom`)?.focus());
      }}
    />
    {#if form.tracks[stream].sel === "custom"}
      <input
        id="track-{stream}-custom"
        type="text"
        class="mono"
        aria-label="{label}: custom mapping"
        placeholder="e.g. 0,1 or ?"
        bind:value={form.tracks[stream].custom}
      />
    {/if}
  </div>
{/snippet}

{#snippet tokens(target: "rename" | "title", list: string[])}
  <div class="tokens" role="group" aria-label="Insert a placeholder">
    {#each list as token (token)}
      <button type="button" class="token" onclick={() => insertToken(target, token)}>{token}</button>
    {/each}
  </div>
{/snippet}

<Shell
  place="Encode profiles"
  {nav}
  note={isOfflineMode
    ? "Not linked to the bot. Profiles are kept in this browser."
    : "Profiles sync to your account on the bot."}
>
  <div class="page">
    <header class="page-head">
      <div>
        <h1>Encoding profiles</h1>
        <p>Build FFmpeg encoding profiles visually. Saved profiles are used by the bot's encode tasks.</p>
      </div>
      <div class="page-actions">
        <button type="button" onclick={openImport}>
          <Icon icon={ClipboardPaste} size={16} /> Import JSON
        </button>
        <button type="button" class="btn-primary" onclick={save} disabled={saving}>
          {#if saving}<span class="spinner" aria-hidden="true"></span> Saving…{:else}<Icon name="check" size={16} /> Save profile{/if}
        </button>
      </div>
    </header>

    {#if isOfflineMode}
      <Feedback tone="warning">
        This page was opened without a link from the bot, so profiles are saved in this browser only. Open
        it from the bot's encode settings to sync them to your account.
      </Feedback>
    {/if}
    {#if error}
      <Feedback tone="danger" announcement="alert">{error}</Feedback>
    {/if}

    <!-- Saved profiles -->
    <section id="profiles" class="panel" aria-labelledby="profiles-title">
      <div class="panel-head">
        <div class="tile-head">
          <span class="tile"><Icon icon={FolderOpen} size={17} /></span>
          <div>
            <h2 id="profiles-title">Saved profiles</h2>
            <p>{isOfflineMode ? "Stored in this browser" : "Stored with your bot account"}</p>
          </div>
        </div>
        {#if listState === "ready"}
          <span class="pill num">{ids.length} {ids.length === 1 ? "profile" : "profiles"}</span>
        {/if}
      </div>
      <div class="panel-body">
        {#if listState === "loading"}
          <div class="rows" aria-hidden="true">
            <div class="skeleton row-skeleton"></div>
            <div class="skeleton row-skeleton"></div>
          </div>
          <p class="visually-hidden" role="status">Loading profiles…</p>
        {:else if listState === "error"}
          <Feedback tone="danger" announcement="alert">
            Unable to load profiles. Check the database connection and try again.
          </Feedback>
          <div><button type="button" onclick={loadProfiles}>Retry</button></div>
        {:else if ids.length === 0}
          <EmptyState title="No saved profiles yet" icon={FolderOpen}>
            Start from a preset or adjust the editor below, then choose Save profile.
          </EmptyState>
        {:else}
          <ul class="rows">
            {#each ids as id (id)}
              {@const p = profiles[id]}
              <li class="inset profile-row">
                <div class="row row-stack">
                  <div class="row-main">
                    <span class="row-title">
                      {p.name || "Unnamed profile"}
                      {#if p.is_default}<span class="pill" data-tone="accent"><Icon icon={Star} size={12} /> Default</span>{/if}
                    </span>
                    <span class="row-meta profile-meta">
                      <span><Icon icon={Film} size={13} /> {p.svtav1_variant === "5fish" ? "SVT-AV1 (5fish · Anime)" : p.video_codec || "copy"}</span>
                      <span><Icon icon={Music} size={13} /> {p.audio_codec || "copy"}</span>
                      {#if p.video_params?.preset !== undefined}<span>Preset {p.video_params.preset}</span>{/if}
                      {#if p.video_params?.crf !== undefined}<span class="num">CRF {p.video_params.crf}</span>{/if}
                    </span>
                  </div>
                  <div class="row-actions">
                    {#if !p.is_default}
                      <button
                        type="button"
                        class="btn-quiet btn-icon"
                        aria-label="Make “{p.name}” the default"
                        title="Make default"
                        disabled={busy[id]}
                        onclick={() => makeDefault(id)}
                      >
                        <Icon icon={Star} size={16} />
                      </button>
                    {/if}
                    <button
                      type="button"
                      class="btn-quiet btn-icon"
                      aria-label="Duplicate “{p.name}”"
                      title="Duplicate"
                      disabled={busy[id]}
                      onclick={() => duplicate(id)}
                    >
                      <Icon icon={CopyPlus} size={16} />
                    </button>
                    <CopyButton
                      value={exportJSON(p, 4)}
                      label="Copy JSON of “{p.name}”"
                      confirm="Profile JSON copied"
                      variant="quiet"
                      iconOnly
                    />
                    <button
                      type="button"
                      class="btn-quiet btn-icon"
                      aria-label="{expanded[id] ? 'Hide' : 'Show'} JSON of “{p.name}”"
                      aria-expanded={!!expanded[id]}
                      aria-controls="json-{id}"
                      title={expanded[id] ? "Hide JSON" : "Show JSON"}
                      onclick={() => (expanded[id] = !expanded[id])}
                    >
                      <Icon icon={Code} size={16} />
                    </button>
                    <button
                      type="button"
                      class="btn-danger-quiet btn-icon"
                      aria-label="Delete “{p.name}”"
                      title="Delete"
                      disabled={busy[id]}
                      onclick={() => (confirmDelete = { id, name: p.name || "Unnamed profile" })}
                    >
                      <Icon name="trash" size={16} />
                    </button>
                    <button type="button" class="edit-btn" onclick={() => edit(id)} disabled={busy[id]}>
                      <Icon name="pencil" size={15} /> Edit
                    </button>
                  </div>
                </div>
                {#if expanded[id]}
                  <pre class="code profile-json" id="json-{id}">{exportJSON(p)}</pre>
                {/if}
              </li>
            {/each}
          </ul>
        {/if}
      </div>
    </section>

    <!-- Editor -->
    <section class="editor" aria-labelledby="editor-title">
      <div class="spread editor-head">
        <div>
          <h2 id="editor-title" tabindex="-1">{editingName ? `Editing “${editingName}”` : "New profile"}</h2>
          <p class="secondary">
            {editingName
              ? "Save profile updates this profile. Changes stay local until you save."
              : "Save profile adds this as a new profile."}
          </p>
        </div>
        <div class="page-actions">
          {#if currentProfileId}
            <button
              type="button"
              class="btn-danger-quiet"
              onclick={() => (confirmDelete = { id: currentProfileId!, name: editingName ?? form.name })}
            >
              <Icon name="trash" size={15} /> Delete profile
            </button>
          {/if}
          <button type="button" class="btn-quiet" onclick={() => (confirmReset = true)}>
            <Icon icon={RotateCcw} size={15} /> Reset
          </button>
        </div>
      </div>

      <div class="split editor-split">
        <div class="editor-main">
          <section id="container" class="panel" aria-labelledby="container-title">
            <div class="panel-head">
              <div class="tile-head">
                <span class="tile"><Icon icon={Film} size={17} /></span>
                <div><h3 id="container-title">Output container</h3></div>
              </div>
            </div>
            <div class="panel-body">
              <div class="field">
                <Select
                  id="output-container"
                  label="Output container"
                  value={form.container}
                  options={OUTPUT_CONTAINERS}
                  describedby="container-note"
                  onchange={(value) => (form.container = value)}
                />
                <p id="container-note" class="note" aria-live="polite">
                  {containerProblem || (form.container === "auto" || form.container === "mkv"
                    ? "MKV keeps ASS subtitles and attached fonts."
                    : "Copied tracks must be compatible with this container. Choose MKV to keep ASS subtitles and attached fonts.")}
                </p>
              </div>
            </div>
          </section>

          <!-- Presets -->
          <section id="presets" class="panel" aria-labelledby="presets-title">
            <div class="panel-head">
              <div class="tile-head">
                <span class="tile"><Icon icon={Sparkles} size={17} /></span>
                <div>
                  <h3 id="presets-title">Start from a preset</h3>
                  <p>Replaces codec settings and stream tags in the editor.</p>
                </div>
              </div>
            </div>
            <div class="panel-body">
              <div class="presets">
                {#each QUICK_PRESETS as preset (preset.name)}
                  <button
                    type="button"
                    class="preset"
                    onclick={() => {
                      applyPreset(form, preset);
                      toast.show(`Applied preset: ${preset.name}`);
                    }}
                  >
                    <span class="preset-name">{preset.name}</span>
                    <span class="preset-desc">{preset.video_codec} · {preset.audio_codec}</span>
                  </button>
                {/each}
              </div>
            </div>
          </section>

          <!-- Identity -->
          <section id="identity" class="panel" aria-labelledby="identity-title">
            <div class="panel-head">
              <div class="tile-head">
                <span class="tile"><Icon icon={IdCard} size={17} /></span>
                <div><h3 id="identity-title">Identity</h3></div>
              </div>
            </div>
            <div class="panel-body">
              <div class="field">
                <label for="p-name">Profile name</label>
                <input id="p-name" type="text" placeholder="e.g. x265-1080p" bind:value={form.name} />
              </div>
            </div>
          </section>

          <!-- Video -->
          <section id="video" class="panel" aria-labelledby="video-title">
            <div class="panel-head">
              <div class="tile-head">
                <span class="tile"><Icon icon={Film} size={17} /></span>
                <div><h3 id="video-title">Video</h3></div>
              </div>
            </div>
            <div class="panel-body">
              <div class="form-row">
                <div class="field">
                  <label for="v-codec">Video codec</label>
                  <Select id="v-codec" value={form.vCodec} options={VIDEO_CODECS} onchange={(v) => applyVideoCodec(form, v)} />
                </div>
                {#if pixOptions.length}
                  <div class="field">
                    {@render field("v-pix_fmt", "Pixel format")}
                    <Select
                      id="v-pix_fmt"
                      value={form.pixFmt}
                      options={pixOptions}
                      describedby="v-pix_fmt-note"
                      onchange={(v) => (form.pixFmt = v)}
                    />
                    <p class="note" id="v-pix_fmt-note">10-bit prevents banding and is recommended for AV1 and HEVC.</p>
                  </div>
                {/if}
              </div>

              {#if form.vCodec === "libsvtav1"}
                <div class="field">
                  <label for="v-svt-variant">SVT-AV1 encoder</label>
                  <Select
                    id="v-svt-variant"
                    value={form.svtVariant}
                    options={[
                      { value: "standard", label: "SVT-AV1 (Standard)" },
                      { value: "5fish", label: "SVT-AV1 (5fish · Anime)", disabled: !data.has_5fish },
                    ]}
                    describedby={data.has_5fish ? undefined : "v-svt-variant-note"}
                    onchange={(v) => applySvtVariant(form, v)}
                  />
                  {#if !data.has_5fish}
                    <p class="note" id="v-svt-variant-note">5fish requires an updated Amaterasu base image.</p>
                  {/if}
                </div>
              {/if}

              {#if !isVideoCopy}
                <div class="field">
                  <div class="spread">
                    <label for="v-crf">CRF (quality)</label>
                    <span class="crf-value num" aria-hidden="true">{form.crf}</span>
                  </div>
                  <input
                    id="v-crf"
                    type="range"
                    min="0"
                    max="63"
                    bind:value={form.crf}
                    aria-describedby="v-crf-note"
                    aria-valuetext="{form.crf}: {crfHint(form.crf)}"
                  />
                  <p class="note" id="v-crf-note">
                    {crfHint(form.crf)}. Lower is higher quality and a larger file; 24–28 is typical for AV1 and HEVC.
                  </p>
                </div>
              {/if}

              {#if !isVideoCopy && hasPreset(form.vCodec)}
                <div class="field">
                  <label for="v-preset">Preset / speed</label>
                  <Select
                    id="v-preset"
                    value={form.preset}
                    options={presetOptions(form.vCodec)}
                    describedby="v-preset-note"
                    onchange={(v) => (form.preset = v)}
                  />
                  <p class="note" id="v-preset-note">Slower presets compress better and take longer to encode.</p>
                </div>
              {/if}

              {#if form.vCodec === "libsvtav1"}
                <div class="form-row">
                  <div class="field">
                    <label for="v-keyint">AV1 seek interval</label>
                    <Select
                      id="v-keyint"
                      value={form.keyint}
                      options={KEYINT_SECONDS}
                      describedby="v-keyint-note"
                      onchange={(v) => (form.keyint = v)}
                    />
                    <p class="note" id="v-keyint-note">Seconds between keyframes. Shorter seeks faster at a small size cost.</p>
                  </div>
                  <div class="field">
                    <span class="field-label">Decoder optimization</span>
                    <label class="switch-row">
                      <input type="checkbox" class="switch" bind:checked={form.fastDecode} />
                      <span>Fast-decode AV1 bitstream</span>
                    </label>
                    <p class="note">Reduces playback complexity with a small compression tradeoff.</p>
                  </div>
                </div>
              {/if}

              <div class="form-row">
                <div class="field">
                  <label for="v-profile">Format profile</label>
                  <Select
                    id="v-profile"
                    value={form.vProfile}
                    options={profileChoices(form.vCodec)}
                    onchange={(v) => {
                      form.vProfile = v;
                      alignPixelFormatForProfile(form);
                    }}
                  />
                </div>
                <div class="field">
                  <label for="v-level">Format level</label>
                  <Select id="v-level" value={form.level} options={LEVELS} onchange={(v) => (form.level = v)} />
                </div>
                <div class="field">
                  <label for="v-fps">Frame timing</label>
                  <Select id="v-fps" value={form.fpsMode} options={FPS_MODES} onchange={(v) => (form.fpsMode = v)} />
                </div>
              </div>

              <div class="form-row">
                <div class="field">
                  <label for="v-prim">Color primaries</label>
                  <Select id="v-prim" value={form.colorPrim} options={COLOR_PRIMARIES} onchange={(v) => (form.colorPrim = v)} />
                </div>
                <div class="field">
                  <label for="v-trc">Color transfer</label>
                  <Select id="v-trc" value={form.colorTrc} options={COLOR_TRC} onchange={(v) => (form.colorTrc = v)} />
                </div>
                <div class="field">
                  <label for="v-space">Colorspace</label>
                  <Select id="v-space" value={form.colorspace} options={COLORSPACES} onchange={(v) => (form.colorspace = v)} />
                </div>
              </div>

              <div class="field">
                <label for="v-extra">Extra encoder parameters</label>
                <input
                  id="v-extra"
                  type="text"
                  class="mono"
                  placeholder="e.g. tune=animation:film-grain=4"
                  aria-describedby="v-extra-note"
                  bind:value={form.extra}
                />
                <p class="note" id="v-extra-note">Colon-separated codec parameters (x264/x265/SVT-AV1 params).</p>
              </div>

              <hr class="divider" />
              {@render trackPicker("v", "Video tracks to keep")}
              <div class="tag-grid">
                <TagBuilder kind="meta" stream="v" streamLabel="Video" list={form.meta} />
                <TagBuilder kind="disp" stream="v" streamLabel="Video" list={form.disp} />
              </div>
            </div>
          </section>

          <!-- Audio -->
          <section id="audio" class="panel" aria-labelledby="audio-title">
            <div class="panel-head">
              <div class="tile-head">
                <span class="tile"><Icon icon={Music} size={17} /></span>
                <div><h3 id="audio-title">Audio</h3></div>
              </div>
            </div>
            <div class="panel-body">
              <div class="form-row">
                <div class="field">
                  <label for="a-codec">Audio codec</label>
                  <Select id="a-codec" value={form.aCodec} options={AUDIO_CODECS} onchange={(v) => (form.aCodec = v)} />
                </div>
                {#if form.aCodec !== "copy" && form.aCodec !== "flac"}
                  <div class="field">
                    <label for="a-bitrate">Bitrate</label>
                    <Select id="a-bitrate" value={form.aBitrate} options={AUDIO_BITRATES} onchange={(v) => (form.aBitrate = v)} />
                  </div>
                {/if}
                {#if form.aCodec !== "copy"}
                  <div class="field">
                    <label for="a-channels">Channels</label>
                    <Select id="a-channels" value={form.aChannels} options={AUDIO_CHANNELS} onchange={setChannels} />
                  </div>
                {/if}
              </div>
              {#if form.aCodec === "libopus"}
                <div class="field">
                  <label class="switch-row">
                    <input type="checkbox" class="switch" bind:checked={form.aVbr} aria-describedby="a-vbr-note" />
                    <span>Variable bitrate (VBR)</span>
                  </label>
                  <p class="note" id="a-vbr-note">Spends bits where the audio is complex.</p>
                </div>
              {/if}

              <hr class="divider" />
              {@render trackPicker("a", "Audio tracks to keep")}
              <div class="tag-grid">
                <TagBuilder kind="meta" stream="a" streamLabel="Audio" list={form.meta} />
                <TagBuilder kind="disp" stream="a" streamLabel="Audio" list={form.disp} />
              </div>
            </div>
          </section>

          <!-- Subtitles -->
          <section id="subtitles" class="panel" aria-labelledby="subtitles-title">
            <div class="panel-head">
              <div class="tile-head">
                <span class="tile"><Icon icon={Captions} size={17} /></span>
                <div><h3 id="subtitles-title">Subtitles</h3></div>
              </div>
            </div>
            <div class="panel-body">
              <div class="form-row">
                <div class="field">
                  <label for="s-mode">Subtitle mode</label>
                  <Select id="s-mode" value={form.sMode} options={SUBTITLE_MODES} onchange={(v) => (form.sMode = v)} />
                </div>
                {@render trackPicker("s", "Subtitle tracks to keep")}
              </div>
              <div class="tag-grid">
                <TagBuilder kind="meta" stream="s" streamLabel="Subtitle" list={form.meta} />
                <TagBuilder kind="disp" stream="s" streamLabel="Subtitle" list={form.disp} />
              </div>
            </div>
          </section>

          <!-- Output -->
          <section id="output" class="panel" aria-labelledby="output-title">
            <div class="panel-head">
              <div class="tile-head">
                <span class="tile"><Icon icon={Tag} size={17} /></span>
                <div><h3 id="output-title">Output and metadata</h3></div>
              </div>
            </div>
            <div class="panel-body">
              <div class="field">
                <label for="g-rename">Rename file to</label>
                <input id="g-rename" type="text" class="mono" placeholder="e.g. {'{title}'} - {'{episode}'}.mkv" bind:value={form.rename} />
                {@render tokens("rename", RENAME_TOKENS)}
              </div>
              <div class="field">
                <label for="g-title">Global title</label>
                <input id="g-title" type="text" placeholder="e.g. {'{basename}'}" bind:value={form.title} />
                {@render tokens("title", TITLE_TOKENS)}
              </div>
              <div class="field">
                <label for="g-cover">Cover image URL</label>
                <input
                  id="g-cover"
                  type="text"
                  placeholder="e.g. https://t.me/channel/123 or https://example.com/poster.jpg"
                  aria-describedby="g-cover-note"
                  bind:value={form.cover}
                />
                <p class="note" id="g-cover-note">A direct image URL or a Telegram post link, attached as the cover.</p>
              </div>
            </div>
          </section>
        </div>

        <aside class="card preview" aria-label="Profile preview">
          <div class="preview-head">
            <div class="segmented" role="tablist" aria-label="Preview format">
              <button type="button" role="tab" aria-selected={mode === "json"} aria-controls="preview-code" onclick={() => (mode = "json")}>
                JSON
              </button>
              <button type="button" role="tab" aria-selected={mode === "ffmpeg"} aria-controls="preview-code" onclick={() => (mode = "ffmpeg")}>
                FFmpeg command
              </button>
            </div>
            <CopyButton
              value={previewText}
              label={mode === "json" ? "Copy profile JSON" : "Copy FFmpeg command"}
              confirm="Copied to clipboard"
              variant="quiet"
              iconOnly
            />
          </div>
          <div class="preview-panel" id="preview-code" role="tabpanel" tabindex="0" aria-label={mode === "json" ? "Profile JSON" : "FFmpeg command"}>
            <pre class="code preview-code">{previewText}</pre>
          </div>
          <p class="note preview-note">
            {mode === "json" ? "The profile as it is saved." : "Approximate command for input.mkv; the bot adds its own input and output."}
          </p>
        </aside>
      </div>
    </section>
  </div>
</Shell>

{#if confirmDelete}
  <Modal
    title="Delete “{confirmDelete.name}”?"
    description="The profile is removed for good. Encodes already running are not affected."
    tone="danger"
    onclose={() => (confirmDelete = null)}
  >
    <div class="dialog-actions">
      <button type="button" class="btn-quiet" onclick={() => (confirmDelete = null)}>Keep profile</button>
      <button type="button" class="btn-danger" onclick={doDelete} disabled={deleting}>
        {deleting ? "Deleting…" : "Delete profile"}
      </button>
    </div>
  </Modal>
{/if}

{#if confirmReset}
  <Modal
    title="Reset the editor?"
    description="Every field returns to its default and the editor starts a new profile. Saved profiles are not changed."
    onclose={() => (confirmReset = false)}
  >
    <div class="dialog-actions">
      <button type="button" class="btn-quiet" onclick={() => (confirmReset = false)}>Cancel</button>
      <button type="button" class="btn-primary" onclick={doReset}>Reset editor</button>
    </div>
  </Modal>
{/if}

{#if importOpen}
  <Modal
    title="Import profile JSON"
    description="Paste a profile copied from this page or the bot. It opens in the editor as a new profile."
    wide
    onclose={() => (importOpen = false)}
  >
    <form class="stack" onsubmit={doImport}>
      <div class="field">
        <label for="import-json">Profile JSON</label>
        <textarea
          id="import-json"
          class="mono import-text"
          spellcheck="false"
          bind:value={importText}
          aria-invalid={importError ? "true" : undefined}
          aria-describedby={importError ? "import-error" : undefined}
        ></textarea>
      </div>
      {#if importError}
        <div id="import-error"><Feedback tone="danger" announcement="alert">{importError}</Feedback></div>
      {/if}
      <div class="dialog-actions">
        <button type="button" class="btn-quiet" onclick={() => (importOpen = false)}>Cancel</button>
        <button type="submit" class="btn-primary" disabled={!importText.trim()}>Import</button>
      </div>
    </form>
  </Modal>
{/if}

<style>
  section[id],
  .editor :global(h2) {
    scroll-margin-top: calc(var(--topbar-height) + var(--space-4));
  }

  .panel {
    container-type: inline-size;
  }

  /* Fields in a row keep label, control and note stacked from the top. */
  .panel-body :global(.field) {
    align-content: start;
  }

  .tile-head h2 {
    font-size: var(--text-section);
  }

  .row-skeleton {
    height: 3.75rem;
    border-radius: var(--radius);
  }

  .profile-row {
    display: grid;
  }

  .row-title {
    display: inline-flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2);
  }

  .profile-meta {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1) var(--space-3);
    margin-top: 2px;
  }

  .profile-meta > span {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
  }

  .profile-row .row-actions {
    flex-wrap: wrap;
    justify-content: flex-end;
  }

  .profile-json {
    margin: 0 var(--space-3) var(--space-3);
    max-height: 22rem;
    overflow: auto;
  }

  .editor {
    display: grid;
    gap: var(--space-5);
  }

  .editor-head h2 {
    font-size: var(--text-title);
    font-weight: 500;
  }

  .editor-head p {
    margin-top: var(--space-1);
  }

  .editor-main {
    display: grid;
    gap: var(--space-5);
    min-width: 0;
  }

  .editor-split {
    grid-template-columns: minmax(0, 1fr) minmax(20rem, 28rem);
  }

  .presets {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(100%, 12rem), 1fr));
    gap: var(--space-2);
  }

  .preset {
    display: grid;
    justify-content: stretch;
    justify-items: start;
    align-content: center;
    gap: 2px;
    min-height: 3.75rem;
    padding: var(--space-2) var(--space-4);
    text-align: left;
  }

  .preset-name {
    font-weight: 560;
    color: var(--text);
  }

  .preset-desc {
    font-size: var(--text-xs);
    font-weight: 500;
    color: var(--text-muted);
  }

  .crf-value {
    font-size: var(--text-section);
    font-weight: 560;
    color: var(--text);
  }

  input[type="range"] {
    width: 100%;
    min-height: var(--control-height);
    margin: 0;
    cursor: pointer;
  }

  .switch-row {
    display: inline-flex;
    align-items: center;
    gap: var(--space-3);
    min-height: var(--control-height);
    font-weight: 520;
    cursor: pointer;
  }

  .mono {
    font-family: var(--font-mono);
    font-size: var(--text-small);
  }

  .tag-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 22rem), 1fr));
    gap: var(--space-5);
  }

  .tokens {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
  }

  .token {
    min-height: 2rem;
    padding: 0 var(--space-2);
    border-radius: var(--radius-xs);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 500;
    color: var(--text-secondary);
    box-shadow: none;
  }

  .preview {
    position: sticky;
    top: calc(var(--topbar-height) + var(--space-4));
    display: grid;
    gap: var(--space-3);
    padding: var(--space-4);
    max-height: calc(100svh - var(--topbar-height) - var(--space-8));
    grid-template-rows: auto minmax(0, 1fr) auto;
  }

  .preview-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
  }

  .preview-panel {
    display: grid;
    min-height: 0;
  }

  .preview-code {
    min-height: 16rem;
    overflow: auto;
    font-size: var(--text-xs);
  }

  .import-text {
    min-height: 14rem;
  }

  @media (max-width: 64rem) {
    .editor-split {
      grid-template-columns: minmax(0, 1fr);
    }
    .preview {
      position: static;
      max-height: none;
    }
    .preview-code {
      max-height: 28rem;
    }
  }

  @media (max-width: 40rem) {
    /* Phones: icon actions on one line, Edit as a full-width button below. */
    .profile-row .row-actions {
      flex-wrap: wrap;
      justify-content: flex-start;
    }
    .edit-btn {
      flex: 1 1 100%;
      white-space: nowrap;
    }
    .page-actions > * {
      flex: 1 1 auto;
    }
  }
</style>
