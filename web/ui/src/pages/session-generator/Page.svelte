<script lang="ts">
  import { untrack } from "svelte";
  import DatabaseZap from "@lucide/svelte/icons/database-zap";
  import ExternalLink from "@lucide/svelte/icons/external-link";
  import Eye from "@lucide/svelte/icons/eye";
  import EyeOff from "@lucide/svelte/icons/eye-off";
  import FingerprintPattern from "@lucide/svelte/icons/fingerprint-pattern";
  import KeyRound from "@lucide/svelte/icons/key-round";
  import LockKeyhole from "@lucide/svelte/icons/lock-keyhole";
  import MessageSquare from "@lucide/svelte/icons/message-square";
  import Send from "@lucide/svelte/icons/send";
  import Shield from "@lucide/svelte/icons/shield";
  import ShieldCheck from "@lucide/svelte/icons/shield-check";
  import Smartphone from "@lucide/svelte/icons/smartphone";
  import Shell, { type NavGroup } from "../../ui/Shell.svelte";
  import Feedback from "../../ui/Feedback.svelte";
  import Icon from "../../ui/Icon.svelte";
  import EmptyState from "../../ui/EmptyState.svelte";
  import { toast } from "../../lib/toast.svelte";

  // Telegram session generator (/app/session-generator). Every step is a
  // native form POST that the server answers with a redirect back here
  // (?step=code|password&attempt=..., ?success=1 or ?error=...). Phone, code,
  // API hash and password are never stored by this page; a saved session is
  // decrypted only when the person presses Copy, and the plaintext is
  // dropped right after it reaches the clipboard.
  interface SavedSession {
    session_id: string;
    account: string;
    telegram_user_id: number | string | null;
    is_premium: boolean;
    created: string;
    is_current: boolean;
  }

  let {
    data,
  }: {
    data: {
      user_id: number | string;
      page_token: string;
      step: "details" | "code" | "password";
      attempt_id: string;
      phone_hint: string;
      password_hint: string;
      session_history: SavedSession[];
      error: string;
      success: boolean;
    };
  } = $props();

  const d = untrack(() => data);
  const auth = `user_id=${encodeURIComponent(String(d.user_id))}&token=${encodeURIComponent(d.page_token)}`;
  const step = d.success ? "done" : d.step;
  const history = d.session_history ?? [];

  let submitting = $state(false);
  let showPassword = $state(false);
  let passwordInput = $state<HTMLInputElement | null>(null);
  let code = $state<HTMLInputElement | null>(null);

  // Copy state per saved session id.
  let copying = $state<Record<string, "busy" | "done" | "error" | undefined>>({});
  let copyMessage = $state<Record<string, string>>({});

  // Digits typed or pasted normally; spaces are inserted so the value
  // matches the pattern the server expects ("1 2 3 4 5").
  function formatLoginCode() {
    if (!code) return;
    const cursor = code.selectionStart ?? code.value.length;
    const digitsBeforeCursor = code.value.slice(0, cursor).replace(/\D/g, "").length;
    const digits = code.value.replace(/\D/g, "").slice(0, 6);
    code.value = digits.split("").join(" ");
    const nextCursor = Math.min(digitsBeforeCursor * 2, code.value.length);
    code.setSelectionRange(nextCursor, nextCursor);
  }

  function onCodeKeydown(event: KeyboardEvent) {
    if (!code) return;
    const start = code.selectionStart ?? 0;
    if (
      event.key === "Backspace" &&
      start === code.selectionEnd &&
      start > 0 &&
      code.value[start - 1] === " "
    ) {
      code.setSelectionRange(start - 1, start - 1);
    }
  }

  function togglePassword() {
    showPassword = !showPassword;
    passwordInput?.focus();
  }

  async function writeSessionToClipboard(value: string) {
    if (navigator.clipboard && window.isSecureContext) {
      try {
        await navigator.clipboard.writeText(value);
        return;
      } catch {
        // Fall through to the short-lived textarea when permissions block it.
      }
    }
    const field = document.createElement("textarea");
    field.value = value;
    field.setAttribute("readonly", "");
    field.style.position = "fixed";
    field.style.opacity = "0";
    document.body.appendChild(field);
    field.select();
    const copied = document.execCommand("copy");
    field.value = "";
    field.remove();
    if (!copied) throw new Error("Browser clipboard permission was denied");
  }

  async function copySession(sessionId: string) {
    const body = new FormData();
    body.append("session_id", sessionId);
    copying[sessionId] = "busy";
    copyMessage[sessionId] = "";
    try {
      const response = await fetch(`/api/session-generator/copy?${auth}`, {
        method: "POST",
        body,
        credentials: "same-origin",
        cache: "no-store",
        headers: { Accept: "application/json" },
      });
      let result: { session?: string; detail?: string } = {};
      try {
        result = await response.json();
      } catch {
        // Non-JSON proxy errors get the safe recovery message below.
      }
      if (!response.ok || !result.session) {
        throw new Error(
          result.detail ||
            "Could not retrieve this session. Refresh your private link and try again.",
        );
      }
      await writeSessionToClipboard(result.session);
      result.session = "";
      copying[sessionId] = "done";
      toast.show("Session copied to your clipboard");
      setTimeout(() => {
        if (copying[sessionId] === "done") copying[sessionId] = undefined;
      }, 2000);
    } catch (error) {
      copying[sessionId] = "error";
      copyMessage[sessionId] =
        (error instanceof Error && error.message) ||
        "Could not copy this session. Refresh your private link and try again.";
    }
  }

  const stepIndex = { details: 0, code: 1, password: 1, done: 3 }[step];
  const stepLabels = ["Account", "Login code", "Secure vault"];

  const nav: NavGroup[] = [
    {
      label: "Session generator",
      items: [
        { label: "Sign in", href: "#signin", glyph: Smartphone, current: true },
        { label: "Session history", href: "#history", glyph: DatabaseZap },
      ],
    },
  ];
</script>

<Shell
  place="Telegram session generator"
  crumbs={["Tools"]}
  {nav}
  note="Each visit needs a fresh private link from /sessiongen."
>
  <div class="page">
    <header class="page-head">
      <div>
        <h1>Telegram session generator</h1>
        <p>
          Create an encrypted WZGram session and receive it privately in Telegram Saved
          Messages.
        </p>
      </div>
    </header>

    {#if d.error || d.success}
      <div class="stack">
        {#if d.error}
          <Feedback tone="danger" announcement="alert">{d.error}</Feedback>
        {/if}
        {#if d.success}
          <Feedback tone="success" announcement="status">
            Your new session is active, was added to your history, and was sent to your
            Telegram Saved Messages.
          </Feedback>
        {/if}
      </div>
    {/if}

    <div class="split session-layout">
      <section class="card" id="signin" aria-labelledby="session-form-title">
        <header class="panel-head">
          <ol class="steps" aria-label="Session generation progress">
            {#each stepLabels as label, i (label)}
              <li
                aria-current={i === stepIndex ? "step" : undefined}
                data-done={i < stepIndex ? "" : undefined}
              >
                {label}
              </li>
            {/each}
          </ol>
        </header>

        <div class="panel-body">
          {#if step === "details" || step === "done"}
            <div class="tile-head">
              <span class="tile"><Icon icon={Smartphone} size={17} /></span>
              <div>
                <h2 id="session-form-title">
                  {step === "done" ? "Create another session" : "Connect your Telegram account"}
                </h2>
                <p>
                  Telegram sends a login code to your account. Amaterasu never writes your
                  phone, code, API hash, or password to the database.
                </p>
              </div>
            </div>

            <form
              class="form-grid"
              method="post"
              action="/api/session-generator/start?{auth}"
              onsubmit={() => (submitting = true)}
            >
              <p class="aside-note">
                <Icon icon={ExternalLink} size={16} />
                <span>
                  Enter the API ID and API hash for your own Telegram application. You can
                  create one at
                  <a href="https://my.telegram.org/apps" target="_blank" rel="noopener noreferrer"
                    >my.telegram.org/apps</a
                  >.
                </span>
              </p>
              <div class="field">
                <label for="api-id">Telegram API ID</label>
                <!-- svelte-ignore a11y_autofocus -->
                <input
                  id="api-id"
                  class="mono"
                  name="api_id"
                  type="text"
                  inputmode="numeric"
                  maxlength="10"
                  autocomplete="off"
                  spellcheck="false"
                  placeholder="12345678"
                  required
                  autofocus={step === "details"}
                />
              </div>
              <div class="field">
                <label for="api-hash">Telegram API hash</label>
                <input
                  id="api-hash"
                  class="mono"
                  name="api_hash"
                  type="password"
                  maxlength="32"
                  autocomplete="off"
                  spellcheck="false"
                  aria-describedby="api-hash-hint"
                  required
                />
                <p id="api-hash-hint" class="note">
                  Use the 32-character API hash shown beside your application.
                </p>
              </div>
              <div class="field">
                <label for="phone">Phone number</label>
                <input
                  id="phone"
                  class="mono"
                  name="phone"
                  type="tel"
                  maxlength="64"
                  autocomplete="tel"
                  placeholder="+14154566376"
                  aria-describedby="phone-hint"
                  required
                />
                <p id="phone-hint" class="note">Include the country code and leading plus sign.</p>
              </div>
              <p class="aside-note">
                <Icon icon={LockKeyhole} size={16} />
                <span>
                  Your sign-in stays in server memory for up to 10 minutes. Only the final
                  session is encrypted and saved.
                </span>
              </p>
              <div class="form-actions">
                <button class="btn btn-primary" type="submit" disabled={submitting} aria-busy={submitting}>
                  {#if submitting}
                    <span class="spinner" aria-hidden="true"></span>
                    <span>Connecting to Telegram...</span>
                  {:else}
                    <Icon icon={Send} size={16} />
                    <span>Send login code</span>
                  {/if}
                </button>
              </div>
            </form>
          {:else if step === "code"}
            <div class="tile-head">
              <span class="tile"><Icon icon={MessageSquare} size={17} /></span>
              <div>
                <h2 id="session-form-title">Enter the Telegram login code</h2>
                <p>
                  Telegram sent the code to {d.phone_hint}. Type or paste the digits normally;
                  spacing is added automatically.
                </p>
              </div>
            </div>

            <form
              class="form-grid"
              method="post"
              action="/api/session-generator/verify?{auth}"
              onsubmit={() => (submitting = true)}
            >
              <input type="hidden" name="attempt" value={d.attempt_id} />
              <div class="field code-field">
                <label for="code">Login code</label>
                <!-- svelte-ignore a11y_autofocus -->
                <input
                  bind:this={code}
                  id="code"
                  class="mono"
                  name="code"
                  type="text"
                  inputmode="numeric"
                  maxlength="11"
                  autocomplete="one-time-code"
                  placeholder="1 2 3 4 5"
                  pattern="[0-9]( [0-9]){'{'}4,5{'}'}"
                  aria-describedby="code-hint"
                  required
                  autofocus
                  oninput={formatLoginCode}
                  onkeydown={onCodeKeydown}
                />
                <p id="code-hint" class="note">Enter the 5 or 6 digit code without adding spaces.</p>
              </div>
              <p class="aside-note">
                <Icon icon={Shield} size={16} />
                <span>The code is used once for this sign-in and is never written to the database.</span>
              </p>
              <div class="form-actions">
                <button class="btn btn-primary" type="submit" disabled={submitting} aria-busy={submitting}>
                  {#if submitting}
                    <span class="spinner" aria-hidden="true"></span>
                    <span>Connecting to Telegram...</span>
                  {:else}
                    <Icon icon={KeyRound} size={16} />
                    <span>Verify and create session</span>
                  {/if}
                </button>
              </div>
            </form>
            <form class="cancel" method="post" action="/api/session-generator/cancel?{auth}">
              <input type="hidden" name="attempt" value={d.attempt_id} />
              <button class="btn btn-quiet" type="submit">Cancel sign-in</button>
            </form>
          {:else}
            <div class="tile-head">
              <span class="tile"><Icon icon={ShieldCheck} size={17} /></span>
              <div>
                <h2 id="session-form-title">Complete two-step verification</h2>
                <p>Your account requires its Telegram two-step verification password.</p>
              </div>
            </div>

            <form
              class="form-grid"
              method="post"
              action="/api/session-generator/password?{auth}"
              onsubmit={() => (submitting = true)}
            >
              <input type="hidden" name="attempt" value={d.attempt_id} />
              <div class="field">
                <label for="password">Two-step verification password</label>
                <div class="password-wrap">
                  <!-- svelte-ignore a11y_autofocus -->
                  <input
                    bind:this={passwordInput}
                    id="password"
                    name="password"
                    type={showPassword ? "text" : "password"}
                    maxlength="256"
                    autocomplete="current-password"
                    aria-describedby={d.password_hint ? "password-hint" : undefined}
                    required
                    autofocus
                  />
                  <button
                    id="password-toggle"
                    class="btn-quiet btn-icon reveal"
                    type="button"
                    aria-label={showPassword ? "Hide password" : "Show password"}
                    aria-pressed={showPassword}
                    onclick={togglePassword}
                  >
                    <Icon icon={showPassword ? EyeOff : Eye} size={18} />
                  </button>
                </div>
                {#if d.password_hint}
                  <p id="password-hint" class="note">Telegram hint: {d.password_hint}</p>
                {/if}
              </div>
              <p class="aside-note">
                <Icon icon={LockKeyhole} size={16} />
                <span>Your password is sent directly to Telegram for verification and is never saved.</span>
              </p>
              <div class="form-actions">
                <button class="btn btn-primary" type="submit" disabled={submitting} aria-busy={submitting}>
                  {#if submitting}
                    <span class="spinner" aria-hidden="true"></span>
                    <span>Connecting to Telegram...</span>
                  {:else}
                    <Icon icon={ShieldCheck} size={16} />
                    <span>Unlock and create session</span>
                  {/if}
                </button>
              </div>
            </form>
            <form class="cancel" method="post" action="/api/session-generator/cancel?{auth}">
              <input type="hidden" name="attempt" value={d.attempt_id} />
              <button class="btn btn-quiet" type="submit">Cancel sign-in</button>
            </form>
          {/if}
        </div>
      </section>

      <aside class="card rail" id="history" aria-labelledby="history-title">
        <header class="panel-head">
          <div class="tile-head">
            <span class="tile"><Icon icon={DatabaseZap} size={17} /></span>
            <div>
              <h2 id="history-title">Session history</h2>
              <p>
                {#if history.length}
                  {history.length} encrypted session{history.length === 1 ? "" : "s"} saved
                {:else}
                  Encrypted in your private record
                {/if}
              </p>
            </div>
          </div>
        </header>
        <div class="panel-body">
          {#if history.length}
            <ul class="rows">
              {#each history as saved (saved.session_id)}
                {@const state = copying[saved.session_id]}
                <li class="inset saved">
                  <div class="spread">
                    <h3 class="row-title">{saved.account}</h3>
                    {#if saved.is_current}
                      <span class="pill" data-tone="success"><span class="dot"></span>Current</span>
                    {/if}
                  </div>
                  <dl class="kv">
                    <dt>Telegram ID</dt>
                    <dd>{saved.telegram_user_id ?? "Unknown"}</dd>
                    <dt>Premium</dt>
                    <dd>{saved.is_premium ? "Yes" : "No"}</dd>
                    <dt>Created</dt>
                    <dd>{saved.created}</dd>
                  </dl>
                  <button
                    type="button"
                    class="btn btn-secondary"
                    data-copy-session={saved.session_id}
                    disabled={state === "busy"}
                    aria-busy={state === "busy"}
                    onclick={() => copySession(saved.session_id)}
                  >
                    {#if state === "busy"}
                      <span class="spinner" aria-hidden="true"></span>
                      <span>Decrypting...</span>
                    {:else}
                      <Icon name={state === "done" ? "check" : "copy"} size={16} />
                      <span>
                        {state === "done" ? "Copied" : state === "error" ? "Try again" : "Copy session"}
                      </span>
                    {/if}
                  </button>
                  {#if state === "error" && copyMessage[saved.session_id]}
                    <Feedback tone="danger" announcement="alert">{copyMessage[saved.session_id]}</Feedback>
                  {/if}
                </li>
              {/each}
            </ul>
          {:else}
            <EmptyState title="No session saved yet" icon={FingerprintPattern}>
              Complete Telegram sign-in to create your private session record.
            </EmptyState>
          {/if}

          <p class="aside-note">
            <Icon icon={ShieldCheck} size={16} />
            <span>
              Sessions stay encrypted in the database and are
              decrypted only when you press Copy. A fresh private link from
              <code>/sessiongen</code> is required for every visit.
            </span>
          </p>
        </div>
      </aside>
    </div>
  </div>
</Shell>

<style>
  .session-layout {
    grid-template-columns: minmax(0, 1fr) minmax(18rem, 24rem);
  }

  .rail {
    position: sticky;
    top: calc(var(--topbar-height) + var(--space-5));
  }

  .tile-head h2 {
    font-size: 1.3125rem;
    font-weight: 520;
    letter-spacing: var(--tracking-heading);
  }

  .rail .tile-head h2 {
    font-size: var(--text-section);
    font-weight: 540;
  }

  .tile-head {
    align-items: flex-start;
  }

  .tile-head p {
    max-width: 62ch;
    margin-top: var(--space-1);
  }

  .mono {
    font-family: var(--font-mono);
    font-size: var(--text-small);
  }

  .aside-note {
    display: flex;
    align-items: flex-start;
    gap: var(--space-2);
    font-size: var(--text-xs);
    line-height: 1.55;
    color: var(--text-muted);
  }

  .aside-note :global(.svg-icon) {
    flex-shrink: 0;
    margin-top: 1px;
    color: var(--text-secondary);
  }

  .code-field {
    max-width: 20rem;
  }

  .code-field input {
    font-size: 1.125rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    font-variant-numeric: tabular-nums;
  }

  .password-wrap {
    position: relative;
    max-width: 32rem;
  }

  .password-wrap input {
    padding-right: calc(var(--control-height) + var(--space-1));
  }

  .reveal {
    position: absolute;
    top: 0;
    right: 0;
    color: var(--text-muted);
  }

  .form-actions {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    padding-top: var(--space-1);
  }

  .form-actions .btn {
    flex: 1 1 14rem;
  }

  .cancel {
    display: flex;
    justify-content: center;
    margin-top: calc(var(--space-2) * -1);
  }

  .saved {
    display: grid;
    gap: var(--space-3);
    padding: var(--space-4);
  }

  .saved h3 {
    font-size: var(--text-ui);
    overflow-wrap: anywhere;
  }

  .saved .btn {
    width: 100%;
  }

  @media (max-width: 64rem) {
    .session-layout {
      grid-template-columns: minmax(0, 1fr);
    }
    .rail {
      position: static;
    }
  }

  @media (max-width: 40rem) {
    /* 16px fields stop iOS from zooming on focus. */
    input,
    .mono {
      font-size: 1rem;
    }
    .cancel .btn {
      width: 100%;
    }
  }
</style>
