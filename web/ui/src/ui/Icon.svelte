<script lang="ts" module>
  // One outline family: 24px grid, 1.75 stroke, round caps. Paths follow the
  // Feather/Lucide drawing conventions.
  export type IconName =
    | "calendar"
    | "user"
    | "users"
    | "tag"
    | "check"
    | "chat"
    | "clock"
    | "close"
    | "plus"
    | "trash"
    | "settings"
    | "arrow-up"
    | "arrow-down"
    | "arrow-left"
    | "arrow-right"
    | "pencil"
    | "alert-triangle"
    | "folder"
    | "list"
    | "board"
    | "search"
    | "sun"
    | "moon"
    | "monitor"
    | "log-out"
    | "log-in"
    | "chevron-down"
    | "chevron-right"
    | "chevron-up-down"
    | "menu"
    | "more"
    | "filter"
    | "pulse"
    | "workflow"
    | "archive"
    | "home"
    | "palette"
    | "layers"
    | "corner-down-left"
    | "circle"
    | "circle-check"
    | "grid"
    | "command"
    | "target"
    | "flag"
    | "trend"
    | "telegram"
    | "slack"
    | "discord"
    | "copy"
    | "image"
    | "upload"
    | "play"
    | "stop"
    | "pause";
</script>

<script lang="ts">
  import type { Component } from "svelte";

  // `name` draws from the hand-tuned set below. `icon` takes any
  // @lucide/svelte component for glyphs the set does not carry, rendered on
  // the same 24px grid with the same 1.75 stroke so both read as one family.
  let {
    name,
    icon,
    size = 16,
    class: className = "",
  }: {
    name?: IconName;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    icon?: Component<any>;
    size?: number;
    class?: string;
  } = $props();
</script>

{#if icon}
  {@const Glyph = icon}
  <Glyph
    {size}
    strokeWidth={1.75}
    absoluteStrokeWidth={false}
    aria-hidden="true"
    focusable="false"
    class="svg-icon {className}"
  />
{:else}
<svg
  xmlns="http://www.w3.org/2000/svg"
  width={size}
  height={size}
  viewBox="0 0 24 24"
  fill="none"
  stroke="currentColor"
  stroke-width="1.75"
  stroke-linecap="round"
  stroke-linejoin="round"
  aria-hidden="true"
  focusable="false"
  class="svg-icon {className}"
>
  {#if name === "calendar"}
    <rect x="3" y="4.5" width="18" height="16.5" rx="2.5" />
    <path d="M16 2.5v4M8 2.5v4M3 10h18" />
  {:else if name === "user"}
    <circle cx="12" cy="8" r="4" />
    <path d="M4.5 20.5a7.5 7.5 0 0 1 15 0" />
  {:else if name === "users"}
    <circle cx="9" cy="8" r="3.5" />
    <path d="M2.5 20a6.5 6.5 0 0 1 13 0" />
    <path d="M16 4.6a3.5 3.5 0 0 1 0 6.8M21.5 20a6.5 6.5 0 0 0-4-6" />
  {:else if name === "tag"}
    <path
      d="M20.6 13.4 13.4 20.6a2 2 0 0 1-2.8 0L3 13V3h10l7.6 7.6a2 2 0 0 1 0 2.8z"
    />
    <path d="M7.5 7.5h.01" />
  {:else if name === "check"}
    <path d="M20 6 9 17l-5-5" />
  {:else if name === "chat"}
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
  {:else if name === "clock"}
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  {:else if name === "close"}
    <path d="M18 6 6 18M6 6l12 12" />
  {:else if name === "plus"}
    <path d="M12 5v14M5 12h14" />
  {:else if name === "trash"}
    <path d="M3 6h18M8 6V4h8v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
    <path d="M10 11v6M14 11v6" />
  {:else if name === "settings"}
    <path
      d="M12.2 2h-.4a2 2 0 0 0-2 2v.2a2 2 0 0 1-1 1.7l-.4.3a2 2 0 0 1-2 0l-.2-.1a2 2 0 0 0-2.7.7l-.2.4a2 2 0 0 0 .7 2.7l.2.1a2 2 0 0 1 1 1.7v.5a2 2 0 0 1-1 1.7l-.2.1a2 2 0 0 0-.7 2.7l.2.4a2 2 0 0 0 2.7.7l.2-.1a2 2 0 0 1 2 0l.4.3a2 2 0 0 1 1 1.7v.2a2 2 0 0 0 2 2h.4a2 2 0 0 0 2-2v-.2a2 2 0 0 1 1-1.7l.4-.3a2 2 0 0 1 2 0l.2.1a2 2 0 0 0 2.7-.7l.2-.4a2 2 0 0 0-.7-2.7l-.2-.1a2 2 0 0 1-1-1.7v-.5a2 2 0 0 1 1-1.7l.2-.1a2 2 0 0 0 .7-2.7l-.2-.4a2 2 0 0 0-2.7-.7l-.2.1a2 2 0 0 1-2 0l-.4-.3a2 2 0 0 1-1-1.7V4a2 2 0 0 0-2-2z"
    />
    <circle cx="12" cy="12" r="3" />
  {:else if name === "arrow-up"}
    <path d="M12 19V5M5 12l7-7 7 7" />
  {:else if name === "arrow-down"}
    <path d="M12 5v14M19 12l-7 7-7-7" />
  {:else if name === "arrow-left"}
    <path d="M19 12H5M12 19l-7-7 7-7" />
  {:else if name === "arrow-right"}
    <path d="M5 12h14M12 5l7 7-7 7" />
  {:else if name === "pencil"}
    <path d="M17 3a2.8 2.8 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5z" />
  {:else if name === "alert-triangle"}
    <path
      d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"
    />
    <path d="M12 9v4M12 17h.01" />
  {:else if name === "folder"}
    <path
      d="M3 7.5A2.5 2.5 0 0 1 5.5 5H9l2 2.5h7.5A2.5 2.5 0 0 1 21 10v7.5a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 17.5z"
    />
  {:else if name === "list"}
    <path d="M9 6h11M9 12h11M9 18h11M4.5 6h.01M4.5 12h.01M4.5 18h.01" />
  {:else if name === "board"}
    <rect x="3" y="3.5" width="18" height="17" rx="2.5" />
    <path d="M9 3.5v17M15 3.5v10" />
  {:else if name === "search"}
    <circle cx="11" cy="11" r="7" />
    <path d="m20.5 20.5-4.5-4.5" />
  {:else if name === "sun"}
    <circle cx="12" cy="12" r="4" />
    <path
      d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"
    />
  {:else if name === "moon"}
    <path d="M20.5 14.1A8.5 8.5 0 0 1 9.9 3.5 8.5 8.5 0 1 0 20.5 14.1z" />
  {:else if name === "monitor"}
    <rect x="2.5" y="3.5" width="19" height="13" rx="2.5" />
    <path d="M8 21h8M12 16.5V21" />
  {:else if name === "log-out"}
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" />
  {:else if name === "log-in"}
    <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4M10 17l5-5-5-5M15 12H3" />
  {:else if name === "chevron-down"}
    <path d="m6 9 6 6 6-6" />
  {:else if name === "chevron-right"}
    <path d="m9 6 6 6-6 6" />
  {:else if name === "chevron-up-down"}
    <path d="m7 15 5 5 5-5M7 9l5-5 5 5" />
  {:else if name === "menu"}
    <path d="M4 7h16M4 12h16M4 17h16" />
  {:else if name === "more"}
    <path d="M5 12h.01M12 12h.01M19 12h.01" stroke-width="3" />
  {:else if name === "filter"}
    <path d="M3 5h18M6.5 12h11M10 19h4" />
  {:else if name === "pulse"}
    <path d="M3 12h4l3-8 4 16 3-8h4" />
  {:else if name === "workflow"}
    <rect x="3" y="3" width="7" height="7" rx="1.5" />
    <rect x="14" y="14" width="7" height="7" rx="1.5" />
    <path d="M6.5 10v4a3 3 0 0 0 3 3H14" />
  {:else if name === "archive"}
    <rect x="2.5" y="3.5" width="19" height="5" rx="1.5" />
    <path d="M4.5 8.5v10a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-10M10 12.5h4" />
  {:else if name === "home"}
    <path
      d="M3 10.5 12 3l9 7.5V19a2 2 0 0 1-2 2h-4.5v-6h-5v6H5a2 2 0 0 1-2-2z"
    />
  {:else if name === "palette"}
    <path
      d="M12 21a9 9 0 1 1 9-9c0 2.5-2 3.5-4 3.5h-1.8a1.7 1.7 0 0 0-1.2 2.9 1.6 1.6 0 0 1-1.1 2.6z"
    />
    <path d="M7.5 11h.01M10 7h.01M15 7.5h.01" stroke-width="2.5" />
  {:else if name === "layers"}
    <path d="m12 3 9 5-9 5-9-5z" />
    <path d="m3 13 9 5 9-5" />
  {:else if name === "corner-down-left"}
    <path d="M9 10 4 15l5 5" />
    <path d="M20 4v7a4 4 0 0 1-4 4H4" />
  {:else if name === "circle"}
    <circle cx="12" cy="12" r="8.5" />
  {:else if name === "grid"}
    <rect x="3" y="3" width="7.5" height="7.5" rx="2" />
    <rect x="13.5" y="3" width="7.5" height="7.5" rx="2" />
    <rect x="3" y="13.5" width="7.5" height="7.5" rx="2" />
    <rect x="13.5" y="13.5" width="7.5" height="7.5" rx="2" />
  {:else if name === "command"}
    <path
      d="M9 6a3 3 0 1 0-3 3h12a3 3 0 1 0-3-3v12a3 3 0 1 0 3-3H6a3 3 0 1 0 3 3z"
    />
  {:else if name === "target"}
    <circle cx="12" cy="12" r="9" />
    <circle cx="12" cy="12" r="5" />
    <circle cx="12" cy="12" r="1" />
  {:else if name === "flag"}
    <path d="M5 21V4M5 4h11l-2 4 2 4H5" />
  {:else if name === "trend"}
    <path d="m3 17 6-6 4 4 8-8M15 7h6v6" />
  {:else if name === "copy"}
    <rect x="8" y="8" width="13" height="13" rx="2.5" />
    <path
      d="M16 8V5.5A2.5 2.5 0 0 0 13.5 3h-8A2.5 2.5 0 0 0 3 5.5v8A2.5 2.5 0 0 0 5.5 16H8"
    />
    <!-- Brand paths adapted from Tabler Icons; MIT notice: /assets/icon-licenses.txt. -->
  {:else if name === "telegram"}
    <path d="M15 10l-4 4l6 6l4 -16l-18 7l4 2l2 6l3 -4" />
  {:else if name === "slack"}
    <path d="M12 12v-6a2 2 0 0 1 4 0v6m0 -2a2 2 0 1 1 2 2h-6" />
    <path d="M12 12h6a2 2 0 0 1 0 4h-6m2 0a2 2 0 1 1 -2 2v-6" />
    <path d="M12 12v6a2 2 0 0 1 -4 0v-6m0 2a2 2 0 1 1 -2 -2h6" />
    <path d="M12 12h-6a2 2 0 0 1 0 -4h6m-2 0a2 2 0 1 1 2 -2v6" />
  {:else if name === "discord"}
    <path d="M8 12a1 1 0 1 0 2 0a1 1 0 0 0 -2 0" />
    <path d="M14 12a1 1 0 1 0 2 0a1 1 0 0 0 -2 0" />
    <path
      d="M15.5 17c0 1 1.5 3 2 3c1.5 0 2.833 -1.667 3.5 -3c.667 -1.667 .5 -5.833 -1.5 -11.5c-1.457 -1.015 -3 -1.34 -4.5 -1.5l-.972 1.923a11.913 11.913 0 0 0 -4.053 0l-.975 -1.923c-1.5 .16 -3.043 .485 -4.5 1.5c-2 5.667 -2.167 9.833 -1.5 11.5c.667 1.333 2 3 3.5 3c.5 0 2 -2 2 -3"
    />
    <path d="M7 16.5c3.5 1 6.5 1 10 0" />
  {:else if name === "circle-check"}
    <circle cx="12" cy="12" r="9" />
    <path d="m8.5 12 2.5 2.5 4.5-5" />
  {:else if name === "image"}
    <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
    <circle cx="8.5" cy="8.5" r="1.5" />
    <polyline points="21 15 16 10 5 21" />
  {:else if name === "upload"}
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <polyline points="17 8 12 3 7 8" />
    <line x1="12" y1="3" x2="12" y2="15" />
  {:else if name === "play"}
    <polygon points="6 4 20 12 6 20 6 4" />
  {:else if name === "stop"}
    <rect x="5" y="5" width="14" height="14" rx="2" />
  {:else if name === "pause"}
    <rect x="6" y="4" width="4" height="16" rx="1" />
    <rect x="14" y="4" width="4" height="16" rx="1" />
  {/if}
</svg>
{/if}

<style>
  :global(.svg-icon) {
    display: inline-block;
    vertical-align: middle;
    flex-shrink: 0;
  }
</style>
