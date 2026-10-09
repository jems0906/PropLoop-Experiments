# Experimentation Methodology

PropLoop treats a product change as a testable bet. A hypothesis names the user, expected behavior, and measurable effect; the experiment then moves through explicit design, planning, build, measurement, and decision stages.

## Lifecycle

1. **Hypothesis:** State the problem, intended user, expected change, and primary metric.
2. **Design brief:** Generate a user story, success definition, acceptance criteria, risks, and mitigations. A human reviews and edits the draft.
3. **AI build plan:** Turn the accepted brief into a short, ordered checklist. A human approves the plan before implementation starts.
4. **Build:** Track the smallest implementation tasks. Raise blockers as soon as progress is at risk.
5. **Measure:** Record the baseline, observed value, unit, and sample size. Track guardrails alongside the target metric.
6. **Decision:** Record a rationale and choose ship, iterate, or stop. Each outcome remains in the decision history.

## Approval gates

Spec approval unlocks task-plan approval. Task-plan approval unlocks implementation tracking. A decision requires both approvals, all implementation tasks complete, and at least one recorded metric. AI output is always a draft; the human owner is accountable for approvals and release decisions.

## Learning practice

Prefer reversible changes, limited cohorts, explicit eligibility, and stable metric definitions. The controlled-test endpoint assigns opaque participant keys deterministically to 50/50 control and treatment arms; do not use names, email addresses, or other personal identifiers as assignment keys. Compare like-for-like populations and time windows. Treat a result as directional when evidence is insufficient. Investigate guardrail regressions even when the primary metric improves. Document the next question after every decision.

## Metrics

The UI supports activation, task completion, simulated CSAT, time saved, and error-rate measurements through metric records. Before/after comparisons use the entered sample size; controlled comparisons use the persisted control and treatment enrollment counts. Percentage outcomes include a two-proportion estimate that supports unequal arm sizes. It is an indicator, not a substitute for a pre-registered statistical design. Time and score metrics are shown directionally.
