<script lang="ts">
  import type { HTMLInputAttributes } from "svelte/elements";

  let {
    id,
    label,
    type = "text",
    value = $bindable(""),
    autocomplete,
    required = false,
    hint,
    disabled = false,
    placeholder,
  }: {
    id: string;
    label: string;
    type?: string;
    value?: string;
    autocomplete?: HTMLInputAttributes["autocomplete"];
    required?: boolean;
    hint?: string;
    disabled?: boolean;
    placeholder?: string;
  } = $props();
</script>

<div class="field">
  <label for={id}>{label}</label>
  <input
    {id}
    {type}
    bind:value
    {autocomplete}
    {required}
    {disabled}
    {placeholder}
    aria-describedby={hint ? `${id}-hint` : undefined}
  />
  {#if hint}
    <p class="note" id="{id}-hint">{hint}</p>
  {/if}
</div>
