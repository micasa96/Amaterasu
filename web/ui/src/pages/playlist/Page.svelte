<script lang="ts">
  import Shell, { type NavGroup } from "../../ui/Shell.svelte";
  import Icon from "../../ui/Icon.svelte";
  import Feedback from "../../ui/Feedback.svelte";
  import Progress from "../../ui/Progress.svelte";
  import ListVideo from "@lucide/svelte/icons/list-video";
  import FileArchive from "@lucide/svelte/icons/file-archive";
  import Download from "@lucide/svelte/icons/download";
  import Film from "@lucide/svelte/icons/film";

  interface Item {
    name: string;
    watch_url: string;
    download_url: string;
    poster_url: string;
  }
  interface PlaylistData {
    playlist_name: string;
    playlist_token: string;
    zip_url: string;
    items: Item[];
  }

  let { data }: { data: PlaylistData } = $props();
  const d = (() => data)();
  const items = d.items ?? [];
  const watch = (item: Item) => `${item.watch_url}?list=${encodeURIComponent(d.playlist_token)}`;

  const nav: NavGroup[] = [
    {
      label: "Playlist",
      items: [
        { label: "Files", href: "#files", glyph: ListVideo, current: true },
        { label: "Download as ZIP", href: "#zip", glyph: FileArchive },
      ],
    },
  ];

  // Posters are generated on demand; hide the image and keep the
  // placeholder tile when one fails.
  let brokenPosters = $state<Record<number, boolean>>({});

  // ── ZIP preparation (POST, then poll status_url until ready) ─────
  type ZipState = "idle" | "working" | "ready" | "error";
  let zipState = $state<ZipState>("idle");
  let zipMessage = $state(
    "Prepare one ZIP before downloading. Temporary ZIPs share the server’s cache space and expire after 24 hours.",
  );
  let zipProgress = $state<number | null>(null);
  let zipHref = $state("");

  const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

  async function fetchJSON(url: string, options: RequestInit = {}) {
    const response = await fetch(url, {
      ...options,
      cache: "no-store",
      signal: AbortSignal.timeout(30000),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || "ZIP preparation failed. Try again.");
    return body;
  }

  const mib = (bytes: number) => (bytes / 1048576).toFixed(1);

  async function prepareZip() {
    if (zipState === "working") return;
    zipState = "working";
    zipHref = "";
    zipProgress = null;
    zipMessage = "Checking playlist files…";
    try {
      const ticket = await fetchJSON(d.zip_url, {
        method: "POST",
        headers: { "X-Amaterasu-Action": "archive" },
      });
      if (ticket.stream || !ticket.status_url) {
        zipHref = ticket.download_url;
        zipState = "ready";
        zipMessage = "The ZIP downloads directly as it is built. Interrupted downloads restart from the beginning.";
        return;
      }
      let failures = 0;
      while (true) {
        let state;
        try {
          state = await fetchJSON(ticket.status_url);
          failures = 0;
        } catch (error) {
          if (++failures >= 3) throw error;
          zipMessage = "Connection interrupted. Reconnecting…";
          await wait(2000);
          continue;
        }
        if (state.state === "ready") {
          zipProgress = 1;
          zipHref = ticket.download_url;
          zipState = "ready";
          zipMessage = "Your ZIP is ready. Downloads support pause, resume and multiple connections.";
          break;
        }
        if (state.state !== "preparing") {
          throw new Error("The ZIP expired or preparation failed. Try again.");
        }
        zipProgress = state.total ? Math.min(state.bytes / state.total, 1) : 0;
        zipMessage = `Preparing files: ${mib(state.bytes)} of ${mib(state.total)} MiB`;
        await wait(2000);
      }
    } catch (error) {
      const err = error as Error;
      zipState = "error";
      zipProgress = null;
      zipMessage =
        err.name === "TimeoutError"
          ? "The server took too long. Try preparing the ZIP again."
          : err.message || "ZIP preparation failed. Try again.";
    }
  }
</script>

<Shell place={d.playlist_name} crumbs={["Playlist"]} {nav}>
  <div class="page">
    <header class="page-head">
      <div>
        <h1>{d.playlist_name}</h1>
        <p>
          <span class="num">{items.length}</span>
          {items.length === 1 ? "media file" : "media files"} ready to stream.
        </p>
      </div>
      {#if items.length}
        <div class="page-actions">
          <a class="btn btn-primary" href={watch(items[0])}>
            <Icon name="play" size={16} /> Play from start
          </a>
        </div>
      {/if}
    </header>

    <div class="split playlist-layout">
      <section id="files" aria-labelledby="files-title" class="files">
        <h2 id="files-title" class="visually-hidden">Files</h2>
        <ol class="rows">
          {#each items as item, i (item.watch_url)}
            <li class="inset row item">
              <a class="thumb" href={watch(item)} aria-label="Play {item.name}">
                {#if !brokenPosters[i]}
                  <img
                    src={item.poster_url}
                    alt=""
                    loading="lazy"
                    onerror={() => (brokenPosters = { ...brokenPosters, [i]: true })}
                  />
                {:else}
                  <span class="thumb-fallback"><Icon icon={Film} size={18} /></span>
                {/if}
                <span class="thumb-play" aria-hidden="true"><Icon name="play" size={14} /></span>
              </a>
              <span class="index num" aria-hidden="true">{String(i + 1).padStart(2, "0")}</span>
              <a class="row-main item-link" href={watch(item)}>
                <span class="row-title">{item.name}</span>
              </a>
              <span class="row-actions">
                <a class="btn btn-quiet btn-icon" href={item.download_url} aria-label="Download {item.name}" title="Download">
                  <Icon icon={Download} size={17} />
                </a>
              </span>
            </li>
          {/each}
        </ol>
      </section>

      <aside id="zip" class="card panel-body rim zip" aria-labelledby="zip-title">
        <div class="tile-head">
          <span class="tile"><Icon icon={FileArchive} size={17} /></span>
          <div>
            <h2 id="zip-title">Download as ZIP</h2>
            <p>Every file in one archive.</p>
          </div>
        </div>

        {#if zipState === "error"}
          <Feedback tone="danger">{zipMessage}</Feedback>
        {:else}
          <p class="note" role="status" aria-live="polite">{zipMessage}</p>
        {/if}

        {#if zipState === "working"}
          {#if zipProgress === null}
            <div class="progress indeterminate" role="progressbar" aria-label="ZIP preparation progress"><span></span></div>
          {:else}
            <Progress value={Math.round(zipProgress * 100)} label="ZIP preparation progress" />
          {/if}
        {/if}

        {#if zipState === "ready" && zipHref}
          <a class="btn btn-primary" href={zipHref} download>
            <Icon icon={Download} size={16} /> Download ZIP
          </a>
          <button type="button" class="btn-quiet" onclick={prepareZip}>Prepare again</button>
        {:else}
          <button type="button" class={zipState === "idle" ? "btn-primary" : ""} onclick={prepareZip} disabled={zipState === "working"}>
            {#if zipState === "working"}
              <span class="spinner" aria-hidden="true"></span> Preparing…
            {:else if zipState === "error"}
              Try again
            {:else}
              Prepare playlist ZIP
            {/if}
          </button>
        {/if}
      </aside>
    </div>
  </div>
</Shell>

<style>
  .playlist-layout {
    grid-template-columns: minmax(0, 1fr) minmax(16rem, 20rem);
  }

  @media (max-width: 64rem) {
    .playlist-layout {
      grid-template-columns: minmax(0, 1fr);
    }
    /* On narrow screens the ZIP action comes first; the list is long. */
    .zip {
      order: -1;
    }
  }

  .item {
    gap: var(--space-4);
    padding: var(--space-2);
  }

  .thumb {
    position: relative;
    flex-shrink: 0;
    width: 7.5rem;
    aspect-ratio: 16 / 9;
    border-radius: var(--radius-sm);
    overflow: hidden;
    background: var(--surface-sunken);
    box-shadow: inset 0 0 0 1px var(--line);
  }

  .thumb img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    transition: transform 420ms var(--ease-spring);
  }

  .thumb-fallback {
    display: grid;
    place-items: center;
    width: 100%;
    height: 100%;
    color: var(--text-muted);
  }

  .thumb-play {
    position: absolute;
    right: var(--space-1);
    bottom: var(--space-1);
    display: grid;
    place-items: center;
    width: 1.75rem;
    height: 1.75rem;
    border-radius: 50%;
    background: var(--primary-fill);
    color: var(--button-text);
    box-shadow: 0 4px 12px -4px var(--glow-accent);
    opacity: 0;
    transform: scale(0.9);
    transition:
      opacity var(--transition-fast),
      transform 240ms var(--ease-spring);
  }

  .item:hover .thumb img,
  .thumb:focus-visible img {
    transform: scale(1.04);
  }

  .item:hover .thumb-play,
  .thumb:focus-visible .thumb-play {
    opacity: 1;
    transform: scale(1);
  }

  .index {
    flex-shrink: 0;
    width: 1.75rem;
    color: var(--text-muted);
    font-size: var(--text-xs);
    font-weight: 600;
  }

  .item-link {
    color: inherit;
    text-decoration: none;
  }

  .item-link:hover .row-title {
    text-decoration: underline;
    text-underline-offset: 0.22em;
  }

  .zip {
    align-content: start;
  }

  .zip button,
  .zip .btn {
    width: 100%;
  }

  /* Indeterminate bar while the server counts the files. */
  .indeterminate > span {
    width: 35%;
    animation: indeterminate 1.3s var(--ease-in-out) infinite;
  }

  @keyframes indeterminate {
    from {
      transform: translateX(-100%);
    }
    to {
      transform: translateX(300%);
    }
  }

  @media (max-width: 40rem) {
    .thumb {
      width: 5.5rem;
    }
    .index {
      display: none;
    }
    .item {
      gap: var(--space-3);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .indeterminate > span {
      animation-duration: 2.6s;
    }
  }
</style>
