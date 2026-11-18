<script lang="ts">
  import { flushSync, onMount, tick, untrack } from "svelte";
  import ChevronUp from "@lucide/svelte/icons/chevron-up";
  import GripVertical from "@lucide/svelte/icons/grip-vertical";
  import KeyRound from "@lucide/svelte/icons/key-round";
  import ListOrdered from "@lucide/svelte/icons/list-ordered";
  import Film from "@lucide/svelte/icons/film";
  import Shell, { type NavGroup } from "../../ui/Shell.svelte";
  import Icon from "../../ui/Icon.svelte";
  import {
    type Plan,
    type PlanItem,
    compareEpisode,
    collator,
    detailFor,
    durationLabel,
    modeLabel,
    pendingLabel,
    statusLabel,
    statusTone,
  } from "./plan";

  // Merge planner: the person orders the parts of a merged video before
  // processing starts. The server is authoritative for the item list and the
  // lock; the page keeps local edits (dirty) across polls, saves every change
  // automatically, and reports conflicts instead of overwriting them.
  let { data }: { data: { plan_id?: string } } = $props();
  const planId = untrack(() => String(data.plan_id ?? ""));

  const params = new URLSearchParams(location.hash.slice(1));
  const legacyParams = new URLSearchParams(location.search);
  let pin = params.get("pin") || legacyParams.get("pin") || "";
  if (legacyParams.has("pin")) {
    legacyParams.delete("pin");
    history.replaceState(
      null,
      "",
      `${location.pathname}?${legacyParams}#pin=${encodeURIComponent(pin)}`,
    );
  }

  // ── View state ───────────────────────────────────────────────────
  let view = $state<"connecting" | "auth" | "error" | "planner">("connecting");
  let current = $state<Plan | null>(null);
  let order = $state<string[]>([]);
  let dirty = $state(false);
  let conflict = $state(false);
  let saving = $state(false);
  let dragging = $state<string | null>(null);
  let dropTarget = $state<string | null>(null);
  let saveText = $state("Up to date");
  let stateText = $state("Connecting");
  let stateKey = $state("");
  let notice = $state(
    "Downloads continue in the background. If you leave this page, Amaterasu uses the latest saved order.",
  );
  let noticeTone = $state<"neutral" | "warning" | "danger">("neutral");
  let authHint = $state("Enter the 12-character code from Telegram.");
  let errorText = $state("This merge plan is no longer available.");
  let pinValue = $state("");
  let pinInput = $state<HTMLInputElement | null>(null);
  let listEl = $state<HTMLOListElement | null>(null);

  // Plain bookkeeping (not rendered).
  let retryTimer: ReturnType<typeof setTimeout> | null = null;
  let pollTimer: ReturnType<typeof setTimeout> | undefined;
  let loading = false;
  let editRevision = 0;
  let authenticated = false;
  let unavailable = false;
  let pendingSave = false;

  const items = $derived(new Map((current?.items ?? []).map((i) => [i.id, i])));
  const locked = $derived(!!current?.locked);
  const showSave = $derived(!saving && (dirty || conflict) && !locked);
  const terminal = () =>
    !!current && ["completed", "failed", "cancelled", "interrupted"].includes(current.status);

  const apiUrl = () => `/api/merge-plan/${encodeURIComponent(planId)}`;
  const authHeaders = () => ({ "X-Merge-Plan-Pin": pin });
  const request = (options: RequestInit = {}) =>
    fetch(apiUrl(), { cache: "no-store", ...options, signal: AbortSignal.timeout(15000) });

  const nav: NavGroup[] = [
    {
      label: "Planner",
      items: [
        { label: "Order", href: "#order", glyph: ListOrdered, current: true },
        { label: "Summary", href: "#summary", glyph: Film },
      ],
    },
  ];

  // ── Views ────────────────────────────────────────────────────────
  function showError(message: string) {
    view = "error";
    errorText = message;
  }

  async function showAuth(message = "Enter the 12-character code from Telegram.") {
    authenticated = false;
    if (retryTimer) clearTimeout(retryTimer);
    retryTimer = null;
    pendingSave = false;
    view = "auth";
    authHint = message;
    stateText = "PIN required";
    await tick();
    pinInput?.focus();
  }

  /** Keep keyboard focus on the control that had it across list updates. */
  async function keepFocus() {
    const focused = document.activeElement as HTMLElement | null;
    const label = focused?.getAttribute("aria-label");
    await tick();
    if (focused && document.activeElement !== focused) {
      const again =
        (focused.isConnected && focused) ||
        (label ? listEl?.querySelector<HTMLElement>(`[aria-label="${CSS.escape(label)}"]`) : null);
      again?.focus({ preventScroll: true });
    }
  }

  function edited() {
    dirty = true;
    editRevision += 1;
    void saveOrder();
  }

  function move(id: string, direction: -1 | 1) {
    if (locked) return;
    const index = order.indexOf(id);
    const to = index + direction;
    if (index < 0 || to < 0 || to >= order.length) return;
    const next = [...order];
    [next[index], next[to]] = [next[to], next[index]];
    void keepFocus();
    order = next;
    edited();
  }

  function sort(kind: "input" | "filename" | "episode" | "reverse") {
    if (!current || locked) return;
    const rows = order.map((id) => items.get(id)).filter(Boolean) as PlanItem[];
    switch (kind) {
      case "input":
        rows.sort((a, b) => Number(a.original_index || 0) - Number(b.original_index || 0));
        break;
      case "filename":
        rows.sort((a, b) => collator.compare(a.name || "", b.name || ""));
        break;
      case "episode":
        rows.sort(compareEpisode);
        break;
      case "reverse":
        rows.reverse();
        break;
    }
    order = rows.map((r) => r.id);
    edited();
  }

  function syncRows(plan: Plan) {
    const serverIds = plan.items.map((item) => item.id);
    const known = new Set(serverIds);
    const keepLocal = (dirty || dragging) && !plan.locked;
    const desired = keepLocal ? order.filter((id) => known.has(id)) : [...serverIds];
    if (keepLocal) {
      for (const id of serverIds) {
        if (desired.includes(id)) continue;
        const sourceIndex = serverIds.indexOf(id);
        const previous = serverIds
          .slice(0, sourceIndex)
          .reverse()
          .find((other) => desired.includes(other));
        desired.splice(previous ? desired.indexOf(previous) + 1 : 0, 0, id);
        conflict = true;
      }
    }
    if (desired.join("\u0000") !== order.join("\u0000")) {
      void keepFocus();
      order = desired;
    }
  }

  function render(plan: Plan) {
    if (dirty && current && plan.order_revision !== current.order_revision) conflict = true;
    if (plan.locked && dirty) {
      dirty = false;
      conflict = false;
      saveText = "Order locked";
    }
    current = plan;
    unavailable = false;
    authenticated = true;
    view = "planner";
    if (plan.locked) {
      if (retryTimer) clearTimeout(retryTimer);
      retryTimer = null;
      pendingSave = false;
      saveText = "Order locked";
    }
    stateKey = plan.status;
    stateText = statusLabel(plan.status);
    syncRows(plan);
    const problem = plan.error || plan.inventory_error;
    notice =
      problem ||
      (plan.locked
        ? plan.status === "completed"
          ? "Merge completed. Open Telegram for your uploaded video."
          : "Processing has started. The saved order is now locked."
        : conflict
          ? "The file list or saved order changed. Review your unsaved order, then save it again."
          : "Downloads continue in the background. If you leave this page, Amaterasu uses the latest saved order.");
    noticeTone = problem ? "danger" : conflict && !plan.locked ? "warning" : "neutral";
    if (!plan.locked && !conflict && dirty) saveText = "Unsaved order";
  }

  // ── Server ───────────────────────────────────────────────────────
  async function loadPlan() {
    if (saving || dragging || loading) return;
    if (!pin) return showAuth();
    loading = true;
    try {
      const response = await request({ headers: authHeaders() });
      if (response.status === 403)
        return showAuth("That code is incorrect. Tap Pincode in Telegram and try again.");
      const body = await response.json();
      if (!response.ok) {
        if (response.status === 404) unavailable = true;
        return showError(body.message || "Unable to load the merge plan. Try again.");
      }
      if (saving || dragging) return;
      if (current && body.revision < current.revision) return;
      render(body as Plan);
    } catch {
      saveText = "Reconnecting";
      stateText = "Reconnecting";
      if (!current) showError("Could not connect. Check your connection and try again.");
    } finally {
      loading = false;
    }
  }

  async function saveOrder(): Promise<void> {
    if (!current || current.locked || !authenticated || conflict) return;
    if (saving) {
      pendingSave = true;
      return;
    }
    saving = true;
    saveText = "Saving…";
    const sentOrder = [...order];
    const sentRevision = editRevision;
    try {
      const response = await request({
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ order: sentOrder, order_revision: current.order_revision }),
      });
      if (response.status === 403)
        return void showAuth(
          "Your planner code was rejected. Enter the code from Telegram again.",
        );
      const body = await response.json();
      if (!response.ok) {
        if (response.status === 409 && body.plan) {
          saveText = "Review order";
          conflict = true;
          pendingSave = false;
          render(body.plan as Plan);
        } else {
          saveText = "Not saved";
          notice = body.message || "Could not save. Try saving again.";
          noticeTone = "danger";
        }
      } else {
        current = body as Plan;
        dirty = editRevision !== sentRevision;
        conflict = false;
        pendingSave = dirty;
        saveText = dirty ? "Saving latest order…" : "Up to date";
        render(body as Plan);
      }
    } catch {
      saveText = "Retrying";
      pendingSave = true;
      retryTimer = setTimeout(() => {
        retryTimer = null;
        if (pendingSave) {
          pendingSave = false;
          void saveOrder();
        }
      }, 1500);
    } finally {
      saving = false;
      if (pendingSave && !retryTimer) {
        pendingSave = false;
        void saveOrder();
      }
    }
  }

  function saveCurrent() {
    if (!current || current.locked) return;
    conflict = false;
    dirty = true;
    void saveOrder();
  }

  function submitPin(event: SubmitEvent) {
    event.preventDefault();
    const value = pinValue.trim();
    if (!/^[A-Za-z0-9_-]{12}$/.test(value)) {
      authHint = "The code has 12 letters, numbers, dashes or underscores.";
      return;
    }
    pin = value;
    params.set("pin", pin);
    history.replaceState(null, "", `${location.pathname}${location.search}#${params}`);
    void loadPlan().finally(() => schedulePoll());
  }

  function retry() {
    void loadPlan().finally(() => schedulePoll());
  }

  function schedulePoll(delay = document.hidden ? 10000 : 3000) {
    clearTimeout(pollTimer);
    pollTimer = setTimeout(async () => {
      await loadPlan();
      if (!terminal() && !unavailable && pin && view !== "auth") schedulePoll();
    }, delay);
  }

  // ── Dragging: mouse (HTML drag and drop) and touch/pen (pointer) ──
  function insertNear(id: string, targetId: string, clientY: number, row: HTMLElement) {
    if (id === targetId) return;
    const rect = row.getBoundingClientRect();
    const before = clientY < rect.top + rect.height / 2;
    const next = order.filter((x) => x !== id);
    const at = next.indexOf(targetId) + (before ? 0 : 1);
    next.splice(at, 0, id);
    if (next.join("\u0000") !== order.join("\u0000")) order = next;
  }

  function finishDrag() {
    if (!dragging) return;
    dragging = null;
    dropTarget = null;
    edited();
  }

  function onDragStart(event: DragEvent, id: string) {
    if (locked) return event.preventDefault();
    dragging = id;
    event.dataTransfer?.setData("text/plain", id);
    if (event.dataTransfer) event.dataTransfer.effectAllowed = "move";
  }

  function onDragOver(event: DragEvent, id: string) {
    if (!dragging || dragging === id) return;
    event.preventDefault();
    dropTarget = id;
    insertNear(dragging, id, event.clientY, event.currentTarget as HTMLElement);
  }

  function onHandleDown(event: PointerEvent, id: string) {
    if (event.pointerType === "mouse" || locked) return;
    dragging = id;
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
    event.preventDefault();
  }

  function onHandleMove(event: PointerEvent) {
    if (!dragging || event.pointerType === "mouse") return;
    const handle = event.currentTarget as HTMLElement;
    const row = document
      .elementFromPoint(event.clientX, event.clientY)
      ?.closest<HTMLElement>(".merge-row");
    const targetId = row?.dataset.id;
    if (!row || !targetId || targetId === dragging) return;
    insertNear(dragging, targetId, event.clientY, row);
    // Moving the row releases pointer capture; keep the drag's end event.
    flushSync();
    if (handle.isConnected) handle.setPointerCapture(event.pointerId);
  }

  function onHandleUp(event: PointerEvent) {
    if (!dragging || event.pointerType === "mouse") return;
    finishDrag();
  }

  onMount(() => {
    const onUnload = (event: BeforeUnloadEvent) => {
      if (!dirty || current?.locked) return;
      event.preventDefault();
      event.returnValue = "";
    };
    const onVisible = () => {
      if (!document.hidden) schedulePoll(0);
    };
    window.addEventListener("beforeunload", onUnload);
    document.addEventListener("visibilitychange", onVisible);
    void loadPlan().finally(() => schedulePoll());
    return () => {
      clearTimeout(pollTimer);
      if (retryTimer) clearTimeout(retryTimer);
      window.removeEventListener("beforeunload", onUnload);
      document.removeEventListener("visibilitychange", onVisible);
    };
  });
</script>

<Shell
  place="Merge order"
  crumbs={["Merge"]}
  nav={view === "planner" ? nav : []}
  note="The order locks when processing starts. Until then every change saves automatically."
>
  <div class="page merge-page merge-shell" data-plan-id={planId}>
    <header class="page-head">
      <div>
        <h1>Arrange your videos</h1>
        <p>
          Choose the playback order for the merged video. Move a part with the arrows, drag it,
          or sort the whole list.
        </p>
      </div>
      <span
        class="pill merge-state"
        id="planState"
        data-state={stateKey}
        data-tone={statusTone(stateKey)}
        aria-live="polite"
      >
        <span class="dot" class:pulse={!terminal() && view === "planner" && !locked}></span>
        <span>{stateText}</span>
      </span>
    </header>

    <section class="card panel-pad merge-auth" id="authPanel" hidden={view !== "auth"}>
      <div class="tile-head">
        <span class="tile"><Icon icon={KeyRound} size={17} /></span>
        <div>
          <h2>Enter the planner code</h2>
          <p>Tap <strong>Pincode</strong> in Telegram, then enter the code shown there.</p>
        </div>
      </div>
      <form id="pinForm" class="merge-pin-form" onsubmit={submitPin}>
        <div class="field">
          <label for="pinInput">Planner code</label>
          <input
            bind:this={pinInput}
            bind:value={pinValue}
            id="pinInput"
            type="text"
            inputmode="text"
            pattern="[A-Za-z0-9_\-]{12}"
            minlength="12"
            maxlength="12"
            autocomplete="one-time-code"
            autocapitalize="none"
            spellcheck="false"
            aria-describedby="pinHint"
            placeholder="12-character code"
            required
          />
          <p class="note" id="pinHint" aria-live="polite">{authHint}</p>
        </div>
        <button class="btn btn-primary" type="submit">Open planner</button>
      </form>
    </section>

    <section class="empty merge-error" id="errorPanel" hidden={view !== "error"}>
      <span class="empty-mark"><Icon name="alert-triangle" size={22} /></span>
      <h2>Planner unavailable</h2>
      <p id="errorMessage">{errorText}</p>
      <button id="retryPlanButton" type="button" class="btn" onclick={retry}>Try again</button>
    </section>

    {#if view === "connecting"}
      <div class="split" aria-hidden="true">
        <div class="card skeleton merge-skeleton"></div>
        <div class="card skeleton merge-skeleton short"></div>
      </div>
      <p class="visually-hidden" role="status">Loading the merge plan…</p>
    {/if}

    <div id="planner" class="split merge-planner" hidden={view !== "planner"}>
      <section class="card merge-workspace" id="order" aria-labelledby="order-title">
        <header class="panel-head merge-head">
          <div>
            <h2 class="panel-title" id="order-title" tabindex="-1">Playback order</h2>
            <p class="note">Changes save automatically. The order locks when processing starts.</p>
          </div>
          <span class="pill">MKV output</span>
        </header>

        <div class="panel-body">
          <div class="spread">
            <div class="cluster merge-toolbar" role="group" aria-label="Sort the list">
              <button type="button" class="btn" data-sort="input" disabled={locked} onclick={() => sort("input")}>Input order</button>
              <button type="button" class="btn" data-sort="filename" disabled={locked} onclick={() => sort("filename")}>Filename</button>
              <button type="button" class="btn" data-sort="episode" disabled={locked} onclick={() => sort("episode")}>Episode</button>
              <button type="button" class="btn" data-sort="reverse" disabled={locked} onclick={() => sort("reverse")}>Reverse</button>
            </div>
            <button
              type="button"
              class="btn btn-primary"
              id="saveOrderButton"
              hidden={!showSave}
              onclick={saveCurrent}>Save current order</button
            >
          </div>

          <p
            class="feedback"
            id="planNotice"
            data-tone={noticeTone}
            data-kind={locked ? "locked" : "active"}
            aria-live="polite"
          >
            <span>{notice}</span>
          </p>

          <ol
            class="rows merge-list"
            id="mergeList"
            aria-label="Video merge order"
            hidden={order.length === 0}
            bind:this={listEl}
          >
            {#each order as id, index (id)}
              {@const item = items.get(id)}
              {#if item}
                <li
                  class="inset row merge-row"
                  class:is-dragging={dragging === id}
                  class:is-drop-target={dropTarget === id && dragging !== id}
                  data-id={id}
                  data-name={item.name || ""}
                  data-original-index={item.original_index || 0}
                  draggable={!locked}
                  ondragstart={(e) => onDragStart(e, id)}
                  ondragover={(e) => onDragOver(e, id)}
                  ondragleave={() => dropTarget === id && (dropTarget = null)}
                  ondragend={finishDrag}
                >
                  <button
                    type="button"
                    class="btn-quiet btn-icon merge-handle"
                    disabled={locked}
                    aria-label="Drag {item.name}"
                    onpointerdown={(e) => onHandleDown(e, id)}
                    onpointermove={onHandleMove}
                    onpointerup={onHandleUp}
                    onpointercancel={onHandleUp}
                  >
                    <Icon icon={GripVertical} size={18} />
                  </button>
                  <span class="merge-pos num" aria-hidden="true">{index + 1}</span>
                  <div class="row-main merge-file">
                    <strong class="row-title" title={item.name || ""}>{item.name || "Preparing item"}</strong>
                    <span class="row-meta" data-ready={item.ready ? "" : undefined}>{detailFor(item)}</span>
                  </div>
                  <div class="row-actions merge-row-actions">
                    <button
                      type="button"
                      class="btn-quiet btn-icon"
                      disabled={locked || index === 0}
                      aria-label="Move up: {item.name}"
                      onclick={() => move(id, -1)}
                    >
                      <Icon icon={ChevronUp} size={18} />
                    </button>
                    <button
                      type="button"
                      class="btn-quiet btn-icon"
                      disabled={locked || index === order.length - 1}
                      aria-label="Move down: {item.name}"
                      onclick={() => move(id, 1)}
                    >
                      <Icon name="chevron-down" size={18} />
                    </button>
                  </div>
                </li>
              {/if}
            {/each}
          </ol>

          <div class="empty" id="emptyState" hidden={order.length > 0}>
            <span class="empty-mark"><Icon icon={ListOrdered} size={22} /></span>
            <h3>Collecting filenames</h3>
            <p>This list fills in as each source is prepared.</p>
          </div>
        </div>
      </section>

      <aside class="card panel-pad merge-summary" id="summary" aria-labelledby="summary-title">
        <div class="tile-head">
          <span class="tile"><Icon icon={Film} size={17} /></span>
          <div>
            <h2 id="summary-title" tabindex="-1">Summary</h2>
            <p id="planTitle" class="truncate" title={current?.title || ""}>
              {current?.title || "Merged video"}
            </p>
          </div>
        </div>

        <dl class="kv">
          <dt>Order</dt>
          <dd><span id="saveState" aria-live="polite">{saveText}</span></dd>
          <dt>Inventory</dt>
          <dd>
            <span id="readyCount">{current?.ready_count ?? 0}</span> ready of
            <span id="itemCount">{current?.items.length ?? 0}</span> listed
            <span class="row-meta merge-pending" id="pendingCount"
              >{current ? pendingLabel(current) : "Preparing"}</span
            >
          </dd>
          <dt>Mode</dt>
          <dd id="modeLabel">{current ? modeLabel(current) : "Stream copy"}</dd>
          <dt>Duration</dt>
          <dd id="durationLabel">{current ? durationLabel(current) : "Calculating"}</dd>
        </dl>

        <p class="note" id="subtitleSummary" hidden={!current?.subtitle_summary}>
          {current?.subtitle_summary || ""}
        </p>
      </aside>
    </div>
  </div>
</Shell>

<style>
  .merge-page .page-head {
    margin-bottom: 0;
    align-items: flex-start;
  }

  .merge-state {
    min-height: 1.75rem;
    padding-inline: 0.75rem;
  }

  .merge-state[data-tone="neutral"] .dot.pulse {
    background: var(--success);
    box-shadow: 0 0 0 3px var(--success-soft);
  }

  [hidden] {
    display: none !important;
  }

  .merge-auth {
    display: grid;
    gap: var(--space-5);
    max-width: 34rem;
  }

  .merge-pin-form {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: start;
    gap: var(--space-3);
  }

  .merge-pin-form button {
    margin-top: calc(var(--text-small) * 1.55 + var(--space-2));
  }

  #pinInput {
    font-variant-numeric: tabular-nums;
    letter-spacing: 0.08em;
  }

  .merge-head .note {
    margin-top: 2px;
  }

  .merge-planner {
    align-items: start;
  }

  .merge-workspace {
    min-width: 0;
  }

  .merge-summary {
    position: sticky;
    top: calc(var(--topbar-height) + var(--space-4));
    display: grid;
    gap: var(--space-5);
  }

  .merge-summary h2 {
    font-size: var(--text-section);
  }

  .merge-pending {
    display: block;
    font-weight: 500;
  }

  .merge-row {
    gap: var(--space-2);
    padding-inline: var(--space-1) var(--space-2);
    transition:
      --veil 180ms var(--ease-out),
      opacity var(--transition-fast),
      box-shadow var(--transition-fast);
  }

  .merge-row.is-dragging {
    opacity: 0.55;
  }

  .merge-row.is-drop-target {
    box-shadow: inset 0 0 0 1px var(--focus);
  }

  .merge-handle {
    color: var(--text-muted);
    cursor: grab;
    touch-action: none;
  }

  .merge-handle:active:not(:disabled) {
    cursor: grabbing;
  }

  .merge-pos {
    min-width: 1.75rem;
    text-align: center;
    color: var(--text-muted);
    font-size: var(--text-small);
    font-weight: 600;
  }

  .merge-file .row-meta[data-ready] {
    color: var(--success);
  }

  .merge-row-actions .btn-icon {
    color: var(--text-secondary);
  }

  .merge-skeleton {
    min-height: 22rem;
  }

  .merge-skeleton.short {
    min-height: 14rem;
  }

  @media (max-width: 64rem) {
    .merge-summary {
      position: static;
    }
  }

  @media (max-width: 40rem) {
    .merge-pin-form {
      grid-template-columns: minmax(0, 1fr);
    }
    .merge-pin-form button {
      margin-top: 0;
    }
    .merge-pos {
      display: none;
    }
  }
</style>
