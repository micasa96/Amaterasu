// Floating panels (menus, pickers): rendered at the end of <body> so no
// scroll container, mask or stacking context can clip them, positioned
// against their trigger, and flipped above it when there is no room below.
import type { Action } from "svelte/action";

export interface FloatingOptions {
  anchor: HTMLElement | null;
  align?: "start" | "end";
  /** Match the trigger's width (field menus) instead of sizing to content. */
  matchWidth?: boolean;
  gap?: number;
  onclose?: () => void;
}

export const floating: Action<HTMLElement, FloatingOptions> = (
  node,
  initial,
) => {
  let opts = initial;
  document.body.appendChild(node);
  node.style.position = "fixed";
  node.style.top = "0px";
  node.style.left = "0px";

  function place() {
    const anchor = opts.anchor;
    if (!anchor || !anchor.isConnected) return;
    const a = anchor.getBoundingClientRect();
    const gap = opts.gap ?? 6;
    const margin = 8;
    const vw = window.innerWidth;
    const vh = window.innerHeight;

    if (opts.matchWidth) node.style.minWidth = `${a.width}px`;
    node.style.maxWidth = `${vw - margin * 2}px`;
    const w = node.offsetWidth;
    const h = node.offsetHeight;

    let left = opts.align === "end" ? a.right - w : a.left;
    left = Math.max(margin, Math.min(left, vw - w - margin));

    const below = vh - a.bottom - gap - margin;
    const above = a.top - gap - margin;
    const flip = h > below && above > below;
    const top = flip ? a.top - gap - Math.min(h, above) : a.bottom + gap;
    node.style.maxHeight = `${Math.max(160, flip ? above : below)}px`;
    const originX = Math.max(0, Math.min(w, a.left + a.width / 2 - left));
    node.style.transformOrigin = `${Math.round(originX)}px ${flip ? "100%" : "0"}`;
    node.style.left = `${Math.round(left)}px`;
    node.style.top = `${Math.round(top)}px`;
  }

  function onPointerDown(e: PointerEvent) {
    const t = e.target as Node;
    if (node.contains(t) || opts.anchor?.contains(t)) return;
    opts.onclose?.();
  }

  place();
  const raf = requestAnimationFrame(place);
  window.addEventListener("resize", place);
  window.addEventListener("scroll", place, true);
  document.addEventListener("pointerdown", onPointerDown, true);

  return {
    update(next) {
      opts = next;
      place();
    },
    destroy() {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
      document.removeEventListener("pointerdown", onPointerDown, true);
      node.remove();
    },
  };
};

let counter = 0;
export const uid = (prefix: string) => `${prefix}-${++counter}`;
