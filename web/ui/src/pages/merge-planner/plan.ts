// Merge plan data and the pure helpers the planner page uses.

export interface PlanItem {
  id: string;
  name?: string;
  original_index?: number;
  ready?: boolean;
  placeholder?: boolean;
}

export interface Plan {
  title?: string;
  status: string;
  mode?: string;
  profile_name?: string;
  duration_seconds?: number | null;
  subtitle_summary?: string;
  locked?: boolean;
  error?: string;
  inventory_error?: string;
  ready_count: number;
  pending_count?: number;
  enumeration_complete?: boolean;
  order_revision: number;
  revision: number;
  items: PlanItem[];
}

export const collator = new Intl.Collator("en", { numeric: true, sensitivity: "base" });

const STATUS: Record<string, string> = {
  collecting: "Collecting files",
  downloading: "Downloading",
  planning: "Planning",
  processing: "Processing",
  validating: "Validating",
  uploading: "Uploading",
  interrupted: "Interrupted",
  completed: "Completed",
  failed: "Stopped",
  cancelled: "Cancelled",
};

export function statusLabel(value: string): string {
  return STATUS[value] || value || "Preparing";
}

export function statusTone(value: string): string {
  if (value === "completed") return "success";
  if (value === "failed" || value === "cancelled" || value === "interrupted") return "danger";
  return "neutral";
}

export function detailFor(item: PlanItem): string {
  return item.placeholder ? "Resolving filename" : item.ready ? "Ready" : "Queued";
}

export function pendingLabel(plan: Plan): string {
  return plan.pending_count
    ? `${plan.pending_count} filenames resolving`
    : plan.enumeration_complete
      ? "All sources found"
      : "Preparing sources";
}

export function modeLabel(plan: Plan): string {
  return plan.mode === "encode"
    ? `Encode${plan.profile_name ? ` · ${plan.profile_name}` : ""}`
    : "Stream copy";
}

export function durationLabel(plan: Plan): string {
  if (plan.duration_seconds == null) return "Calculating";
  const seconds = Math.round(plan.duration_seconds || 0);
  return `${Math.floor(seconds / 60)} min ${seconds % 60} sec`;
}

function episodeKey(name?: string): [number, number, string] {
  const text = String(name || "").replaceAll("\\", "/");
  let match = text.match(/(?:^|\D)s(\d{1,3})[ ._-]*e(\d{1,4})(?:\D|$)/i);
  if (match) return [Number(match[1]), Number(match[2]), text];
  match = text.match(/(?:^|\D)(\d{1,3})x(\d{1,4})(?:\D|$)/i);
  if (match) return [Number(match[1]), Number(match[2]), text];
  match = text.match(/(?:episode|ep)[ ._-]*(\d{1,4})(?:\D|$)/i);
  if (match) {
    const folder = text.match(/(?:^|\/)(?:season|s)[ ._-]*(\d{1,3})\//i);
    return [folder ? Number(folder[1]) : 0, Number(match[1]), text];
  }
  return [Number.MAX_SAFE_INTEGER, Number.MAX_SAFE_INTEGER, text];
}

export function compareEpisode(a: PlanItem, b: PlanItem): number {
  const left = episodeKey(a.name);
  const right = episodeKey(b.name);
  return left[0] - right[0] || left[1] - right[1] || collator.compare(left[2], right[2]);
}
