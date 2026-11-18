/** Up to two initials for an avatar. */
export function initials(name?: string | null): string {
  if (!name) return "?";
  return (
    name
      .trim()
      .split(/\s+/)
      .filter(Boolean)
      .map((part) => part[0])
      .slice(0, 2)
      .join("")
      .toUpperCase() || "?"
  );
}

/** A stable hue per person or workspace, so identity tints never shuffle. */
export function identityHue(seed: string): number {
  let hash = 0;
  for (let i = 0; i < seed.length; i++) {
    hash = (hash * 31 + seed.charCodeAt(i)) | 0;
  }
  // Twelve steps 30° apart keep neighbouring people visibly distinct.
  return (Math.abs(hash) % 12) * 30;
}

/** "3 days ago" style relative time for recency labels. */
export function relativeTime(iso: string, now = Date.now()): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const seconds = Math.round((then - now) / 1000);
  const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  const steps: [Intl.RelativeTimeFormatUnit, number][] = [
    ["year", 31536000],
    ["month", 2592000],
    ["week", 604800],
    ["day", 86400],
    ["hour", 3600],
    ["minute", 60],
  ];
  for (const [unit, size] of steps) {
    if (Math.abs(seconds) >= size) {
      return rtf.format(Math.round(seconds / size), unit);
    }
  }
  return rtf.format(0, "minute");
}

/** Short calendar date for a YYYY-MM-DD due date, without timezone drift. */
export function formatDueDate(value: string): string {
  const [y, m, d] = value.split("-").map(Number);
  if (!y || !m || !d) return value;
  return new Date(y, m - 1, d).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

/** Whether a YYYY-MM-DD due date is before today in local time. */
export function isOverdue(value: string | null, today = new Date()): boolean {
  if (!value) return false;
  const [y, m, d] = value.split("-").map(Number);
  if (!y || !m || !d) return false;
  const due = new Date(y, m - 1, d);
  const start = new Date(
    today.getFullYear(),
    today.getMonth(),
    today.getDate(),
  );
  return due < start;
}
