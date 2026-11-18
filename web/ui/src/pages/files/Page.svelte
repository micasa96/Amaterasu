<script lang="ts">
  import { onMount, tick } from "svelte";
  import type { Action } from "svelte/action";
  import Database from "@lucide/svelte/icons/database";
  import FileGlyph from "@lucide/svelte/icons/file";
  import FolderTree from "@lucide/svelte/icons/folder-tree";
  import ListChecks from "@lucide/svelte/icons/list-checks";
  import Repeat from "@lucide/svelte/icons/repeat";
  import CheckCheck from "@lucide/svelte/icons/check-check";
  import KeyRound from "@lucide/svelte/icons/key-round";
  import Shell, { type NavGroup } from "../../ui/Shell.svelte";
  import Icon from "../../ui/Icon.svelte";
  import Feedback from "../../ui/Feedback.svelte";
  import Modal from "../../ui/Modal.svelte";
  import Progress from "../../ui/Progress.svelte";
  import { toast } from "../../lib/toast.svelte";
  import {
    type FileNode,
    type SortBy,
    formatSize,
    nodeSize,
    isChecked,
    isMixed,
    allSelected,
    sortNodes,
    setNode,
    invert,
    syncFolders,
    stats as treeStats,
  } from "./tree";

  // Torrent / TeraBox / rclone file selector (/app/files).
  // Query: gid (task), pin (optional; prefilled from the Telegram link),
  // type = torrent | terabox | rclone. API: /app/files/<type>?gid&pin[&mode]
  //   GET  (torrent: mode=get)        -> {files, engine} or {error, message}
  //   POST (torrent: mode=selection)  body = the full tree JSON
  //   POST (torrent: mode=rename)     body = {old_path, new_path, type}
  let { data: _data }: { data: Record<string, unknown> } = $props();

  const params = new URLSearchParams(location.search);
  const gid = params.get("gid") ?? "";
  const rawType = (params.get("type") || "torrent").toLowerCase();
  const endpoint = ["terabox", "rclone"].includes(rawType) ? rawType : "torrent";
  const typeLabel =
    endpoint === "torrent" ? "Torrent" : endpoint === "terabox" ? "TeraBox" : "rclone";
  // Mid-sentence form: "Choose torrent files", "Choose TeraBox files".
  const typeWord = endpoint === "torrent" ? "torrent" : typeLabel;

  let pin = $state(params.get("pin") ?? "");
  let pinInput = $state<HTMLInputElement | null>(null);
  let unlocking = $state(false);
  let pinError = $state("");

  let files = $state<FileNode[]>([]);
  let loaded = $state(false);
  let allowEdit = $state(false);
  // Opened folders from the top level down; the last is the current folder.
  let trail = $state<FileNode[]>([]);
  let sortBy = $state<SortBy>("name");
  let sortAsc = $state(true);
  let query = $state("");
  let lastSelected: FileNode | null = null;

  let submitting = $state(false);
  let submitError = $state("");

  let renaming = $state<FileNode | null>(null);
  let renameValue = $state("");
  let renameBusy = $state(false);
  let renameError = $state("");

  const current = $derived(trail.length ? trail[trail.length - 1] : null);
  const level = $derived(current ? (current.children ?? []) : files);
  const visible = $derived(
    sortNodes(
      level.filter((n) => !query.trim() || n.name.toLowerCase().includes(query.trim().toLowerCase())),
      sortBy,
      sortAsc,
    ),
  );
  const totals = $derived(treeStats(files));
  const levelAllSelected = $derived(
    level.length > 0 && level.every((n) => (n.type === "folder" ? allSelected(n) : !!n.selected)),
  );
  const everythingSelected = $derived(
    totals.totalCount > 0 && totals.selectedCount === totals.totalCount,
  );

  const nav: NavGroup[] = [
    {
      label: `${typeLabel} task`,
      items: [
        { label: "Selection", href: "#summary", glyph: ListChecks, current: true },
        { label: "Files", href: "#files", icon: "folder" },
      ],
    },
  ];

  function filesApiUrl(mode: "get" | "selection" | "rename") {
    const base = `/app/files/${endpoint}?gid=${encodeURIComponent(gid)}&pin=${encodeURIComponent(pin)}`;
    return endpoint === "torrent" ? `${base}&mode=${mode}` : base;
  }

  async function unlock(e?: SubmitEvent) {
    e?.preventDefault();
    pinInput?.blur();
    pinError = "";
    if (!pin) {
      pinError = "Enter the PIN from the Telegram message.";
      pinInput?.focus();
      return;
    }
    if (!gid) {
      pinError = "This link has no task ID (gid). Open the selector from the Telegram message again.";
      return;
    }
    unlocking = true;
    try {
      const res = await fetch(filesApiUrl("get"));
      let body: { files?: FileNode[]; engine?: string; error?: string; message?: string } | null =
        null;
      try {
        body = await res.json();
      } catch {
        body = null;
      }
      if (!res.ok) {
        pinError = body?.message || `The server answered with status ${res.status}. Try again.`;
      } else if (body?.error) {
        pinError = body.message || body.error;
      } else {
        files = body?.files ?? [];
        allowEdit = body?.engine === "qbittorrent";
        trail = [];
        loaded = true;
      }
    } catch (err) {
      pinError = `Could not reach the server: ${(err as Error).message}`;
    } finally {
      unlocking = false;
      if (pinError) pinInput?.focus();
    }
  }

  function afterChange() {
    syncFolders(files);
  }

  function toggle(node: FileNode, shiftKey = false) {
    const shouldSelect = node.type === "folder" ? !allSelected(node) : !node.selected;
    const nodes = visible;
    const start = shiftKey && lastSelected ? nodes.findIndex((n) => n.id === lastSelected!.id) : -1;
    const end = nodes.findIndex((n) => n.id === node.id);
    if (start !== -1 && end !== -1) {
      for (let i = Math.min(start, end); i <= Math.max(start, end); i++) {
        setNode(nodes[i], shouldSelect);
      }
    } else {
      setNode(node, shouldSelect);
    }
    lastSelected = node;
    afterChange();
  }

  function selectLevel() {
    const value = !levelAllSelected;
    level.forEach((n) => setNode(n, value));
    afterChange();
  }

  function invertLevel() {
    level.forEach(invert);
    afterChange();
  }

  function selectEverything() {
    const value = !files.every((n) => (n.type === "folder" ? allSelected(n) : !!n.selected));
    files.forEach((n) => setNode(n, value));
    afterChange();
  }

  function setSort(type: SortBy) {
    if (sortBy === type) sortAsc = !sortAsc;
    else {
      sortBy = type;
      sortAsc = type === "name";
    }
  }

  async function openFolder(folder: FileNode) {
    trail = [...trail, folder];
    query = "";
    await tick();
    document.getElementById("files-heading")?.focus({ preventScroll: true });
  }

  function goTo(depth: number) {
    trail = trail.slice(0, depth);
  }

  function parentPath(): string {
    return trail.map((f) => f.name).join("/");
  }

  function openRename(node: FileNode) {
    renaming = node;
    renameValue = node.name;
    renameError = "";
  }

  async function saveRename(e?: SubmitEvent) {
    e?.preventDefault();
    const node = renaming;
    if (!node) return;
    const newName = renameValue.trim();
    if (!newName || newName === node.name) {
      renaming = null;
      return;
    }
    const full = parentPath();
    const body = {
      old_path: full ? `${full}/${node.name}` : node.name,
      new_path: full ? `${full}/${newName}` : newName,
      type: node.type,
    };
    renameBusy = true;
    renameError = "";
    try {
      const res = await fetch(filesApiUrl("rename"), { method: "POST", body: JSON.stringify(body) });
      if (res.ok) {
        node.name = newName;
        renaming = null;
        toast.show("Rename submitted.");
      } else {
        renameError = `The rename was not accepted (status ${res.status}). Check the name and try again.`;
      }
    } catch (err) {
      renameError = `Could not reach the server: ${(err as Error).message}`;
    } finally {
      renameBusy = false;
    }
  }

  async function submit() {
    submitError = "";
    if (totals.selectedCount === 0) {
      submitError = "Select at least one file before submitting.";
      return;
    }
    submitting = true;
    try {
      const res = await fetch(filesApiUrl("selection"), {
        method: "POST",
        body: JSON.stringify($state.snapshot(files)),
      });
      if (res.ok) toast.show("Selection submitted. The download continues with these files.");
      else submitError = `The selection was not accepted (status ${res.status}). Try again.`;
    } catch (err) {
      submitError = `Could not reach the server: ${(err as Error).message}`;
    } finally {
      submitting = false;
    }
  }

  // Checkbox state is derived from the tree; keep the DOM in step with it
  // (including indeterminate, which has no attribute).
  const checkState: Action<HTMLInputElement, { checked: boolean; mixed: boolean }> = (
    el,
    value,
  ) => {
    const apply = (v: { checked: boolean; mixed: boolean }) => {
      el.checked = v.checked;
      el.indeterminate = v.mixed;
    };
    apply(value);
    return { update: apply };
  };

  function onRowClick(e: MouseEvent, node: FileNode) {
    const target = e.target as HTMLElement;
    if (target.closest("button, a, input")) return;
    toggle(node, e.shiftKey);
  }

  function onCheckClick(e: MouseEvent, node: FileNode) {
    e.preventDefault();
    toggle(node, e.shiftKey);
    const el = e.currentTarget as HTMLInputElement;
    // preventDefault restores the old state after this handler; re-apply.
    setTimeout(() => {
      el.checked = isChecked(node);
      el.indeterminate = isMixed(node);
    });
  }

  onMount(() => {
    if (pin) void unlock();
    else pinInput?.focus();
  });
</script>

<Shell
  place="{typeLabel} file selection"
  {nav}
  note="Only the files you keep selected are downloaded. The PIN came with the Telegram message."
  dense
>
  {#if !loaded}
    <section class="page page-narrow unlock" aria-labelledby="unlock-title">
      <header class="page-head">
        <div>
          <h1 id="unlock-title">Choose {typeWord} files</h1>
          <p>Enter the PIN from your Telegram message to open this task's files.</p>
        </div>
      </header>

      <form class="card panel-body unlock-card rim" onsubmit={unlock}>
        <div class="tile-head">
          <span class="tile"><Icon icon={KeyRound} size={17} /></span>
          <div>
            <h2>Unlock the file list</h2>
            <p>Task <span class="key">{gid || "missing"}</span></p>
          </div>
        </div>
        <div class="field">
          <label for="pin">PIN</label>
          <input
            bind:this={pinInput}
            bind:value={pin}
            id="pin"
            type="password"
            autocomplete="one-time-code"
            inputmode="text"
            aria-invalid={pinError ? "true" : undefined}
            aria-describedby={pinError ? "pin-error" : "pin-hint"}
          />
          <p class="note" id="pin-hint">The code the bot sent with this link.</p>
        </div>
        {#if pinError}
          <div id="pin-error"><Feedback tone="danger" announcement="alert">{pinError}</Feedback></div>
        {/if}
        <div class="settings-form-actions">
          <button type="submit" class="btn btn-primary" disabled={unlocking}>
            {#if unlocking}<span class="spinner" aria-hidden="true"></span> Opening…{:else}Open files{/if}
          </button>
        </div>
      </form>
    </section>
  {:else}
    <div class="page">
      <header class="page-head">
        <div>
          <h1 id="summary" tabindex="-1">Choose {typeWord} files</h1>
          <p>Select what to download, then submit the list. Unselected files are skipped.</p>
        </div>
        <div class="page-actions">
          <span class="pill" data-tone="success"><span class="dot"></span>Unlocked</span>
        </div>
      </header>

      <div class="stats">
        <article class="card stat">
          <header class="stat-head">
            <span class="tile"><Icon icon={FileGlyph} size={17} /></span>
            <h3>Selected files</h3>
          </header>
          <p class="stat-value">
            {totals.selectedCount}<span class="of">&nbsp;/&nbsp;{totals.totalCount}</span>
          </p>
          <p class="stat-note">{totals.totalCount - totals.selectedCount} skipped</p>
        </article>
        <article class="card stat">
          <header class="stat-head">
            <span class="tile"><Icon icon={Database} size={17} /></span>
            <h3>Download size</h3>
          </header>
          <p class="stat-value">{formatSize(totals.selectedSize)}</p>
          <div class="stat-bar">
            <Progress
              value={totals.selectedSize}
              max={totals.totalSize || 1}
              label="Selected size of total"
            />
            <p class="stat-note">of {formatSize(totals.totalSize)} in this task</p>
          </div>
        </article>
      </div>

      <section class="card browser" aria-labelledby="files-heading" id="files">
        <div class="panel-head browser-head">
          <nav class="path" aria-label="Folder path">
            <Icon icon={FolderTree} size={16} />
            {#if trail.length === 0}
              <h2 class="panel-title" id="files-heading" tabindex="-1">All files</h2>
            {:else}
              <button type="button" class="crumb-btn" onclick={() => goTo(0)}>All files</button>
              {#each trail as folder, i (i)}
                <Icon name="chevron-right" size={14} class="sep" />
                {#if i === trail.length - 1}
                  <h2 class="panel-title truncate" id="files-heading" tabindex="-1">{folder.name}</h2>
                {:else}
                  <button type="button" class="crumb-btn truncate" onclick={() => goTo(i + 1)}>{folder.name}</button>
                {/if}
              {/each}
            {/if}
          </nav>
        </div>

        <div class="toolbar">
          <div class="search">
            <Icon name="search" size={16} />
            <input
              id="fileSearch"
              type="search"
              bind:value={query}
              placeholder="Search this folder"
              aria-label="Search files in the current folder"
            />
          </div>
          <div class="segmented" role="group" aria-label="Sort">
            <button type="button" aria-pressed={sortBy === "name"} onclick={() => setSort("name")}>
              Name
              {#if sortBy === "name"}<Icon name={sortAsc ? "arrow-up" : "arrow-down"} size={13} />{/if}
              <span class="visually-hidden">{sortBy === "name" ? (sortAsc ? "ascending" : "descending") : ""}</span>
            </button>
            <button type="button" aria-pressed={sortBy === "size"} onclick={() => setSort("size")}>
              Size
              {#if sortBy === "size"}<Icon name={sortAsc ? "arrow-up" : "arrow-down"} size={13} />{/if}
              <span class="visually-hidden">{sortBy === "size" ? (sortAsc ? "ascending" : "descending") : ""}</span>
            </button>
          </div>
          <div class="cluster bulk">
            <button type="button" class="btn-quiet" onclick={selectLevel} disabled={!level.length}>
              <Icon icon={ListChecks} size={16} />
              {levelAllSelected ? "Deselect folder" : "Select folder"}
            </button>
            <button type="button" class="btn-quiet" onclick={invertLevel} disabled={!level.length}>
              <Icon icon={Repeat} size={16} /> Invert
            </button>
            <button type="button" class="btn-quiet" onclick={selectEverything} disabled={!totals.totalCount}>
              <Icon icon={CheckCheck} size={16} />
              {everythingSelected ? "Deselect everything" : "Select everything"}
            </button>
          </div>
        </div>

        <ul class="rows file-rows" aria-label="Files and folders">
          {#if trail.length}
            <li>
              <button type="button" class="inset row back" onclick={() => goTo(trail.length - 1)}>
                <span class="tile tile-sm"><Icon name="arrow-left" size={15} /></span>
                <span class="row-title">Back to {trail.length > 1 ? trail[trail.length - 2].name : "all files"}</span>
              </button>
            </li>
          {/if}
          {#each visible as node (node.type + ":" + node.id)}
            {@const checked = isChecked(node)}
            {@const mixed = isMixed(node)}
            <li>
              <!-- The whole row is a pointer shortcut; the checkbox is the
                   keyboard and screen-reader control. -->
              <!-- svelte-ignore a11y_click_events_have_key_events -->
              <div
                role="presentation"
                class="inset row file-row"
                class:is-folder={node.type === "folder"}
                class:is-off={!checked && !mixed}
                onclick={(e) => onRowClick(e, node)}
              >
                <input
                  type="checkbox"
                  id="node-{node.type}-{node.id}"
                  use:checkState={{ checked, mixed }}
                  onclick={(e) => onCheckClick(e, node)}
                  aria-label="{checked ? 'Deselect' : 'Select'} {node.name}"
                />
                <span class="tile tile-sm" class:file-tile={node.type === "file"}>
                  {#if node.type === "folder"}
                    <Icon name="folder" size={15} />
                  {:else}
                    <Icon icon={FileGlyph} size={15} />
                  {/if}
                </span>
                <span class="row-main">
                  {#if node.type === "folder"}
                    <button type="button" class="name-btn row-title" onclick={() => openFolder(node)}>
                      {node.name}
                    </button>
                    <span class="row-meta">
                      {(node.children ?? []).length} item{(node.children ?? []).length === 1 ? "" : "s"}
                      {#if mixed}· partly selected{/if}
                    </span>
                  {:else}
                    <span class="row-title">{node.name}</span>
                    {#if node.progress !== undefined && node.progress !== null}
                      <span class="row-progress">
                        <Progress value={node.progress} label="Downloaded of {node.name}" />
                        <span class="num">{Math.round(node.progress * 10) / 10}%</span>
                      </span>
                    {/if}
                  {/if}
                </span>
                <span class="size num">{formatSize(nodeSize(node))}</span>
                <span class="row-actions">
                  {#if allowEdit}
                    <button
                      type="button"
                      class="btn-quiet btn-icon"
                      aria-label="Rename {node.name}"
                      title="Rename"
                      onclick={() => openRename(node)}
                    >
                      <Icon name="pencil" size={15} />
                    </button>
                  {/if}
                  {#if node.type === "folder"}
                    <button
                      type="button"
                      class="btn-quiet btn-icon"
                      aria-label="Open {node.name}"
                      title="Open folder"
                      onclick={() => openFolder(node)}
                    >
                      <Icon name="chevron-right" size={16} />
                    </button>
                  {/if}
                </span>
              </div>
            </li>
          {/each}
        </ul>

        {#if visible.length === 0}
          <div class="empty-wrap">
            <div class="empty">
              <span class="empty-mark"><Icon name="search" size={22} /></span>
              {#if query.trim()}
                <h3>Nothing matches “{query.trim()}”</h3>
                <p>Search looks at names in this folder only.</p>
                <button type="button" onclick={() => (query = "")}>Clear search</button>
              {:else}
                <h3>This folder is empty</h3>
                <p>There are no files to select here.</p>
              {/if}
            </div>
          </div>
        {/if}

        <footer class="submit-bar">
          <p class="submit-summary">
            <strong class="num">{totals.selectedCount}</strong> of
            <span class="num">{totals.totalCount}</span> files ·
            <span class="num">{formatSize(totals.selectedSize)}</span>
            <span class="hint">Shift-click selects a range.</span>
          </p>
          <button type="button" class="btn btn-primary" onclick={submit} disabled={submitting}>
            {#if submitting}<span class="spinner" aria-hidden="true"></span> Submitting…{:else}<Icon name="circle-check" size={16} /> Submit selection{/if}
          </button>
        </footer>
        {#if submitError}
          <div class="submit-error"><Feedback tone="danger" announcement="alert">{submitError}</Feedback></div>
        {/if}
      </section>
    </div>
  {/if}
</Shell>

{#if renaming}
  <Modal
    title="Rename {renaming.type === 'folder' ? 'folder' : 'file'}"
    description="The new name is applied inside the torrent client."
    onclose={() => (renaming = null)}
  >
    <form class="form-grid" onsubmit={saveRename}>
      <div class="field">
        <label for="rename-input">Name</label>
        <input id="rename-input" type="text" bind:value={renameValue} disabled={renameBusy} />
      </div>
      {#if renameError}<Feedback tone="danger" announcement="alert">{renameError}</Feedback>{/if}
      <div class="dialog-actions">
        <button type="button" class="btn-quiet" onclick={() => (renaming = null)}>Cancel</button>
        <button type="submit" class="btn btn-primary" disabled={renameBusy || !renameValue.trim()}>
          {renameBusy ? "Saving…" : "Save name"}
        </button>
      </div>
    </form>
  </Modal>
{/if}

<style>
  .unlock-card {
    gap: var(--space-5);
  }

  .of {
    font-size: 1.25rem;
    color: var(--text-muted);
    letter-spacing: -0.02em;
  }

  .stat-bar {
    display: grid;
    gap: var(--space-2);
  }

  /* ── Browser panel ─────────────────────────────────────────── */
  .browser {
    overflow: clip;
  }

  .browser-head {
    min-height: 3.25rem;
  }

  .path {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    min-width: 0;
    color: var(--text-muted);
  }

  .path :global(.sep) {
    opacity: 0.7;
    flex-shrink: 0;
  }

  .crumb-btn {
    min-height: 2rem;
    padding: 0 var(--space-2);
    margin: 0 calc(var(--space-2) * -1);
    border: 0;
    background: none;
    box-shadow: none;
    color: var(--text-secondary);
    font-size: var(--text-small);
    font-weight: 540;
    flex-shrink: 1;
    display: block;
    max-width: 14rem;
    white-space: nowrap;
  }

  .crumb-btn:hover:not(:disabled) {
    background: var(--hover);
    color: var(--text);
  }

  .toolbar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2) var(--space-3);
    padding: var(--space-3) var(--space-5);
    border-bottom: var(--border-width) solid var(--line);
  }

  .search {
    position: relative;
    flex: 1 1 14rem;
    min-width: min(100%, 12rem);
  }

  .search :global(.svg-icon) {
    position: absolute;
    left: var(--space-3);
    top: 50%;
    transform: translateY(-50%);
    color: var(--text-muted);
    pointer-events: none;
  }

  .search input {
    padding-left: 2.25rem;
  }

  .segmented button {
    gap: var(--space-1);
  }

  .bulk {
    gap: var(--space-1);
  }

  .bulk button {
    padding: 0 var(--space-3);
    font-size: var(--text-small);
  }

  /* ── Rows ──────────────────────────────────────────────────── */
  .file-rows {
    padding: var(--space-3) var(--space-3) var(--space-2);
    max-height: min(64vh, 40rem);
    overflow-y: auto;
    overscroll-behavior: contain;
  }

  .file-row {
    cursor: pointer;
    user-select: none;
  }

  .file-row input[type="checkbox"] {
    flex-shrink: 0;
  }

  .file-row.is-off .row-title {
    color: var(--text-secondary);
  }

  .file-row.is-off .file-tile {
    opacity: 0.6;
  }

  .is-folder .row-title {
    font-weight: 580;
  }

  .name-btn {
    justify-content: flex-start;
    min-height: auto;
    padding: 0;
    border: 0;
    background: none;
    box-shadow: none;
    text-align: left;
  }

  .name-btn:hover:not(:disabled) {
    --veil: transparent;
    text-decoration: underline;
    text-underline-offset: 0.22em;
  }

  .row-progress {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    max-width: 16rem;
    margin-top: var(--space-1);
    font-size: var(--text-xs);
    color: var(--text-muted);
  }

  .row-progress :global(.progress) {
    flex: 1;
    height: 0.375rem;
  }

  .size {
    flex-shrink: 0;
    min-width: 5.5rem;
    text-align: right;
    font-size: var(--text-small);
    color: var(--text-secondary);
  }

  .row-actions {
    min-width: var(--control-height);
    justify-content: flex-end;
  }

  .back {
    width: 100%;
    justify-content: flex-start;
    text-align: left;
    box-shadow: none;
    font-weight: 540;
  }

  .empty-wrap {
    padding: 0 var(--space-3) var(--space-3);
  }

  /* ── Submit bar ────────────────────────────────────────────── */
  .submit-bar {
    position: sticky;
    bottom: 0;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    padding: var(--space-3) var(--space-5);
    border-top: var(--border-width) solid var(--line);
    background: var(--surface-raised);
  }

  .submit-summary {
    color: var(--text-secondary);
    font-size: var(--text-small);
  }

  .hint {
    margin-left: var(--space-2);
    color: var(--text-muted);
  }

  .submit-error {
    padding: 0 var(--space-5) var(--space-4);
  }

  @media (pointer: coarse) {
    .hint {
      display: none;
    }
  }

  /* ── Phone: two-line rows, full-width actions ──────────────── */
  @media (max-width: 40rem) {
    .toolbar {
      padding: var(--space-3) var(--space-4);
    }

    .bulk {
      width: 100%;
    }

    .bulk button {
      flex: 1 1 auto;
    }

    .file-rows {
      max-height: none;
      overflow: visible;
      padding: var(--space-2);
    }

    .file-row {
      display: grid;
      grid-template-columns: auto auto minmax(0, 1fr) auto;
      grid-template-areas:
        "check tile main actions"
        "check tile size actions";
      column-gap: var(--space-3);
      row-gap: 0;
    }

    .file-row > input {
      grid-area: check;
    }
    .file-row > .tile {
      grid-area: tile;
    }
    .file-row > .row-main {
      grid-area: main;
    }
    .file-row > .size {
      grid-area: size;
      text-align: left;
      min-width: 0;
      font-size: var(--text-xs);
      color: var(--text-muted);
    }
    .file-row > .row-actions {
      grid-area: actions;
      width: auto;
    }

    .submit-bar {
      padding: var(--space-3) var(--space-4);
      padding-bottom: max(var(--space-3), env(safe-area-inset-bottom));
    }

    .submit-bar .btn {
      width: 100%;
    }

    .hint {
      display: none;
    }
  }
</style>
