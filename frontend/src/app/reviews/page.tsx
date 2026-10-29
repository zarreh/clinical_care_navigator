import { ClipboardCheck } from "lucide-react";

import { HITLDrawer } from "@/components/HITLDrawer";
import { Callout } from "@/components/ui/Callout";
import { PageHeader } from "@/components/ui/PageHeader";
import { docsLink } from "@/lib/docs";

export default function ReviewsPage() {
  return (
    <div>
      <PageHeader
        icon={ClipboardCheck}
        eyebrow="Human in the loop"
        title="Clinician review queue"
        docsHref={docsLink("postFlight")}
        docsLabel="How post-flight decides what to hold"
      >
        <p>
          These are answers the AI drafted but the <strong>post-flight checks would not publish on
          their own</strong>: a clinical claim with no evidence behind it, or a draft the scope
          check flags for telling the patient what to do about their care or for contradicting
          their record. The patient sees each one labelled “pending”, never as answered.
        </p>
        <p>
          <strong>You decide, as the clinician.</strong> Your decision resumes the exact paused run
          from its saved checkpoint. No new AI answer is generated.
        </p>
      </PageHeader>
      <Callout variant="warning" title="Demo only: this page has no login" className="mb-6">
        Anyone who can open this page can approve, edit or decline a held answer. A real
        deployment would put clinician sign-in in front of it. All patients here are synthetic.
      </Callout>
      <HITLDrawer />
    </div>
  );
}
