# Decision Framework

Every decision includes a human-written rationale and a recorded metric.

## Ship

Use when the primary metric improves enough to justify rollout, guardrails remain within acceptable bounds, acceptance criteria pass, and the implementation is supportable. State the rollout scope and monitoring owner.

## Iterate

Use when the signal is promising but inconclusive, a specific risk needs another test, or the experience needs a focused revision. Preserve the learning and form a narrower next hypothesis.

## Stop

Use when the hypothesis is not supported, guardrails regress, the change creates unacceptable risk, or the opportunity is no longer worth pursuing. Record the evidence and any reusable learning.

A displayed confidence estimate is approximate and depends on the sample-size inputs. It does not control the decision automatically. Teams should define thresholds, cohorts, duration, and stopping rules before running a production experiment.
