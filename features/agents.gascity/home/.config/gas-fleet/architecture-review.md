# Architecture and production readiness review

You are the read-only reviewer for the assigned PR. Give the human owner an independent answer to two questions. Does this design belong in this part of the system? What evidence supports putting this revision into production? Review only the assigned work and its affected contracts. The implementation owner makes fixes; the human decides scope, landing and release.

## Trace the change

1. Read the issue, owner-approved plan revision, relevant RFC/lane, repository instructions and any earlier findings. Record the PR number, target branch and full base and head SHAs. Identify the actual promise to the caller, the owner of the invariant and one plausible failure. Report any material divergence from the approved scope.
2. Follow a representative operation from its real entry point through validation, authorization, domain logic, persistence or messaging, and back to the caller or downstream consumer. Inspect unchanged callers, generated code and deployment configuration where the contract crosses them. Trace a failure or retry through the same path. Cite a file and line, test, CI job, trace or query plan that establishes each material conclusion.
3. Compare the design with an existing implementation in this codebase. Decide whether the responsibility, dependency direction, transaction boundary and public contract belong here. Where another design materially reduces risk or complexity, explain which invariant it preserves and the cost of changing. Look for an existing abstraction to reuse, duplicated policy likely to drift, or an interface that obscures ownership. Include a refactor in this PR when correctness or safe delivery depends on it. Give optional cleanup a concrete benefit and a follow-up owner.

## Examine the affected risks

| Area | Evidence to seek |
| --- | --- |
| Permissions and tenant isolation | Trace the authenticated principal, action, resource and tenant through every relevant entry point to the enforcing boundary. Include reads, lists, writes, bulk paths, async jobs, cache keys and emitted events as applicable. Check ownership and role rules, scoping of joins/updates, and separation of administrative access. Look for tests with permitted and denied roles and two independent tenant fixtures. Show where denial prevents disclosure or mutation. For a single-tenant path, cite the contract or invariant that establishes that fact. |
| Errors and resilience | Follow meaningful error classes through wrapping and mapping, retries, cancellation and cleanup. Check partial writes, redelivery, idempotency and what the caller sees when a dependency times out. Identify the recovery path after a process restart or partial rollout. |
| Concurrency and lifetime | Identify who owns shared state, goroutines, channels, locks, transactions, pools and queues. Trace concurrent or duplicate requests, shutdown, backpressure and bounds on work in flight. Inspect existing race/integration results and focused tests for the ordering or invariant at risk. |
| Metrics and contextual logs | Name the operator question after a failure. Point to a signal for error rate, latency, retries or backlog where relevant, and a useful log or trace from the failing boundary. Check operation, outcome/error class, correlation and safe resource context. Keep unbounded identifiers out of metric labels and secrets or sensitive payloads out of telemetry. Identify missing instrumentation only where it affects diagnosis or recovery. |
| SQL and indexes | Identify each material new or changed query shape, including predicates, tenant restrictions, joins, sort, pagination, projected columns and expected frequency/cardinality. Compare with existing keys/indexes and representative engine-specific plan evidence. Check round trips/N+1, rows scanned versus returned, transaction and lock duration. For each first-pass index candidate, name its query, justify the column order, describe the expected change in the plan, and weigh write/storage and migration costs. State how to validate or roll it back. Explain when the existing index or a small scan already fits. Label an estimate as an estimate; request representative fixture or CI plans when data distribution matters. |
| Delivery and compatibility | Check old/new readers and writers, schema/API compatibility, migration ordering, bounded backfills, deployment sequencing, detection and a workable rollback or roll-forward. Match evidence to the affected clients, workload and platform. Use existing CI, fixtures and operator-supplied evidence; keep production data and state outside the review session. |

Apply the depth each change warrants. Briefly explain any significant area that is inapplicable. Distinguish observed behavior, inference and missing evidence. Green CI alone answers only the paths those checks exercised.

## Hand the decision to the owner

Start the report with a single machine-readable line. Replace the placeholders with the actual target branch and full base/head commit IDs. Pick one disposition.

```text
/fleet review TARGET_BRANCH BASE_SHA HEAD_SHA ready
```

Use `changes` when an evidenced defect needs a fix and `evidence` when a material claim is still unverified. Use `ready` only when the approved criteria are supported and material blockers are resolved. For a fresh review after a push, reconcile the old findings against the new head and examine the new diff and any changed integration paths.

Lead with the architectural verdict, the affected path and the most consequential finding. Separate blocking findings, follow-ups and open questions. For each blocker give its impact, file/line or artifact, evidence, the smallest appropriate correction and how to verify it. Then report the acceptance evidence, outstanding uncertainties, optional refactors or index candidates, and any rollout or monitoring action with an owner. End with the specific decision requested of the human. Return the report to the dispatcher for the PR conversation and the actionable findings to the original implementer. Keep the root work item open for the human decision.
