# Property Management Experiment Templates

Templates are starting points, not approved specifications. Teams should validate local policy, resident expectations, data quality, and operational ownership before testing.

| Experiment | Primary metric | Important guardrails |
| --- | --- | --- |
| Tenant maintenance triage assistant | Median time to first assignment | Misroute rate, missed urgent safety requests |
| Rent delinquency reminder flow | On-time recovery rate | Incorrect balance rate, opt-outs, support escalations |
| Lease renewal outreach optimizer | Lease renewal conversion rate | Fair housing review, offer parity, resident complaints |
| Owner report summarizer | Report preparation time | Source traceability, material variance omissions |
| Support ticket auto-categorizer | Correct first-route rate | Human escalation rate, time to resolution |

## Domain safeguards

- Keep a human in the loop for safety concerns, financial actions, lease terms, and externally shared owner communications.
- Do not use protected attributes to personalize lease offers or prioritize service.
- Verify resident/account/property identity and source data before sending generated content.
- Provide a clear route to a person and preserve an audit trail of corrections.
- Start with a limited cohort and a rollback path.
