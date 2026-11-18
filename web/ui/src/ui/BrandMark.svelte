<script lang="ts">
  let { size = 32 }: { size?: number } = $props();
</script>

<!-- Amaterasu's flame, drawn in the primary ink: a white flame on a black
     tile in light theme, a black flame on a white tile in dark theme.
     The viewBox is cropped to the flame's own bounds (x 36–220, y 20–241),
     so the flame fills ~70% of the tile instead of floating in padding. -->
<span class="brand-mark" style:--mark="{size}px" aria-hidden="true">
  <svg viewBox="28 14 200 234" fill="currentColor">
    <path
      d="M144 20 C144 80 220 92 220 158 C220 192 198 220 168 232 L142 202 C162 194 174 180 174 160 C174 138 152 126 138 108 C136 142 96 154 96 180 C96 198 110 208 126 208 L150 236 C86 246 36 206 36 150 C36 122 52 102 76 82 C76 110 90 122 106 112 C128 94 116 56 144 20 Z"
    />
  </svg>
</span>

<style>
  .brand-mark {
    display: inline-grid;
    place-items: center;
    flex-shrink: 0;
    width: var(--mark);
    height: var(--mark);
    border-radius: 28%;
    color: var(--button-text);
    background: var(--primary-fill);
    box-shadow:
      inset 0 1px 0 oklch(1 0 0 / 0.25),
      0 4px 14px -4px var(--accent-glow);
  }

  .brand-mark svg {
    width: auto;
    height: 76%;
  }
</style>
