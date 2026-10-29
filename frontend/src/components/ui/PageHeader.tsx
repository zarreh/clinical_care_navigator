import { ArrowRight } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

export function PageHeader({
  icon: Icon,
  eyebrow,
  title,
  children,
  docsHref,
  docsLabel = "Learn more in the docs",
}: {
  icon: LucideIcon;
  eyebrow?: string;
  title: string;
  children?: ReactNode;
  docsHref?: string;
  docsLabel?: string;
}) {
  return (
    <header className="mb-8">
      <div className="flex items-start gap-4">
        <div className="hidden rounded-xl bg-sky-600 p-3 text-white shadow-sm sm:block">
          <Icon className="h-6 w-6" aria-hidden />
        </div>
        <div className="min-w-0">
          {eyebrow && (
            <p className="text-xs font-semibold uppercase tracking-wider text-sky-700 dark:text-sky-400">{eyebrow}</p>
          )}
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl dark:text-white">{title}</h1>
          {children && (
            <div className="mt-3 max-w-3xl space-y-2 text-[15px] leading-relaxed text-slate-600 dark:text-slate-300">
              {children}
            </div>
          )}
          {docsHref && (
            <a
              href={docsHref}
              target="_blank"
              rel="noreferrer"
              className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-sky-700 hover:text-sky-900 dark:text-sky-400 dark:hover:text-sky-300"
            >
              {docsLabel}
              <ArrowRight className="h-4 w-4" aria-hidden />
            </a>
          )}
        </div>
      </div>
    </header>
  );
}
