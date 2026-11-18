<script lang="ts" module>
  import type { Component, Snippet } from "svelte";
  import type { IconName } from "./Icon.svelte";
  import type { Command } from "./CommandPalette.svelte";

  export interface NavItem {
    label: string;
    /** A URL, or "#id" to focus a section on this page. */
    href: string;
    icon?: IconName;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    glyph?: Component<any>;
    current?: boolean;
  }

  export interface NavGroup {
    label: string;
    items: NavItem[];
  }

  export type { Command };
</script>

<script lang="ts">
  import { onMount } from "svelte";
  import Lockup from "./Lockup.svelte";
  import Icon from "./Icon.svelte";
  import CommandPalette from "./CommandPalette.svelte";
  import Toast from "./Toast.svelte";
  import { preferences } from "../lib/preferences.svelte";
  import { toast } from "../lib/toast.svelte";

  // The one application frame every Amaterasu page renders inside: a
  // sidebar with grouped navigation, a sticky top bar with breadcrumbs,
  // search and the theme switch, and the main work area. Pages pass their
  // own navigation (usually the sections of that page) and content.
  let {
    place,
    nav = [],
    crumbs,
    note,
    commands = [],
    actions,
    children,
    dense = false,
  }: {
    /** The current place, shown in the tab title and the last breadcrumb. */
    place: string;
    nav?: NavGroup[];
    /** Breadcrumb trail before `place`. */
    crumbs?: string[];
    /** Small print at the foot of the sidebar. */
    note?: string;
    /** Extra command-palette entries beyond navigation and theme. */
    commands?: Command[];
    /** Extra controls at the start of the top bar's action group. */
    actions?: Snippet;
    children: Snippet;
    /** Compact 38px controls on desktop pointers, for dense work screens. */
    dense?: boolean;
  } = $props();

  const version = (document.documentElement.dataset.version ?? "").trim();
  const isMac =
    typeof navigator !== "undefined" &&
    /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);

  let hash = $state(typeof location !== "undefined" ? location.hash : "");
  let paletteOpen = $state(false);
  let navEl = $state<HTMLElement | null>(null);
  let indicator = $state({ x: 0, y: 0, w: 0, h: 0, visible: false });

  function isCurrent(item: NavItem): boolean {
    if (item.current !== undefined && !item.href.startsWith("#")) return item.current;
    if (item.href.startsWith("#")) {
      if (hash) return hash === item.href;
      return !!item.current;
    }
    return false;
  }

  function placeIndicator() {
    const link = navEl?.querySelector<HTMLElement>("a.selected");
    if (!navEl || !link) {
      indicator = { ...indicator, visible: false };
      return;
    }
    indicator = {
      x: link.offsetLeft,
      y: link.offsetTop,
      w: link.offsetWidth,
      h: link.offsetHeight,
      visible: true,
    };
  }

  $effect(() => {
    void hash;
    void nav;
    queueMicrotask(placeIndicator);
  });

  function focusSection(href: string, e: MouseEvent) {
    if (!href.startsWith("#")) return;
    const target = document.getElementById(href.slice(1));
    if (!target) return;
    e.preventDefault();
    history.replaceState(null, "", href);
    hash = href;
    target.scrollIntoView({
      behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
      block: "start",
    });
    // Focus the section's heading so keyboard and screen-reader users land there.
    const heading =
      target.matches("h1, h2, h3") ? target : target.querySelector<HTMLElement>("h1, h2, h3");
    if (heading) {
      if (!heading.hasAttribute("tabindex")) heading.setAttribute("tabindex", "-1");
      heading.focus({ preventScroll: true });
    }
  }

  const allCommands = $derived<Command[]>([
    ...nav.flatMap((g) =>
      g.items.map((item, i) => ({
        id: `nav-${g.label}-${i}`.replace(/\W+/g, "-"),
        label: item.label,
        group: g.label,
        icon: item.icon ?? (item.glyph ? undefined : "arrow-right"),
        glyph: item.glyph,
        run: () => {
          if (item.href.startsWith("#")) {
            const target = document.getElementById(item.href.slice(1));
            if (target) {
              focusSection(item.href, new MouseEvent("click"));
              return;
            }
          }
          location.href = item.href;
        },
      })),
    ),
    ...commands,
    {
      id: "theme-light",
      label: "Light theme",
      group: "Appearance",
      icon: "sun",
      run: () => preferences.setTheme("light"),
    },
    {
      id: "theme-dark",
      label: "Dark theme",
      group: "Appearance",
      icon: "moon",
      run: () => preferences.setTheme("dark"),
    },
    {
      id: "theme-system",
      label: "Match system theme",
      group: "Appearance",
      icon: "monitor",
      run: () => preferences.setTheme("system"),
    },
  ]);

  function typing(target: EventTarget | null): boolean {
    const el = target as HTMLElement | null;
    return !!el?.closest?.("input, textarea, select, [contenteditable='true']");
  }

  function onKeydown(e: KeyboardEvent) {
    if (paletteOpen) return;
    if (document.querySelector("[role='dialog'][aria-modal='true']")) return;
    const mod = isMac ? e.metaKey : e.ctrlKey;
    if (mod && e.key.toLowerCase() === "k") {
      e.preventDefault();
      paletteOpen = true;
    } else if (e.key === "/" && !typing(e.target) && !e.metaKey && !e.ctrlKey && !e.altKey) {
      e.preventDefault();
      paletteOpen = true;
    }
  }

  onMount(() => {
    document.title = `${place} — Amaterasu`;
    const onHash = () => (hash = location.hash);
    const onResize = () => placeIndicator();
    window.addEventListener("hashchange", onHash);
    window.addEventListener("resize", onResize);
    // Fonts change link widths; re-measure once they settle.
    document.fonts?.ready.then(placeIndicator);
    return () => {
      window.removeEventListener("hashchange", onHash);
      window.removeEventListener("resize", onResize);
    };
  });

  $effect(() => {
    document.title = `${place} — Amaterasu`;
  });
</script>

<svelte:window onkeydown={onKeydown} />

<a class="skip-link" href="#main">Skip to content</a>

<div class="shell">
  <!-- data-scheme="dark": the sidebar (the nav band on phones) stays inked in light theme. -->
  <aside class="sidebar" aria-label="Sidebar" data-scheme="dark">
    <a class="sidebar-brand" href="/" aria-label="Amaterasu home">
      <Lockup size="md" />
      {#if version}<span class="build-label">{version}</span>{/if}
    </a>

    {#if nav.length}
      <nav aria-label="Application" bind:this={navEl}>
        <span
          class="nav-indicator"
          aria-hidden="true"
          style:opacity={indicator.visible ? 1 : 0}
          style:transform="translate({indicator.x}px, {indicator.y}px)"
          style:width="{indicator.w}px"
          style:height="{indicator.h}px"
        ></span>
        {#each nav as group (group.label)}
          <p class="nav-group">{group.label}</p>
          {#each group.items as item (item.href + item.label)}
            {@const current = isCurrent(item)}
            <a
              href={item.href}
              class:selected={current}
              aria-current={current ? (item.href.startsWith("#") ? "location" : "page") : undefined}
              onclick={(e) => {
                focusSection(item.href, e);
              }}
            >
              <Icon name={item.icon} icon={item.glyph} size={18} />
              <span>{item.label}</span>
            </a>
          {/each}
        {/each}
      </nav>
    {/if}

    <div class="sidebar-foot">
      <div class="command-card">
        <span class="tile tile-lg command-tile" aria-hidden="true">
          <Icon name="command" size={20} />
        </span>
        <p class="command-title">Jump anywhere</p>
        <p class="command-text">
          Move between sections or change the theme from the keyboard.
        </p>
        <button type="button" class="command-btn" onclick={() => (paletteOpen = true)}>
          Open search
          <span class="search-keys" aria-hidden="true">
            <kbd>{isMac ? "⌘" : "Ctrl"}</kbd><kbd>K</kbd>
          </span>
        </button>
      </div>
      {#if note}<p class="foot-note">{note}</p>{/if}
    </div>
  </aside>

  <div class="canvas">
    <header class="topbar">
      <a class="topbar-brand" href="/" aria-label="Amaterasu home">
        <span class="topbar-lockup"><Lockup size="sm" /></span>
        <span class="topbar-mark"><Lockup size="sm" showWordmark={false} /></span>
      </a>

      <div class="breadcrumbs" aria-label="Current location">
        {#each crumbs ?? [] as crumb, i (i)}
          <span class="crumb">{crumb}</span>
          <Icon name="chevron-right" size={14} class="crumb-sep" />
        {/each}
        <span class="crumb crumb-current">{place}</span>
      </div>

      <div class="topbar-actions">
        {#if actions}{@render actions()}{/if}

        <button
          type="button"
          class="search-trigger"
          onclick={() => (paletteOpen = true)}
          aria-label="Search and commands"
          aria-keyshortcuts={isMac ? "Meta+K" : "Control+K"}
        >
          <Icon name="search" size={16} />
          <span class="search-text">Search or jump to…</span>
          <span class="search-keys" aria-hidden="true">
            <kbd>{isMac ? "⌘" : "Ctrl"}</kbd><kbd>K</kbd>
          </span>
        </button>

        <button
          type="button"
          class="btn-icon icon-chip"
          onclick={() => preferences.toggleScheme()}
          aria-label={preferences.resolvedDark ? "Switch to light theme" : "Switch to dark theme"}
          title={preferences.resolvedDark ? "Switch to light theme" : "Switch to dark theme"}
        >
          <Icon name={preferences.resolvedDark ? "sun" : "moon"} size={18} />
        </button>
      </div>
    </header>

    <main id="main" tabindex="-1" class:dense>
      {@render children()}
    </main>
  </div>
</div>

{#if paletteOpen}
  <CommandPalette commands={allCommands} onclose={() => (paletteOpen = false)} />
{/if}

<Toast message={toast.message} onclear={() => toast.clear()} />

<style>
  .shell {
    min-height: 100svh;
    display: grid;
    grid-template-columns: var(--nav-width) minmax(0, 1fr);
  }

  /* ── Sidebar ─────────────────────────────────────────────────── */
  .sidebar {
    position: sticky;
    top: 0;
    height: 100svh;
    color: var(--text);
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    padding: var(--space-4) var(--space-3);
    padding-left: max(var(--space-3), env(safe-area-inset-left));
    background: var(--surface-nav);
    border-right: var(--border-width) solid var(--line);
    overflow-y: auto;
  }

  .sidebar-brand,
  .topbar-brand {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    color: var(--text);
    text-decoration: none;
  }

  .sidebar-brand {
    padding: var(--space-1) var(--space-2) var(--space-3);
  }

  .build-label {
    margin-left: auto;
    padding: 0.125rem 0.5rem;
    border-radius: var(--radius-full);
    border: var(--border-width) solid var(--line-strong);
    font-size: 0.6875rem;
    font-weight: 600;
    color: var(--text-muted);
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }

  nav {
    position: relative;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .nav-group {
    padding: var(--space-4) var(--space-3) var(--space-2);
    font-size: var(--text-xs);
    font-weight: 600;
    color: var(--text-muted);
  }

  nav a {
    position: relative;
    z-index: 1;
    display: flex;
    align-items: center;
    gap: var(--space-3);
    min-height: var(--control-height);
    padding: 0 var(--space-3);
    border: var(--border-width) solid transparent;
    border-radius: var(--radius);
    color: var(--text-muted);
    font-size: var(--text-ui);
    font-weight: 500;
    text-decoration: none;
    white-space: nowrap;
    transition:
      background-color var(--transition-fast),
      color var(--transition-fast);
  }

  nav a :global(.svg-icon) {
    color: var(--text-muted);
    transition: color var(--transition-fast);
  }

  nav a:hover {
    background: var(--hover);
    color: var(--text);
  }

  nav a.selected {
    color: var(--text);
    font-weight: 580;
  }

  nav a.selected:hover {
    background: transparent;
  }

  nav a.selected :global(.svg-icon) {
    color: var(--accent);
  }

  /* The lit pill behind the current destination; it glides between items. */
  .nav-indicator {
    position: absolute;
    top: 0;
    left: 0;
    z-index: 0;
    border-radius: var(--radius);
    border: var(--border-width) solid transparent;
    background:
      var(--inset-fill) padding-box,
      var(--inset-edge) border-box;
    box-shadow: 0 6px 16px -10px oklch(0 0 0 / 0.5);
    pointer-events: none;
    transition:
      transform 420ms var(--ease-spring),
      width 420ms var(--ease-spring),
      height 420ms var(--ease-spring),
      opacity var(--duration) var(--ease-out);
    will-change: transform;
  }

  /* A lit marker on the current destination. */
  .nav-indicator::after {
    content: "";
    position: absolute;
    right: -0.75rem;
    top: 50%;
    width: 3px;
    height: 1.25rem;
    border-radius: 3px 0 0 3px;
    transform: translateY(-50%);
    background: var(--accent);
    box-shadow: 0 0 12px 1px var(--glow-accent);
  }

  .sidebar-foot {
    margin-top: auto;
    display: grid;
    gap: var(--space-4);
    padding: var(--space-4) 0 var(--space-2);
  }

  .foot-note {
    padding: 0 var(--space-3);
    font-size: var(--text-xs);
    color: var(--text-muted);
    line-height: 1.45;
  }

  /* The glowing card: the command palette, one click away. */
  .command-card {
    position: relative;
    display: grid;
    justify-items: center;
    gap: var(--space-2);
    padding: var(--space-5) var(--space-4) var(--space-4);
    text-align: center;
    border-radius: var(--radius-lg);
    border: var(--border-width) solid transparent;
    background:
      radial-gradient(
          120% 90% at 50% 120%,
          light-dark(oklch(0.82 0 0 / 0.55), oklch(0.55 0 0 / 0.45)),
          transparent 70%
        )
        padding-box,
      var(--card-fill) padding-box,
      linear-gradient(
          180deg,
          light-dark(oklch(0.9 0 0), oklch(1 0 0 / 0.14)),
          light-dark(oklch(0.72 0 0), oklch(1 0 0 / 0.32))
        )
        border-box;
    overflow: hidden;
  }

  .command-tile {
    margin-bottom: var(--space-1);
    border-radius: 50%;
  }

  .command-title {
    font-size: var(--text-section);
    font-weight: 540;
    color: var(--text);
    letter-spacing: -0.012em;
  }

  .command-text {
    font-size: var(--text-xs);
    line-height: 1.45;
    color: var(--text-secondary);
  }

  .command-btn {
    width: 100%;
    margin-top: var(--space-2);
    background:
      linear-gradient(
          light-dark(oklch(1 0 0 / 0.75), oklch(1 0 0 / 0.08)),
          light-dark(oklch(1 0 0 / 0.55), oklch(1 0 0 / 0.04))
        )
        padding-box,
      linear-gradient(light-dark(oklch(1 0 0), oklch(1 0 0 / 0.18)), transparent)
        border-box;
    font-size: var(--text-small);
  }

  /* ── Canvas ──────────────────────────────────────────────────── */
  .canvas {
    position: relative;
    min-width: 0;
    display: flex;
    flex-direction: column;
    isolation: isolate;
  }

  /* The ambient light: one soft source over the top of the work area. */
  .canvas::before {
    content: "";
    position: absolute;
    inset: 0 0 auto 0;
    height: 34rem;
    z-index: -1;
    pointer-events: none;
    background:
      linear-gradient(112deg, transparent 44%, var(--sheen) 56%, transparent 66%),
      radial-gradient(46rem 22rem at 80% -8rem, var(--glow-accent), transparent 72%),
      radial-gradient(
        30rem 16rem at 22% -10rem,
        light-dark(transparent, oklch(1 0 0 / 0.05)),
        transparent 70%
      );
    -webkit-mask-image: linear-gradient(180deg, #000 0%, #000 35%, transparent 100%);
    mask-image: linear-gradient(180deg, #000 0%, #000 35%, transparent 100%);
  }

  .topbar {
    position: sticky;
    top: 0;
    z-index: var(--layer-sticky);
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--space-3);
    min-height: var(--topbar-height);
    padding: var(--space-2) var(--gutter);
    padding-right: max(var(--gutter), env(safe-area-inset-right));
    background: var(--surface);
    border-bottom: var(--border-width) solid var(--line);
  }

  .topbar-brand {
    display: none;
    gap: var(--space-2);
  }

  .topbar-mark {
    display: none;
  }

  .breadcrumbs {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    min-width: 0;
    font-size: var(--text-small);
    color: var(--text-muted);
  }

  .breadcrumbs :global(.crumb-sep) {
    color: var(--text-muted);
    opacity: 0.7;
  }

  .crumb {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .crumb-current {
    color: var(--text);
    font-weight: 600;
  }

  .topbar-actions {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    justify-content: flex-end;
    gap: var(--space-2);
    margin-left: auto;
    min-width: 0;
  }

  .search-trigger {
    justify-content: flex-start;
    width: clamp(12rem, 26vw, 22rem);
    padding: 0 var(--space-2) 0 var(--space-3);
    border-radius: var(--radius);
    color: var(--text-muted);
    font-weight: 460;
  }

  .search-trigger:hover:not(:disabled) {
    color: var(--text-secondary);
  }

  .icon-chip {
    border-radius: var(--radius);
    color: var(--text-secondary);
  }

  .search-text {
    flex: 1;
    text-align: left;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .search-keys {
    display: inline-flex;
    gap: 3px;
  }

  main {
    flex: 1;
    width: 100%;
    max-width: var(--content-width);
    margin: 0 auto;
    padding: var(--space-8) var(--gutter) var(--space-12);
    padding-left: max(var(--gutter), env(safe-area-inset-left));
    padding-right: max(var(--gutter), env(safe-area-inset-right));
    overflow-wrap: anywhere;
  }

  /* ── Tablet: tighter search ──────────────────────────────────── */
  @media (max-width: 72rem) {
    .search-trigger {
      width: auto;
    }
    .search-text {
      display: none;
    }
  }

  /* ── Phone and narrow tablet: nav becomes a scrolling strip ──── */
  @media (max-width: 60rem) {
    .shell {
      grid-template-columns: minmax(0, 1fr);
      grid-template-rows: auto auto 1fr auto;
    }

    .sidebar {
      position: sticky;
      top: 0;
      z-index: var(--layer-sticky);
      height: auto;
      flex-direction: row;
      align-items: center;
      gap: var(--space-2);
      padding: var(--space-2) var(--gutter);
      overflow-x: auto;
      overflow-y: hidden;
      overscroll-behavior-x: contain;
      scrollbar-width: none;
      border-right: 0;
      border-bottom: var(--border-width) solid var(--line);
      order: 2;
    }

    .sidebar::-webkit-scrollbar {
      display: none;
    }

    .sidebar:not(:has(nav)) {
      display: none;
    }

    .sidebar-brand,
    .sidebar-foot,
    .nav-group {
      display: none;
    }

    nav {
      flex-direction: row;
      gap: var(--space-1);
      flex-shrink: 0;
    }

    nav a {
      padding: 0 var(--space-3);
      border-radius: var(--radius-full);
    }

    .nav-indicator {
      border-radius: var(--radius-full);
    }

    .nav-indicator::after {
      display: none;
    }

    .canvas {
      display: contents;
    }

    .canvas::before {
      position: fixed;
    }

    .topbar {
      grid-row: auto;
      order: 1;
      position: relative;
      z-index: calc(var(--layer-sticky) + 1);
      padding-top: max(var(--space-2), env(safe-area-inset-top));
    }

    .topbar-brand {
      display: flex;
    }

    .breadcrumbs {
      order: 3;
      flex-basis: 100%;
    }

    main {
      order: 3;
      padding-top: var(--space-6);
    }
  }

  @media (max-width: 40rem) {
    .topbar-actions {
      display: contents;
    }
    .search-trigger {
      margin-left: auto;
    }
    .search-keys,
    .topbar-lockup {
      display: none;
    }
    .topbar-mark {
      display: inline-flex;
    }
    main {
      padding-top: var(--space-5);
    }
  }
</style>
