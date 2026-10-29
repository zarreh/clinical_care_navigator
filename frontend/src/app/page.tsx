import { ArrowRight, BookOpen, ClipboardCheck, FileCheck2, Search, ShieldCheck } from "lucide-react";
import { Suspense } from "react";

import { AskPanel } from "@/components/AskPanel";
import { Callout } from "@/components/ui/Callout";
import { InfoTip } from "@/components/ui/InfoTip";
import { docsLink } from "@/lib/docs";
import { GLOSSARY } from "@/lib/glossary";

const STEPS = [
  {
    icon: ShieldCheck,
    title: "Pre-flight screen",
    owner: "Rules + AI classifier",
    text: "Before the AI reads anything, fixed safety rules and a classifier sort your question. Emergencies and decisions only a clinician can make stop here.",
    tip: GLOSSARY.preFlight,
  },
  {
    icon: Search,
    title: "Read your record",
    owner: "AI, with scoped tools",
    text: "The AI looks up labs, medications and notes with read-only tools that can only ever see your own record.",
    tip: GLOSSARY.scopedTools,
  },
  {
    icon: FileCheck2,
    title: "Post-flight check",
    owner: "Code + AI judge",
    text: "The draft is split into claims. Each clinical claim must rest on something actually retrieved. Critical lab values override the draft.",
    tip: GLOSSARY.postFlight,
  },
  {
    icon: ClipboardCheck,
    title: "Publish, hold or replace",
    owner: "Code decides, a clinician reviews",
    text: "Code, not the AI, publishes the answer, holds it for a clinician, or swaps it for a safe pre-written reply.",
    tip: GLOSSARY.clinicianReview,
  },
];

export default function Home() {
  return (
    <div className="space-y-12">
      <section className="rounded-2xl border border-slate-200 bg-gradient-to-br from-white to-sky-50 p-6 shadow-sm sm:p-10 dark:border-slate-800 dark:from-slate-900 dark:to-sky-950/40">
        <p className="text-xs font-semibold uppercase tracking-wider text-sky-700 dark:text-sky-400">
          A patient-facing AI assistant that is allowed to refuse
        </p>
        <h1 className="mt-2 max-w-3xl text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl dark:text-white">
          Ask about your own health record, and watch every answer get checked before you see it.
        </h1>
        <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-slate-600 dark:text-slate-300">
          An AI drafts answers from your record, but it never gets the last word. Safety rules run
          before it, and evidence checks run after it. Anything risky goes to a human clinician or
          is replaced with a safe, pre-written reply. Each run streams step by step so you can see
          who decided what.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <a
            href="#try"
            className="inline-flex items-center gap-1.5 rounded-lg bg-sky-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-sky-700"
          >
            Try a question <ArrowRight className="h-4 w-4" aria-hidden />
          </a>
          <a
            href={docsLink("plainLanguage")}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:border-sky-500 hover:text-sky-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
          >
            <BookOpen className="h-4 w-4" aria-hidden /> How it works, in plain language
          </a>
        </div>
      </section>

      <section aria-labelledby="how-heading">
        <h2 id="how-heading" className="text-lg font-semibold text-slate-900 dark:text-white">
          How it works: the guardrail sandwich
        </h2>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
          The AI is the filling. Deterministic checks are the bread on both sides.
        </p>
        <ol className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((step, i) => (
            <li
              key={step.title}
              className="relative rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900"
            >
              <div className="flex items-center gap-3">
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-sky-600 text-sm font-bold text-white">
                  {i + 1}
                </span>
                <step.icon className="h-5 w-5 text-sky-600 dark:text-sky-400" aria-hidden />
              </div>
              <h3 className="mt-3 font-semibold text-slate-900 dark:text-white">
                {step.title}
                <InfoTip text={step.tip} />
              </h3>
              <p className="mt-0.5 text-xs font-medium uppercase tracking-wide text-indigo-600 dark:text-indigo-400">
                {step.owner}
              </p>
              <p className="mt-2 text-sm leading-relaxed text-slate-600 dark:text-slate-400">{step.text}</p>
            </li>
          ))}
        </ol>
        <a
          href={docsLink("guardrailSandwich")}
          target="_blank"
          rel="noreferrer"
          className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-sky-700 hover:text-sky-900 dark:text-sky-400"
        >
          Read about the guardrail sandwich <ArrowRight className="h-4 w-4" aria-hidden />
        </a>
      </section>

      <section id="try" aria-labelledby="try-heading" className="scroll-mt-20 space-y-4">
        <div>
          <h2 id="try-heading" className="text-lg font-semibold text-slate-900 dark:text-white">
            Try it
          </h2>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
            Pick one of four questions, each ending a different way, or write your own.
          </p>
        </div>
        <Callout title="Whose record is this?">
          There is no sign-in in this demo, so you choose which <strong>synthetic patient</strong>{" "}
          to ask as. All of them are generated by Synthea: fake but realistic, picked for their rich
          histories. One record includes a deliberately planted critical potassium value so you can
          watch the safety override fire.
        </Callout>
        <Suspense fallback={null}>
          <AskPanel />
        </Suspense>
      </section>
    </div>
  );
}
