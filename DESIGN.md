# Design

Visual direction for every Amaterasu web page. Implementation, tokens and
the page contract live in [web/ui/README.md](web/ui/README.md).

## World

Amaterasu's web pages use Trestle's design system: the same tokens,
material, components and shell. Amaterasu runs it in **pure black and
white**. The palette knobs hold zero chroma and zero tint. The accent family
is ink on paper in light theme and paper on ink in dark theme.

- **Dark is the default.** The grounds are near-black, stacked in four tone
  steps: ground, nav, panel, floating. One soft ambient light falls over the
  top of the work area, crossed by a diagonal beam. Resting panels carry a
  one-pixel edge light instead of a drop shadow.
- **Light is a counterpart, not an afterthought.** It is a grey paper ground
  with white cards that sit on soft offset shadows, and a white beam across
  the canvas. The sidebar stays inked: a black rail beside the paper. Icon
  tiles are black squircles with white glyphs.
- **Signature: the Blackflare flame.** It is drawn in the primary ink on a
  lit tile: a black flame on a white tile in dark theme, and a white flame
  on a black tile in light theme. It appears in the sidebar, the top bar on
  phones, and the sign-in page.

## Material

These come from Trestle:

- Panels use a gradient fill inside a luminous 1px edge.
- Rows are inset cards inside panels.
- Icons sit in lit squircle tiles.
- The primary button is lit, with a soft glow.
- The sidebar holds a glowing "Jump anywhere" card that opens the command
  palette.
- Headings are set light (480–540) and large.
- Desktop pointers get 38px controls on dense work screens. Touch keeps 44px.

## Type

Mona Sans variable, self-hosted and bundled. Weights run 420–600. Headings
are 480–540. Figures are tabular. Monospace is only for code, tokens and
identifiers that people copy.

## Colour rules

- Only black, white and greys carry the brand.
- Hue is reserved for state: success, warning, danger and info. State always
  comes with words.
- No raw colours in pages. Use only the semantic tokens.
- An inverted region uses `data-scheme="dark"` or `data-scheme="light"`.
  Never hand-pick colours for it.

## Shell

Every page renders inside one frame:

- A sidebar with grouped navigation, usually the sections of the current
  page. Pages are reached through signed per-user links, so the sidebar does
  not link between tools.
- A sticky top bar with breadcrumbs, search and a theme toggle.
- The command palette, opened with Ctrl/⌘ K or `/`. It lists the page's
  sections and the theme commands.

Below 60rem the sidebar becomes a horizontally scrolling nav band. Below
40rem dialogs become bottom sheets.
