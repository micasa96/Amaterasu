<script lang="ts">
  let {
    value,
    max = 100,
    label,
    tone,
  }: {
    value: number;
    max?: number;
    label: string;
    tone?: "success" | "danger";
  } = $props();
  const pct = $derived(max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0);
</script>

<div
  class="progress"
  data-tone={tone}
  role="progressbar"
  aria-label={label}
  aria-valuemin={0}
  aria-valuemax={max}
  aria-valuenow={value}
  style:--value="{pct}%"
>
  <span></span>
</div>
