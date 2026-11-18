<script lang="ts">
  // The Blackflare flame from the README banner, alive: a pearl-white flame
  // with shaded inner edges, heat lines that keep rising out of it and
  // fading, a slow breathing sway, and a sheen that passes over its surface.
  // Decorative only. Reduced motion holds the static banner pose.
  const D =
    "M144 20 C144 80 220 92 220 158 C220 192 198 220 168 232 L142 202 C162 194 174 180 174 160 C174 138 152 126 138 108 C136 142 96 154 96 180 C96 198 110 208 126 208 L150 236 C86 246 36 206 36 150 C36 122 52 102 76 82 C76 110 90 122 106 112 C128 94 116 56 144 20 Z";
  // The outer silhouette only (no inner flame or stem notch), for heat lines.
  const HULL =
    "M144 20 C144 80 220 92 220 158 C220 192 198 220 168 232 L150 236 C86 246 36 206 36 150 C36 122 52 102 76 82 C76 110 90 122 106 112 C128 94 116 56 144 20 Z";
  const LINES = 6;
  const uid = `flame-${Math.random().toString(36).slice(2, 8)}`;
</script>

<svg class="flame" viewBox="0 0 256 256" aria-hidden="true" focusable="false">
  <defs>
    <linearGradient id="{uid}-fill" x1="0.1" y1="0" x2="0.9" y2="1">
      <stop offset="0" stop-color="oklch(1 0 0)" />
      <stop offset="0.32" stop-color="oklch(0.955 0 0)" />
      <stop offset="0.46" stop-color="oklch(0.995 0 0)" />
      <stop offset="0.72" stop-color="oklch(0.88 0 0)" />
      <stop offset="1" stop-color="oklch(0.74 0 0)" />
    </linearGradient>
    <filter id="{uid}-volume" x="-10%" y="-10%" width="120%" height="120%">
      <feGaussianBlur in="SourceAlpha" stdDeviation="5" result="soft" />
      <feComposite in="SourceAlpha" in2="soft" operator="out" result="rim" />
      <feFlood flood-color="#000" flood-opacity="0.32" />
      <feComposite in2="rim" operator="in" result="shade" />
      <feOffset in="SourceAlpha" dx="-0.6" dy="1" result="up" />
      <feComposite in="SourceAlpha" in2="up" operator="out" result="lipHard" />
      <feGaussianBlur in="lipHard" stdDeviation="0.35" result="lip" />
      <feFlood flood-color="#fff" flood-opacity="0.75" />
      <feComposite in2="lip" operator="in" result="lit" />
      <feMerge>
        <feMergeNode in="SourceGraphic" />
        <feMergeNode in="shade" />
        <feMergeNode in="lit" />
      </feMerge>
    </filter>
    <clipPath id="{uid}-clip"><path d={D} /></clipPath>
    <linearGradient id="{uid}-band" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#fff" stop-opacity="0" />
      <stop offset="0.5" stop-color="#fff" stop-opacity="0.85" />
      <stop offset="1" stop-color="#fff" stop-opacity="0" />
    </linearGradient>
    <linearGradient id="{uid}-rise" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#fff" />
      <stop offset="0.62" stop-color="#fff" />
      <stop offset="0.92" stop-color="#fff" stop-opacity="0" />
    </linearGradient>
    <mask id="{uid}-fade" maskUnits="userSpaceOnUse" x="-300" y="-300" width="856" height="856">
      <rect x="-300" y="-300" width="856" height="856" fill="url(#{uid}-rise)" />
    </mask>
  </defs>

  <!-- Heat lines: copies of the silhouette rising outward and fading. -->
  <g class="heat" mask="url(#{uid}-fade)">
    {#each { length: LINES } as _, i (i)}
      <path class="line" d={HULL} style:--i={i} />
    {/each}
  </g>

  <g class="body">
    <path d={D} fill="url(#{uid}-fill)" filter="url(#{uid}-volume)" />
    <!-- The sheen pass, clipped to the flame. -->
    <g clip-path="url(#{uid}-clip)">
      <rect class="sheen" x="-120" y="-40" width="70" height="340" fill="url(#{uid}-band)" />
    </g>
  </g>
</svg>

<style>
  .flame {
    display: block;
    width: 100%;
    height: auto;
    overflow: visible;
    filter: drop-shadow(0 30px 50px oklch(0 0 0 / 0.55));
  }

  /* ── Heat lines ───────────────────────────────────────────────── */
  .line {
    fill: none;
    stroke: var(--text);
    stroke-width: 1;
    vector-effect: non-scaling-stroke;
    transform-box: view-box;
    transform-origin: 130px 176px;
    /* Static pose (reduced motion): the banner's spread of lines. */
    transform: scale(calc(1.16 + var(--i) * 0.22));
    opacity: calc(0.34 - var(--i) * 0.05);
  }

  /* ── The flame ────────────────────────────────────────────────── */
  .body {
    transform-box: view-box;
    transform-origin: 128px 240px;
  }

  .sheen {
    transform: translateX(-60px) skewX(-18deg);
    opacity: 0;
  }

  @media (prefers-reduced-motion: no-preference) {
    /* Each line is born at the flame's edge, rises and fades; staggered so
       the radiation never stops. Linear time keeps the spacing even. */
    .line {
      animation: heat 7.2s linear infinite;
      animation-delay: calc(var(--i) * -1.2s);
    }

    /* A slow breath anchored at the base: never a bounce. */
    .body {
      animation: breathe 5.6s cubic-bezier(0.45, 0, 0.55, 1) infinite;
    }

    .sheen {
      animation: sheen 7s cubic-bezier(0.65, 0, 0.35, 1) infinite;
      animation-delay: 1.4s;
    }
  }

  @keyframes heat {
    0% {
      transform: scale(1.02);
      opacity: 0;
    }
    12% {
      opacity: 0.42;
    }
    100% {
      transform: scale(2.4);
      opacity: 0;
    }
  }

  @keyframes breathe {
    0%,
    100% {
      transform: scale(1, 1) skewX(0deg);
    }
    35% {
      transform: scale(0.992, 1.022) skewX(-0.8deg);
    }
    70% {
      transform: scale(1.006, 0.994) skewX(0.6deg);
    }
  }

  @keyframes sheen {
    0% {
      transform: translateX(-60px) skewX(-18deg);
      opacity: 0;
    }
    8% {
      opacity: 0.55;
    }
    32% {
      transform: translateX(330px) skewX(-18deg);
      opacity: 0.55;
    }
    36%,
    100% {
      transform: translateX(330px) skewX(-18deg);
      opacity: 0;
    }
  }
</style>
