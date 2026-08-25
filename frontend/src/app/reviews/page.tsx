import { HITLDrawer } from "@/components/HITLDrawer";

export default function ReviewsPage() {
  return (
    <main className="mx-auto max-w-3xl p-8 font-sans">
      <h1 className="text-2xl font-bold">Clinician review queue</h1>
      <p className="mt-2 text-sm text-neutral-500">
        Answers the post-flight guardrails held for a human. A decision here
        resumes the suspended conversation from its checkpoint. On synthetic data
        only — these are not real patients.
      </p>
      <div className="mt-6">
        <HITLDrawer />
      </div>
    </main>
  );
}
