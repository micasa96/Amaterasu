<script lang="ts">
  import { identityHue, initials } from "../lib/identity";

  let {
    id,
    name,
    avatarUrl = null,
    size = "md",
    class: className = "",
    title,
  }: {
    id: string;
    name: string;
    avatarUrl?: string | null;
    size?: "sm" | "md" | "lg";
    class?: string;
    title?: string;
  } = $props();

  let imgFailed = $state(false);

  $effect(() => {
    // When avatarUrl changes (e.g. upload or refresh), allow image to render again.
    if (avatarUrl) {
      imgFailed = false;
    }
  });
</script>

<span
  class="avatar {size === 'sm'
    ? 'avatar-sm'
    : size === 'lg'
      ? 'avatar-lg'
      : ''} {className}"
  style:--avatar-hue={identityHue(id)}
  {title}
  aria-hidden="true"
>
  {#if avatarUrl && !imgFailed}
    <img
      src={avatarUrl}
      alt=""
      class="avatar-img"
      onerror={() => {
        imgFailed = true;
      }}
    />
  {/if}
  <span class="avatar-initials">{initials(name)}</span>
</span>
