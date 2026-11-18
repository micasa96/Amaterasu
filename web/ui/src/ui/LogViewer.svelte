<script lang="ts">
  import { onMount, tick, untrack } from "svelte";
  import Pause from "@lucide/svelte/icons/pause";
  import Play from "@lucide/svelte/icons/play";
  import Download from "@lucide/svelte/icons/download";
  import Eraser from "@lucide/svelte/icons/eraser";
  import WrapText from "@lucide/svelte/icons/wrap-text";
  import ArrowDownToLine from "@lucide/svelte/icons/arrow-down-to-line";
  import Icon from "./Icon.svelte";
  import { copyText } from "../lib/format";
  import { toast } from "../lib/toast.svelte";

  // A live, redacted view of the bot's log over server-sent events
  // (/api/logs/stream). Pause holds new lines; scrolling up stops following;
  // selection copies like any text; Download fetches the whole log file.
  let {
    auth = "",
    height = "min(70svh, 44rem)",
  }: {
    /** "user_id=…&token=…" from a signed link, or "" for the login session. */
    auth?: string;
    height?: string;
  } = $props();

  type Level = "debug" | "info" | "warning" | "error";
  type Line = { id: number; time: string; level: Level; text: string; raw: string };

  const MAX_LINES = 5000;
  const LEVELS: { value: "all" | Level; label: string }[] = [
    { value: "all", label: "All" },
    { value: "info", label: "Info" },
    { value: "warning", label: "Warnings" },
    { value: "error", label: "Errors" },
  ];

  let lines = $state<Line[]>([]);
  let held = $state<Line[]>([]);
  let paused = $state(false);
  let follow = $state(true);
  let wrap = $state(true);
  let query = $state("");
  let level = $state<"all" | Level>("all");
  let connection = $state<"connecting" | "live" | "reconnecting">("connecting");
  let viewport = $state<HTMLElement | null>(null);
  let nextId = 0;

  const qs = $derived(untrack(() => (auth ? `?${auth}` : "")));
  const downloadHref = $derived(`/api/logs/download${qs}`);

  // "[18-Nov-26 01:24:33 PM] [INFO] - message" (text format) or a JSON line.
  const TEXT_RE = /^\[([^\]]+)\]\s+\[([A-Z]+)\]\s+-\s?(.*)$/s;

  function toLevel(name: string): Level {
    const n = name.toUpperCase();
    if (n.startsWith("ERR") || n === "CRITICAL" || n === "FATAL") return "error";
    if (n.startsWith("WARN")) return "warning";
    if (n === "DEBUG") return "debug";
    return "info";
  }

  function parse(raw: string): Line {
    const m = TEXT_RE.exec(raw);
    if (m) return { id: nextId++, time: m[1], level: toLevel(m[2]), text: m[3], raw };
    if (raw.startsWith("{")) {
      try {
        const j = JSON.parse(raw);
        const text = [j.message ?? j.msg ?? "", j.exception ?? ""].filter(Boolean).join(" ");
        return {
          id: nextId++,
          time: String(j.time ?? j.timestamp ?? j.asctime ?? ""),
          level: toLevel(String(j.level ?? j.levelname ?? "INFO")),
          text: text || raw,
          raw,
        };
      } catch {
        /* not JSON after all */
      }
    }
    // Continuation lines (tracebacks) inherit the previous line's level.
    const prev = lines.at(-1);
    return { id: nextId++, time: "", level: prev?.level ?? "info", text: raw, raw };
  }

  function push(batch: string[]) {
    const parsed = batch.map(parse);
    if (paused) {
      held = [...held, ...parsed].slice(-MAX_LINES);
      return;
    }
    lines = [...lines, ...parsed].slice(-MAX_LINES);
    void stickToBottom();
  }

  async function stickToBottom() {
    if (!follow) return;
    await tick();
    viewport?.scrollTo({ top: viewport.scrollHeight });
  }

  function onScroll() {
    if (!viewport) return;
    const fromBottom = viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight;
    follow = fromBottom < 40;
  }

  function jumpToLatest() {
    follow = true;
    void stickToBottom();
  }

  function togglePause() {
    paused = !paused;
    if (!paused && held.length) {
      lines = [...lines, ...held].slice(-MAX_LINES);
      held = [];
      void stickToBottom();
    }
  }

  function clearView() {
    lines = [];
    held = [];
  }

  const needle = $derived(query.trim().toLowerCase());
  const visible = $derived(
    lines.filter(
      (l) =>
        (level === "all" ||
          l.level === level ||
          (level === "info" && l.level === "debug")) &&
        (!needle || l.raw.toLowerCase().includes(needle)),
    ),
  );

  async function copy() {
    const selection = window.getSelection();
    const selected =
      selection && viewport && !selection.isCollapsed && viewport.contains(selection.anchorNode)
        ? selection.toString()
        : "";
    const text = selected || visible.map((l) => l.raw).join("\n");
    if (!text) return;
    if (await copyText(text)) {
      toast.show(selected ? "Selection copied" : `Copied ${visible.length} lines`);
    }
  }

  onMount(() => {
    const source = new EventSource(`/api/logs/stream${qs}`);
    source.onopen = () => (connection = "live");
    source.onerror = () => (connection = "reconnecting");
    source.onmessage = (event) => {
      connection = "live";
      try {
        const data = JSON.parse(event.data) as { lines: string[]; rotated: boolean };
        if (data.rotated) push(["── log file rotated ──"]);
        if (data.lines.length) push(data.lines);
      } catch {
        /* ignore malformed events */
      }
    };
    return () => source.close();
  });
</script>

<div class="viewer" style:--viewer-height={height}>
  <div class="toolbar">
    <div class="cluster">
      <span
        class="pill"
        data-tone={paused ? "warning" : connection === "live" ? "success" : "warning"}
        aria-live="polite"
      >
        <span class="dot"></span>
        {paused
          ? held.length
            ? `Paused · ${held.length} new`
            : "Paused"
          : connection === "live"
            ? "Live"
            : connection === "connecting"
              ? "Connecting…"
              : "Reconnecting…"}
      </span>
      <div class="segmented" role="group" aria-label="Log level">
        {#each LEVELS as opt (opt.value)}
          <button
            type="button"
            aria-pressed={level === opt.value}
            onclick={() => (level = opt.value)}>{opt.label}</button
          >
        {/each}
      </div>
    </div>

    <div class="cluster tools">
      <label class="search">
        <span class="visually-hidden">Filter log lines</span>
        <Icon name="search" size={15} />
        <input type="search" bind:value={query} placeholder="Filter lines" autocomplete="off" />
      </label>
      <button type="button" class="btn" onclick={togglePause} aria-pressed={paused}>
        <Icon icon={paused ? Play : Pause} size={16} />
        <span>{paused ? "Resume" : "Pause"}</span>
      </button>
      <button type="button" class="btn" onclick={copy} title="Copies your selection, or every visible line">
        <Icon name="copy" size={16} />
        <span>Copy</span>
      </button>
      <a class="btn" href={downloadHref} download>
        <Icon icon={Download} size={16} />
        <span>Download</span>
      </a>
      <button
        type="button"
        class="btn btn-icon"
        aria-pressed={wrap}
        onclick={() => (wrap = !wrap)}
        aria-label={wrap ? "Turn off line wrapping" : "Wrap long lines"}
        title={wrap ? "Turn off line wrapping" : "Wrap long lines"}
      >
        <Icon icon={WrapText} size={16} />
      </button>
      <button
        type="button"
        class="btn btn-icon"
        onclick={clearView}
        aria-label="Clear the view"
        title="Clear the view (the log file is not changed)"
      >
        <Icon icon={Eraser} size={16} />
      </button>
    </div>
  </div>

  <div class="frame">
    <!-- Focusable so keyboard users can scroll the log (WCAG 2.1.1). -->
    <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
    <div
      class="lines"
      class:wrap
      bind:this={viewport}
      onscroll={onScroll}
      role="log"
      aria-live="off"
      aria-label="Live log"
      tabindex="0"
    >
      {#if visible.length === 0}
        <p class="placeholder">
          {lines.length
            ? "No lines match the filter."
            : connection === "live"
              ? "Waiting for new log lines…"
              : "Connecting to the log…"}
        </p>
      {:else}
        {#each visible as line (line.id)}
          <div class="line" class:cont={!line.time} data-level={line.level}>
            {#if line.time}<span class="time">{line.time}</span>{/if}
            {#if line.time}<span class="level">{line.level}</span>{/if}
            <span class="text">{line.text}</span>
          </div>
        {/each}
      {/if}
    </div>

    {#if !follow && visible.length}
      <button type="button" class="btn btn-primary jump" onclick={jumpToLatest}>
        <Icon icon={ArrowDownToLine} size={16} />
        Jump to latest
      </button>
    {/if}
  </div>

  <p class="note foot">
    {visible.length} of {lines.length} lines shown · keeps the latest {MAX_LINES.toLocaleString()} ·
    secrets are redacted on the server
  </p>
</div>

<style>
  .viewer {
    display: grid;
    gap: var(--space-3);
    min-width: 0;
  }

  .toolbar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
  }

  .tools {
    flex: 1 1 auto;
    justify-content: flex-end;
  }

  .search {
    position: relative;
    display: flex;
    align-items: center;
    width: clamp(9rem, 16vw, 14rem);
    color: var(--text-muted);
  }

  .search :global(.svg-icon) {
    position: absolute;
    left: var(--space-3);
    pointer-events: none;
  }

  .search input {
    padding-left: 2.25rem;
  }

  .frame {
    position: relative;
    min-width: 0;
  }

  /* The log well: a sunken surface, monospace (it is data), selectable. */
  .lines {
    height: var(--viewer-height);
    overflow: auto;
    overscroll-behavior: contain;
    padding: var(--space-3) 0;
    border-radius: var(--radius-lg);
    border: var(--border-width) solid var(--line);
    background: var(--surface-sunken);
    font-family: var(--font-mono);
    font-size: 0.8125rem;
    line-height: 1.6;
    color: var(--text-secondary);
    user-select: text;
    -webkit-user-select: text;
    scrollbar-gutter: stable;
  }

  .lines:focus-visible {
    outline: var(--focus-width) solid var(--focus);
    outline-offset: 2px;
  }

  .line {
    display: flex;
    gap: var(--space-3);
    padding: 0 var(--space-4);
    white-space: pre;
    min-width: max-content;
  }

  .wrap .line {
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    min-width: 0;
  }

  .line:hover {
    background: var(--hover-veil);
  }

  .time {
    flex-shrink: 0;
    width: 21ch;
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
  }

  /* Continuation lines (tracebacks) line up under the message column. */
  .line.cont .text {
    margin-left: calc(21ch + 4.25rem + 2 * var(--space-3));
  }

  .level {
    flex-shrink: 0;
    width: 4.25rem;
    color: var(--text-muted);
    text-transform: uppercase;
    font-size: 0.6875rem;
    letter-spacing: 0.04em;
    line-height: 2.1;
  }

  .text {
    color: var(--text);
    min-width: 0;
  }

  /* Hue only for state, always with the level word beside it. */
  .line[data-level="warning"] .level,
  .line[data-level="warning"] .text {
    color: var(--warning);
  }

  .line[data-level="error"] {
    background: var(--danger-soft);
  }

  .line[data-level="error"] .level,
  .line[data-level="error"] .text {
    color: var(--danger);
  }

  .placeholder {
    padding: var(--space-6) var(--space-4);
    color: var(--text-muted);
    font-family: var(--font-body);
  }

  .jump {
    position: absolute;
    right: var(--space-4);
    bottom: var(--space-4);
    box-shadow: var(--shadow-float);
  }

  .foot {
    font-variant-numeric: tabular-nums;
  }

  ::selection {
    background: var(--accent-soft);
    color: var(--text);
  }

  @media (max-width: 48rem) {
    .tools {
      justify-content: flex-start;
    }
    .search {
      width: 100%;
    }
    .tools .btn span {
      display: none;
    }
    .tools .btn {
      width: var(--control-height);
      padding: 0;
    }
    .time {
      display: none;
    }
    .line.cont .text {
      margin-left: calc(4.25rem + var(--space-3));
    }
  }
</style>
