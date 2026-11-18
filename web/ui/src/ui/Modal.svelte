<script lang="ts">
  import { onMount, type Snippet } from "svelte";
  import Icon from "./Icon.svelte";
  import { dialogIn, dialogOut, fadeIn } from "../lib/motion";

  let {
    title,
    description,
    onclose,
    wide = false,
    tone,
    closeLabel = "Close dialog",
    children,
  }: {
    title: string;
    description?: string;
    onclose: () => void;
    wide?: boolean;
    tone?: "danger";
    closeLabel?: string;
    children: Snippet;
  } = $props();

  const id = `dialog-${Math.random().toString(36).slice(2, 9)}`;
  let dialog = $state<HTMLElement | null>(null);

  const focusable =
    'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === "Escape") {
      e.stopPropagation();
      onclose();
      return;
    }
    if (e.key !== "Tab" || !dialog) return;
    // Keep keyboard focus inside the dialog while it is open.
    const items = [...dialog.querySelectorAll<HTMLElement>(focusable)];
    if (items.length === 0) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }

  onMount(() => {
    const previous = document.activeElement as HTMLElement | null;
    // Start on the first field when there is one, otherwise the dialog.
    const field = dialog?.querySelector<HTMLElement>(
      "input:not([disabled]), select:not([disabled]), textarea:not([disabled])",
    );
    (field ?? dialog)?.focus();
    return () => {
      if (previous && document.contains(previous)) previous.focus();
    };
  });
</script>

<div
  class="scrim"
  role="presentation"
  in:fadeIn|global={{ duration: 200 }}
  out:fadeIn|global={{ duration: 160 }}
  onclick={(e) => {
    if (e.target === e.currentTarget) onclose();
  }}
>
  <div
    bind:this={dialog}
    class="dialog"
    class:dialog-wide={wide}
    data-tone={tone}
    role="dialog"
    aria-modal="true"
    aria-labelledby="{id}-title"
    aria-describedby={description ? `${id}-desc` : undefined}
    tabindex="-1"
    onkeydown={handleKeydown}
    in:dialogIn|global
    out:dialogOut|global
  >
    <div class="dialog-head">
      <div>
        <h3 id="{id}-title">{title}</h3>
        {#if description}
          <p id="{id}-desc">{description}</p>
        {/if}
      </div>
      <button
        type="button"
        class="btn-quiet btn-icon"
        onclick={onclose}
        aria-label={closeLabel}
      >
        <Icon name="close" size={18} />
      </button>
    </div>
    <div class="dialog-body">
      {@render children()}
    </div>
  </div>
</div>

<style>
  .dialog:focus {
    outline: none;
  }

  .dialog[data-tone="danger"] .dialog-head h3 {
    color: var(--danger);
  }
</style>
