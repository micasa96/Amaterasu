<script lang="ts">
  import { untrack } from "svelte";
  import Lock from "@lucide/svelte/icons/lock";
  import Shell, { type NavGroup } from "../../ui/Shell.svelte";
  import LogViewer from "../../ui/LogViewer.svelte";
  import EmptyState from "../../ui/EmptyState.svelte";
  import Icon from "../../ui/Icon.svelte";

  // Live logs for owner and sudo users. Access is checked on the server: a
  // signed link from /log or /status in Telegram, or the LOGIN_PASS session.
  let { data }: { data: { authorized?: boolean; login_enabled?: boolean } } = $props();

  const authorized = untrack(() => !!data.authorized);
  const loginEnabled = untrack(() => !!data.login_enabled);

  // Keep the signed-link query (user_id, token) for the stream and download.
  const auth = (() => {
    const params = new URLSearchParams(location.search);
    const user = params.get("user_id");
    const token = params.get("token");
    return user && token ? new URLSearchParams({ user_id: user, token }).toString() : "";
  })();

  const nav: NavGroup[] = [
    {
      label: "Instance",
      items: [
        { label: "Overview", href: "/", icon: "home" },
        { label: "Live logs", href: "#logs", icon: "list", current: true },
      ],
    },
  ];
</script>

<Shell
  place="Live logs"
  crumbs={["Instance"]}
  {nav}
  note="Logs are redacted on the server. Links from Telegram expire after one hour."
  dense
>
  <div class="page">
    <header class="page-head">
      <div>
        <h1 id="logs" tabindex="-1">Live logs</h1>
        <p>
          The bot's log as it is written. Pause to read, select or copy lines, filter by text or
          level, and download the full file.
        </p>
      </div>
    </header>

    {#if authorized}
      <LogViewer {auth} />
    {:else}
      <EmptyState title="Live logs are private" icon={Lock}>
        {#snippet children()}
          Only the owner and sudo users can read logs. Send <code>/log</code> or
          <code>/status</code> to the bot and press <strong>Live logs</strong>: a private link
          arrives in your chat and works for one hour.
        {/snippet}
        {#snippet actions()}
          {#if loginEnabled}
            <a class="btn btn-primary" href="/login?next=/app/logs">
              <Icon name="log-in" size={16} /> Sign in
            </a>
          {/if}
          <a class="btn" href="/">Back to overview</a>
        {/snippet}
      </EmptyState>
    {/if}
  </div>
</Shell>
