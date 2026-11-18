<script lang="ts">
  import { onMount } from "svelte";
  import Shell, { type NavGroup } from "../../ui/Shell.svelte";
  import Icon from "../../ui/Icon.svelte";
  import Feedback from "../../ui/Feedback.svelte";
  import HardDrive from "@lucide/svelte/icons/hard-drive";
  import FileType from "@lucide/svelte/icons/file-type";
  import ListVideo from "@lucide/svelte/icons/list-video";
  import AudioLines from "@lucide/svelte/icons/audio-lines";
  import FileDown from "@lucide/svelte/icons/file-down";
  import Download from "@lucide/svelte/icons/download";
  import Shield from "@lucide/svelte/icons/shield";
  import MonitorPlay from "@lucide/svelte/icons/monitor-play";
  import { installLucideShim, createIcons } from "./lucide-shim";
  import { loadScript } from "./load-script";
  // The vanilla runtime stays at its tested paths (tests/player_runtime.test.cjs,
  // tests/test_filetolink_streaming.py); Vite emits them as content-hashed
  // assets so every deploy busts the cache.
  import libmediaPlayerUrl from "../../../../static/js/libmedia-player.js?url";
  import playerControllerUrl from "../../../../static/js/player.js?url";

  interface Subtitle {
    url: string;
    label: string;
    srclang: string;
  }
  interface PlaylistContext {
    name: string;
    index: number;
    total: number;
    url: string;
    previous_url: string;
    next_url: string;
  }
  interface PlayerData {
    file_name: string;
    file_url: string;
    absolute_file_url: string;
    download_url: string;
    absolute_download_url: string;
    doc_preview_url: string;
    file_size: string;
    file_type: string;
    file_extension: string;
    mime_type: string;
    subtitles: Subtitle[];
    poster_url: string;
    tracks_url: string;
    playlist: PlaylistContext | null;
  }

  let { data }: { data: PlayerData } = $props();

  // Server data does not change after render; read it once.
  const d = (() => data)();
  const type = d.file_type || "unknown";
  const playlist = d.playlist;
  const subtitles = Array.isArray(d.subtitles) ? d.subtitles : [];
  const downloadHref = d.absolute_download_url || d.download_url || d.file_url;
  const typeLabel = type === "unknown" ? (d.file_extension || "file").toUpperCase() : type;

  const nav: NavGroup[] = [
    {
      label: "Stream",
      items: [
        { label: type === "video" ? "Player" : "Preview", href: "#stream", glyph: MonitorPlay, current: true },
        { label: "Details", href: "#details", icon: "list" },
        ...(playlist ? [{ label: playlist.name, href: playlist.url, glyph: ListVideo }] : []),
      ],
    },
  ];

  let runtimeError = $state("");

  onMount(() => {
    // Configuration the controller reads (formerly an inline <script>).
    (window as unknown as { AMATERASU_PLAYER: object }).AMATERASU_PLAYER = {
      fileUrl: d.file_url,
      absoluteFileUrl: d.absolute_file_url,
      downloadUrl: d.download_url,
      absoluteDownloadUrl: d.absolute_download_url,
      fileType: d.file_type,
      fileName: d.file_name,
      fileSize: d.file_size,
      mimeType: d.mime_type,
      subtitles,
      posterUrl: d.poster_url,
      tracksUrl: d.tracks_url,
      playlist,
    };
    installLucideShim();
    createIcons();
    loadScript(libmediaPlayerUrl)
      .then(() => loadScript(playerControllerUrl))
      .catch(() => {
        runtimeError =
          "The player controls could not load. Use Download below, or reload the page.";
      });
  });
</script>

<Shell
  place={d.file_name || "Stream"}
  crumbs={playlist ? [playlist.name] : ["Stream"]}
  {nav}
  note="Streams are served through signed, expiring links."
>
  <div class="watch">
    <section id="stream" class="stage card" aria-label={type === "video" ? "Video player" : "File preview"}>
      <div class="stream-player stream-player--{type}">
        {#if type === "video"}
          <div class="am-player is-paused" id="am-player" data-player-shell data-scheme="dark">
            <video id="player" playsinline controls preload="metadata" poster={d.poster_url || undefined}>
              <source src={d.file_url} type={d.mime_type} />
              {#each subtitles as sub (sub.url)}
                <track kind="subtitles" src={sub.url} label={sub.label} srclang={sub.srclang} />
              {/each}
            </video>
            <div class="am-subtitle-overlay" id="subtitle-overlay" aria-live="off" hidden>
              <span id="subtitle-text" dir="auto"></span>
            </div>

            <div class="am-topbar">
              <button class="am-btn" id="help-btn" type="button" aria-label="Show keyboard shortcuts" title="Keyboard shortcuts">
                <i data-lucide="circle-help"></i>
              </button>
            </div>

            <div class="am-overlay" id="tap-layer" aria-hidden="true"></div>
            <div class="am-toast-stack" id="player-toasts" aria-live="polite" aria-atomic="false"></div>
            <div class="am-seek-indicator" id="seek-indicator">+10s</div>
            <div class="am-gesture-indicator" id="gesture-left" data-side="left" aria-hidden="true">
              <i data-lucide="sun"></i>
              <div class="am-gesture-track"><div class="am-gesture-fill"></div></div>
            </div>
            <div class="am-gesture-indicator" id="gesture-right" data-side="right" aria-hidden="true">
              <i data-lucide="volume-2"></i>
              <div class="am-gesture-track"><div class="am-gesture-fill"></div></div>
            </div>

            <div class="am-stats" id="stats-panel" hidden></div>

            <div class="am-error-card" id="error-card" role="alert" hidden>
              <h2>Playback failed</h2>
              <p id="error-message">The browser could not load this stream.</p>
              <div class="am-error-actions">
                <button type="button" class="btn-primary" id="retry-btn" aria-label="Retry playback">Retry</button>
                <a class="btn" id="error-download" href={downloadHref}>Download instead</a>
              </div>
            </div>

            <div class="am-panel" id="audio-panel" hidden>
              <button class="am-panel-close" type="button" data-panel-close aria-label="Close audio tracks"><i data-lucide="x"></i></button>
              <h2>Audio tracks</h2>
              <div class="am-track-list" id="audio-track-list"></div>
            </div>

            <div class="am-panel" id="subtitle-panel" hidden>
              <button class="am-panel-close" type="button" data-panel-close aria-label="Close subtitles"><i data-lucide="x"></i></button>
              <h2>Subtitles</h2>
              <p class="am-track-status" id="subtitle-status" role="status"></p>
              <div class="am-track-list" id="subtitle-track-list"></div>
              <div id="subtitle-compatibility" hidden>
                <label class="am-track-option">
                  <input id="subtitle-plain-text" type="checkbox" aria-describedby="subtitle-plain-text-help" />
                  <span>Use plain text subtitles</span>
                </label>
                <p class="am-track-status" id="subtitle-plain-text-help">
                  Try this if styled subtitles disappear after seeking. Styling is removed; the first load may take longer.
                </p>
              </div>
              <div class="am-panel-row">
                <label for="subtitle-delay">Subtitle timing</label>
                <output id="subtitle-delay-value" for="subtitle-delay">0.00s</output>
              </div>
              <input id="subtitle-delay" class="am-subtitle-delay" type="range" min="-5" max="5" step="0.25" value="0" aria-label="Subtitle delay in seconds" />
              <p class="am-track-status">Negative: earlier. Positive: later.</p>
            </div>

            <div class="am-panel" id="settings-panel" hidden>
              <button class="am-panel-close" type="button" data-panel-close aria-label="Close settings"><i data-lucide="x"></i></button>
              <h2>Settings</h2>
              <h3>Playback speed</h3>
              <div class="am-speed-grid" id="speed-grid"></div>
              <div class="am-panel-row">
                <span>Source resolution</span>
                <strong id="info-resolution">Unknown</strong>
              </div>
              <div class="am-panel-row">
                <span>MIME type</span>
                <strong id="info-mime">{d.mime_type}</strong>
              </div>
              <div class="am-panel-row">
                <span>File size</span>
                <strong id="info-size">{d.file_size}</strong>
              </div>
              <div class="am-panel-row">
                <span>Picture in Picture</span>
                <button class="am-toggle" id="pip-btn" type="button" aria-label="Toggle Picture in Picture">Open</button>
              </div>
              <div class="am-panel-row">
                <span>Loop</span>
                <button class="am-toggle" id="loop-btn" type="button" aria-label="Toggle loop" aria-pressed="false">Off</button>
              </div>
              <div class="am-panel-row">
                <span>Autoplay next</span>
                <button class="am-toggle" id="autoplay-next-btn" type="button" aria-label="Autoplay next instructions">Setup</button>
              </div>
            </div>

            <div class="am-controls" id="controls">
              <div class="am-control-surface">
                <div class="am-progress-wrap">
                  <span class="am-time" id="current-time">0:00</span>
                  <div class="am-progress" id="progress" role="slider" aria-label="Playback progress" aria-valuemin="0" aria-valuemax="0" aria-valuenow="0" tabindex="0">
                    <div class="am-progress-buffer" id="buffered-bar"></div>
                    <div class="am-progress-fill" id="progress-fill"></div>
                    <div class="am-progress-thumb" id="progress-thumb"></div>
                    <div class="am-tooltip" id="progress-tooltip">0:00</div>
                  </div>
                  <span class="am-time" id="duration-time">0:00</span>
                </div>
                <div class="am-control-row">
                  <div class="am-transport-controls">
                    <button class="am-btn am-seek-btn" id="backward-btn" type="button" aria-label="Seek backward 10 seconds" title="Back 10 seconds">−10</button>
                    <button class="am-btn am-play-btn" id="play-btn" type="button" aria-label="Play" title="Play or pause">
                      <i data-lucide="play"></i>
                    </button>
                    <button class="am-btn am-seek-btn" id="forward-btn" type="button" aria-label="Seek forward 10 seconds" title="Forward 10 seconds">+10</button>
                    <a class="am-btn" id="playlist-prev-btn" href={playlist?.previous_url || "#"} aria-label="Previous playlist item" title="Previous episode" hidden={!playlist?.previous_url}>
                      <i data-lucide="skip-back"></i>
                    </a>
                    <a class="am-btn" id="playlist-next-btn" href={playlist?.next_url || "#"} aria-label="Next playlist item" title="Next episode" hidden={!playlist?.next_url}>
                      <i data-lucide="skip-forward"></i>
                    </a>
                  </div>
                  <div class="am-player-tools">
                    <button class="am-btn am-extra-desktop" id="mute-btn" type="button" aria-label="Mute" title="Volume">
                      <i data-lucide="volume-2"></i>
                    </button>
                    <button class="am-btn" id="audio-btn" type="button" aria-label="Audio tracks" aria-controls="audio-panel" aria-expanded="false" title="Audio tracks" hidden>
                      <i data-lucide="languages"></i>
                    </button>
                    <button class="am-btn" id="subtitle-btn" type="button" aria-label="Subtitle tracks" aria-controls="subtitle-panel" aria-expanded="false" title="Subtitles" hidden>
                      <i data-lucide="captions"></i>
                    </button>
                    <button class="am-btn" id="settings-btn" type="button" aria-label="Settings" aria-controls="settings-panel" aria-expanded="false" title="Playback settings">
                      <i data-lucide="settings"></i>
                    </button>
                    <button class="am-btn am-extra-desktop" id="theater-btn" type="button" aria-label="Toggle theater mode" title="Theater mode">
                      <i data-lucide="rectangle-horizontal"></i>
                    </button>
                    <button class="am-btn" id="fullscreen-btn" type="button" aria-label="Fullscreen" title="Fullscreen">
                      <i data-lucide="maximize"></i>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        {:else if type === "audio"}
          <div class="stream-audio-panel">
            <span class="tile tile-lg"><Icon icon={AudioLines} size={22} /></span>
            <audio id="player" controls preload="metadata">
              <source src={d.file_url} type={d.mime_type} />
            </audio>
          </div>
        {:else if type === "image"}
          <a class="stream-image-preview" href={d.file_url} target="_blank" rel="noopener">
            <img src={d.file_url} alt={d.file_name} loading="lazy" />
          </a>
        {:else if type === "pdf"}
          <iframe class="stream-doc-frame" src={d.file_url} title={d.file_name}></iframe>
        {:else if type === "text"}
          <iframe class="stream-doc-frame" src={d.file_url} title={d.file_name} sandbox=""></iframe>
        {:else if type === "doc"}
          <iframe class="stream-doc-frame" src={d.doc_preview_url} title={d.file_name}></iframe>
        {:else}
          <div class="stream-generic-preview">
            <span class="empty-mark"><Icon icon={FileDown} size={24} /></span>
            <h2>{(d.file_extension || "file").toUpperCase()} file</h2>
            <p class="note">{d.mime_type}</p>
          </div>
        {/if}
      </div>
    </section>

    {#if type !== "video"}
      <!-- Copy confirmations from the controller land here. -->
      <div class="am-toast-stack am-toast-stack--page" id="player-toasts" aria-live="polite" aria-atomic="false"></div>
    {/if}

    {#if runtimeError}<Feedback tone="danger" announcement="alert">{runtimeError}</Feedback>{/if}

    <div class="split details-grid">
      <section id="details" class="card panel-body details" aria-labelledby="file-title">
        <div class="title-block">
          <h1 id="file-title" tabindex="-1">{d.file_name}</h1>
          <div class="cluster">
            <span class="pill"><Icon icon={HardDrive} size={13} /> <span class="num">{d.file_size}</span></span>
            <span class="pill"><Icon icon={FileType} size={13} /> {typeLabel}</span>
            <span class="pill">{d.mime_type}</span>
          </div>
        </div>

        {#if playlist}
          <a class="inset row playlist-row" href={playlist.url}>
            <span class="tile tile-sm"><Icon icon={ListVideo} size={15} /></span>
            <span class="row-main">
              <span class="row-title">{playlist.name}</span>
              <span class="row-meta">Playlist</span>
            </span>
            <span class="pill num">{playlist.index} of {playlist.total}</span>
          </a>
        {/if}

        <div class="open-with">
          <h2 class="panel-title">Open with</h2>
          <div class="stream-actions" id="action-buttons"></div>
        </div>
      </section>

      <aside class="card panel-body rim download-card" aria-label="Download">
        <div class="tile-head">
          <span class="tile"><Icon icon={Download} size={17} /></span>
          <div>
            <h2>Download</h2>
            <p>Save the original file.</p>
          </div>
        </div>
        <a class="btn btn-primary download-btn" id="main-download-btn" href={downloadHref} aria-label="Download file">
          <Icon icon={Download} size={16} /> Download file
        </a>
        <p class="note security"><Icon icon={Shield} size={13} /> Protected by Amaterasu token authentication.</p>
      </aside>
    </div>
  </div>
</Shell>

<!-- Keyboard shortcuts (opened by the controller's help button). -->
<div class="am-modal scrim" id="help-modal" hidden>
  <div class="am-modal-card dialog" role="dialog" aria-modal="true" aria-labelledby="help-title">
    <div class="dialog-head">
      <h2 id="help-title">Keyboard shortcuts</h2>
      <button class="btn-quiet btn-icon" id="help-close-btn" type="button" aria-label="Close keyboard shortcuts">
        <i data-lucide="x"></i>
      </button>
    </div>
    <div class="dialog-body am-shortcut-grid">
      <div class="inset am-shortcut"><span>Play or pause</span><kbd>Space / K</kbd></div>
      <div class="inset am-shortcut"><span>Seek backward</span><kbd>Left</kbd></div>
      <div class="inset am-shortcut"><span>Seek forward</span><kbd>Right</kbd></div>
      <div class="inset am-shortcut"><span>Volume up</span><kbd>Up</kbd></div>
      <div class="inset am-shortcut"><span>Volume down</span><kbd>Down</kbd></div>
      <div class="inset am-shortcut"><span>Mute</span><kbd>M</kbd></div>
      <div class="inset am-shortcut"><span>Fullscreen</span><kbd>F</kbd></div>
      <div class="inset am-shortcut"><span>Debug stats</span><kbd>Ctrl Shift D</kbd></div>
    </div>
  </div>
</div>

<style>
  /* ── Page layout ─────────────────────────────────────────────── */
  .watch {
    display: grid;
    gap: var(--space-5);
    max-width: 78rem;
    margin: 0 auto;
  }

  .stage {
    padding: 0;
    overflow: hidden;
  }

  .details-grid {
    grid-template-columns: minmax(0, 1fr) minmax(16rem, 20rem);
  }

  @media (max-width: 64rem) {
    .details-grid {
      grid-template-columns: minmax(0, 1fr);
    }
  }

  .title-block {
    display: grid;
    gap: var(--space-3);
  }

  .title-block h1 {
    font-size: clamp(1.375rem, 1.1rem + 0.9vw, 1.875rem);
    font-weight: 500;
    letter-spacing: -0.028em;
    overflow-wrap: anywhere;
  }

  .playlist-row {
    color: inherit;
    text-decoration: none;
  }

  .open-with {
    display: grid;
    gap: var(--space-3);
  }

  .download-card {
    align-content: start;
  }

  .download-btn {
    width: 100%;
  }

  .security {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  /* ── Stage ───────────────────────────────────────────────────── */
  .stream-player {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    background: var(--surface-sunken);
  }

  .stream-player--video {
    /* The video stage is pure black in both themes; it is content, not chrome. */
    --stage: oklch(0 0 0);
    aspect-ratio: 16 / 9;
    min-height: 13.75rem;
    max-height: calc(100svh - 10rem);
    background: var(--stage);
  }

  .stream-player--audio {
    padding: var(--space-8) var(--space-6);
  }

  .stream-audio-panel {
    width: min(100%, 45rem);
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    align-items: center;
    gap: var(--space-5);
  }

  .stream-audio-panel audio {
    width: 100%;
  }

  /* A transparency checkerboard: the canvas an image sits on. */
  .stream-image-preview {
    width: 100%;
    display: flex;
    justify-content: center;
    background:
      conic-gradient(var(--hover) 25%, transparent 0 50%, var(--hover) 0 75%, transparent 0)
        0 0 / 1.5rem 1.5rem,
      var(--surface-sunken);
  }

  .stream-image-preview img {
    max-width: 100%;
    max-height: min(78vh, 54rem);
    width: auto;
    height: auto;
    object-fit: contain;
  }

  .stream-doc-frame {
    width: 100%;
    height: min(75vh, 47.5rem);
    min-height: 26rem;
    border: 0;
    background: var(--surface-float);
  }

  .stream-generic-preview {
    width: 100%;
    min-height: 20rem;
    display: grid;
    justify-items: center;
    align-content: center;
    gap: var(--space-2);
    padding: var(--space-8);
    text-align: center;
  }

  .stream-generic-preview h2 {
    font-size: var(--text-section);
    font-weight: 540;
  }

  .empty-mark {
    width: 3.5rem;
    height: 3.5rem;
    display: grid;
    place-items: center;
    border-radius: 1rem;
    background: var(--tile-fill);
    color: var(--tile-ink);
    box-shadow:
      inset 0 1px 0 oklch(1 0 0 / 0.28),
      0 8px 20px -8px var(--glow-accent);
    margin-bottom: var(--space-2);
  }

  /* ── Open-with actions (built by the controller) ─────────────── */
  .stream-actions {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(100%, 14rem), 1fr));
    gap: var(--space-2);
  }

  .stream-actions :global(.action-card) {
    display: flex;
    align-items: center;
    justify-content: flex-start;
    gap: var(--space-3);
    min-height: 3.5rem;
    padding: var(--space-2) var(--space-3);
    border: var(--border-width) solid transparent;
    border-radius: var(--radius);
    background:
      linear-gradient(var(--veil), var(--veil)) padding-box,
      var(--inset-fill) padding-box,
      var(--inset-edge) border-box;
    box-shadow: none;
    color: var(--text);
    text-align: left;
    text-decoration: none;
    font-weight: 500;
    transition:
      --veil 160ms var(--ease-out),
      transform 240ms var(--ease-spring);
  }

  .stream-actions :global(.action-card:hover) {
    --veil: var(--hover-veil);
    color: var(--text);
  }

  .stream-actions :global(.action-card:active) {
    transform: scale(0.98);
    transition-duration: 80ms;
  }

  .stream-actions :global(.action-icon) {
    display: inline-grid;
    place-items: center;
    flex-shrink: 0;
    width: 2rem;
    height: 2rem;
    border-radius: 0.6rem;
    background: var(--tile-fill);
    color: var(--tile-ink);
    box-shadow:
      inset 0 1px 0 oklch(1 0 0 / 0.28),
      inset 0 -1px 0 oklch(0 0 0 / 0.12);
  }

  .stream-actions :global(.action-icon svg) {
    width: 1rem;
    height: 1rem;
  }

  .stream-actions :global(.action-card > div:last-child) {
    display: grid;
    min-width: 0;
    line-height: 1.3;
  }

  .stream-actions :global(.action-text) {
    font-size: var(--text-small);
    font-weight: 560;
    color: var(--text);
  }

  .stream-actions :global(.action-desc) {
    font-size: var(--text-xs);
    font-weight: 450;
    color: var(--text-muted);
    overflow-wrap: anywhere;
  }

  /* ── Player shell (markup above, state classes from player.js) ── */
  .am-player {
    position: relative;
    width: 100%;
    height: 100%;
    background: var(--stage);
    color: var(--text);
    touch-action: manipulation;
  }

  .am-player:fullscreen {
    width: 100vw;
    height: 100vh;
  }

  .am-player :global(video),
  .am-player :global(amaterasu-libmedia-player) {
    display: block;
    width: 100%;
    height: 100%;
    object-fit: contain;
    background: var(--stage);
  }

  .am-player :global([hidden]) {
    display: none !important;
  }

  .am-overlay {
    position: absolute;
    inset: 0;
    z-index: 2;
    cursor: pointer;
  }

  .am-player:not(:global(.is-ready)) .am-overlay,
  .am-player:not(:global(.is-ready)) .am-controls,
  .am-player:not(:global(.is-ready)) .am-toast-stack,
  .am-player:not(:global(.is-ready)) .am-seek-indicator,
  .am-player:not(:global(.is-ready)) .am-gesture-indicator {
    display: none;
  }

  .am-topbar,
  .am-controls {
    position: absolute;
    left: 0;
    right: 0;
    z-index: 4;
    transition: opacity 350ms var(--ease-out);
  }

  .am-player:global(.is-idle):not(:global(.is-paused)) .am-controls,
  .am-player:global(.is-idle):not(:global(.is-paused)) .am-topbar {
    opacity: 0;
    pointer-events: none;
  }

  .am-player:global(.is-idle):not(:global(.is-paused)) {
    cursor: none;
  }

  .am-player:global(.is-paused) .am-controls,
  .am-player:global(.is-paused) .am-topbar,
  .am-player:focus-within .am-controls,
  .am-player:focus-within .am-topbar {
    opacity: 1;
    pointer-events: auto;
  }

  .am-topbar {
    top: 0;
    display: flex;
    justify-content: flex-end;
    padding: clamp(0.75rem, 2vw, 1.25rem);
    background: linear-gradient(to bottom, color-mix(in oklch, var(--stage) 70%, transparent), transparent);
  }

  .am-controls {
    bottom: 0;
    padding: clamp(0.75rem, 2.4vw, 1.5rem);
    background: linear-gradient(
      to top,
      color-mix(in oklch, var(--stage) 90%, transparent) 0%,
      color-mix(in oklch, var(--stage) 50%, transparent) 58%,
      transparent 100%
    );
  }

  /* The control bar is the Trestle panel material, floated over the picture. */
  .am-control-surface {
    display: grid;
    gap: var(--space-2);
    padding: var(--space-3) var(--space-4) var(--space-2);
    border: var(--border-width) solid transparent;
    border-radius: var(--radius-lg);
    background:
      linear-gradient(
          160deg,
          color-mix(in oklch, var(--surface-float) 88%, transparent),
          color-mix(in oklch, var(--surface-raised) 80%, transparent)
        )
        padding-box,
      var(--card-edge) border-box;
    backdrop-filter: blur(20px) saturate(120%);
    -webkit-backdrop-filter: blur(20px) saturate(120%);
    box-shadow: var(--shadow-float);
  }

  .am-control-row,
  .am-transport-controls,
  .am-player-tools {
    display: flex;
    align-items: center;
  }

  .am-control-row {
    justify-content: space-between;
    gap: var(--space-3);
  }

  .am-transport-controls,
  .am-player-tools {
    gap: var(--space-1);
  }

  /* Round icon buttons; override the global button material. */
  .am-player .am-btn {
    width: 2.5rem;
    height: 2.5rem;
    min-height: 0;
    padding: 0;
    flex: 0 0 auto;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border: var(--border-width) solid transparent;
    border-radius: 50%;
    background: transparent;
    box-shadow: none;
    color: var(--text-secondary);
    text-decoration: none;
    transition:
      color var(--transition-fast),
      background-color var(--transition-fast),
      transform 240ms var(--ease-spring);
  }

  .am-player .am-btn:hover,
  .am-player .am-btn:focus-visible {
    background: var(--hover);
    color: var(--text);
  }

  .am-player .am-btn:active {
    transform: scale(0.92);
    transition-duration: 80ms;
  }

  .am-player .am-btn :global(svg) {
    width: 1.2rem;
    height: 1.2rem;
  }

  .am-player .am-play-btn {
    width: 2.875rem;
    height: 2.875rem;
    margin-inline: 2px;
    background: var(--primary-fill);
    color: var(--button-text);
    box-shadow:
      inset 0 1px 0 oklch(1 0 0 / 0.35),
      0 6px 18px -6px var(--glow-accent);
  }

  .am-player .am-play-btn:hover,
  .am-player .am-play-btn:focus-visible {
    background: var(--primary-fill);
    color: var(--button-text);
    filter: brightness(1.06);
  }

  .am-player .am-play-btn :global(svg) {
    fill: currentColor;
  }

  .am-player .am-seek-btn {
    width: 2.625rem;
    border-radius: var(--radius-sm);
    font-size: var(--text-xs);
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }

  .am-progress-wrap {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    min-width: 0;
    padding: 0 2px;
  }

  .am-time {
    min-width: 2.75rem;
    font-size: var(--text-xs);
    font-variant-numeric: tabular-nums;
    color: var(--text-muted);
    text-align: center;
  }

  .am-progress {
    position: relative;
    flex: 1;
    min-width: 0;
    height: 4px;
    border-radius: var(--radius-full);
    background: var(--line-strong);
    cursor: pointer;
    outline: none;
    transition: height var(--transition-fast);
  }

  .am-progress:hover,
  .am-progress:focus-visible {
    height: 6px;
  }

  .am-progress:focus-visible {
    box-shadow: 0 0 0 3px var(--accent-soft);
  }

  .am-progress-buffer,
  .am-progress-fill {
    position: absolute;
    inset: 0 auto 0 0;
    width: 0%;
    border-radius: inherit;
    pointer-events: none;
  }

  .am-progress-buffer {
    background: var(--border);
    opacity: 0.6;
  }

  .am-progress-fill {
    background: var(--accent);
    box-shadow: 0 0 10px var(--glow-accent);
  }

  .am-progress-thumb {
    position: absolute;
    top: 50%;
    left: 0%;
    width: 0.75rem;
    height: 0.75rem;
    border-radius: 50%;
    background: var(--accent);
    box-shadow: 0 0 0 4px var(--accent-soft);
    transform: translate(-50%, -50%);
    pointer-events: none;
  }

  .am-tooltip {
    position: absolute;
    bottom: 1.125rem;
    left: 0;
    padding: 0.25rem 0.5rem;
    border-radius: var(--radius-xs);
    background: var(--surface-float);
    box-shadow: var(--shadow-float);
    color: var(--text);
    font-size: var(--text-xs);
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
    transform: translateX(-50%);
    opacity: 0;
    pointer-events: none;
    transition: opacity var(--transition-fast);
  }

  .am-progress:hover .am-tooltip {
    opacity: 1;
  }

  /* Subtitles: white type with a dark outline, readable on any frame. */
  .am-subtitle-overlay {
    position: absolute;
    z-index: 3;
    left: 7%;
    right: 7%;
    bottom: clamp(4.5rem, 13%, 6.75rem);
    display: flex;
    justify-content: center;
    pointer-events: none;
    text-align: center;
  }

  .am-player:not(:global(.is-idle)) .am-subtitle-overlay,
  .am-player:global(.is-paused) .am-subtitle-overlay,
  .am-player:focus-within .am-subtitle-overlay {
    bottom: 8.25rem;
  }

  .am-subtitle-overlay span {
    max-width: min(92%, 70ch);
    padding: 0.22em 0.55em 0.26em;
    color: var(--text);
    font-size: clamp(0.9375rem, 2vw, 1.375rem);
    font-weight: 620;
    line-height: 1.25;
    letter-spacing: -0.012em;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    text-shadow:
      -1px -1px 1px var(--stage),
      1px -1px 1px var(--stage),
      -1px 1px 1px var(--stage),
      1px 1px 1px var(--stage),
      0 2px 4px var(--stage);
  }

  /* ── Floating panels (audio, subtitles, settings) ────────────── */
  .am-panel {
    position: absolute;
    top: var(--space-3);
    right: var(--space-4);
    z-index: 6;
    width: min(20rem, calc(100% - 2rem));
    max-height: calc(100% - 1.5rem);
    overflow-y: auto;
    overscroll-behavior: contain;
    padding: var(--space-4);
    border: var(--border-width) solid transparent;
    border-radius: var(--radius-lg);
    background:
      var(--card-fill) padding-box,
      var(--card-edge) border-box;
    box-shadow: var(--shadow-float);
    color: var(--text);
    animation: panel-in 260ms var(--ease-spring);
    transform-origin: top right;
  }

  @keyframes panel-in {
    from {
      opacity: 0;
      transform: translateY(-4px) scale(0.98);
    }
  }

  .am-panel h2,
  .am-panel h3 {
    margin: 0 0 var(--space-3);
    font-size: var(--text-small);
    font-weight: 560;
    letter-spacing: -0.01em;
  }

  .am-panel h2 {
    font-size: var(--text-ui);
    padding-right: 2.5rem;
    min-height: 1.5rem;
  }

  .am-player .am-panel-close {
    position: absolute;
    top: 0.25rem;
    right: 0.25rem;
    width: 2.75rem;
    min-height: 2.75rem;
    padding: 0;
    border: 0;
    border-radius: var(--radius-sm);
    background: transparent;
    box-shadow: none;
    color: var(--text-secondary);
  }

  .am-player .am-panel-close:hover {
    background: var(--hover);
    color: var(--text);
  }

  .am-panel-close :global(svg) {
    width: 1.1rem;
    height: 1.1rem;
  }

  .am-track-status {
    margin: 0 0 var(--space-3);
    font-size: var(--text-xs);
    line-height: 1.5;
    color: var(--text-muted);
    overflow-wrap: anywhere;
  }

  .am-track-status:empty {
    display: none;
  }

  .am-subtitle-delay {
    width: 100%;
    min-height: 2rem;
    accent-color: var(--accent);
  }

  .am-track-list {
    display: grid;
    gap: var(--space-1);
  }

  .am-track-list:global([aria-busy="true"]) {
    opacity: 0.65;
  }

  .am-panel :global(.am-track-option) {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    min-height: var(--control-height);
    padding: var(--space-2) var(--space-3);
    border: var(--border-width) solid transparent;
    border-radius: var(--radius);
    background:
      var(--inset-fill) padding-box,
      var(--inset-edge) border-box;
    color: var(--text-secondary);
    font-size: var(--text-small);
    cursor: pointer;
  }

  .am-panel :global(.am-track-option:hover) {
    color: var(--text);
  }

  .am-panel :global(.am-track-option:has(input:checked)) {
    background: var(--selected) padding-box;
    border-color: var(--border);
    color: var(--text);
    font-weight: 560;
  }

  .am-panel :global(.am-track-option span) {
    min-width: 0;
    overflow-wrap: anywhere;
  }

  .am-panel-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    min-height: 2.5rem;
    padding: var(--space-1) 0;
    border-top: var(--border-width) solid var(--line);
    font-size: var(--text-small);
    color: var(--text-secondary);
  }

  .am-panel-row strong,
  .am-panel-row output {
    color: var(--text);
    font-weight: 560;
    font-variant-numeric: tabular-nums;
    overflow-wrap: anywhere;
    text-align: right;
  }

  .am-speed-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 2px;
    padding: 3px;
    margin-bottom: var(--space-3);
    border-radius: var(--radius-sm);
    border: var(--border-width) solid var(--line);
    background: var(--surface-sunken);
  }

  .am-speed-grid :global(.am-chip) {
    min-height: 2.25rem;
    padding: 0 var(--space-1);
    border: 0;
    border-radius: calc(var(--radius-sm) - 3px);
    background: transparent;
    box-shadow: none;
    color: var(--text-muted);
    font-size: var(--text-xs);
    font-weight: 580;
    font-variant-numeric: tabular-nums;
  }

  .am-speed-grid :global(.am-chip:hover) {
    background: var(--hover);
    color: var(--text);
  }

  .am-speed-grid :global(.am-chip.is-active) {
    background: var(--surface-float);
    color: var(--text);
    box-shadow: var(--shadow-sm);
  }

  .am-player .am-toggle {
    min-height: 2rem;
    padding: 0 var(--space-3);
    border-radius: var(--radius-full);
    font-size: var(--text-xs);
    font-weight: 580;
  }

  .am-player .am-toggle:global([aria-pressed="true"]) {
    background: var(--button-bg);
    color: var(--button-text);
  }

  /* ── Transient feedback inside the stage ─────────────────────── */
  .am-toast-stack {
    position: absolute;
    top: var(--space-3);
    left: 50%;
    z-index: 8;
    display: grid;
    gap: var(--space-2);
    transform: translateX(-50%);
    pointer-events: none;
  }

  .am-player:has(.am-panel:not([hidden])) .am-toast-stack {
    display: none;
  }

  .am-toast-stack--page {
    position: fixed;
    top: auto;
    left: auto;
    right: max(var(--space-5), env(safe-area-inset-right));
    bottom: max(var(--space-5), env(safe-area-inset-bottom));
    z-index: calc(var(--layer-palette) + 5);
    transform: none;
  }

  :global(.am-toast) {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    min-width: min(17.5rem, calc(100vw - 2rem));
    padding: var(--space-2) var(--space-3);
    border: var(--border-width) solid transparent;
    border-radius: var(--radius);
    background:
      var(--card-fill) padding-box,
      var(--card-edge) border-box;
    box-shadow: var(--shadow-float);
    color: var(--text);
    font-size: var(--text-small);
    font-weight: 520;
    animation: am-toast-in 220ms var(--ease-spring) both;
  }

  :global(.am-toast svg) {
    width: 1rem;
    height: 1rem;
    color: var(--text-secondary);
    flex-shrink: 0;
  }

  :global(.am-toast.is-leaving) {
    animation: am-toast-out 180ms var(--ease-exit) both;
  }

  @keyframes -global-am-toast-in {
    from {
      opacity: 0;
      transform: translateY(-8px) scale(0.98);
    }
  }

  @keyframes -global-am-toast-out {
    to {
      opacity: 0;
      transform: translateY(-8px);
    }
  }

  .am-player :global(.am-ripple) {
    position: absolute;
    z-index: 3;
    width: 5.375rem;
    height: 5.375rem;
    border-radius: 50%;
    border: 2px solid var(--accent);
    background: var(--accent-soft);
    opacity: 0;
    transform: translate(-50%, -50%);
    pointer-events: none;
    animation: am-ripple 700ms var(--ease-out) both;
  }

  @keyframes am-ripple {
    from {
      opacity: 0.6;
      transform: translate(-50%, -50%) scale(0.25);
    }
    to {
      opacity: 0;
      transform: translate(-50%, -50%) scale(1.75);
    }
  }

  .am-seek-indicator {
    position: absolute;
    left: 50%;
    top: 50%;
    z-index: 5;
    padding: var(--space-3) var(--space-5);
    border-radius: var(--radius-full);
    background: color-mix(in oklch, var(--surface-float) 88%, transparent);
    box-shadow: var(--shadow-float);
    color: var(--text);
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    transform: translate(-50%, -50%) scale(0.96);
    opacity: 0;
    pointer-events: none;
  }

  .am-seek-indicator:global(.is-visible) {
    animation: am-seek-flash 800ms var(--ease-out) both;
  }

  @keyframes am-seek-flash {
    0% {
      opacity: 0;
      transform: translate(-50%, -50%) scale(0.9);
    }
    18% {
      opacity: 1;
      transform: translate(-50%, -50%) scale(1);
    }
    100% {
      opacity: 0;
      transform: translate(-50%, -50%) scale(1.04);
    }
  }

  .am-gesture-indicator {
    position: absolute;
    top: 50%;
    z-index: 5;
    display: grid;
    justify-items: center;
    width: 2.875rem;
    padding: var(--space-3) var(--space-2);
    border-radius: var(--radius-full);
    background: color-mix(in oklch, var(--surface-float) 88%, transparent);
    box-shadow: var(--shadow-float);
    color: var(--text);
    transform: translateY(-50%);
    opacity: 0;
    pointer-events: none;
    transition: opacity var(--transition-fast);
  }

  .am-gesture-indicator :global(svg) {
    width: 1.1rem;
    height: 1.1rem;
  }

  .am-gesture-indicator:global(.is-visible) {
    opacity: 1;
  }

  .am-gesture-indicator[data-side="left"] {
    left: var(--space-5);
  }

  .am-gesture-indicator[data-side="right"] {
    right: var(--space-5);
  }

  .am-gesture-track {
    display: flex;
    align-items: flex-end;
    width: 6px;
    height: 7.375rem;
    margin: var(--space-2) auto 0;
    border-radius: var(--radius-full);
    background: var(--line-strong);
    overflow: hidden;
  }

  .am-gesture-fill {
    width: 100%;
    height: 50%;
    border-radius: inherit;
    background: var(--accent);
  }

  .am-error-card {
    position: absolute;
    inset: 50% auto auto 50%;
    z-index: 9;
    display: grid;
    gap: var(--space-2);
    width: min(22rem, calc(100% - 2rem));
    padding: var(--space-5);
    border: var(--border-width) solid transparent;
    border-radius: var(--radius-lg);
    background:
      var(--card-fill) padding-box,
      var(--card-edge) border-box;
    box-shadow: var(--shadow-modal);
    transform: translate(-50%, -50%);
    text-align: center;
  }

  .am-error-card h2 {
    font-size: var(--text-section);
    font-weight: 540;
  }

  .am-error-card p {
    font-size: var(--text-small);
  }

  .am-error-actions {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: var(--space-2);
    margin-top: var(--space-2);
  }

  .am-stats {
    position: absolute;
    left: var(--space-3);
    top: var(--space-3);
    z-index: 7;
    min-width: 13.75rem;
    padding: var(--space-3);
    border-radius: var(--radius-sm);
    background: color-mix(in oklch, var(--surface-float) 90%, transparent);
    box-shadow: var(--shadow-float);
    color: var(--text-secondary);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-variant-numeric: tabular-nums;
    white-space: pre-line;
    pointer-events: none;
  }

  /* ── Keyboard-shortcut dialog ─────────────────────────────────── */
  .am-modal[hidden] {
    display: none;
  }

  .am-modal .dialog {
    width: min(100%, 38rem);
    animation: am-dialog-in 320ms var(--ease-spring);
  }

  @keyframes am-dialog-in {
    from {
      opacity: 0;
      transform: translateY(12px) scale(0.98);
    }
  }

  .am-modal .dialog-head :global(svg) {
    width: 1.1rem;
    height: 1.1rem;
  }

  .am-shortcut-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--space-2);
  }

  .am-shortcut {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    min-height: 2.75rem;
    padding: var(--space-2) var(--space-3);
    font-size: var(--text-small);
    color: var(--text-secondary);
  }

  /* ── Theater mode (toggled on <body> by the controller) ───────── */
  :global(body.theater-mode) {
    overflow: hidden;
  }

  :global(body.theater-mode) .stream-player--video {
    position: fixed;
    inset: 0;
    z-index: var(--layer-overlay);
    max-height: none;
    aspect-ratio: auto;
  }

  /* ── Responsive ──────────────────────────────────────────────── */
  @media (max-width: 51.25rem) {
    .am-player :global(.am-extra-desktop) {
      display: none;
    }
  }

  @media (max-width: 40rem) {
    .watch {
      gap: var(--space-4);
    }

    .stream-player--video {
      min-height: 11.25rem;
    }

    .stream-audio-panel {
      grid-template-columns: minmax(0, 1fr);
      justify-items: center;
    }

    .am-controls {
      padding: var(--space-2);
    }

    .am-player:not(:global(.is-idle)) .am-subtitle-overlay,
    .am-player:global(.is-paused) .am-subtitle-overlay,
    .am-player:focus-within .am-subtitle-overlay {
      bottom: 5.875rem;
    }

    .am-control-surface {
      gap: var(--space-1);
      padding: var(--space-2) var(--space-2);
      border-radius: var(--radius);
    }

    .am-control-row {
      gap: var(--space-1);
    }

    .am-transport-controls,
    .am-player-tools {
      gap: 1px;
    }

    .am-player .am-btn {
      width: 2.25rem;
      height: 2.25rem;
    }

    .am-player .am-btn :global(svg) {
      width: 1rem;
      height: 1rem;
    }

    .am-player .am-seek-btn {
      width: 2.25rem;
    }

    .am-player .am-play-btn {
      width: 2.5rem;
      height: 2.5rem;
    }

    .am-time {
      min-width: 2.375rem;
    }

    .am-progress-thumb {
      width: 1rem;
      height: 1rem;
    }

    .am-shortcut-grid {
      grid-template-columns: minmax(0, 1fr);
    }

    .am-panel {
      top: var(--space-2);
      right: var(--space-2);
      width: min(18.75rem, calc(100% - 1rem));
      max-height: calc(100% - 1rem);
      padding: var(--space-3);
    }
  }

  @media (max-width: 26.25rem) {
    .am-player .am-seek-btn {
      display: none;
    }

    .am-player .am-btn {
      width: 2rem;
      height: 2rem;
    }

    .am-player .am-play-btn {
      width: 2.375rem;
      height: 2.375rem;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .am-panel,
    .am-modal .dialog,
    :global(.am-toast) {
      animation-duration: 1ms;
    }
  }
</style>
