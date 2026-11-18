<script lang="ts">
  import { onMount } from "svelte";
  import Activity from "@lucide/svelte/icons/activity";
  import Cpu from "@lucide/svelte/icons/cpu";
  import Clock from "@lucide/svelte/icons/clock";
  import MemoryStick from "@lucide/svelte/icons/memory-stick";
  import Download from "@lucide/svelte/icons/download";
  import Link2 from "@lucide/svelte/icons/link-2";
  import FileText from "@lucide/svelte/icons/file-text";
  import Shield from "@lucide/svelte/icons/shield";
  import Film from "@lucide/svelte/icons/film";
  import Rss from "@lucide/svelte/icons/rss";
  import ArrowUpRight from "@lucide/svelte/icons/arrow-up-right";
  import Shell, { type NavGroup } from "../../ui/Shell.svelte";
  import Icon from "../../ui/Icon.svelte";
  import Feedback from "../../ui/Feedback.svelte";
  import Flame from "./Flame.svelte";
  import Lock from "@lucide/svelte/icons/lock";
  import LogViewer from "../../ui/LogViewer.svelte";

  // Public overview of this instance: what Amaterasu is, its live status
  // (polled from /api/status every 3s) and its components. The hero carries
  // the animated Blackflare flame from the README banner.
  let { data }: { data: { version?: string; bot_name?: string } } = $props();

  const version = $derived(data.version ?? "");
  const SOURCE = "https://github.com/its-niloy/Amaterasu";

  // active_tasks/uptime come from the bot process's published snapshot; they
  // are null (and bot_reporting false) when the bot is not reporting.
  type Status = {
    active_tasks: number | null;
    uptime: string | null;
    bot_reporting?: boolean;
    cpu: number;
    ram: number;
  };
  let status = $state<Status | null>(null);
  let failed = $state(false);

  const nav: NavGroup[] = [
    {
      label: "Instance",
      items: [
        { label: "Overview", href: "#overview", icon: "home", current: true },
        { label: "Live status", href: "#status", icon: "pulse" },
        { label: "Live logs", href: "#logs", icon: "list" },
        { label: "Components", href: "#components", icon: "layers" },
      ],
    },
  ];

  const components = [
    {
      icon: Download,
      title: "Multi-engine downloads",
      tag: "Core",
      text: "Aria2c, qBittorrent, JDownloader and Sabnzbd under one interface, with automatic engine selection.",
    },
    {
      icon: Link2,
      title: "FileToLink streaming",
      tag: "F2L",
      text: "Direct download and streamable links for Telegram files, with token-based authentication.",
    },
    {
      icon: FileText,
      title: "Auto-rename engine",
      tag: "Smart",
      text: "File renaming with pattern matching, episode detection and custom template variables.",
    },
    {
      icon: Shield,
      title: "Resilience",
      tag: "Robust",
      text: "Automatic retry, connection pooling, multi-account rotation and graceful degradation.",
    },
    {
      icon: Film,
      title: "Media processing",
      tag: "FFmpeg",
      text: "FFmpeg encoding with profile presets, codec selection and quality optimisation.",
    },
    {
      icon: Rss,
      title: "RSS automation",
      tag: "Auto",
      text: "Watch feeds, download new episodes automatically and organise them by category.",
    },
  ];

  async function refresh() {
    try {
      const res = await fetch("/api/status", { headers: { Accept: "application/json" } });
      if (!res.ok) throw new Error(String(res.status));
      status = (await res.json()) as Status;
      failed = false;
    } catch {
      failed = true;
    }
  }

  // Live logs are private: shown inline only to a signed-in owner session.
  let logAccess = $state<{ authorized: boolean; login_enabled: boolean } | null>(null);

  async function checkLogAccess() {
    try {
      const res = await fetch("/api/logs/access", { headers: { Accept: "application/json" } });
      logAccess = res.ok ? await res.json() : { authorized: false, login_enabled: false };
    } catch {
      logAccess = { authorized: false, login_enabled: false };
    }
  }

  const botReporting = $derived(status ? status.bot_reporting !== false : false);

  const pct = (n: number | undefined) =>
    n == null || !Number.isFinite(Number(n)) ? "—" : `${Math.round(Number(n))}`;

  onMount(() => {
    void checkLogAccess();
    void refresh();
    let timer = setInterval(refresh, 3000);
    // Stop polling while the tab is hidden; catch up when it returns.
    const onVisibility = () => {
      clearInterval(timer);
      if (document.visibilityState === "visible") {
        void refresh();
        timer = setInterval(refresh, 3000);
      }
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  });
</script>

<Shell place="Overview" {nav} note="Self-hosted. Status refreshes every 3 seconds.">
  <div class="page">
    <!-- Inked in both themes so the white flame always reads (like the banner). -->
    <section class="hero" aria-labelledby="overview" data-scheme="dark">
      <div class="hero-copy">
        <h1 id="overview" tabindex="-1">Amaterasu</h1>
        <p class="hero-lead">
          Self-hosted Telegram mirroring with multi-engine downloads and media processing.
        </p>
        <div class="hero-meta">
          {#if version}
            <span class="pill"><Icon icon={Shield} size={12} /> {version}</span>
          {/if}
          <span
            class="pill"
            data-tone={status ? (botReporting ? "success" : "warning") : failed ? "danger" : undefined}
          >
            <span class="dot"></span>
            {status
              ? botReporting
                ? "Online"
                : "Bot not reporting"
              : failed
                ? "Unreachable"
                : "Checking…"}
          </span>
          {#if data.bot_name}<span class="pill">Node: {data.bot_name}</span>{/if}
        </div>
        <div class="hero-actions">
          <a class="btn btn-primary" href="#status">
            Live status
            <Icon name="arrow-right" size={16} />
          </a>
          <a class="btn" href={SOURCE} target="_blank" rel="noopener noreferrer">
            Source
            <Icon icon={ArrowUpRight} size={16} />
          </a>
        </div>
      </div>

      <div class="hero-flame" aria-hidden="true">
        <Flame />
      </div>
    </section>

    <section id="status" aria-labelledby="status-title" class="section">
      <div class="page-head">
        <div>
          <h2 id="status-title">Live status</h2>
          <p>Read from this instance every three seconds.</p>
        </div>
      </div>

      {#if failed}
        <Feedback tone="warning" announcement="status">
          Status is not reachable right now. Retrying automatically.
        </Feedback>
      {:else if status && !botReporting}
        <Feedback tone="warning" announcement="status">
          The web server is up, but the bot has not reported its tasks in the last few seconds. It
          may still be starting. Task count and uptime will appear once it does.
        </Feedback>
      {/if}

      <div class="stats" aria-live="off">
        <article class="card stat">
          <header class="stat-head">
            <span class="tile"><Icon icon={Activity} size={17} /></span>
            <h3>Active tasks</h3>
          </header>
          <p class="stat-value">{status?.active_tasks ?? "—"}</p>
          <p class="stat-note">
            {status && !botReporting
              ? "Waiting for the bot to report"
              : "Downloads, uploads and processing in flight"}
          </p>
        </article>
        <article class="card stat">
          <header class="stat-head">
            <span class="tile"><Icon icon={Cpu} size={17} /></span>
            <h3>Server CPU</h3>
          </header>
          <p class="stat-value">{status ? `${pct(status.cpu)}%` : "—"}</p>
          <div class="stat-bar">
            <div
              class="progress"
              role="progressbar"
              aria-label="Server CPU"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={status ? Number(status.cpu) : 0}
              style:--value="{status ? Math.min(100, Number(status.cpu)) : 0}%"
            >
              <span></span>
            </div>
          </div>
        </article>
        <article class="card stat">
          <header class="stat-head">
            <span class="tile"><Icon icon={MemoryStick} size={17} /></span>
            <h3>Memory</h3>
          </header>
          <p class="stat-value">{status ? `${pct(status.ram)}%` : "—"}</p>
          <div class="stat-bar">
            <div
              class="progress"
              role="progressbar"
              aria-label="Memory in use"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={status ? Number(status.ram) : 0}
              style:--value="{status ? Math.min(100, Number(status.ram)) : 0}%"
            >
              <span></span>
            </div>
          </div>
        </article>
        <article class="card stat">
          <header class="stat-head">
            <span class="tile"><Icon icon={Clock} size={17} /></span>
            <h3>Uptime</h3>
          </header>
          <p class="stat-value uptime">{status?.uptime ?? "—"}</p>
          <p class="stat-note">Since the bot last started</p>
        </article>
      </div>
    </section>

    <section id="logs" aria-labelledby="logs-title" class="section">
      <div class="page-head">
        <div>
          <h2 id="logs-title">Live logs</h2>
          <p>The bot's log as it is written, with secrets redacted.</p>
        </div>
        {#if logAccess?.authorized}
          <div class="page-actions">
            <a class="btn" href="/app/logs">
              Open full view <Icon icon={ArrowUpRight} size={16} />
            </a>
          </div>
        {/if}
      </div>

      {#if logAccess === null}
        <div class="skeleton logs-skeleton" aria-hidden="true"></div>
      {:else if logAccess.authorized}
        <LogViewer height="min(55svh, 30rem)" />
      {:else}
        <div class="empty">
          <span class="empty-mark"><Icon icon={Lock} size={22} /></span>
          <h3>Logs are private</h3>
          <p>
            Only the owner and sudo users can read them. Send <code>/log</code> or
            <code>/status</code> to the bot and press <strong>Live logs</strong> for a private
            link{logAccess.login_enabled ? ", or sign in to watch them here" : ""}.
          </p>
          {#if logAccess.login_enabled}
            <a class="btn btn-primary" href="/login?next=/%23logs">
              <Icon name="log-in" size={16} /> Sign in
            </a>
          {/if}
        </div>
      {/if}
    </section>

    <section id="components" aria-labelledby="components-title" class="section">
      <div class="page-head">
        <div>
          <h2 id="components-title">Components</h2>
          <p>The toolkit behind every mirror, leech and stream.</p>
        </div>
      </div>

      <div class="panel components">
        <ul class="rows component-list">
          {#each components as c (c.title)}
            <li class="inset row component">
              <span class="tile"><Icon icon={c.icon} size={17} /></span>
              <div class="row-main">
                <span class="component-head">
                  <span class="row-title">{c.title}</span>
                  <span class="pill">{c.tag}</span>
                </span>
                <span class="component-text">{c.text}</span>
              </div>
            </li>
          {/each}
        </ul>
      </div>
    </section>

    <footer class="foot">
      <span class="foot-brand">© 2026 Amaterasu — Black Sun Infrastructure</span>
      <a href={SOURCE} target="_blank" rel="noopener noreferrer">
        Source on GitHub <Icon icon={ArrowUpRight} size={14} />
      </a>
    </footer>
  </div>
</Shell>

<style>
  .page {
    gap: var(--space-10);
  }

  /* ── Hero: the overview card with the architecture stack ─────── */
  .hero {
    position: relative;
    display: grid;
    grid-template-columns: minmax(0, 1.1fr) minmax(0, 0.9fr);
    gap: var(--space-8);
    align-items: center;
    padding: clamp(1.5rem, 1rem + 2.5vw, 3rem);
    border: var(--border-width) solid transparent;
    border-radius: var(--radius-xl);
    background:
      radial-gradient(
          60% 90% at 100% 0%,
          light-dark(oklch(0.94 0 0 / 0.7), oklch(0.3 0 0 / 0.35)),
          transparent 70%
        )
        padding-box,
      linear-gradient(var(--surface-raised), var(--surface-raised)) padding-box,
      var(--card-edge) border-box;
    box-shadow: var(--shadow-card);
    overflow: hidden;
  }

  /* Light from the upper right, and a diagonal sheen across the hero. */
  .hero::before {
    content: "";
    position: absolute;
    inset: 0;
    pointer-events: none;
    background:
      linear-gradient(115deg, transparent 40%, var(--sheen) 55%, transparent 68%),
      radial-gradient(60% 90% at 100% 0%, var(--glow-accent), transparent 70%);
    opacity: 0.9;
  }

  .hero > * {
    position: relative;
  }

  h1 {
    font-size: var(--text-display);
    font-weight: 520;
    letter-spacing: var(--tracking-display);
    line-height: 0.95;
  }

  .hero-lead {
    margin-top: var(--space-4);
    max-width: 24ch;
    font-size: clamp(1.125rem, 1rem + 0.6vw, 1.5rem);
    line-height: 1.3;
    color: var(--text);
    font-weight: 420;
    letter-spacing: -0.018em;
  }

  .hero-meta {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    margin-top: var(--space-5);
  }

  .hero-actions {
    display: flex;
    gap: var(--space-3);
    flex-wrap: wrap;
    margin-top: var(--space-6);
  }

  /* The flame sits in the right half and its heat lines run off the
     hero's edges (the hero clips them). */
  .hero-flame {
    justify-self: center;
    width: min(100%, 22rem);
    margin-block: var(--space-6);
    pointer-events: none;
  }

  /* ── Sections ────────────────────────────────────────────────── */
  .section {
    display: grid;
    gap: var(--space-4);
    scroll-margin-top: calc(var(--topbar-height) + var(--space-4));
  }

  .section .page-head {
    margin-bottom: 0;
  }

  .logs-skeleton {
    height: 18rem;
    border-radius: var(--radius-lg);
  }

  .stat-bar {
    margin-top: var(--space-2);
  }

  .uptime {
    font-size: clamp(1.5rem, 1.2rem + 1vw, 2.25rem);
  }

  .components {
    padding: var(--space-3);
  }

  .component-list {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .component {
    align-items: flex-start;
    padding: var(--space-4);
  }

  .component-head {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--space-2);
  }

  .component-text {
    margin-top: var(--space-1);
    font-size: var(--text-small);
    color: var(--text-secondary);
    line-height: 1.5;
  }

  .foot {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    padding-top: var(--space-5);
    border-top: var(--border-width) solid var(--line);
    font-size: var(--text-small);
    color: var(--text-muted);
  }

  .foot a {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    min-height: var(--control-height);
    color: var(--text-secondary);
    text-decoration: none;
  }

  .foot a:hover {
    color: var(--text);
  }

  @media (max-width: 64rem) {
    .hero {
      grid-template-columns: minmax(0, 1fr);
    }
    .hero-flame {
      order: -1;
      width: min(60%, 15rem);
      margin-block: var(--space-4) var(--space-2);
    }
  }

  @media (max-width: 48rem) {
    .component-list {
      grid-template-columns: minmax(0, 1fr);
    }
  }

  @media (max-width: 40rem) {
    .stats {
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: var(--space-3);
    }
    .stat {
      padding: var(--space-4);
    }
    .stat-value {
      font-size: 1.75rem;
    }
    .uptime {
      font-size: 1.25rem;
    }
    .components {
      padding: var(--space-2);
    }
  }
</style>
