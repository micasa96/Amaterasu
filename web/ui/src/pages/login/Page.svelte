<script lang="ts">
  import { onMount, untrack } from "svelte";
  import Lockup from "../../ui/Lockup.svelte";
  import Feedback from "../../ui/Feedback.svelte";
  import Icon from "../../ui/Icon.svelte";
  import { preferences } from "../../lib/preferences.svelte";

  // Owner sign-in for the web UI (LOGIN_PASS). The form posts to /login,
  // which answers JSON {"status":"ok"} and sets the session cookie, or a
  // 401 with an error. Without JavaScript the plain form post still works.
  let { data }: { data: { error?: string } } = $props();

  let password = $state("");
  let busy = $state(false);
  let error = $state(untrack(() => data.error) ?? "");
  let input = $state<HTMLInputElement | null>(null);

  const next = (() => {
    const raw = new URLSearchParams(location.search).get("next") ?? "/";
    // Only same-origin paths.
    return raw.startsWith("/") && !raw.startsWith("//") ? raw : "/";
  })();

  onMount(() => {
    document.title = "Sign in — Amaterasu";
    input?.focus();
  });

  async function submit(e: SubmitEvent) {
    e.preventDefault();
    if (busy) return;
    busy = true;
    error = "";
    try {
      const res = await fetch("/login", {
        method: "POST",
        body: new URLSearchParams({ password }),
        credentials: "same-origin",
      });
      if (res.ok) {
        location.href = next;
        return;
      }
      let message = "That password is not correct.";
      try {
        const body = await res.json();
        message = body.detail || body.error || body.message || message;
      } catch {
        /* keep default */
      }
      error = message;
      password = "";
      input?.focus();
    } catch {
      error = "Could not reach the server. Check the connection and try again.";
    } finally {
      busy = false;
    }
  }
</script>

<a class="skip-link" href="#signin">Skip to sign in</a>

<div class="signin-page">
  <header class="signin-top">
    <a class="brand" href="/" aria-label="Amaterasu home">
      <span class="full"><Lockup size="md" /></span>
      <span class="compact"><Lockup size="md" showWordmark={false} /></span>
    </a>
    <button
      type="button"
      class="btn-icon btn-quiet"
      onclick={() => preferences.toggleScheme()}
      aria-label={preferences.resolvedDark ? "Switch to light theme" : "Switch to dark theme"}
    >
      <Icon name={preferences.resolvedDark ? "sun" : "moon"} size={18} />
    </button>
  </header>

  <main id="signin" class="signin-main" tabindex="-1">
    <form class="card signin-card rim" method="POST" action="/login" onsubmit={submit}>
      <div class="signin-head">
        <span class="tile tile-lg"><Icon name="log-in" size={20} /></span>
        <h1>Sign in</h1>
        <p>Enter the web password set in <code>LOGIN_PASS</code> to manage this instance.</p>
      </div>

      <div class="field">
        <label for="password">Password</label>
        <input
          bind:this={input}
          bind:value={password}
          id="password"
          name="password"
          type="password"
          autocomplete="current-password"
          required
          aria-invalid={error ? "true" : undefined}
          aria-describedby={error ? "signin-error" : undefined}
        />
      </div>

      {#if error}
        <div id="signin-error"><Feedback tone="danger" announcement="alert">{error}</Feedback></div>
      {/if}

      <button type="submit" class="btn btn-primary signin-submit" disabled={busy || !password}>
        {#if busy}<span class="spinner" aria-hidden="true"></span> Signing in…{:else}Sign in{/if}
      </button>

      <p class="note">Sessions last seven days. Changing the password signs every session out.</p>
    </form>
  </main>
</div>

<style>
  .signin-page {
    position: relative;
    min-height: 100svh;
    display: grid;
    grid-template-rows: auto 1fr;
    isolation: isolate;
  }

  /* The same ambient light as the app canvas. */
  .signin-page::before {
    content: "";
    position: absolute;
    inset: 0 0 auto 0;
    height: 34rem;
    z-index: -1;
    pointer-events: none;
    background:
      linear-gradient(112deg, transparent 44%, var(--sheen) 56%, transparent 66%),
      radial-gradient(46rem 22rem at 50% -8rem, var(--glow-accent), transparent 72%);
    mask-image: linear-gradient(180deg, #000 35%, transparent 100%);
  }

  .signin-top {
    container-type: inline-size;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    padding: var(--space-4) var(--gutter);
  }

  /* With enlarged text on a narrow phone, keep the flame and drop the
     wordmark rather than scroll sideways (the link keeps its label). */
  .compact {
    display: none;
  }

  @container (max-width: 15em) {
    .full {
      display: none;
    }
    .compact {
      display: inline-flex;
    }
  }

  .brand {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    color: var(--text);
    text-decoration: none;
  }

  .signin-main {
    display: grid;
    place-items: center;
    padding: var(--space-6) var(--gutter) var(--space-16);
  }

  .signin-card {
    width: min(100%, 26rem);
    min-width: 0;
    display: grid;
    gap: var(--space-5);
    padding: var(--space-8) var(--space-6) var(--space-6);
    overflow-wrap: anywhere;
  }

  @media (max-width: 30rem) {
    .signin-card {
      padding: var(--space-6) var(--space-4) var(--space-5);
    }
  }

  .signin-head {
    display: grid;
    justify-items: start;
    gap: var(--space-2);
  }

  .signin-head .tile {
    margin-bottom: var(--space-2);
  }

  .signin-head h1 {
    font-size: var(--text-title);
  }

  .signin-submit {
    width: 100%;
  }
</style>
