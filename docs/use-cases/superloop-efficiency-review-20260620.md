# SuperLoop Efficiency Review

Date: 2026-06-20
Controller: codex-thread:019ede5e-c2c8-72b0-8665-2effa6288d05
Trigger: required reflection after #247 local controller acceptance and before
resuming dependency-ordered use-case work.

## Repeated Controller Actions Observed

- Rebuilding the same mental evidence map after every compaction or long run.
- Reconstructing latest evidence package paths by hand from timestamps.
- Rewriting near-identical semantic evaluator prompts for Pi and OpenCode.
- Waiting on evaluator agents while leaving GitHub issue, PR, and Project state
  stale.
- Rechecking broad source modules only after all dialogue work is done.
- Retaining completed subagents long enough to hit the thread agent limit.

## Adopted Low-Risk Accelerators

1. Record a tracked controller acceptance report for every accepted use case.

   The report must list current evidence packages, deterministic verifier
   boundary, semantic evaluator agents, controller decision, and residual risks.
   This avoids re-deriving acceptance state from scattered evidence paths after
   compaction.

2. Dispatch semantic evaluators by client family, not by individual shape, when
   the evidence packages share one scorecard.

   For UC5, one non-Spark evaluator covered all Pi shapes and one covered all
   OpenCode shapes. This preserved non-deterministic judgment while reducing
   prompt repetition and agent-slot churn.

3. Use evaluator wait time for non-overlapping hygiene.

   During semantic review waits, run focused source tests, refresh issue/PR
   state, check rate limits, and update GitHub comments/Project state. Do not
   start unrelated implementation that would complicate integration.

4. Close completed agents immediately after integrating their evidence.

   This prevents thread-limit failures before the next evaluator or worker
   dispatch.

5. Prefer targeted Project #6 reads and no-op-free updates.

   Read the specific issue or PR items affected by the durable state change.
   Avoid broad board scans and do not create duplicate PR items when auto-add
   is expected but not immediately visible.

6. Keep deterministic helpers structural.

   The controller may use scripts to assemble evidence paths, command status,
   verifier JSON, and generation counts. It must not add deterministic prose
   scoring or string/regex meaning gates.

## Deferred Automation

The controller should not add a new automation script merely to save a few
minutes unless it will be reused across multiple use cases without weakening
review quality.

Good future candidates:

- a latest-evidence indexer that reports newest package, verifier, metadata,
  and raw turn paths per use case/client/shape;
- a GitHub comment body generator that consumes a controller acceptance report;
- a Project #6 reconciliation helper that performs targeted field updates from
  an explicit local plan.

Not adopted now:

- automated semantic scoring;
- deterministic checks over assistant prose meaning;
- broad Project board mutation;
- one-shot scripts that duplicate existing runner/verifier contracts.

## Controller Rule Going Forward

Before dequeuing the next use case, create or update a compact tracked report
for the just-accepted use case and reconcile the corresponding GitHub issue/PR
coordination state. During any evaluator wait, run only non-overlapping hygiene
or focused tests that cannot invalidate the evaluator's evidence set.
