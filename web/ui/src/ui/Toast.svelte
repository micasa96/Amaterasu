<script lang="ts">
  import { onDestroy } from "svelte";
  import Icon from "./Icon.svelte";
  import { toastIn, toastOut } from "../lib/motion";

  // A transient confirmation. It floats over the work instead of pushing it
  // down, pauses while hovered or focused, and can be dismissed. Errors do
  // not use this: they stay inline until the person acts on them.
  let {
    message,
    onclear,
    duration = 4500,
  }: {
    message: string | null;
    onclear: () => void;
    duration?: number;
  } = $props();

  let timer: ReturnType<typeof setTimeout> | undefined;
  let paused = $state(false);

  function schedule() {
    clearTimeout(timer);
    if (message && !paused) timer = setTimeout(onclear, duration);
  }

  $effect(() => {
    // Restart the countdown whenever a new message arrives or hover ends.
    void message;
    void paused;
    schedule();
  });

  onDestroy(() => clearTimeout(timer));
</script>

<div class="toast-region" role="status" aria-live="polite">
  {#if message}
    <div
      class="toast"
      role="presentation"
      in:toastIn
      out:toastOut
      onmouseenter={() => (paused = true)}
      onmouseleave={() => (paused = false)}
      onfocusin={() => (paused = true)}
      onfocusout={() => (paused = false)}
    >
      <span class="toast-icon" aria-hidden="true">
        <Icon name="check" size={14} />
      </span>
      <span class="toast-text">{message}</span>
      <button
        type="button"
        class="toast-close"
        onclick={onclear}
        aria-label="Dismiss notification"
      >
        <Icon name="close" size={14} />
      </button>
    </div>
  {/if}
</div>

<style>
  .toast-region {
    position: fixed;
    right: max(var(--space-5), env(safe-area-inset-right));
    bottom: max(var(--space-5), env(safe-area-inset-bottom));
    z-index: calc(var(--layer-palette) + 5);
    pointer-events: none;
  }

  .toast {
    pointer-events: auto;
    display: flex;
    align-items: center;
    gap: var(--space-3);
    max-width: min(26rem, calc(100vw - 2.5rem));
    padding: var(--space-2) var(--space-2) var(--space-2) var(--space-3);
    border-radius: var(--radius);
    border: var(--border-width) solid transparent;
    background:
      var(--card-fill) padding-box,
      var(--card-edge) border-box;
    box-shadow: var(--shadow-float);
    color: var(--text);
    font-size: var(--text-small);
    font-weight: 520;
  }

  .toast-icon {
    display: grid;
    place-items: center;
    width: 1.5rem;
    height: 1.5rem;
    border-radius: 50%;
    background: var(--success-soft);
    color: var(--success);
    flex-shrink: 0;
  }

  .toast-text {
    flex: 1;
    min-width: 0;
  }

  .toast-close {
    width: 2rem;
    min-height: 2rem;
    padding: 0;
    border: 0;
    background: transparent;
    box-shadow: none;
    color: var(--text-muted);
    border-radius: var(--radius-sm);
  }

  .toast-close:hover:not(:disabled) {
    background: var(--hover);
    color: var(--text);
  }

  @keyframes toast-in {
    from {
      opacity: 0;
      transform: translateY(10px) scale(0.98);
    }
  }

  @media (max-width: 40rem) {
    .toast-region {
      left: var(--space-4);
      right: var(--space-4);
      bottom: max(var(--space-4), env(safe-area-inset-bottom));
    }

    .toast {
      max-width: none;
    }
  }
</style>
