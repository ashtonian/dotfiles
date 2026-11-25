# Request a human decision on a unit of work

Give the owner a decision they can make after reading the first paragraph. Ask to approve one outcome, select an alternative, fund a bounded investigation, split, or defer. Cite the issue, RFC/lane, affected repos, base revisions and any existing PR. State which part of a larger RFC this approval would release.

Choose the depth from the **highest** of impact, implementation complexity and uncertainty. Explain the rating with the fact that drove it. A small diff that changes tenant identity or an ambiguous contract can require a deep brief. Distinguish observations from assumptions. If you cannot define a safe implementation, propose a time-bounded investigation with a deliverable and return decision.

| Depth | When it fits | What the owner needs |
| --- | --- | --- |
| Routine | Local, reversible, understood behavior with one owner | A short paragraph covering the decision, evidence of the problem, proposed mechanism, who benefits or pays, the cost of deferring, immediate and lasting effects, and how to verify or revert. |
| Coordinated | Several components, a release dependency or meaningful operating cost | Add the change path, producer/consumer contract and release order, exclusions, realistic alternatives including deferral, test and observability evidence, rollout and recovery. Name each dependency owner. |
| Deep | High blast radius, difficult reversal, subtle concurrency, permission or data boundaries, or consequential uncertainty | Add the strongest case against the recommendation, estimates and confidence, competing stakeholder priorities, failure and mixed-version behavior, staged exposure, a measurable stop condition and the person who can recover. Identify the fact that would change the decision. |

Use these headings for a coordinated or deep approval comment. Replace each instruction with facts about this change. Keep the decision and important uncertainty above the fold.

1. **Decision and why now.** Who is affected today? Cite the observed behavior, frequency or impact. What happens if we defer one release? How will the owner recognize success?
2. **How it works.** Trace the current and proposed flow across component and trust boundaries. Name scope, exclusions, revisions, dependencies and independently approvable milestones.
3. **Options and tradeoffs.** Compare the recommendation, a credible alternative and deferral from the material perspectives. Consider user experience, maintainers, on-call, privacy or tenant isolation, downstream consumers, time and infrastructure cost. Name who pays each cost and when.
4. **Impact over time.** Separate rollout-day effects and effort from ongoing reliability, operating cost, maintenance and future constraints. Quantify where evidence supports it. State unknowns, assumptions, confidence and how to resolve them.
5. **Delivery and recovery.** List acceptance evidence, tests and representative workload, rollout order, metrics or logs, stop thresholds, rollback or roll-forward, and owners. Identify any irreversible step that needs a later decision.
6. **Owner choice.** State exactly what starts on approval, what remains pending and when the work returns to the owner. Link the evidence needed for that next decision.

At completion, the reviewer compares actual impact and remaining risk with these commitments. If scope or a material assumption changed, return the revised proposal for a new approval.
