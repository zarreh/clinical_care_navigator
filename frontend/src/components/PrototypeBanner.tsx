import { docsLink } from "@/lib/docs";

// The synthetic-data banner is on every page (docs/PLAN.md §7): it renders in
// the root layout above all routes.
export function PrototypeBanner() {
  return (
    <div className="border-b border-amber-300 bg-amber-50 px-4 py-2 text-center text-xs text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
      <span>
        Research prototype, fully synthetic data only. Not a medical device, does not diagnose,
        and not a substitute for care. See the{" "}
        <a className="underline" href={docsLink("regulatoryBasis")} target="_blank" rel="noreferrer">
          regulatory basis
        </a>
        .
      </span>
    </div>
  );
}
