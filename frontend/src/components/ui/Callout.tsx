import { CircleAlert, CircleCheck, Info, TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";

const STYLES = {
  info: {
    box: "border-sky-200 bg-sky-50 text-sky-900 dark:border-sky-900 dark:bg-sky-950/60 dark:text-sky-100",
    icon: Info,
  },
  success: {
    box: "border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/60 dark:text-emerald-100",
    icon: CircleCheck,
  },
  warning: {
    box: "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900 dark:bg-amber-950/60 dark:text-amber-100",
    icon: TriangleAlert,
  },
  error: {
    box: "border-red-200 bg-red-50 text-red-900 dark:border-red-900 dark:bg-red-950/60 dark:text-red-100",
    icon: CircleAlert,
  },
} as const;

export function Callout({
  variant = "info",
  title,
  children,
  className = "",
  role,
}: {
  variant?: keyof typeof STYLES;
  title?: string;
  children: ReactNode;
  className?: string;
  role?: "alert" | "status";
}) {
  const { box, icon: Icon } = STYLES[variant];
  return (
    <div role={role} className={`flex gap-3 rounded-xl border p-4 text-sm ${box} ${className}`}>
      <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <div className="min-w-0 space-y-1">
        {title && <p className="font-semibold">{title}</p>}
        <div className="leading-relaxed">{children}</div>
      </div>
    </div>
  );
}
