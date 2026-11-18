import { playerIcons } from "./player-icons";

// player.js (vanilla) writes <i data-lucide="name"> placeholders and then
// calls window.lucide.createIcons(). This shim swaps each placeholder for
// the matching outline icon on the shared 24px grid at the design-system
// stroke (1.75), so the controller keeps working without the Lucide CDN.
const SVG_NS = "http://www.w3.org/2000/svg";

export function createIcons(root: ParentNode = document): void {
  root.querySelectorAll<HTMLElement>("i[data-lucide]").forEach((placeholder) => {
    const name = placeholder.dataset.lucide ?? "";
    const node = playerIcons[name];
    if (!node) return;
    const svg = document.createElementNS(SVG_NS, "svg");
    const attrs: Record<string, string> = {
      xmlns: SVG_NS,
      width: "24",
      height: "24",
      viewBox: "0 0 24 24",
      fill: "none",
      stroke: "currentColor",
      "stroke-width": "1.75",
      "stroke-linecap": "round",
      "stroke-linejoin": "round",
      "aria-hidden": "true",
      focusable: "false",
      class: `lucide lucide-${name}`,
      "data-lucide": name,
    };
    for (const [key, value] of Object.entries(attrs)) svg.setAttribute(key, value);
    for (const [tag, childAttrs] of node) {
      const child = document.createElementNS(SVG_NS, tag);
      for (const [key, value] of Object.entries(childAttrs)) {
        if (key !== "key") child.setAttribute(key, String(value));
      }
      svg.appendChild(child);
    }
    placeholder.replaceWith(svg);
  });
}

export function installLucideShim(): void {
  const w = window as unknown as { lucide?: { createIcons: () => void } };
  w.lucide = { createIcons: () => createIcons() };
}
