# Use Case 5c Package: Context7 Single-Service Lifecycle

## Status

Queue state: selected after accepted UC1, UC2, UC3, UC4, UC7, UC5a, and UC5b.

Controller state: accepted for the current branch evidence set.

Acceptance report:
`run/holistic-orchestrator/reports/uc5c-controller-acceptance-20260620T023500Z.md`.

Accepted evidence:

The raw evidence paths below are local ignored artifacts; this package and the
linked GitHub issue/PR updates are the durable tracked summary.

- Source evidence:
  `docker/client-harness/evidence/use-case-5c/context7-lifecycle/context7-lifecycle-use-case-5c-evidence-20260620T023300Z.md`
- Evaluation package:
  `docker/client-harness/evidence/use-case-5c/context7-lifecycle/context7-lifecycle-evaluation-package-20260620T023300Z.md`
- Metadata:
  `docker/client-harness/evidence/use-case-5c/context7-lifecycle/context7-lifecycle-metadata-20260620T023300Z.json`
- Structural verifier:
  `docker/client-harness/evidence/use-case-5c/context7-lifecycle/context7-lifecycle-verifier-20260620T023300Z.json`
- Semantic evaluator: Hilbert `019ee2e0-789d-7bc0-9172-c214cbeeb3b6`,
  PASS 100/100.

GitHub source: issue #260, "Decompose #247: context7 service readiness and
apply proof."

Parent umbrella: issue #247, "Ordinary use case 05: Add a useful project
service with plan and approval."

Prerequisites:

- UC5a / #270 service localization taxonomy.
- UC5b / #259 helper-offered service readiness matrix.

Downstream slices: #261-#268 per-service readiness, #269 selection-shape
validation, and #247 umbrella acceptance.

## Method Binding

This package localizes the reusable method in
`holistic_orchestrated_pipeline_spec.md`,
`docs/use-cases/dependency-mesh.md`, and
`docker/client-harness/DIALOGUE_EVALUATION_METHOD.md`.

UC5c is a source/docs/tests service-lifecycle slice. It proves the Context7
single-service project-local plan/apply/readback substrate for Pi and OpenCode.
It does not prove the full #247 ordinary dialogue, curated multi-service
selection, all-services apply, post-refresh target-client visibility, or actual
Context7 tool use.

## Full Story

1. Refresh live GitHub issue/PR context for #247, #260, #259, #270, and PR
   #271.
2. Preserve accepted lower-layer evidence from UC1, UC2, UC3, UC4, UC7, UC5a,
   and UC5b.
3. Inspect the readiness matrix row for `context7` and confirm it remains the
   current first service slice owned by #260.
4. Exercise the source-level single-service lifecycle tests for Pi and
   OpenCode using a current-worktree venv.
5. For Pi, approve/apply `context7:canonical` through the helper and assert:
   project state is written, no `opencode.json` is written, target-client
   status is installed, lifecycle activation is shared ContextForge service,
   and the flow stops at the Pi reload boundary.
6. For OpenCode, approve/apply `context7:canonical` through the helper and
   assert: project state plus project-local `opencode.json` are written,
   target-client status is planned/installed as appropriate, lifecycle
   activation is shared ContextForge service, and the flow stops at the new
   session boundary.
7. Assemble an evaluation package with issue context, artifacts, test output,
   structural verifier output, and scorecard.
8. Dispatch a non-Spark semantic evaluator to judge whether the evidence
   satisfies #260 and safely advances toward #247 without overclaiming.

## Terminal Boundary

UC5c ends when Context7 single-service project-local lifecycle/apply proof is
accepted as a sufficient prerequisite for later #247 single-service dialogue
and selection-shape work. It does not accept #247, #269, #261-#268, actual
post-refresh target-client tool visibility, or Context7 tool-use follow-up.

## Expected Artifact Story

- The readiness matrix identifies `context7` as the current first service slice
  and routes it to #260.
- The source test covers both Pi and OpenCode lifecycle behavior.
- The helper mutates only approved project-local artifacts.
- Pi apply writes project state only and stops at reload-required.
- OpenCode apply writes project state plus project-local `opencode.json` and
  stops at new-session-required.
- Target-client status in project state is an install/binding state, not proof
  of post-refresh tool invocation.
- No validation/probe phase is introduced into ordinary project init.

## Deterministic Setup

Required setup for the source-evidence attempt:

```text
run/test-venvs/project-init-workflow/bin/python
```

The runner must execute from the current worktree and must not borrow a sibling
checkout venv.

## Step Criteria

This use case has no model-dependent target-client dialogue turn. The semantic
evaluator still must score the authored artifact and the total source evidence
package. Deterministic checks may validate command status, artifact presence,
JSON parseability, required structured fields, enum relationships, and test
results. They must not judge the meaning of prose.

### issue_context_refreshed (10 pts)

Expected: Evidence includes current issue/PR readback for #247, #260, #259,
#270, and PR #271.

Fail if: package acceptance relies only on stale dependency-mesh text.

### readiness_matrix_binding (15 pts)

Expected: The matrix row for `context7` points to #260, is marked as the
current slice, and uses a taxonomy type from the structured taxonomy contract.

Fail if: Context7 readiness is inferred from menu presence alone or the row
does not route to #260.

### pi_lifecycle_apply (20 pts)

Expected: The Pi source test proves approved `context7:canonical` apply writes
only project state, records shared ContextForge service lifecycle, marks the
target-client layer installed, and stops at reload-required.

Fail if: Pi apply writes OpenCode config, global client config, trust state,
secrets, registry state, or a post-install validation/probe result.

### opencode_lifecycle_apply (20 pts)

Expected: The OpenCode source test proves approved `context7:canonical` apply
writes project state plus project-local `opencode.json`, records shared
ContextForge service lifecycle, marks the OpenCode binding status, and stops at
new-session-required.

Fail if: OpenCode apply mutates global config, live ContextForge, secrets,
trust state, or a post-install validation/probe result.

### source_boundary (15 pts)

Expected: The evidence is honest that UC5c is source/docs/tests lifecycle proof
only, not a target-client dialogue pass or post-refresh tool invocation.

Fail if: the package claims #247, #269, #261-#268, or Context7 tool-use
success.

### install_only_boundary (10 pts)

Expected: The flow preserves install-only completion and reload/new-session
stop.

Fail if: validation, smoke probing, reload interrogation, or low-level helper
key collection is added to ordinary project init.

### deterministic_boundary (10 pts)

Expected: Deterministic tests and verifier remain structural and source-level;
semantic adequacy is judged by the evaluator.

Fail if: deterministic code scores prose meaning, uses regex/string matching as
a semantic gate, or replaces the evaluator.

## Acceptance Commands

```text
run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_context7_single_service_lifecycle -v
run/test-venvs/project-init-workflow/bin/python docker/client-harness/scripts/run-use-case-5c-context7-lifecycle.py
```

The runner produces source evidence, verifier JSON, evaluation-package
Markdown, and semantic-evaluator-ready criteria.

## Remediation Routing

- matrix row mismatch: repair `docs/contextforge-service-readiness-matrix.json`
  and rerun UC5b regression if semantics change materially;
- Pi lifecycle failure: repair helper/project-state binding behavior and rerun
  source tests;
- OpenCode lifecycle failure: repair project-local config planning/apply and
  rerun source tests;
- validation/probe leakage: restore install-only terminal boundary in code,
  prompts, and tests;
- target-client overclaim: revise state/readback wording and package criteria;
- deterministic prose gate: move checks to structured JSON and evaluator
  criteria;
- evaluator fails semantic adequacy: remediate source artifacts, rerun tests and
  source evidence package, then dispatch a new non-Spark evaluator.
