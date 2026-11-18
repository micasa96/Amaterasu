<script lang="ts">
  import { untrack } from "svelte";
  import Shell from "../../ui/Shell.svelte";
  import Icon from "../../ui/Icon.svelte";

  // Google OAuth callback failure (/app/token-generator/callback). The
  // attempt is one-time, so the only recovery is a fresh /tokengen link.
  let { data }: { data: { message: string } } = $props();
  const message = untrack(() => data.message);
</script>

<Shell place="OAuth attempt unavailable" crumbs={["Tools", "Google token generator"]}>
  <div class="page page-narrow error-page">
    <section class="card panel-pad error-card" aria-labelledby="error-title">
      <span class="error-mark"><Icon name="alert-triangle" size={22} /></span>
      <h1 id="error-title">OAuth attempt unavailable</h1>
      <p>{message}</p>
      <p class="note">
        Send <code>/tokengen</code> to the bot for a new private link, then start the
        authorization again.
      </p>
    </section>
  </div>
</Shell>

<style>
  .error-page {
    margin: var(--space-8) auto 0;
    width: 100%;
    max-width: 34rem;
  }

  .error-card {
    display: grid;
    justify-items: center;
    gap: var(--space-3);
    padding: var(--space-10) var(--space-6);
    text-align: center;
  }

  .error-mark {
    display: grid;
    place-items: center;
    width: 3rem;
    height: 3rem;
    margin-bottom: var(--space-1);
    border-radius: 0.9rem;
    background: var(--danger-soft);
    color: var(--danger);
  }

  .error-card p {
    max-width: 44ch;
    overflow-wrap: anywhere;
  }
</style>
