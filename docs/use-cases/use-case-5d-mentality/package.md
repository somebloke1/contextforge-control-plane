# Use Case 5d Package: Mentality Repo-Local Static Lifecycle

## Status

Queue state: selected after accepted UC1, UC2, UC3, UC4, UC7, UC5a, UC5b, and
UC5c.

Controller state: accepted for the current branch evidence set.

Acceptance report:
`run/holistic-orchestrator/reports/uc5d-controller-acceptance-20260620T024610Z.md`.

Accepted evidence:

The raw evidence paths below are local ignored artifacts; this package and the
linked GitHub issue/PR updates are the durable tracked summary.

- Source evidence:
  `docker/client-harness/evidence/use-case-5d/mentality-lifecycle/mentality-lifecycle-use-case-5d-evidence-20260620T024230Z.md`
- Evaluation package:
  `docker/client-harness/evidence/use-case-5d/mentality-lifecycle/mentality-lifecycle-evaluation-package-20260620T024230Z.md`
- Metadata:
  `docker/client-harness/evidence/use-case-5d/mentality-lifecycle/mentality-lifecycle-metadata-20260620T024230Z.json`
- Structural verifier:
  `docker/client-harness/evidence/use-case-5d/mentality-lifecycle/mentality-lifecycle-verifier-20260620T024230Z.json`
- Semantic evaluator: Erdos `019ee2e8-edd3-7fa3-85a4-73c2a61134d9`,
  PASS 100/100.

GitHub source: issue #263, "Decompose #247: mentality service readiness and
apply proof."

Parent umbrella: issue #247, "Ordinary use case 05: Add a useful project
service with plan and approval."

Prerequisites:

- UC4 / #246 governance route through ContextForge.
- UC5a / #270 service localization taxonomy.
- UC5b / #259 helper-offered service readiness matrix.
- UC5c / #260 Context7 first service lifecycle proof.

Downstream slices: remaining #261-#268 per-service readiness, #269
selection-shape validation, and #247 umbrella acceptance.

## Method Binding

This package localizes the reusable method in
`holistic_orchestrated_pipeline_spec.md`,
`docs/use-cases/dependency-mesh.md`, and
`docker/client-harness/DIALOGUE_EVALUATION_METHOD.md`.

UC5d is a source/docs/tests service-lifecycle slice. It proves the `mentality`
repo-local/static project-local plan/apply/readback substrate for Pi and
OpenCode. It does not prove the full #247 ordinary dialogue, curated
multi-service selection, all-services apply, post-refresh target-client
visibility, or actual governance tool invocation.

## Ordering Rationale

`mentality` is selected ahead of numeric #261 because it is the least-dependent
remaining service slice: repo-local/static, credential-free, known-safe, and
directly continuous with the already accepted UC4 governance-route remediation.
Credential-scoped, session-scoped, and project-scoped runtime services carry
more external dependency and side-effect risk.

## Full Story

1. Refresh live GitHub issue/PR context for #247, #263, #259, #260, #270, and
   PR #271.
2. Preserve accepted lower-layer evidence from UC1, UC2, UC3, UC4, UC7, UC5a,
   UC5b, and UC5c.
3. Inspect the readiness matrix row for `mentality` and confirm it is owned by
   #263, has taxonomy type `repo_local_static`, and carries read-only
   governance non-actions.
4. Exercise source-level single-service lifecycle tests for Pi and OpenCode
   using a current-worktree venv.
5. For Pi, approve/apply `mentality:static_repo_local` through the helper and
   assert: project state is written, no `opencode.json` is written, governance
   ledgers are unchanged, target-client status is installed, lifecycle
   activation is shared ContextForge service, tool policy is read-only, and the
   flow stops at the Pi reload boundary.
6. For OpenCode, approve/apply `mentality:static_repo_local` through the helper
   and assert: project state plus project-local `opencode.json` are written,
   governance ledgers are unchanged, target-client status is installed,
   lifecycle activation is shared ContextForge service, tool policy is
   read-only, and the flow stops at the new-session boundary.
7. Assemble an evaluation package with issue context, artifacts, test output,
   structural verifier output, and scorecard.
8. Dispatch a non-Spark semantic evaluator to judge whether the evidence
   satisfies #263 and safely advances toward #247 without overclaiming.

## Terminal Boundary

UC5d ends when mentality repo-local/static project-local lifecycle/apply proof
is accepted as a sufficient prerequisite for later #247 multi-service work. It
does not accept #247, #269, remaining #261-#268 services, actual post-refresh
target-client tool visibility, or governance tool-use follow-up.

## Expected Artifact Story

- The readiness matrix identifies `mentality` as repo-local/static and routes
  it to #263.
- The source test covers both Pi and OpenCode lifecycle behavior.
- The helper mutates only approved project-local artifacts.
- Pi apply writes project state only and stops at reload-required.
- OpenCode apply writes project state plus project-local `opencode.json` and
  stops at new-session-required.
- Governance ledgers remain unchanged.
- Tool policy is read-only and forbids mutating governance operations and local
  ledger-file substitution.
- Target-client status in project state is an install/binding state, not proof
  of post-refresh tool invocation.

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

Expected: Evidence includes current issue/PR readback for #247, #263, #259,
#260, #270, and PR #271.

Fail if: package acceptance relies only on stale dependency-mesh text.

### readiness_matrix_binding (15 pts)

Expected: The matrix row for `mentality` points to #263, has taxonomy type
`repo_local_static`, and carries read-only governance non-actions.

Fail if: mentality readiness is inferred from menu presence alone or the row
does not route to #263.

### pi_lifecycle_apply (20 pts)

Expected: The Pi source test proves approved `mentality:static_repo_local`
apply writes only project state, preserves governance ledgers, records shared
ContextForge service lifecycle, marks the target-client layer installed, and
stops at reload-required.

Fail if: Pi apply writes OpenCode config, global client config, governance
ledgers, trust state, secrets, registry state, or a post-install probe result.

### opencode_lifecycle_apply (20 pts)

Expected: The OpenCode source test proves approved
`mentality:static_repo_local` apply writes project state plus project-local
`opencode.json`, preserves governance ledgers, records shared lifecycle
activation, marks the OpenCode binding status, and stops at new-session-
required.

Fail if: OpenCode apply mutates global config, live ContextForge, governance
ledgers, secrets, trust state, or a post-install probe result.

### governance_read_only_boundary (15 pts)

Expected: The service record preserves read-only governance policy and forbids
mutating governance operations and local ledger-file substitution.

Fail if: apply creates, updates, deletes, or directly reads local ledger files
as proof of target-client readiness.

### source_boundary (10 pts)

Expected: The evidence is honest that UC5d is source/docs/tests lifecycle proof
only, not a target-client dialogue pass or post-refresh governance tool call.

Fail if: the package claims #247, #269, remaining services, or tool-use
success.

### deterministic_boundary (10 pts)

Expected: Deterministic tests and verifier remain structural and source-level;
semantic adequacy is judged by the evaluator.

Fail if: deterministic code scores prose meaning, uses regex/string matching as
a semantic gate, or replaces the evaluator.

## Acceptance Commands

```text
run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_mentality_single_service_lifecycle -v
run/test-venvs/project-init-workflow/bin/python docker/client-harness/scripts/run-use-case-5d-mentality-lifecycle.py
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
- governance mutation or direct ledger proof: repair service policy and source
  behavior to preserve read-only route boundaries;
- target-client overclaim: revise state/readback wording and package criteria;
- deterministic prose gate: move checks to structured JSON and evaluator
  criteria;
- evaluator fails semantic adequacy: remediate source artifacts, rerun tests and
  source evidence package, then dispatch a new non-Spark evaluator.
