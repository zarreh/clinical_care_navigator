const TONES = {
  sky: "bg-sky-500",
  green: "bg-emerald-500",
  amber: "bg-amber-500",
  red: "bg-red-500",
} as const;

/** A labelled value with a bar, exposed to assistive tech as a meter. */
export function Meter({
  value,
  max,
  label,
  display,
  tone = "sky",
}: {
  value: number;
  max: number;
  label: string;
  display: string;
  tone?: keyof typeof TONES;
}) {
  const pct = max > 0 ? Math.max(0, Math.min(1, value / max)) * 100 : 0;
  return (
    <div className="flex items-center gap-3">
      <span className="w-14 shrink-0 text-sm font-semibold tabular-nums text-slate-900 dark:text-white">
        {display}
      </span>
      <div
        className="h-2 flex-1 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700"
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuenow={Number(value.toFixed(2))}
      >
        <div className={`h-full rounded-full ${TONES[tone]}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
