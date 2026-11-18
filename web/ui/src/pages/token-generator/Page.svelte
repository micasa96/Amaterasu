<script lang="ts">
  import { untrack } from "svelte";
  import CloudCheck from "@lucide/svelte/icons/cloud-check";
  import CloudUpload from "@lucide/svelte/icons/cloud-upload";
  import Download from "@lucide/svelte/icons/download";
  import ExternalLink from "@lucide/svelte/icons/external-link";
  import FileBraces from "@lucide/svelte/icons/file-braces";
  import KeyRound from "@lucide/svelte/icons/key-round";
  import LockKeyhole from "@lucide/svelte/icons/lock-keyhole";
  import RefreshCw from "@lucide/svelte/icons/refresh-cw";
  import ShieldCheck from "@lucide/svelte/icons/shield-check";
  import ShieldExclamationPoint from "@lucide/svelte/icons/shield-exclamation-point";
  import Shell, { type NavGroup } from "../../ui/Shell.svelte";
  import Feedback from "../../ui/Feedback.svelte";
  import Icon from "../../ui/Icon.svelte";
  import CopyButton from "../../ui/CopyButton.svelte";
  import EmptyState from "../../ui/EmptyState.svelte";

  // Google Drive token generator (/app/token-generator). FastAPI renders the
  // signed private link; the OAuth start and activation are native form
  // POSTs that redirect back here with ?success=1, ?active=1, ?refresh=0 or
  // ?error=..., so this page only renders state and never holds secrets.
  interface TokenStatus {
    updated: string;
    size: string;
    scopes: string[];
    json_available: boolean;
    has_refresh_token: boolean;
    is_active: boolean;
  }

  let {
    data,
  }: {
    data: {
      user_id: number | string;
      page_token: string;
      callback_url: string;
      default_scope: string;
      token_status: TokenStatus | null;
      error: string;
      success: boolean;
      activation_success: boolean;
      refresh_warning: boolean;
    };
  } = $props();

  const d = untrack(() => data);
  const auth = `user_id=${encodeURIComponent(String(d.user_id))}&token=${encodeURIComponent(d.page_token)}`;
  const status = d.token_status;

  type Method = "upload" | "manual";
  let method = $state<Method>("upload");
  let fileName = $state("");
  let fileInput = $state<HTMLInputElement | null>(null);
  let clientIdInput = $state<HTMLInputElement | null>(null);
  let dragOver = $state(false);
  let submitting = $state(false);

  function selectMethod(next: Method) {
    method = next;
  }

  function onTabKey(e: KeyboardEvent) {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    const next: Method = method === "upload" ? "manual" : "upload";
    selectMethod(next);
    document.getElementById(`${next}-tab`)?.focus();
  }

  function replaceToken() {
    const target = document.getElementById("authorize");
    target?.scrollIntoView({
      behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
      block: "start",
    });
    window.setTimeout(() => {
      if (method === "upload") fileInput?.focus();
      else clientIdInput?.focus();
    }, 350);
  }

  const nav: NavGroup[] = [
    {
      label: "Token generator",
      items: [
        { label: "Configure OAuth", href: "#configure", icon: "settings", current: true },
        { label: "Authorize", href: "#authorize", icon: "log-in" },
        { label: "Saved token", href: "#saved", glyph: KeyRound },
      ],
    },
  ];
</script>

<Shell
  place="Google token generator"
  crumbs={["Tools"]}
  {nav}
  note="This private link expires 15 minutes after /tokengen sent it."
>
  <div class="page">
    <header class="page-head">
      <div>
        <h1>Google token generator</h1>
        <p>Create and securely save your personal Google Drive token.pickle.</p>
      </div>
    </header>

    <div class="stack">
      {#if d.error}
        <Feedback tone="danger" announcement="alert">{d.error}</Feedback>
      {/if}
      {#if d.success}
        <Feedback tone="success" announcement="status">
          Your token.pickle was generated, encrypted, and saved to your private download
          library. Your active Drive token was not changed.
        </Feedback>
      {/if}
      {#if d.activation_success}
        <Feedback tone="success" announcement="status">
          This generated token is now your active per-user Google Drive token in Amaterasu.
        </Feedback>
      {/if}
      {#if d.refresh_warning}
        <Feedback tone="warning" announcement="status">
          Google did not return a refresh token. Revoke the app in your Google Account, then
          replace this token if long-term offline access is required.
        </Feedback>
      {/if}
      <Feedback tone="warning">
        <span>For longer-lived Google Drive access, set your Google OAuth Audience publishing status
        to <strong>In production</strong>, then generate a new token. External projects in
        Testing issue refresh tokens that expire after 7 days, for both Web and Desktop
        clients. The private page link's 15-minute expiry is separate.</span>
      </Feedback>
    </div>

    <div class="split token-layout">
      <div class="work">
        <section class="card" id="configure" aria-labelledby="configure-title">
          <header class="panel-head">
            <div class="tile-head">
              <span class="tile"><Icon name="settings" size={17} /></span>
              <div>
                <h2 id="configure-title">Configure Google OAuth</h2>
                <p>Create a Web application OAuth client and add this exact callback URL.</p>
              </div>
            </div>
          </header>
          <div class="panel-body">
            <div class="field">
              <label for="callback-url">Authorized redirect URI (read-only)</label>
              <div class="copy-field">
                <input
                  id="callback-url"
                  class="mono"
                  type="text"
                  value={d.callback_url}
                  readonly
                  aria-describedby="callback-hint"
                  onfocus={(e) => (e.currentTarget as HTMLInputElement).select()}
                />
                <CopyButton value={d.callback_url} confirm="Redirect URI copied" />
              </div>
              <p id="callback-hint" class="note">
                It must match Google Cloud character-for-character.
              </p>
            </div>

            <hr class="divider" />

            <div class="guide-head">
              <div>
                <h3>Prepare your OAuth client before you continue with Google</h3>
                <p class="note">
                  Use the same Google account for the Cloud project, test user, login hint, and
                  final authorization. On mobile, switch Google Cloud Console to desktop mode
                  first.
                </p>
              </div>
              <a
                class="btn btn-secondary"
                href="https://console.cloud.google.com/"
                target="_blank"
                rel="noopener noreferrer"
              >
                <Icon icon={ExternalLink} size={16} />
                <span>Open Console</span>
              </a>
            </div>

            <ol class="guide">
              <li class="inset">
                <strong>Secure the account</strong>
                <span>Enable 2-Step Verification, then create or select a Google Cloud project.</span>
              </li>
              <li class="inset">
                <strong>Enable Drive API</strong>
                <span>Go to APIs &amp; Services, open Library, search Google Drive API, and enable it.</span>
              </li>
              <li class="inset">
                <strong>Set consent screen</strong>
                <span>Open OAuth consent screen, click Get Started, enter an app name, choose External, add your Gmail, and save.</span>
              </li>
              <li class="inset">
                <strong>Add test user</strong>
                <span>In OAuth consent screen, open Audience, add the same Gmail under Test users.</span>
              </li>
              <li class="inset">
                <strong>Create Web client</strong>
                <span>Go to Credentials, create an OAuth client ID, and choose Web application.</span>
              </li>
              <li class="inset">
                <strong>Paste this redirect URI</strong>
                <span>Copy the URI above into Authorized redirect URIs, then create the client.</span>
              </li>
              <li class="inset">
                <strong>Download credentials</strong>
                <span>Download the OAuth client JSON and rename it exactly to credentials.json.</span>
              </li>
              <li class="inset">
                <strong>Authorize here</strong>
                <span>Upload credentials.json below, enter the same Gmail as the login hint, continue, review Google's warning, and allow access.</span>
              </li>
            </ol>

            <p class="aside-note">
              <Icon icon={ShieldExclamationPoint} size={16} />
              <span>
                Only continue past Google's unverified-app warning when the Cloud project and
                OAuth credentials belong to you. Keep credentials.json, token.pickle, and this
                private bot link away from public repos and shared chats.
              </span>
            </p>
          </div>
        </section>

        <section class="card" id="authorize" aria-labelledby="authorize-title">
          <header class="panel-head">
            <div class="tile-head">
              <span class="tile"><Icon name="log-in" size={17} /></span>
              <div>
                <h2 id="authorize-title">Authorize your account</h2>
                <p>
                  Upload your Web application client file or enter the same values manually.
                </p>
              </div>
            </div>
          </header>

          <form
            id="oauth-form"
            class="panel-body"
            method="post"
            enctype="multipart/form-data"
            action="/api/token-generator/start?{auth}"
            onsubmit={() => (submitting = true)}
          >
            <p class="note">
              Desktop app clients require a callback on your own computer and cannot use this
              hosted portal.
            </p>
            <input type="hidden" name="auth_method" value={method} />

            <div class="segmented method-switch" role="tablist" aria-label="OAuth credential method">
              <button
                id="upload-tab"
                type="button"
                role="tab"
                aria-selected={method === "upload"}
                aria-controls="upload-pane"
                tabindex={method === "upload" ? 0 : -1}
                onclick={() => selectMethod("upload")}
                onkeydown={onTabKey}>Upload credentials.json</button
              >
              <button
                id="manual-tab"
                type="button"
                role="tab"
                aria-selected={method === "manual"}
                aria-controls="manual-pane"
                tabindex={method === "manual" ? 0 : -1}
                onclick={() => selectMethod("manual")}
                onkeydown={onTabKey}>Enter manually</button
              >
            </div>

            <div id="upload-pane" role="tabpanel" aria-labelledby="upload-tab" hidden={method !== "upload"}>
              <div class="upload">
                <input
                  bind:this={fileInput}
                  id="credentials-file"
                  class="visually-hidden"
                  name="credentials_file"
                  type="file"
                  accept=".json,application/json"
                  required={method === "upload"}
                  disabled={method !== "upload"}
                  onchange={(e) =>
                    (fileName = (e.currentTarget as HTMLInputElement).files?.[0]?.name ?? "")}
                />
                <label
                  class="dropzone"
                  for="credentials-file"
                  data-over={dragOver ? "" : undefined}
                  ondragenter={() => (dragOver = true)}
                  ondragleave={() => (dragOver = false)}
                  ondragover={(e) => e.preventDefault()}
                  ondrop={(e) => {
                    e.preventDefault();
                    dragOver = false;
                    const files = e.dataTransfer?.files;
                    if (files?.length && fileInput) {
                      fileInput.files = files;
                      fileName = files[0].name;
                    }
                  }}
                >
                  <span class="tile tile-lg"><Icon icon={CloudUpload} size={20} /></span>
                  <strong>{fileName ? "Replace credentials.json" : "Choose credentials.json"}</strong>
                  <span class="file-name" class:chosen={!!fileName}>{fileName || "No file selected"}</span>
                </label>
              </div>
              <p class="aside-note">
                <Icon icon={LockKeyhole} size={16} />
                <span>
                  Your file is encrypted only for this pending OAuth attempt, consumed once, and
                  never saved as a standalone file.
                </span>
              </p>
            </div>

            <div id="manual-pane" class="form-grid" role="tabpanel" aria-labelledby="manual-tab" hidden={method !== "manual"}>
              <div class="field">
                <label for="client-id">Google OAuth Client ID</label>
                <input
                  bind:this={clientIdInput}
                  id="client-id"
                  class="mono"
                  name="client_id"
                  type="text"
                  maxlength="512"
                  autocomplete="off"
                  spellcheck="false"
                  placeholder="123456789.apps.googleusercontent.com"
                  required={method === "manual"}
                  disabled={method !== "manual"}
                />
              </div>
              <div class="field">
                <label for="client-secret">Google OAuth Client Secret</label>
                <input
                  id="client-secret"
                  class="mono"
                  name="client_secret"
                  type="password"
                  maxlength="512"
                  autocomplete="off"
                  spellcheck="false"
                  required={method === "manual"}
                  disabled={method !== "manual"}
                />
              </div>
              <p class="aside-note">
                <Icon icon={LockKeyhole} size={16} />
                <span>
                  Client values expire after 15 minutes, are consumed once, and are not retained
                  separately from your generated token.
                </span>
              </p>
            </div>

            <div class="field">
              <label for="login-hint">Google account hint <span class="muted">(optional)</span></label>
              <input
                id="login-hint"
                name="login_hint"
                type="email"
                maxlength="320"
                autocomplete="email"
                placeholder="you@example.com"
              />
            </div>
            <div class="field">
              <label for="scopes">Scopes</label>
              <textarea
                id="scopes"
                class="mono"
                name="scopes"
                maxlength="4096"
                rows="3"
                aria-describedby="scopes-hint">{d.default_scope}</textarea
              >
              <p id="scopes-hint" class="note">
                Separate multiple scopes with spaces or new lines. The default grants Google
                Drive access.
              </p>
            </div>

            <button class="btn btn-primary continue" type="submit" disabled={submitting} aria-busy={submitting}>
              {#if submitting}
                <span class="spinner" aria-hidden="true"></span>
                <span>Opening Google…</span>
              {:else}
                <span>Continue with Google</span>
                <Icon name="arrow-right" size={16} />
              {/if}
            </button>
          </form>
        </section>
      </div>

      <aside class="card rail" id="saved" aria-labelledby="saved-title">
        <header class="panel-head">
          <div class="tile-head">
            <span class="tile"><Icon icon={KeyRound} size={17} /></span>
            <div>
              <h2 id="saved-title">Your saved token</h2>
              <p>Encrypted in your private record.</p>
            </div>
          </div>
        </header>
        <div class="panel-body">
          {#if status}
            <span class="pill" data-tone={status.is_active ? "success" : "accent"}>
              <span class="dot"></span>
              {status.is_active ? "In use by Amaterasu" : "Saved and ready"}
            </span>
            <dl class="kv">
              <dt>Updated</dt>
              <dd>{status.updated}</dd>
              <dt>File size</dt>
              <dd>{status.size}</dd>
              <dt>Scope</dt>
              <dd class="scopes">
                {#each status.scopes as scope (scope)}<code>{scope}</code>{/each}
              </dd>
              {#if !status.has_refresh_token}
                <dt>Refresh</dt>
                <dd>No refresh token</dd>
              {/if}
            </dl>

            <div class="actions">
              <a
                class="btn btn-primary"
                href="/api/token-generator/download/pickle?{auth}"
                download="token.pickle"
              >
                <Icon icon={Download} size={16} />
                <span>Download token.pickle</span>
              </a>
              {#if status.is_active}
                <button type="button" class="btn btn-secondary" disabled>
                  <Icon name="circle-check" size={16} />
                  <span>In use by Amaterasu</span>
                </button>
              {:else}
                <form method="post" action="/api/token-generator/activate?{auth}">
                  <button class="btn btn-secondary" type="submit">
                    <Icon icon={CloudCheck} size={16} />
                    <span>Use in Amaterasu</span>
                  </button>
                </form>
              {/if}
              {#if status.json_available}
                <a
                  class="btn btn-secondary"
                  href="/api/token-generator/download/json?{auth}"
                  download="token.json"
                >
                  <Icon icon={FileBraces} size={16} />
                  <span>Download token.json</span>
                </a>
              {:else}
                <button
                  type="button"
                  class="btn btn-secondary"
                  disabled
                  title="token.json is available after generating a token on this page"
                >
                  <Icon icon={FileBraces} size={16} />
                  <span>token.json unavailable</span>
                </button>
              {/if}
              <button id="replace-token" type="button" class="btn btn-danger-quiet" onclick={replaceToken}>
                <Icon icon={RefreshCw} size={16} />
                <span>Replace token</span>
              </button>
            </div>
          {:else}
            <EmptyState title="No token saved yet" icon={KeyRound}>
              Complete Google authorization and your downloads will stay available here.
            </EmptyState>
          {/if}

          <p class="aside-note">
            <Icon icon={ShieldCheck} size={16} />
            <span>
              Your token is encrypted in your private database record and can only be
              downloaded through a fresh private link from <code>/tokengen</code>.
            </span>
          </p>
        </div>
      </aside>
    </div>
  </div>
</Shell>

<style>
  .token-layout {
    grid-template-columns: minmax(0, 1fr) minmax(18rem, 24rem);
  }

  .work {
    display: grid;
    gap: var(--space-5);
    min-width: 0;
  }

  .rail {
    position: sticky;
    top: calc(var(--topbar-height) + var(--space-5));
  }

  .mono {
    font-family: var(--font-mono);
    font-size: var(--text-small);
  }

  .copy-field > :global(.btn) {
    flex-shrink: 0;
  }

  .guide-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-4);
  }

  .guide-head > div {
    display: grid;
    gap: var(--space-1);
    min-width: 0;
  }

  .guide-head h3 {
    font-size: var(--text-section);
  }

  .guide-head .btn {
    flex-shrink: 0;
  }

  /* Eight setup steps as numbered inset cards. */
  .guide {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--space-2);
    margin: 0;
    padding: 0;
    list-style: none;
    counter-reset: guide;
  }

  .guide li {
    position: relative;
    display: grid;
    align-content: start;
    gap: 2px;
    padding: var(--space-3) var(--space-3) var(--space-3) 3rem;
    counter-increment: guide;
    min-width: 0;
  }

  .guide li::before {
    content: counter(guide);
    position: absolute;
    left: var(--space-3);
    top: var(--space-3);
    display: grid;
    place-items: center;
    width: 1.5rem;
    height: 1.5rem;
    border-radius: 50%;
    border: var(--border-width) solid var(--line-strong);
    color: var(--text-secondary);
    font-size: var(--text-xs);
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }

  .guide strong {
    font-size: var(--text-small);
    font-weight: 560;
  }

  .guide span {
    font-size: var(--text-xs);
    color: var(--text-muted);
    line-height: 1.5;
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

  .method-switch {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  [role="tabpanel"] {
    display: grid;
    gap: var(--space-3);
  }

  [role="tabpanel"][hidden] {
    display: none;
  }

  .upload {
    position: relative;
  }

  /* The global field rule outranks .visually-hidden; keep the native file
     input focusable but out of layout. */
  .upload input[type="file"] {
    width: 1px;
    min-height: 0;
    height: 1px;
    padding: 0;
    border: 0;
  }

  .upload .dropzone {
    cursor: pointer;
  }

  .upload input:focus-visible + .dropzone {
    outline: var(--focus-width) solid var(--focus);
    outline-offset: var(--focus-offset);
  }

  .dropzone strong {
    color: var(--text);
    font-weight: 560;
  }

  .file-name {
    font-size: var(--text-xs);
    color: var(--text-muted);
    overflow-wrap: anywhere;
  }

  .file-name.chosen {
    color: var(--text-secondary);
    font-family: var(--font-mono);
  }

  .continue {
    width: 100%;
  }

  .scopes {
    display: grid;
    gap: var(--space-1);
  }

  .scopes code {
    font-size: var(--text-xs);
    overflow-wrap: anywhere;
  }

  .actions {
    display: grid;
    gap: var(--space-2);
  }

  .actions form,
  .actions .btn {
    width: 100%;
  }

  .actions form .btn {
    width: 100%;
  }

  @media (max-width: 64rem) {
    .token-layout {
      grid-template-columns: minmax(0, 1fr);
    }
    .rail {
      position: static;
    }
  }

  @media (max-width: 40rem) {
    .guide {
      grid-template-columns: minmax(0, 1fr);
    }
    .guide-head {
      flex-direction: column;
    }
    .guide-head .btn {
      width: 100%;
    }
    /* 16px fields stop iOS from zooming on focus. */
    input,
    textarea,
    .mono {
      font-size: 1rem;
    }
  }

  @media (max-width: 24rem) {
    .method-switch {
      grid-template-columns: minmax(0, 1fr);
    }
    .copy-field {
      flex-direction: column;
    }
  }
</style>
