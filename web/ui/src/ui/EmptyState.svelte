<script lang="ts">
  import type { Component, Snippet } from "svelte";
  import Icon, { type IconName } from "./Icon.svelte";

  let {
    title,
    name,
    icon,
    children,
    actions,
  }: {
    title: string;
    name?: IconName;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    icon?: Component<any>;
    children?: Snippet;
    actions?: Snippet;
  } = $props();
</script>

<div class="empty">
  <span class="empty-mark"><Icon {name} {icon} size={22} /></span>
  <h3>{title}</h3>
  {#if children}<p>{@render children()}</p>{/if}
  {#if actions}<div class="cluster">{@render actions()}</div>{/if}
</div>
