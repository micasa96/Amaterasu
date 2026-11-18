<script lang="ts">
  import type { Snippet } from "svelte";
  let {
    children,
    disabled = false,
    onclick,
    type = "button",
    variant = "secondary",
    class: className = "",
    label,
  }: {
    children: Snippet;
    disabled?: boolean;
    onclick?: () => void;
    type?: "button" | "submit";
    variant?: "primary" | "secondary" | "quiet" | "danger" | "danger-quiet";
    class?: string;
    label?: string;
  } = $props();
</script>

<button
  {type}
  {disabled}
  {onclick}
  aria-label={label}
  class="btn btn-{variant} {className}"
>
  {@render children()}
</button>
