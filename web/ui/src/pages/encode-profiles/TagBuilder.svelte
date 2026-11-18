<script lang="ts">
  import Select from "../../ui/Select.svelte";
  import Icon from "../../ui/Icon.svelte";
  import {
    DISPOSITION_OPTIONS,
    LANGUAGES,
    TAG_TRACKS,
    TAG_TYPES,
    matchesPrefix,
    type Tag,
  } from "./profile";

  // Stream-scoped metadata tags (key `s:<stream>:<track>`, value
  // `title=…`, `language=…`, `handler_name=…` or raw `KEY=VALUE`) or
  // disposition flags (key `<stream>:<track>`). Rows edit the shared list
  // in place, so the profile JSON sees every change.
  let {
    kind,
    stream,
    streamLabel,
    list,
  }: {
    kind: "meta" | "disp";
    stream: "v" | "a" | "s";
    streamLabel: string;
    list: Tag[];
  } = $props();

  const prefix = $derived(kind === "meta" ? `s:${stream}:` : `${stream}:`);
  const rows = $derived(list.filter((item) => matchesPrefix(item.key, prefix)));
  const title = $derived(kind === "meta" ? `${streamLabel} metadata tags` : `${streamLabel} disposition flags`);
  const uid = $derived(`tags-${kind}-${stream}`);

  function parse(value: string) {
    const i = value.indexOf("=");
    if (i === -1) return { type: "custom", key: value, val: "" };
    const key = value.substring(0, i);
    const val = value.substring(i + 1);
    return { type: ["title", "language", "handler_name"].includes(key) ? key : "custom", key, val };
  }

  function add() {
    list.push(kind === "meta" ? { key: `${prefix}0`, value: "title=" } : { key: `${prefix}0`, value: "" });
  }

  function remove(item: Tag) {
    const i = list.indexOf(item);
    if (i !== -1) list.splice(i, 1);
  }

  function setType(item: Tag, newType: string) {
    if (newType === "custom") return;
    const i = item.value.indexOf("=");
    const old = i !== -1 ? item.value.substring(i + 1) : "";
    item.value = `${newType}=${old}`;
  }

  function setTypedValue(item: Tag, type: string, value: string) {
    item.value = `${type}=${value}`;
  }
</script>

<div class="tag-builder">
  <div class="spread">
    <h4 id="{uid}-title" class="field-label">{title}</h4>
    <button type="button" class="btn-quiet tag-add" onclick={add}>
      <Icon name="plus" size={15} />
      {kind === "meta" ? "Add tag" : "Add flag"}
    </button>
  </div>

  {#if rows.length === 0}
    <p class="note">
      {kind === "meta" ? "No metadata tags for this stream." : "No disposition flags for this stream."}
    </p>
  {:else}
    <ul class="rows" aria-labelledby="{uid}-title">
      {#each rows as item, i (item)}
        {@const parsed = parse(item.value)}
        <li class="inset tag-row" class:disp={kind === "disp"}>
          <Select
            label="Track for {kind === 'meta' ? 'tag' : 'flag'} {i + 1}"
            value={item.key.trim().slice(prefix.length)}
            options={TAG_TRACKS}
            onchange={(v) => (item.key = `${prefix}${v}`)}
          />
          {#if kind === "meta"}
            <Select
              label="Tag type {i + 1}"
              value={parsed.type}
              options={TAG_TYPES}
              onchange={(v) => setType(item, v)}
            />
            {#if parsed.type === "language"}
              <Select
                label="Language {i + 1}"
                value={parsed.val}
                options={LANGUAGES}
                placeholder="Select language…"
                onchange={(v) => setTypedValue(item, "language", v)}
              />
            {:else if parsed.type === "custom"}
              <input
                type="text"
                aria-label="Custom tag {i + 1}"
                placeholder="e.g. BPS=120"
                value={item.value}
                oninput={(e) => (item.value = e.currentTarget.value)}
              />
            {:else}
              <input
                type="text"
                aria-label="{parsed.type === 'title' ? 'Title' : 'Handler'} {i + 1}"
                placeholder="Enter {parsed.type === 'handler_name' ? 'handler' : parsed.type}…"
                value={parsed.val}
                oninput={(e) => setTypedValue(item, parsed.type, e.currentTarget.value)}
              />
            {/if}
          {:else}
            <Select
              label="Disposition {i + 1}"
              value={item.value}
              options={DISPOSITION_OPTIONS}
              placeholder="Select disposition…"
              onchange={(v) => (item.value = v)}
            />
          {/if}
          <button
            type="button"
            class="btn-danger-quiet btn-icon"
            aria-label="Remove {kind === 'meta' ? 'tag' : 'flag'} {i + 1}"
            title="Remove"
            onclick={() => remove(item)}
          >
            <Icon name="trash" size={16} />
          </button>
        </li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  .tag-builder {
    display: grid;
    gap: var(--space-2);
    min-width: 0;
  }

  h4 {
    font-size: var(--text-small);
    font-weight: 580;
    letter-spacing: 0;
  }

  .tag-add {
    min-height: 2.25rem;
    padding: 0 var(--space-2);
    font-size: var(--text-small);
  }

  .tag-row {
    display: grid;
    grid-template-columns: minmax(6.5rem, 0.8fr) minmax(7rem, 0.9fr) minmax(0, 1.6fr) auto;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2);
  }

  .tag-row.disp {
    grid-template-columns: minmax(6.5rem, 0.8fr) minmax(0, 2fr) auto;
  }

  /* Narrow: track and type share a line with remove; the value gets its own. */
  @container (max-width: 34rem) {
    .tag-row:not(.disp) {
      grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto;
    }
    .tag-row:not(.disp) > :global(:nth-child(3)) {
      grid-column: 1 / 3;
      grid-row: 2;
    }
    .tag-row.disp {
      grid-template-columns: minmax(5.5rem, 0.7fr) minmax(0, 1.3fr) auto;
    }
  }
</style>
