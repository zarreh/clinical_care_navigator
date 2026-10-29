import { Info } from "lucide-react";

// CSS-only (hover + keyboard focus), so it works inside server components.
export function InfoTip({ text, label = "What does this mean?" }: { text: string; label?: string }) {
  return (
    <span className="group relative inline-flex align-middle">
      <button
        type="button"
        aria-label={`${label} ${text}`}
        className="ml-1 inline-flex rounded-full text-slate-400 hover:text-sky-600 focus:text-sky-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
      >
        <Info className="h-3.5 w-3.5" aria-hidden />
      </button>
      <span
        role="tooltip"
        className="pointer-events-none invisible absolute bottom-full left-1/2 z-20 mb-2 w-64 -translate-x-1/2 rounded-lg bg-slate-900 px-3 py-2 text-left text-xs font-normal normal-case leading-relaxed tracking-normal text-slate-100 opacity-0 shadow-lg transition-opacity group-hover:visible group-hover:opacity-100 group-focus-within:visible group-focus-within:opacity-100 dark:bg-slate-700"
      >
        {text}
      </span>
    </span>
  );
}
