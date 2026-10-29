"use client";

import { BookOpen, HeartPulse } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { DOCS_URL } from "@/lib/docs";

const NAV = [
  { href: "/", label: "Ask a question" },
  { href: "/reviews", label: "Clinician review queue" },
];

function isActive(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

export function AppHeader() {
  const pathname = usePathname();
  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/90 backdrop-blur dark:border-slate-800 dark:bg-slate-950/90">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3 sm:px-6">
        <Link href="/" className="flex items-center gap-2 font-semibold text-slate-900 dark:text-white">
          <span className="rounded-lg bg-sky-600 p-1.5 text-white">
            <HeartPulse className="h-4 w-4" aria-hidden />
          </span>
          Clinical Care Navigator
        </Link>
        <nav aria-label="Main" className="order-3 flex w-full gap-1 overflow-x-auto sm:order-none sm:w-auto">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              aria-current={isActive(pathname, item.href) ? "page" : undefined}
              className={`whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                isActive(pathname, item.href)
                  ? "bg-sky-50 text-sky-800 dark:bg-sky-950 dark:text-sky-200"
                  : "text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-white"
              }`}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <a
          href={DOCS_URL}
          target="_blank"
          rel="noreferrer"
          className="ml-auto inline-flex items-center gap-1.5 rounded-lg border border-sky-600 px-3 py-1.5 text-sm font-medium text-sky-700 hover:bg-sky-600 hover:text-white dark:border-sky-500 dark:text-sky-300 dark:hover:bg-sky-600 dark:hover:text-white"
        >
          <BookOpen className="h-4 w-4" aria-hidden />
          Docs
        </a>
      </div>
    </header>
  );
}
