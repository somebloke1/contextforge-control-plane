# Use Case 5b Package: Helper-Offered Service Readiness Matrix

## Status

Queue state: selected after accepted UC1, UC2, UC3, UC4, UC7, and UC5a.

Controller state: accepted for the current branch evidence set.

Acceptance report:
`run/holistic-orchestrator/reports/uc5b-controller-acceptance-20260620T022136Z.md`.

Accepted evidence:

The raw evidence paths below are local ignored artifacts; this package and the
linked GitHub issue/PR updates are the durable tracked summary.

- Source evidence:
  `docker/client-harness/evidence/use-case-5b/readiness-matrix/readiness-matrix-use-case-5b-evidence-20260620T021440Z.md`
- Evaluation package:
  `docker/client-harness/evidence/use-case-5b/readiness-matrix/readiness-matrix-evaluation-package-20260620T021440Z.md`
- Metadata:
  `docker/client-harness/evidence/use-case-5b/readiness-matrix/readiness-matrix-metadata-20260620T021440Z.json`
- Structural verifier:
  `docker/client-harness/evidence/use-case-5b/readiness-matrix/readiness-matrix-verifier-20260620T021440Z.json`
- Semantic evaluator: Euclid `019ee2cf-6829-75f0-8086-18b601b49eca`,
  PASS 96/100.

GitHub source: issue #259, "Decompose #247: service readiness matrix for
helper-offered services."

Parent umbrella: issue #247, "Ordinary use case 05: Add a useful project
service with plan and approval."

Prerequisite: UC5a / #270 service localization taxonomy.

Downstream slices: #260-#268 per-service readiness and #269 selection-shape
validation.

## Method Binding

This package localizes the reusable method in
`holistic_orchestrated_pipeline_spec.md`,
`docs/use-cases/dependency-mesh.md`, and
`docker/client-harness/DIALOGUE_EVALUATION_METHOD.md`.

UC5b is a source/docs/tests readiness-matrix slice. It does not prove any
individual service ready, and it does not run Pi/OpenCode service-selection
dialogues. Acceptance requires current issue context, structured matrix
coverage, focused source tests, a structural verifier, and non-Spark semantic
evaluation of whether #259 can safely guide later #247 service readiness work.

## Full Story

1. Refresh live GitHub issue/PR context for #247, #259, #270, #260-#268, and
   PR #271.
2. Preserve accepted lower-layer evidence from UC1, UC2, UC3, UC4, UC7, and
   UC5a.
3. Inspect the current readiness artifacts:
   - `docs/contextforge-service-localization-taxonomy.json`;
   - `docs/contextforge-service-readiness-matrix.json`;
   - `tests/test_service_readiness_matrix.py`.
4. Ensure the matrix covers every real helper-offered service:
   `context7`, `exa-search`, `github`, `mentality`,
   `openzeppelin-solidity-contracts`, `playwright`, `ssh-tmux`, `web-search`,
   and `serena`.
5. Ensure the matrix excludes `None` from service readiness and represents it
   only as a not-a-service option owned by #248.
6. Ensure each service row has:
   - service id and binding or binding pattern;
   - taxonomy type from the structured taxonomy contract;
   - owner issue;
   - source paths;
   - instantiation path;
   - Pi visibility expectation;
   - OpenCode visibility expectation;
   - safe probe status and probe shape;
   - blockers or non-actions;
   - current-slice marker.
7. Ensure the matrix distinguishes ready/known-safe, conditional, blocked, and
   future per-service proof obligations without silently marking conditional
   services active.
8. Run current-worktree source tests that validate structured matrix shape and
   taxonomy relationships. Deterministic checks may inspect JSON structure and
   enum/value relationships. They must not judge prose meaning.
9. Assemble an evaluation package with issue context, artifacts, test output,
   structural verifier output, and scorecard.
10. Dispatch a non-Spark semantic evaluator to judge whether the matrix
    satisfies #259 and can safely drive #260-#268 and #247 without false
    readiness claims.

## Terminal Boundary

UC5b ends when the readiness matrix is accepted as a sufficient planning and
evidence-routing artifact for #247's decomposed service work. It does not
accept #247, #260-#268, #269, or any user-facing service-selection/apply flow.

## Expected Artifact Story

- The matrix uses UC5a's structured taxonomy contract.
- The matrix covers all real helper-offered services in the current menu.
- The matrix excludes `None` from service readiness.
- Each service has a next issue/evidence path before #247 attempts
  all-services apply.
- Conditional or blocked services remain conditional or blocked; the matrix
  must not imply readiness from mere menu presence, credentials, backend health,
  bridge reachability, or local file/source presence.
- Pi/OpenCode visibility expectations are defined as follow-on expectations,
  not as already-proven client visibility unless evidence exists in the
  relevant service slice.

## Deterministic Setup

Required setup for the source-evidence attempt:

```text
run/test-venvs/project-init-workflow/bin/python
```

The runner must execute from the current worktree and must not borrow a sibling
checkout venv.

## Step Criteria

This use case has no model-dependent target-client dialogue turn. The semantic
evaluator still must score the authored matrix and the total source evidence
package. Deterministic checks may validate command status, artifact presence,
JSON parseability, required structured fields, enum relationships, and test
results. They must not judge prose meaning.

### issue_context_refreshed (10 pts)

Expected: Evidence includes current issue/PR readback for #247, #259, #270,
#260-#268, and PR #271.

Fail if: matrix acceptance relies only on stale dependency-mesh text.

### taxonomy_consumed (10 pts)

Expected: The matrix points at UC5a's structured taxonomy contract and uses
only taxonomy ids defined there.

Fail if: the matrix invents classes or treats service-binding suffixes as
lifecycle authority.

### service_coverage (20 pts)

Expected: The matrix covers all real helper-offered services and excludes
`None` from service readiness.

Fail if: any required service is missing, duplicated, or silently folded into a
generic bucket.

### per_service_fields (20 pts)

Expected: Each service row includes owner issue, source paths, instantiation
path, Pi/OpenCode visibility expectations, safe probe status, probe shape, and
blockers/non-actions.

Fail if: a service lacks a concrete next issue/evidence path.

### false_readiness_prevention (20 pts)

Expected: Conditional services remain conditional, blocked services remain
blocked, and readiness is not inferred from menu presence, credential presence,
backend health, direct bridge checks, or local files alone.

Fail if: the matrix lets #247 count a service as active without per-service
proof or an explicit blocked/non-action result.

### current_slice_boundary (10 pts)

Expected: The matrix marks only the intended current first service slice and
does not accept the full #247 umbrella.

Fail if: matrix acceptance is treated as all-services readiness.

### deterministic_boundary (10 pts)

Expected: Deterministic tests and verifier remain structural and source-level;
semantic adequacy is judged by the evaluator.

Fail if: deterministic code scores prose meaning, uses regex/string matching as
a semantic gate, or replaces the evaluator.

## Acceptance Commands

```text
run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_service_readiness_matrix -v
run/test-venvs/project-init-workflow/bin/python docker/client-harness/scripts/run-use-case-5b-readiness-matrix.py
```

The runner produces source evidence, verifier JSON, evaluation-package
Markdown, and semantic-evaluator-ready criteria.

## Remediation Routing

- service omission or duplicate: repair matrix and tests, then rerun;
- taxonomy mismatch: repair taxonomy contract or matrix reference, then rerun
  UC5a regression if taxonomy changes materially;
- missing owner/evidence path: repair matrix row and package criteria;
- false readiness overclaim: repair row status, blockers, and non-actions;
- deterministic prose gate: move checks to structured JSON and evaluator
  criteria;
- evaluator fails semantic adequacy: remediate matrix/source artifacts, rerun
  tests and source evidence package, then dispatch a new non-Spark evaluator.
