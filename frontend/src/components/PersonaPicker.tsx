import { Check, UserRound } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { InfoTip } from "@/components/ui/InfoTip";
import type { Persona } from "@/lib/api";
import { READING_TARGET, historyLine, languageLabel, LITERACY_LABELS } from "@/lib/personas";

/**
 * "Who are you asking as?" The app has no sign-in, so the patient is an explicit
 * choice among a few synthetic demonstration patients, chosen for how much history
 * their record has. This is a demo selector, not authentication.
 */
export function PersonaPicker({
  personas,
  selectedId,
  onSelect,
  disabled,
}: {
  personas: Persona[];
  selectedId: string | undefined;
  onSelect: (patientId: string) => void;
  disabled: boolean;
}) {
  return (
    <div role="radiogroup" aria-label="Who are you asking as?" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {personas.map((persona) => {
        const selected = persona.patient_id === selectedId;
        const target = READING_TARGET[persona.literacy];
        return (
          <button
            key={persona.patient_id}
            type="button"
            role="radio"
            aria-checked={selected}
            disabled={disabled}
            onClick={() => onSelect(persona.patient_id)}
            className={`relative flex flex-col rounded-xl border p-4 text-left shadow-sm transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
              selected
                ? "border-sky-500 bg-sky-50 ring-2 ring-sky-500/40 dark:border-sky-500 dark:bg-sky-950/40"
                : "border-slate-200 bg-white hover:border-sky-400 dark:border-slate-800 dark:bg-slate-900 dark:hover:border-sky-700"
            }`}
          >
            <span className="flex items-start justify-between gap-2">
              <span className="flex items-center gap-2">
                <UserRound className="h-4 w-4 shrink-0 text-sky-600 dark:text-sky-400" aria-hidden />
                <span className="font-semibold text-slate-900 dark:text-white">{persona.name}</span>
              </span>
              {selected && (
                <span className="inline-flex items-center gap-1 rounded-full bg-sky-600 px-2 py-0.5 text-[11px] font-semibold text-white">
                  <Check className="h-3 w-3" aria-hidden /> Asking as
                </span>
              )}
            </span>
            <span className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              {persona.age !== null ? `${persona.age}, ` : ""}
              {persona.gender === "F" ? "female" : persona.gender === "M" ? "male" : persona.gender}
            </span>
            <span className="mt-2 flex flex-wrap gap-1.5">
              <Badge variant="slate">{languageLabel(persona.language)}</Badge>
              <Badge variant={persona.literacy === "basic" ? "amber" : "slate"}>
                {LITERACY_LABELS[persona.literacy] ?? persona.literacy}
                {target !== undefined && ` · grade ${target}`}
              </Badge>
            </span>
            <span className="mt-3 text-sm font-medium text-slate-800 dark:text-slate-100">{persona.headline}</span>
            <span className="mt-1 text-xs leading-relaxed text-slate-600 dark:text-slate-400">{persona.blurb}</span>
            <span className="mt-3 text-[11px] leading-relaxed text-slate-500 dark:text-slate-400">
              {historyLine(persona)}
            </span>
          </button>
        );
      })}
    </div>
  );
}

export function PersonaHelp() {
  return (
    <InfoTip text="There is no sign-in in this demo, so you pick which synthetic patient's record the assistant may read. Each is chosen for having a rich history. In a real deployment the server would learn who you are from your login, not from a choice on the page." />
  );
}

