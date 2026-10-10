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

Each cycle has six named reviewer/admin approvals: hypothesis, design, plan, build, measurement, and decision. Members can draft and record work but cannot approve gates. Completing tasks does not automatically advance the build. An unresolved blocker prevents approval. Repeated or out-of-order approvals are rejected without replacing tasks. AI output is always a draft; design fields lock after design approval, while checklist and effort remain editable until plan approval.

Iteration archives the reviewed cycle's spec, tasks, metrics, assignments, observations, and audit entries, then starts a new hypothesis cycle. Prior decisions and approval identities remain available. Shipped and stopped experiments cannot resume implementation or measurement.

## Learning practice

Prefer reversible changes, limited cohorts, explicit eligibility, and stable metric definitions. The controlled-test endpoint assigns opaque participant keys deterministically to 50/50 control and treatment arms; do not use names, email addresses, or other personal identifiers as assignment keys. Compare like-for-like populations and time windows. Treat a result as directional when evidence is insufficient. Investigate guardrail regressions even when the primary metric improves. Document the next question after every decision.

## Metrics

Record exposure and outcomes against enrolled opaque participant keys. Activation is exposed / enrolled. Completion and error rates use exposed participants only. CSAT averages submitted 1-5 ratings; duration averages submitted minute values. Missing ratings and durations are excluded, not zero-filled. Time saved is control duration minus treatment duration. The dashboard shows actual denominators separately for each metric.

Binary outcomes use a two-sided Fisher exact test. Ratings and durations use a two-sided Welch t-test with a 95% interval for the treatment-minus-control difference; fewer than two observations per arm or zero total variance make continuous inference unavailable. A p-value is not the probability that a hypothesis is true. Tests are exploratory, unadjusted for multiple comparisons, and cannot remove selection bias, missing-data bias, or repeated-peeking effects. Choose a primary metric, guardrails, cohorts, duration, and stopping rules in advance. Enrollment without a recorded exposure counts as not activated; close the exposure-recording window before interpreting activation.

Manually entered before/after results remain descriptive; they do not claim randomized-test significance. Historic manually entered controlled metrics are also legacy descriptive evidence, not validated participant outcomes.
