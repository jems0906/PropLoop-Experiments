# Decision Framework

Every decision includes a human-written rationale and a recorded metric.

## Ship

Use when the primary metric improves enough to justify rollout, guardrails remain within acceptable bounds, acceptance criteria pass, and the implementation is supportable. State the rollout scope and monitoring owner.

## Iterate

Use when the signal is promising but inconclusive, a specific risk needs another test, or the experience needs a focused revision. Preserve the learning and form a narrower next hypothesis.

## Stop

Use when the hypothesis is not supported, guardrails regress, the change creates unacceptable risk, or the opportunity is no longer worth pursuing. Record the evidence and any reusable learning.

Only reviewers/admins can approve measurement and release decisions; their identity, cycle, and timestamp are stored. Blockers prevent advancement. Iteration archives the current evidence and resets build/measurement state for a new cycle instead of mixing old and new results.

Displayed significance uses actual participant outcomes, not enrollment counts as a substitute for completed actions. Binary outcomes use Fisher's exact test; continuous outcomes use Welch's t-test. Manual before/after values are descriptive. Statistical results never choose a release automatically. Define thresholds, cohorts, duration, and stopping rules before running an experiment, and account for multiple testing and missing observations.
