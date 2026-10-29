// The MkDocs site (docs/). Overridable at build time so a fork or staging deploy
// can point at its own copy (NEXT_PUBLIC_* is inlined into the bundle).
export const DOCS_URL = (
  process.env.NEXT_PUBLIC_DOCS_URL ?? "https://zarreh.ai/clinical_care_navigator/"
).replace(/\/?$/, "/");

export const REPO_URL = "https://github.com/zarreh/clinical_care_navigator";

export const DOC_PAGES = {
  home: "",
  plainLanguage: "how-it-works/in-plain-language/",
  guardrailSandwich: "how-it-works/the-guardrail-sandwich/",
  realQuestion: "how-it-works/a-real-question/",
  autonomy: "how-it-works/autonomy/",
  whatItWontDo: "how-it-works/what-it-wont-do/",
  watchItWork: "how-it-works/watch-it-work/",
  architecture: "architecture/overview/",
  policyEngine: "architecture/policy-engine/",
  postFlight: "architecture/post-flight/",
  toolsAndScoping: "architecture/tools-and-scoping/",
  stateAndFlow: "architecture/state-and-flow/",
  evaluation: "evidence/evaluation/",
  guardrailCost: "evidence/guardrail-cost/",
  postFlightOverrides: "evidence/post-flight-overrides/",
  regulatoryBasis: "regulatory-basis/",
  runItYourself: "run-it-yourself/",
  publicationIsDeterministic:
    "architecture/decisions/D-A3-6-publication-is-deterministic-and-refusals-short-circuit/",
  citationsAreReal: "architecture/decisions/D-A3-4-citations-are-real-and-that-is-free/",
} as const;

export type DocPage = keyof typeof DOC_PAGES;

export function docsLink(page: DocPage): string {
  return `${DOCS_URL}${DOC_PAGES[page]}`;
}
