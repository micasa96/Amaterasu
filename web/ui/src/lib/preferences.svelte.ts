// Browser-local appearance preference. The value is allowlisted before use
// and storage failures never block the page: changes still apply to this tab.
// The inline script in templates/base.html applies the same key before first
// paint so there is no flash of the wrong scheme.

export type Theme = "system" | "light" | "dark";

export const themes: readonly { value: Theme; label: string }[] = [
  { value: "dark", label: "Dark" },
  { value: "light", label: "Light" },
  { value: "system", label: "System preference" },
];

/** Amaterasu is dark-first: with no saved choice the page is dark. */
export const DEFAULT_THEME: Theme = "dark";

const THEME_KEY = "amaterasu.theme";

function isTheme(value: string | null): value is Theme {
  return value === "system" || value === "light" || value === "dark";
}

class Preferences {
  theme = $state<Theme>(DEFAULT_THEME);
  systemDark = $state(false);
  storageError = $state(false);

  /** Effective scheme, resolving "system" against the device setting. */
  get resolvedDark(): boolean {
    if (this.theme === "dark") return true;
    if (this.theme === "light") return false;
    return this.systemDark;
  }

  init() {
    if (typeof matchMedia === "function") {
      const mq = matchMedia("(prefers-color-scheme: dark)");
      this.systemDark = mq.matches;
      mq.addEventListener?.("change", (e) => (this.systemDark = e.matches));
    }
    try {
      const stored = localStorage.getItem(THEME_KEY);
      this.apply(isTheme(stored) ? stored : DEFAULT_THEME);
    } catch {
      this.apply(DEFAULT_THEME);
      this.storageError = true;
    }
  }

  private apply(value: Theme) {
    this.theme = value;
    document.documentElement.dataset.theme = value;
  }

  setTheme(value: string) {
    if (!isTheme(value)) return;
    const run = () => this.apply(value);
    // Theme changes cross-fade the whole screen instead of flashing.
    const doc = document as Document & {
      startViewTransition?: (cb: () => void) => { finished: Promise<void> };
    };
    if (doc.startViewTransition && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
      document.documentElement.dataset.vt = "theme";
      doc.startViewTransition(run).finished.finally(() => {
        delete document.documentElement.dataset.vt;
      });
    } else run();
    try {
      localStorage.setItem(THEME_KEY, value);
      this.storageError = false;
    } catch {
      this.storageError = true;
    }
  }

  toggleScheme() {
    this.setTheme(this.resolvedDark ? "light" : "dark");
  }
}

export const preferences = new Preferences();
