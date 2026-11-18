<script lang="ts" module>
  import type { IconName } from "./Icon.svelte";

  export interface SelectOption {
    value: string;
    label: string;
    /** A colour dot before the label (statuses, labels). */
    color?: string;
    icon?: IconName;
    /** Secondary text after the label. */
    hint?: string;
    /** A one-line explanation under the label. */
    description?: string;
    disabled?: boolean;
  }
</script>

<script lang="ts">
  import { tick } from "svelte";
  import Icon from "./Icon.svelte";
  import { floating, uid } from "../lib/floating";
  import { pop, shrink } from "../lib/motion";

  let {
    id,
    value,
    options,
    onchange,
    label,
    placeholder = "Select…",
    variant = "field",
    disabled = false,
    describedby,
    align = "start",
    class: className = "",
  }: {
    /** Lets a visible <label for=id> name the control. */
    id?: string;
    value: string;
    options: readonly SelectOption[];
    onchange: (value: string) => void;
    /** Accessible name when there is no visible label. */
    label?: string;
    placeholder?: string;
    /** field: form control · chip: compact pill · ghost: toolbar filter */
    variant?: "field" | "chip" | "ghost";
    disabled?: boolean;
    describedby?: string;
    align?: "start" | "end";
    class?: string;
  } = $props();

  const listId = uid("listbox");
  let open = $state(false);
  let active = $state(0);
  let trigger = $state<HTMLButtonElement | null>(null);
  let list = $state<HTMLElement | null>(null);
  let typed = "";
  let typedTimer: ReturnType<typeof setTimeout> | undefined;

  const current = $derived(options.find((o) => o.value === value));

  async function openMenu() {
    if (disabled || open) return;
    const index = options.findIndex((o) => o.value === value);
    active = index >= 0 ? index : firstEnabled(0, 1);
    open = true;
    await tick();
    list?.focus();
    scrollActive();
  }

  function close(restore = true) {
    if (!open) return;
    open = false;
    if (restore) trigger?.focus();
  }

  function choose(index: number) {
    const opt = options[index];
    if (!opt || opt.disabled) return;
    close();
    if (opt.value !== value) onchange(opt.value);
  }

  function firstEnabled(from: number, step: 1 | -1) {
    for (let i = 0, n = options.length; i < n; i++) {
      const idx = (from + i * step + n * 2) % n;
      if (!options[idx]?.disabled) return idx;
    }
    return 0;
  }

  async function scrollActive() {
    await tick();
    list
      ?.querySelector<HTMLElement>(`[data-index="${active}"]`)
      ?.scrollIntoView?.({ block: "nearest" });
  }

  function onTriggerKey(e: KeyboardEvent) {
    if (["ArrowDown", "ArrowUp", "Enter", " "].includes(e.key)) {
      e.preventDefault();
      void openMenu();
    }
  }

  function onListKey(e: KeyboardEvent) {
    const n = options.length;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      active = firstEnabled((active + 1) % n, 1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      active = firstEnabled((active - 1 + n) % n, -1);
    } else if (e.key === "Home") {
      e.preventDefault();
      active = firstEnabled(0, 1);
    } else if (e.key === "End") {
      e.preventDefault();
      active = firstEnabled(n - 1, -1);
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      choose(active);
      return;
    } else if (e.key === "Escape") {
      // Close the menu only, never the dialog or drawer behind it.
      e.preventDefault();
      e.stopPropagation();
      close();
      return;
    } else if (e.key === "Tab") {
      close(false);
      return;
    } else if (e.key.length === 1 && !e.metaKey && !e.ctrlKey) {
      // Typeahead: jump to the first option starting with what was typed.
      clearTimeout(typedTimer);
      typed += e.key.toLowerCase();
      typedTimer = setTimeout(() => (typed = ""), 600);
      const hit = options.findIndex(
        (o) => !o.disabled && o.label.toLowerCase().startsWith(typed),
      );
      if (hit >= 0) active = hit;
    } else {
      return;
    }
    scrollActive();
  }
</script>

<button
  bind:this={trigger}
  {id}
  type="button"
  class="select select-{variant} {className}"
  class:open
  class:placeholder={!current}
  aria-haspopup="listbox"
  aria-expanded={open}
  aria-controls={open ? listId : undefined}
  aria-label={label}
  aria-describedby={describedby}
  {disabled}
  onclick={() => (open ? close() : openMenu())}
  onkeydown={onTriggerKey}
  style:--opt-color={current?.color}
>
  {#if current?.icon}
    <Icon name={current.icon} size={15} class="select-icon" />
  {:else if current?.color}
    <span class="select-dot" aria-hidden="true"></span>
  {/if}
  <span class="select-text">{current ? current.label : placeholder}</span>
  <Icon name="chevron-down" size={15} class="select-chevron" />
</button>

{#if open}
  <div
    class="menu"
    use:floating={{
      anchor: trigger,
      align,
      matchWidth: variant === "field",
      onclose: () => close(false),
    }}
    in:pop
    out:shrink
  >
    <ul
      bind:this={list}
      id={listId}
      class="menu-list"
      role="listbox"
      tabindex="-1"
      aria-label={label}
      aria-labelledby={label ? undefined : id}
      aria-activedescendant="{listId}-{active}"
      onkeydown={onListKey}
    >
      {#each options as opt, i (opt.value)}
        <li
          id="{listId}-{i}"
          class="menu-option"
          class:active={i === active}
          class:selected={opt.value === value}
          class:disabled={opt.disabled}
          role="option"
          aria-selected={opt.value === value}
          aria-disabled={opt.disabled}
          data-index={i}
          onpointermove={() => {
            if (!opt.disabled) active = i;
          }}
          onclick={() => choose(i)}
          onkeydown={() => {}}
          style:--opt-color={opt.color}
        >
          {#if opt.icon}
            <Icon name={opt.icon} size={15} class="opt-icon" />
          {:else if opt.color}
            <span class="opt-dot" aria-hidden="true"></span>
          {/if}
          <span class="opt-text">
            <span class="opt-label">{opt.label}</span>
            {#if opt.description}
              <span class="opt-desc">{opt.description}</span>
            {/if}
          </span>
          {#if opt.hint}
            <span class="opt-hint">{opt.hint}</span>
          {/if}
          <span class="opt-check" aria-hidden="true">
            {#if opt.value === value}<Icon name="check" size={15} />{/if}
          </span>
        </li>
      {/each}
    </ul>
  </div>
{/if}

<style>
  .select {
    justify-content: flex-start;
    gap: var(--space-2);
    width: 100%;
    min-width: 0;
    padding: 0 var(--space-2) 0 var(--space-3);
    text-align: left;
    font-weight: 500;
    box-shadow: none;
  }

  .select-text {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .placeholder .select-text {
    color: var(--text-muted);
  }

  .select :global(.select-chevron) {
    color: var(--text-muted);
    transition: transform var(--duration) var(--ease-spring);
    flex-shrink: 0;
  }

  .select.open :global(.select-chevron) {
    transform: rotate(180deg);
  }

  .select :global(.select-icon) {
    color: var(--opt-color, var(--text-muted));
  }

  .select-dot,
  .opt-dot {
    width: 0.5rem;
    height: 0.5rem;
    border-radius: 50%;
    background: var(--opt-color);
    box-shadow: 0 0 8px -1px var(--opt-color);
    flex-shrink: 0;
  }

  /* field: sits in forms like an input. */
  .select-field {
    background: var(--surface-sunken);
    border: var(--border-width) solid var(--border);
  }

  .select-field:hover:not(:disabled) {
    background: var(--surface-sunken);
    border-color: var(--text-muted);
  }

  .select-field.open {
    border-color: var(--focus);
    box-shadow: 0 0 0 3px var(--accent-soft);
  }

  /* chip: a compact pill that shows its edge only when touched. */
  .select-chip {
    width: auto;
    max-width: 100%;
    min-height: 2.125rem;
    padding: 0 0.5rem 0 0.75rem;
    border-radius: var(--radius-full);
    background: var(--surface-sunken);
    border: var(--border-width) solid transparent;
    font-size: var(--text-small);
  }

  .select-chip:hover:not(:disabled),
  .select-chip.open {
    background:
      linear-gradient(var(--hover), var(--hover)) padding-box,
      linear-gradient(var(--line-strong), var(--line-strong)) border-box;
  }

  /* ghost: toolbar filters, quiet until used. */
  .select-ghost {
    width: auto;
    min-width: 8.5rem;
    font-size: var(--text-small);
  }

  /* ── Menu ────────────────────────────────────────────────────── */
  .menu {
    z-index: var(--layer-popover);
    display: flex;
    min-width: 12rem;
    border-radius: var(--radius);
    border: var(--border-width) solid transparent;
    background:
      var(--card-fill) padding-box,
      var(--card-edge) border-box;
    box-shadow: var(--shadow-float);
    overflow: hidden;
  }

  .menu-list {
    list-style: none;
    margin: 0;
    padding: 4px;
    width: 100%;
    overflow-y: auto;
    overscroll-behavior: contain;
    outline: none;
  }

  .menu-option {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    min-height: 2.25rem;
    padding: 0.375rem 0.5rem 0.375rem 0.625rem;
    border-radius: calc(var(--radius) - 4px);
    color: var(--text-secondary);
    font-size: var(--text-small);
    cursor: pointer;
    user-select: none;
    transition: background-color 80ms linear;
  }

  .menu-option.active {
    background: var(--selected);
    color: var(--text);
  }

  .menu-option.selected {
    color: var(--text);
    font-weight: 560;
  }

  .menu-option.disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  .menu-option :global(.opt-icon) {
    color: var(--opt-color, var(--text-muted));
  }

  .opt-text {
    flex: 1;
    min-width: 0;
    display: grid;
  }

  .opt-label {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .opt-desc {
    font-size: var(--text-xs);
    color: var(--text-muted);
    white-space: normal;
    line-height: 1.35;
  }

  .opt-hint {
    font-size: var(--text-xs);
    color: var(--text-muted);
  }

  .opt-check {
    width: 15px;
    display: grid;
    place-items: center;
    color: var(--accent);
  }

  @media (pointer: coarse) {
    .menu-option {
      min-height: var(--control-height);
    }
  }
</style>
