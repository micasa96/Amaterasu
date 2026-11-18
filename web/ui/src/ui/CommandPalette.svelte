<script lang="ts" module>
  import type { Component } from "svelte";
  import type { IconName } from "./Icon.svelte";

  export interface Command {
    id: string;
    label: string;
    group: string;
    icon?: IconName;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    glyph?: Component<any>;
    hint?: string;
    keywords?: string;
    run: () => void;
  }
</script>

<script lang="ts">
  import { onMount, tick } from "svelte";
  import Icon from "./Icon.svelte";
  import { dialogIn, dialogOut, fadeIn } from "../lib/motion";

  let {
    commands,
    loading = false,
    onclose,
  }: {
    commands: Command[];
    loading?: boolean;
    onclose: () => void;
  } = $props();

  let query = $state("");
  let active = $state(0);
  let input = $state<HTMLInputElement | null>(null);
  let list = $state<HTMLElement | null>(null);

  const results = $derived.by(() => {
    const q = query.trim().toLowerCase();
    if (!q) return commands;
    const terms = q.split(/\s+/);
    return commands.filter((c) => {
      const haystack =
        `${c.label} ${c.group} ${c.hint ?? ""} ${c.keywords ?? ""}`.toLowerCase();
      return terms.every((t) => haystack.includes(t));
    });
  });

  // Groups in first-appearance order, each keeping its result indexes.
  const grouped = $derived.by(() => {
    const groups: { name: string; items: { cmd: Command; index: number }[] }[] =
      [];
    results.forEach((cmd, index) => {
      let group = groups.find((g) => g.name === cmd.group);
      if (!group) {
        group = { name: cmd.group, items: [] };
        groups.push(group);
      }
      group.items.push({ cmd, index });
    });
    return groups;
  });

  $effect(() => {
    // Keep the highlight inside the result set as it narrows.
    if (active >= results.length) active = Math.max(0, results.length - 1);
  });

  async function scrollActiveIntoView() {
    await tick();
    list
      ?.querySelector<HTMLElement>(`[data-index="${active}"]`)
      ?.scrollIntoView?.({ block: "nearest" });
  }

  function run(cmd: Command) {
    onclose();
    cmd.run();
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (results.length) active = (active + 1) % results.length;
      void scrollActiveIntoView();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (results.length)
        active = (active - 1 + results.length) % results.length;
      void scrollActiveIntoView();
    } else if (e.key === "Home") {
      active = 0;
      void scrollActiveIntoView();
    } else if (e.key === "End") {
      active = Math.max(0, results.length - 1);
      void scrollActiveIntoView();
    } else if (e.key === "Enter") {
      e.preventDefault();
      const cmd = results[active];
      if (cmd) run(cmd);
    } else if (e.key === "Escape") {
      e.preventDefault();
      onclose();
    } else if (e.key === "Tab") {
      // The palette is a single control; Tab closes it rather than escaping
      // focus into the page behind the scrim.
      e.preventDefault();
    }
  }

  onMount(() => {
    input?.focus();
  });
</script>

<div
  class="palette-scrim"
  role="presentation"
  in:fadeIn|global={{ duration: 160 }}
  out:fadeIn|global={{ duration: 120 }}
  onclick={(e) => {
    if (e.target === e.currentTarget) onclose();
  }}
>
  <div
    class="palette"
    role="dialog"
    aria-modal="true"
    aria-label="Search and commands"
    in:dialogIn|global={{ duration: 280 }}
    out:dialogOut|global={{ duration: 140 }}
  >
    <div class="palette-input">
      <Icon name="search" size={18} />
      <input
        bind:this={input}
        bind:value={query}
        oninput={() => (active = 0)}
        onkeydown={handleKeydown}
        type="text"
        role="combobox"
        aria-expanded="true"
        aria-controls="palette-results"
        aria-activedescendant={results[active]
          ? `palette-option-${results[active].id}`
          : undefined}
        aria-autocomplete="list"
        aria-label="Search pages and commands"
        placeholder="Jump to a section or run a command…"
        autocomplete="off"
        spellcheck="false"
      />
      <kbd>Esc</kbd>
    </div>

    <div
      class="palette-results"
      id="palette-results"
      role="listbox"
      aria-label="Results"
      bind:this={list}
    >
      {#each grouped as group (group.name)}
        <div role="group" aria-labelledby="palette-group-{group.name}">
          <p class="palette-group" id="palette-group-{group.name}">
            {group.name}
          </p>
          {#each group.items as { cmd, index } (cmd.id)}
            <div
              id="palette-option-{cmd.id}"
              class="palette-option"
              class:active={index === active}
              role="option"
              tabindex="-1"
              aria-selected={index === active}
              data-index={index}
              onclick={() => run(cmd)}
              onkeydown={() => {}}
              onpointermove={() => (active = index)}
            >
              <span class="option-icon"><Icon name={cmd.icon} icon={cmd.glyph} size={16} /></span
              >
              <span class="option-label">{cmd.label}</span>
              {#if cmd.hint}
                <span class="option-hint">{cmd.hint}</span>
              {/if}
              {#if index === active}
                <span class="option-enter" aria-hidden="true">
                  <Icon name="corner-down-left" size={14} />
                </span>
              {/if}
            </div>
          {/each}
        </div>
      {/each}

      {#if results.length === 0}
        <p class="palette-empty">
          {loading ? "Loading…" : `Nothing matches “${query.trim()}”.`}
        </p>
      {/if}
    </div>

    <footer class="palette-foot" aria-hidden="true">
      <span><kbd>↑</kbd><kbd>↓</kbd> Move</span>
      <span><kbd>↵</kbd> Open</span>
      <span><kbd>Esc</kbd> Close</span>
    </footer>
  </div>
</div>

<style>
  .palette-scrim {
    position: fixed;
    inset: 0;
    z-index: var(--layer-palette);
    display: grid;
    justify-items: center;
    align-items: start;
    padding: min(14vh, 8rem) var(--space-4) var(--space-4);
    background: var(--drawer-scrim);
  }

  .palette {
    background:
      var(--card-fill) padding-box,
      var(--card-edge) border-box;
    border: var(--border-width) solid transparent;
    width: min(100%, 40rem);
    max-height: min(32rem, calc(100svh - 6rem));
    display: grid;
    grid-template-rows: auto 1fr auto;
    overflow: hidden;
    border-radius: var(--radius-xl);
    box-shadow:
      var(--shadow-modal),
      0 0 0 6px light-dark(oklch(1 0 0 / 0.5), oklch(1 0 0 / 0.025));
  }

  .palette-input {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: 0 var(--space-4);
    border-bottom: var(--border-width) solid var(--line);
    color: var(--text-muted);
  }

  .palette-input input {
    flex: 1;
    min-height: 3.5rem;
    padding: 0;
    border: 0;
    background: transparent;
    box-shadow: none;
    font-size: var(--text-body);
    color: var(--text);
  }

  .palette-input input:focus {
    box-shadow: none;
    background: transparent;
  }

  .palette-results {
    overflow-y: auto;
    overscroll-behavior: contain;
    padding: var(--space-2);
  }

  .palette-group {
    padding: var(--space-3) var(--space-3) var(--space-1);
    font-size: var(--text-xs);
    font-weight: 600;
    color: var(--text-muted);
  }

  .palette-option {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    min-height: var(--control-height);
    padding: 0 var(--space-3);
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    cursor: pointer;
  }

  .palette-option.active {
    background: var(--selected);
    color: var(--text);
  }

  .option-icon {
    display: grid;
    place-items: center;
    color: var(--text-muted);
  }

  .palette-option.active .option-icon {
    color: var(--accent);
  }

  .option-label {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-weight: 540;
  }

  .option-hint {
    font-size: var(--text-xs);
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
  }

  .option-enter {
    color: var(--text-muted);
  }

  .palette-empty {
    padding: var(--space-8) var(--space-4);
    text-align: center;
    font-size: var(--text-small);
    color: var(--text-muted);
  }

  .palette-foot {
    display: flex;
    gap: var(--space-4);
    padding: var(--space-2) var(--space-4);
    border-top: var(--border-width) solid var(--line);
    background: var(--surface-sunken);
    font-size: var(--text-xs);
    color: var(--text-muted);
  }

  .palette-foot span {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
  }

  @media (max-width: 40rem) {
    .palette-scrim {
      padding: var(--space-3);
    }
    .palette-foot {
      display: none;
    }
  }
</style>
