// Motion system. Principles (Apple, "Designing Fluid Interfaces"; Material
// motion): critically damped by default, never overshoot on things that
// were not thrown; exits retrace their entrance; large surfaces move longer
// than small ones; only transform and opacity animate; reduced motion
// becomes a short cross-fade.
import type { TransitionConfig } from "svelte/transition";

export function reducedMotion(): boolean {
  return (
    typeof matchMedia === "function" &&
    matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

/** A critically damped spring (damping ratio 1): fast start, no overshoot. */
export function settle(t: number): number {
  const k = 9.2; // reaches 99.9% of the distance at t = 1
  return t >= 1 ? 1 : 1 - (1 + k * t) * Math.exp(-k * t);
}

/** cubic-bezier(x1, y1, x2, y2) as an easing function. */
export function bezier(x1: number, y1: number, x2: number, y2: number) {
  const cx = 3 * x1;
  const bx = 3 * (x2 - x1) - cx;
  const ax = 1 - cx - bx;
  const cy = 3 * y1;
  const by = 3 * (y2 - y1) - cy;
  const ay = 1 - cy - by;
  const sx = (t: number) => ((ax * t + bx) * t + cx) * t;
  const sy = (t: number) => ((ay * t + by) * t + cy) * t;
  const dx = (t: number) => (3 * ax * t + 2 * bx) * t + cx;
  return (x: number) => {
    if (x <= 0) return 0;
    if (x >= 1) return 1;
    let t = x;
    for (let i = 0; i < 6; i++) {
      const d = dx(t);
      if (Math.abs(d) < 1e-6) break;
      t -= (sx(t) - x) / d;
    }
    return sy(Math.min(1, Math.max(0, t)));
  };
}

/** iOS sheet curve: the drawer arrives quickly and settles softly. */
export const sheet = bezier(0.32, 0.72, 0, 1);
/** Material "emphasized accelerate": leaving gets out of the way. */
export const exit = bezier(0.3, 0, 0.8, 0.15);
/** A gentle decelerate for small things fading in. */
export const easeOut = bezier(0.2, 0, 0, 1);

// Kept for callers that ask for the old name.
export const easeOutExpo = easeOut;

const none: TransitionConfig = { duration: 0 };

/**
 * Menus and popovers: grow from the side they are attached to. The origin
 * is set by the floating positioner, so the menu emerges from its trigger.
 */
export function pop(
  node: Element,
  { duration = 200, scale = 0.96 } = {},
): TransitionConfig {
  if (reducedMotion()) return fadeIn(node, { duration: 120 });
  return {
    duration,
    easing: settle,
    css: (t) =>
      `opacity:${Math.min(1, t * 1.4)};transform:scale(${scale + (1 - scale) * t})`,
  };
}

/** The exit of a popover: shorter, accelerating, the same path back. */
export function shrink(
  node: Element,
  { duration = 130, scale = 0.97 } = {},
): TransitionConfig {
  if (reducedMotion()) return fadeIn(node, { duration: 100 });
  return {
    duration,
    easing: exit,
    css: (t) => `opacity:${t};transform:scale(${scale + (1 - scale) * t})`,
  };
}

/** Dialogs: materialise in place, a touch larger than they leave. */
export function dialogIn(
  node: Element,
  { duration = 320 } = {},
): TransitionConfig {
  if (reducedMotion()) return fadeIn(node, { duration: 150 });
  return {
    duration,
    easing: settle,
    css: (t, u) =>
      `opacity:${Math.min(1, t * 1.6)};transform:translateY(${u * 10}px) scale(${0.965 + 0.035 * t})`,
  };
}

export function dialogOut(
  node: Element,
  { duration = 160 } = {},
): TransitionConfig {
  if (reducedMotion()) return fadeIn(node, { duration: 120 });
  return {
    duration,
    easing: exit,
    css: (t, u) =>
      `opacity:${t};transform:translateY(${u * 6}px) scale(${0.98 + 0.02 * t})`,
  };
}

/** The drawer enters from the right edge and leaves the same way. */
export function drawerIn(
  node: Element,
  { duration = 460 } = {},
): TransitionConfig {
  if (reducedMotion()) return fadeIn(node, { duration: 150 });
  return {
    duration,
    easing: sheet,
    css: (_t, u) => `transform:translateX(${u * 100}%)`,
  };
}

export function drawerOut(
  node: Element,
  { duration = 280 } = {},
): TransitionConfig {
  if (reducedMotion()) return fadeIn(node, { duration: 120 });
  return {
    duration,
    easing: exit,
    css: (_t, u) => `transform:translateX(${u * 100}%)`,
  };
}

/** Toasts rise from the bottom edge and sink back into it. */
export function toastIn(node: Element): TransitionConfig {
  if (reducedMotion()) return fadeIn(node, { duration: 150 });
  return {
    duration: 380,
    easing: settle,
    css: (t, u) =>
      `opacity:${Math.min(1, t * 1.5)};transform:translateY(${u * 16}px) scale(${0.97 + 0.03 * t})`,
  };
}

export function toastOut(node: Element): TransitionConfig {
  if (reducedMotion()) return fadeIn(node, { duration: 120 });
  return {
    duration: 200,
    easing: exit,
    css: (t, u) => `opacity:${t};transform:translateY(${u * 12}px)`,
  };
}

/** A small element appearing in place (a chip, a save bar). */
export function appear(
  node: Element,
  { duration = 220, y = 4 } = {},
): TransitionConfig {
  if (reducedMotion()) return fadeIn(node, { duration: 120 });
  return {
    duration,
    easing: settle,
    css: (t, u) => `opacity:${t};transform:translateY(${u * y}px)`,
  };
}

export function fadeIn(
  node: Element,
  { duration = 180, delay = 0 } = {},
): TransitionConfig {
  return { duration, delay, easing: easeOut, css: (t) => `opacity:${t}` };
}

/** Deprecated aliases from the first motion pass, mapped to calm motion. */
export const rise = (node: Element, opts: { duration?: number } = {}) =>
  appear(node, { duration: opts.duration ?? 220 });
export const leave = (node: Element) => dialogOut(node);
export const slide = (node: Element) => drawerIn(node);
export const spring = settle;
void none;

/**
 * Run a DOM update inside a View Transition when the browser supports it,
 * so the outgoing and incoming views cross-fade instead of swapping.
 */
export function withViewTransition(update: () => void | Promise<void>) {
  const doc = document as Document & {
    startViewTransition?: (cb: () => void | Promise<void>) => {
      finished: Promise<void>;
      ready: Promise<void>;
    };
  };
  if (!doc.startViewTransition || reducedMotion()) {
    void update();
    return;
  }
  // The page is named only while it transitions: a permanent
  // view-transition-name would make <main> a stacking context and trap
  // overlays (drawers, menus) beneath the sticky top bar.
  const root = document.documentElement;
  root.dataset.vt = "page";
  const vt = doc.startViewTransition(update);
  // A newer navigation may skip this one; the newer one simply wins.
  vt.ready.catch(() => {});
  vt.finished
    .catch(() => {})
    .finally(() => {
      if (root.dataset.vt === "page") delete root.dataset.vt;
    });
}
