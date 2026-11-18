// Single entry for every Amaterasu page.
//
// FastAPI renders a Jinja template that extends base.html, which outputs
//   <div id="app" data-page="encode-profiles"></div>
//   <script type="application/json" id="page-data">{...}</script>
// This entry loads the shared design system once, then lazily imports
// ./pages/<name>/Page.svelte and mounts it with the server data as `data`.
// Each page lives in its own folder; shared pieces live in ui/ and lib/.
import "@fontsource-variable/mona-sans";
import "./styles/tokens.css";
import "./styles/app.css";
import "./styles/components.css";

import { mount, type Component } from "svelte";
import { preferences } from "./lib/preferences.svelte";
import { readPageData } from "./lib/page";

type PageModule = { default: Component<{ data: Record<string, unknown> }> };

const pages = import.meta.glob<PageModule>("./pages/*/Page.svelte");

async function start() {
  preferences.init();
  const target = document.getElementById("app");
  if (!target) return;
  const name = target.dataset.page ?? "";
  const load = pages[`./pages/${name}/Page.svelte`];
  if (!load) {
    target.textContent = `Unknown page “${name}”.`;
    return;
  }
  const { default: Page } = await load();
  target.replaceChildren();
  mount(Page, { target, props: { data: readPageData() } });
}

void start();
