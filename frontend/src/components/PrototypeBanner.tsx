const REGULATORY_BASIS_URL =
  "https://github.com/zarreh/clinical_care_navigator/blob/main/docs/regulatory-basis.md";

// The synthetic-data banner is on every page (docs/PLAN.md §7): it renders in
// the root layout above all routes.
export function PrototypeBanner() {
  return (
    <div className="border-b border-amber-300 bg-amber-50 px-4 py-2 text-center text-xs text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
      Research prototype, fully synthetic data only — not a medical device, does
      not diagnose, and not a substitute for care. See{" "}
      <a className="underline" href={REGULATORY_BASIS_URL}>
        regulatory basis
      </a>
      .
    </div>
  );
}
