<script lang="ts">
  import Icon from "./Icon.svelte";
  import { copyText } from "../lib/format";
  import { toast } from "../lib/toast.svelte";

  let {
    value,
    label = "Copy",
    confirm = "Copied to clipboard",
    variant = "secondary",
    iconOnly = false,
  }: {
    value: string;
    label?: string;
    confirm?: string;
    variant?: "primary" | "secondary" | "quiet";
    iconOnly?: boolean;
  } = $props();

  let done = $state(false);
  let failed = $state(false);

  async function copy() {
    failed = false;
    if (await copyText(value)) {
      done = true;
      toast.show(confirm);
      setTimeout(() => (done = false), 1600);
    } else failed = true;
  }
</script>

<button
  type="button"
  class="btn btn-{variant}"
  class:btn-icon={iconOnly}
  onclick={copy}
  aria-label={iconOnly ? label : undefined}
  title={failed ? "Copy failed — select the text and copy it manually" : label}
>
  <Icon name={done ? "check" : "copy"} size={16} />
  {#if !iconOnly}<span>{done ? "Copied" : label}</span>{/if}
</button>
