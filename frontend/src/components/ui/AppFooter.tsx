import { BookOpen, Code, Scale } from "lucide-react";

import { DOCS_URL, REPO_URL, docsLink } from "@/lib/docs";

export function AppFooter() {
  return (
    <footer className="mt-16 border-t border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950">
      <div className="mx-auto flex max-w-5xl flex-col gap-3 px-4 py-6 text-sm text-slate-500 sm:flex-row sm:items-center sm:justify-between sm:px-6 dark:text-slate-400">
        <p>All patients are synthetic (Synthea). Not a medical device. Does not diagnose.</p>
        <div className="flex flex-wrap gap-4">
          <a className="inline-flex items-center gap-1 hover:text-sky-700 dark:hover:text-sky-400" href={DOCS_URL} target="_blank" rel="noreferrer">
            <BookOpen className="h-4 w-4" aria-hidden /> Documentation
          </a>
          <a className="inline-flex items-center gap-1 hover:text-sky-700 dark:hover:text-sky-400" href={docsLink("regulatoryBasis")} target="_blank" rel="noreferrer">
            <Scale className="h-4 w-4" aria-hidden /> Regulatory basis
          </a>
          <a className="inline-flex items-center gap-1 hover:text-sky-700 dark:hover:text-sky-400" href={REPO_URL} target="_blank" rel="noreferrer">
            <Code className="h-4 w-4" aria-hidden /> Source code
          </a>
        </div>
      </div>
    </footer>
  );
}
