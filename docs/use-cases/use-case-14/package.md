# Use Case 14 Package: Trustworthy Readiness Report

Issue: #256.

## Status

Queue state: selected after UC13 Codex parity acceptance. UC14 aggregates the
accepted use-case evidence into a user-facing readiness report that separates
proven layers from remaining gaps.

Controller state: package materialized. Acceptance requires report generation,
structural verifier pass, source checks, and non-Spark evaluator review of the
report's claim honesty.

## Method Binding

This package localizes the reusable method in
`holistic_orchestrated_pipeline_spec.md` and
`docs/use-cases/dependency-mesh.md`.

UC14 is a claim-ladder/reporting use case. Its product value is not a new MCP
tool invocation; it is an honest summary of what the SuperLoop evidence proves
for Pi, OpenCode, and Codex, and what remains unproven.

## Full Story

1. Use the current checkout as the authority.
2. Use only the current-worktree test venv:
   `run/test-venvs/project-init-workflow/bin/python`.
3. Gather durable evidence from accepted use-case packages, controller
   acceptance records, runtime evidence packages, verifier JSON, semantic
   evaluator reports, and issue/Project coordination records.
4. Build a structured claim ladder with separate layers for source/tests,
   backend/container, ContextForge route, target-client visibility, ordinary
   interactive proof, safe-call proof, and handoff readiness.
5. Name Pi, OpenCode, and Codex separately.
6. Preserve non-actions and residual risks, especially where OpenCode or Codex
   have list/config-readback evidence but no reviewed safe-call proof.
7. Generate a concise readiness report for the user.
8. Run a deterministic verifier over metadata, artifact presence, structured
   claim fields, and declared gaps.
9. Send the generated report package to a non-Spark evaluator for semantic
   judgment of claim honesty and usefulness.

## Terminal Boundary

The terminal boundary is a readiness report package showing:

- exact evidence artifacts used;
- structured claim ladder by layer and client;
- explicit gaps and residual risks;
- source/test and verifier results;
- evaluator review of the generated prose.

The terminal boundary is not a claim that the project is release-ready, that
every service has safe-call proof in every client, that live/legacy
ContextForge was mutated, or that the report can replace the underlying
evidence.

## Minimal Commands

```bash
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python \
  docker/client-harness/scripts/run-use-case-14-readiness-report.py
```

## Expected Visible Story

The generated report should give a succinct answer to "is this ready?" by
separating:

- proven SuperLoop/harness readiness;
- proven project-init and target-client dialogue behavior;
- controlled dev-surface proof;
- client-specific limitations;
- work that remains intentionally unclaimed.

It should not use generic validation language to hide the weakest proven layer.

## Deterministic Boundary

UC14 deterministic scripts may verify JSON parseability, artifact presence,
required fields, declared clients, declared claim layers, and report file
existence.

They must not use matched strings, regexes, keyword searches, or text parsing as
the oracle for the meaning or quality of the generated readiness prose. The
generated report's semantic adequacy belongs to the non-Spark evaluator and
controller.

## Step Criteria

### evidence_inventory (20 pts)

Expected: the package lists the accepted evidence artifacts it relies on and
flags missing artifacts.

Fail if: missing artifacts are silently ignored.

### claim_ladder (25 pts)

Expected: source/tests, backend/container, ContextForge route, target-client
visibility, ordinary interactive proof, safe-call proof, and handoff readiness
are separate structured layers.

Fail if: the report collapses weaker proof into a stronger readiness claim.

### client_separation (20 pts)

Expected: Pi, OpenCode, and Codex are named separately with their strongest
proven layer and gaps.

Fail if: one client's evidence is generalized to all clients.

### no_overclaim_boundary (20 pts)

Expected: OpenCode/Codex list-only or config-readback surfaces are not reported
as safe-call proof, and UC13 is not reported as semantic dialogue proof.

Fail if: the report claims release readiness or full safe-call readiness without
evidence.

Fatal overclaims to forbid:

- "all services are ready" from UC5 source lifecycle or install-only evidence;
- OpenCode/Codex safe-call proof from UC13 list/config-readback;
- UC13 dialogue readiness or UC13 re-evaluation of UC12 semantics;
- project service existence implying every client imported or used it;
- readback, list, or config evidence being treated as tool-use proof;
- UC10 same-session hot-registration proof;
- UC12 runtime readiness for `calendar-notes`;
- credential-scoped provider validity for credentialed services;
- Serena runtime indexing/LSP health;
- deterministic verifier judgment of assistant/report prose meaning.

### evaluator_review (15 pts)

Expected: a non-Spark evaluator reviews the generated readiness report and
returns a narrative scorecard.

Fail if: deterministic checks are used as the final judge of prose meaning.

## Source Checks

```bash
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python \
  -m py_compile \
  docker/client-harness/scripts/run-use-case-14-readiness-report.py \
  docker/client-harness/scripts/verify-use-case-14-readiness-evidence.py

PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python \
  -m unittest tests.test_use_case1_e2e_gate -v
```

## Remediation Routing

- missing accepted evidence: record the gap and either rerun the source use case
  or lower the readiness claim;
- collapsed claim layers: repair the report metadata and visible report before
  evaluator review;
- deterministic prose judgment: repair verifier scope and repeat evaluation;
- stale client coverage: update the package for the current Pi/OpenCode/Codex
  target set before rerunning;
- evaluator failure: classify as package/report defect unless the evaluator
  identifies a lower-layer evidence contradiction.
