import type { Persona } from "./api";

// Mirrors READING_LEVEL_TARGET in navigator.graph.nodes.draft_answer: the grade an
// answer is written at for each literacy band.
export const READING_TARGET: Record<string, number> = { basic: 6, intermediate: 8, proficient: 10 };

export const LANGUAGE_LABELS: Record<string, string> = { en: "English", es: "Spanish" };
export const LITERACY_LABELS: Record<string, string> = {
  basic: "Basic literacy",
  intermediate: "Intermediate literacy",
  proficient: "Proficient literacy",
};

const NUMBER = new Intl.NumberFormat("en-US");

export function languageLabel(code: string): string {
  return LANGUAGE_LABELS[code] ?? code;
}

/** "Name, 82, English, reading target grade 8" — what the run was asked as. */
export function personaSummary(p: Persona): string {
  const target = READING_TARGET[p.literacy];
  return [
    p.name,
    p.age !== null ? String(p.age) : null,
    languageLabel(p.language),
    target !== undefined ? `reading target grade ${target}` : null,
  ]
    .filter(Boolean)
    .join(", ");
}

/** The size of the record, in plain words. */
export function historyLine(p: Persona): string {
  const h = p.history;
  return [
    `${NUMBER.format(h.labs)} lab results across ${NUMBER.format(h.analytes)} tests`,
    `${NUMBER.format(h.medications)} medications`,
    `${NUMBER.format(h.conditions)} conditions`,
    `${NUMBER.format(h.encounters)} visits`,
  ].join(" · ");
}

export function findPersona(personas: Persona[], patientId: string | null | undefined): Persona | undefined {
  return patientId ? personas.find((p) => p.patient_id === patientId) : undefined;
}
