<script lang="ts">
  import BrandMark from "./BrandMark.svelte";

  // The Amaterasu lockup: flame tile plus wordmark, in fixed optical pairs
  // so the mark and the letters always balance. The wordmark's box is
  // trimmed to its cap height, so the letters centre exactly on the tile.
  let {
    size = "md",
    showWordmark = true,
  }: {
    size?: "sm" | "md" | "lg";
    showWordmark?: boolean;
  } = $props();

  // tile px, wordmark px, gap px
  const scale = { sm: [29, 18, 7], md: [34, 21, 8], lg: [52, 32, 12] } as const;
  const dims = $derived(scale[size]);
</script>

<span class="lockup" style:--gap="{dims[2]}px" style:--type="{dims[1]}px">
  <BrandMark size={dims[0]} />
  {#if showWordmark}<span class="wordmark">Amaterasu</span>{/if}
</span>

<style>
  .lockup {
    display: inline-flex;
    align-items: center;
    gap: var(--gap);
    min-width: 0;
    color: var(--text);
  }

  .wordmark {
    font-size: var(--type);
    font-weight: 560;
    letter-spacing: -0.032em;
    line-height: 1;
    white-space: nowrap;
    /* Trim the line box to cap height and baseline so centring is optical,
       not padded by the (unused) descender space. */
    text-box: trim-both cap alphabetic;
  }

  /* Browsers without text-box: nudge down by the descender share instead. */
  @supports not (text-box: trim-both cap alphabetic) {
    .wordmark {
      transform: translateY(0.06em);
    }
  }
</style>
