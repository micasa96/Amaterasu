<script lang="ts">
  import Shell, { type NavGroup } from "../../ui/Shell.svelte";
  import Icon from "../../ui/Icon.svelte";
  import EmptyState from "../../ui/EmptyState.svelte";
  import Feedback from "../../ui/Feedback.svelte";
  import Library from "@lucide/svelte/icons/library";
  import Download from "@lucide/svelte/icons/download";
  import FileVideo from "@lucide/svelte/icons/file-play";
  import BarChart from "@lucide/svelte/icons/chart-no-axes-column";
  import Archive from "@lucide/svelte/icons/archive";
  import HardDrive from "@lucide/svelte/icons/hard-drive";

  interface Item {
    name: string;
    size_label: string;
    mime_type: string;
    watch_url: string;
    download_url: string;
  }
  interface Totals {
    bytes: number;
    downloads: number;
    zip_downloads: number;
    completed: number;
    failed: number;
    incomplete: number;
    persistence: string;
  }
  interface LibraryData {
    items: Item[];
    page: number;
    pages: number;
    total: number;
    query: string;
    user_id: string | number;
    token: string;
    previous: string;
    next: string;
    totals: Totals;
  }

  let { data }: { data: LibraryData } = $props();
  const d = (() => data)();
  const items = d.items ?? [];
  const totals: Totals = d.totals ?? {
    bytes: 0,
    downloads: 0,
    zip_downloads: 0,
    completed: 0,
    failed: 0,
    incomplete: 0,
    persistence: "saved",
  };

  let query = $state(d.query ?? "");

  const count = new Intl.NumberFormat();
  const mib = (bytes: number) =>
    new Intl.NumberFormat(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(
      (bytes || 0) / 1048576,
    );

  const nav: NavGroup[] = [
    {
      label: "Library",
      items: [
        { label: "Files", href: "#files", glyph: Library, current: true },
        { label: "Delivery totals", href: "#totals", glyph: BarChart },
      ],
    },
  ];
</script>

<Shell
  place="Media library"
  {nav}
  note="This private browsing link expires one hour after it was issued."
  dense
>
  <div class="page">
    <header class="page-head">
      <div>
        <h1>Media library</h1>
        <p>
          <span class="num">{count.format(d.total ?? 0)}</span>
          {d.total === 1 ? "indexed file" : "indexed files"}. Open one to stream it, or download it directly.
        </p>
      </div>
    </header>

    <section id="files" class="files" aria-labelledby="files-title">
      <h2 id="files-title" class="visually-hidden">Files</h2>

      <form class="search" action="/library" method="get" role="search">
        <input type="hidden" name="user_id" value={d.user_id} />
        <input type="hidden" name="token" value={d.token} />
        <label class="visually-hidden" for="library-query">Find a file</label>
        <div class="search-field">
          <Icon name="search" size={16} class="search-icon" />
          <input
            id="library-query"
            type="search"
            name="q"
            bind:value={query}
            maxlength="100"
            placeholder="Search by file name"
            autocomplete="off"
          />
        </div>
        <button type="submit" class="btn-primary">Search</button>
      </form>

      {#if items.length}
        <ul class="rows" aria-label="Indexed media">
          {#each items as item (item.watch_url)}
            <li class="inset row">
              <span class="tile tile-sm"><Icon icon={FileVideo} size={15} /></span>
              <a class="row-main file-link" href={item.watch_url}>
                <span class="row-title">{item.name}</span>
                <span class="row-meta num">
                  {[item.size_label, item.mime_type].filter(Boolean).join(" · ")}
                </span>
              </a>
              <span class="row-actions">
                <a class="btn btn-quiet download" href={item.download_url} aria-label="Download {item.name}">
                  <Icon icon={Download} size={16} /><span class="download-text">Download</span>
                </a>
              </span>
            </li>
          {/each}
        </ul>
      {:else if d.query}
        <EmptyState title="No files match “{d.query}”" name="search">
          Try a shorter part of the name.
        </EmptyState>
      {:else}
        <EmptyState title="No indexed files yet" icon={Library}>
          In your private bot chat, send <code>/link index LAST_POST_LINK</code> to scan a channel.
        </EmptyState>
      {/if}

      {#if d.pages > 1}
        <nav class="pager" aria-label="Library pages">
          {#if d.page > 1}
            <a class="btn" href={d.previous} rel="prev"><Icon name="arrow-left" size={16} /> Previous</a>
          {:else}
            <span></span>
          {/if}
          <span class="note num">Page {d.page} of {d.pages}</span>
          {#if d.page < d.pages}
            <a class="btn" href={d.next} rel="next">Next <Icon name="arrow-right" size={16} /></a>
          {:else}
            <span></span>
          {/if}
        </nav>
      {/if}
    </section>

    <section id="totals" class="totals" aria-labelledby="totals-title">
      <h2 id="totals-title" class="panel-title">Lifetime delivery</h2>
      <div class="stats">
        <article class="card stat">
          <header class="stat-head">
            <span class="tile"><Icon icon={HardDrive} size={17} /></span>
            <h3>Delivered</h3>
          </header>
          <p class="stat-value">{mib(totals.bytes)}<span class="unit">MiB</span></p>
        </article>
        <article class="card stat">
          <header class="stat-head">
            <span class="tile"><Icon icon={Download} size={17} /></span>
            <h3>Files downloaded</h3>
          </header>
          <p class="stat-value">{count.format(totals.downloads)}</p>
        </article>
        <article class="card stat">
          <header class="stat-head">
            <span class="tile"><Icon icon={Archive} size={17} /></span>
            <h3>ZIPs downloaded</h3>
          </header>
          <p class="stat-value">{count.format(totals.zip_downloads)}</p>
        </article>
        <article class="card stat">
          <header class="stat-head">
            <span class="tile"><Icon icon={BarChart} size={17} /></span>
            <h3>Requests</h3>
          </header>
          <p class="stat-value">{count.format(totals.completed)}</p>
          <p class="stat-note">
            Completed · <span class="num">{count.format(totals.failed)}</span> failed ·
            <span class="num">{count.format(totals.incomplete)}</span> incomplete
          </p>
        </article>
      </div>
      {#if totals.persistence && totals.persistence !== "saved"}
        <Feedback tone="warning">Totals are currently {totals.persistence}; they may not be saved yet.</Feedback>
      {/if}
    </section>
  </div>
</Shell>

<style>
  .files,
  .totals {
    display: grid;
    gap: var(--space-4);
  }

  .search {
    display: flex;
    gap: var(--space-2);
  }

  .search-field {
    position: relative;
    flex: 1;
    min-width: 0;
  }

  .search-field :global(.search-icon) {
    position: absolute;
    left: var(--space-3);
    top: 50%;
    transform: translateY(-50%);
    color: var(--text-muted);
    pointer-events: none;
  }

  .search-field input {
    padding-left: 2.5rem;
  }

  .file-link {
    color: inherit;
    text-decoration: none;
  }

  .file-link:hover .row-title {
    text-decoration: underline;
    text-underline-offset: 0.22em;
  }

  .row-meta {
    overflow-wrap: anywhere;
  }

  .pager {
    display: grid;
    grid-template-columns: 1fr auto 1fr;
    align-items: center;
    gap: var(--space-3);
  }

  .pager > :first-child {
    justify-self: start;
  }

  .pager > :last-child {
    justify-self: end;
  }

  .unit {
    margin-left: 0.3em;
    font-size: var(--text-ui);
    letter-spacing: 0;
    color: var(--text-muted);
  }

  @media (max-width: 40rem) {
    .download {
      width: var(--control-height);
      padding: 0;
    }
    .download-text {
      display: none;
    }
    .search button {
      padding: 0 var(--space-3);
    }
  }
</style>
