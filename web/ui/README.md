# Amaterasu web UI

Every Amaterasu web page is a Svelte 5 page. All pages share **one** design
system, so a change here updates every page. The visual direction is in
[../../DESIGN.md](../../DESIGN.md).

## How a page is served

1. FastAPI keeps routing, auth, signed links and server data. Nothing about
   the backend changes when you change the UI.
2. The route renders a Jinja template that extends `web/templates/base.html`
   and fills two blocks:

   ```jinja
   {% extends "base.html" %}
   {% block page %}encode-profiles{% endblock %}
   {% block page_data %}{{ {"user_id": user_id}|tojson }}{% endblock %}
   ```

3. `base.html` links the built bundle. `web/wserver.py` reads the hashed
   file names from the Vite manifest and serves that build at `/static/dist`.
4. `src/main.ts` loads the shared CSS and lazily imports
   `src/pages/<name>/Page.svelte`. It mounts the page with the JSON as
   `data`.

## Layout

| Path | What lives there |
| --- | --- |
| `src/styles/tokens.css` | **The palette and scale.** Theme knobs, semantic colour roles, material (card, inset, tile, primary fill, sheen), type, space, radii, motion. Dark is the default. `[data-scheme]` re-resolves the palette for a subtree. |
| `src/styles/app.css` | Global element styles and core classes: buttons (`btn-primary`, `btn-quiet`, `btn-danger`, `btn-icon`, `btn-link`), fields, `.panel`/`.card`, `.inset`, `.tile`, `.pill`, `.feedback`, `.empty`, dialogs, `.segmented`, skip link, view transitions |
| `src/styles/components.css` | Shared page classes: `.page`, `.page-head`, `.split`, `.tabs`, `.stats`/`.stat`, `.rows`/`.row`, `.kv`, `.table`, `.progress`, `.code`, `.copy-field`, `.check`, `input.switch`, `.steps`, `.dropzone`, `details.disclosure`, `.skeleton`, `.spinner` |
| `src/ui/` | Shared components: `Shell` (sidebar, top bar, palette, toast), `BrandMark`, `Icon`, `Button`, `InputField`, `Select`, `Modal`, `Feedback`, `Toast`, `CommandPalette`, `CopyButton`, `Progress`, `EmptyState`, `Avatar` |
| `src/lib/` | `preferences` (theme), `toast` (success confirmations), `api` (JSON fetch with server error text), `page` (page data, query params), `format` (bytes, durations, copy), `motion`, `floating` |
| `src/pages/<name>/` | One folder per page, holding `Page.svelte` and any page-only parts |

## Rules

- Pages compose the shared classes and components. A page `<style>` only
  holds layout unique to that page, and only with tokens. Never use raw
  colours.
- When a second page needs a part, promote it from `pages/<name>/` into
  `ui/` and use it from both.
- Use icons via `<Icon name="…">` (the hand-tuned set) or
  `<Icon icon={Glyph}>` with a deep import:
  `import Glyph from "@lucide/svelte/icons/hard-drive"`.
- Toasts are only for success. Errors stay inline (`Feedback tone="danger"`)
  until they are resolved.
- Use the primary button only for the main action of a view.
- Never use eyebrow labels, gradient text or emoji icons, and never show
  invented numbers.

## Commands

```sh
npm ci            # once
npm run dev       # rebuild to ../static/dist on change (refresh the page)
npm run build     # production build (Docker runs this in the web-ui stage)
npm run check     # svelte-check
```

The Docker image builds this folder in a Node stage and copies the built
assets to `/opt/amaterasu-ui`, outside the Compose checkout mount. Local
builds use `web/static/dist`. That directory and `node_modules` are git-ignored.
