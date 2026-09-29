# Portfolio card (draft — staged for the shared portfolio site)

This is drafted content for the per-app card described in
`PORTFOLIO_PLAN_V3.md` §14. It lives here, excluded from this repo's own
published docs site (`mkdocs.yml` `exclude_docs`), because the shared
portfolio site (`/methodology`, `/writing`, the per-app card grid) does not
exist yet in this workspace — this file exists so the content is ready to
migrate once it does.

---

**Clinical Care Navigator (A3)**

1. **Problem statement.** A patient reads a lab result they don't understand
   and asks an assistant about it — and the same interface will eventually
   receive a dosing question, a "do I have cancer" question, and a chest-pain
   emergency. This one answers the first kind, and is architecturally allowed
   to refuse the rest.
2. **Pillar badge.** Governance & Security ★ priority domain.
3. **Live demo link.** *(pending deployment — see `docs/run-it-yourself.md`
   to run it locally in the meantime)*
4. **Live ops badge.** Not yet populated — requires a deployed instance with
   real traffic (X1). Layer 1's 18-run canonical result and the red-flag
   screen recall figure are available today: see
   [Evaluation](../evidence/evaluation.md).
5. **Architecture diagram.** See [The guardrail sandwich](../how-it-works/the-guardrail-sandwich.md).
6. **The artifact — the one thing to click.** Case 4, one click, no typing: a
   benign lab-education question over a critical potassium value — watch the
   pre-flight gate allow it, then watch post-flight escalate it to clinician
   review anyway. See [Watch it work](../how-it-works/watch-it-work.md).
7. **Stack badges.** FastAPI · LangGraph · Next.js · SQLite · Qdrant ·
   pytest · mypy --strict · Playwright · MkDocs Material.
8. **Key design decisions** (linked to this repo's ADRs):
   - [D-A3-1](../architecture/decisions/D-A3-1-the-sandwich-has-two-independent-halves.md) — the guardrail is two independent checks, before and after the model, not one system prompt.
   - [D-A3-2](../architecture/decisions/D-A3-2-substring-matching-is-not-a-guardrail.md) — a metaphor defeats a keyword filter; an attributed mention must not trigger one.
   - [D-A3-6](../architecture/decisions/D-A3-6-publication-is-deterministic-and-refusals-short-circuit.md) — a refusal never reaches a patient tool, enforced by graph topology.
9. **Regulatory-basis link.** [regulatory-basis.md](../regulatory-basis.md) — leads with the FDA Clinical Decision Support device-exclusion argument.
10. **Repo link.** `github.com/zarreh/clinical_care_navigator`.
11. **CTA.** *"This pattern, applied to your domain — let's talk."*
