# Use Case 5e Package: OpenZeppelin Shared-Canonical Lifecycle

## Status

Queue state: selected after accepted UC1, UC2, UC3, UC4, UC7, UC5a, UC5b,
UC5c, and UC5d.

Controller state: accepted for the current branch evidence set.

Acceptance report:
`run/holistic-orchestrator/reports/uc5e-controller-acceptance-20260620T025500Z.md`.

Accepted evidence:

The raw evidence paths below are local ignored artifacts; this package and the
linked GitHub issue/PR updates are the durable tracked summary.

- Source evidence:
  `docker/client-harness/evidence/use-case-5e/openzeppelin-lifecycle/openzeppelin-lifecycle-use-case-5e-evidence-20260620T025202Z.md`
- Evaluation package:
  `docker/client-harness/evidence/use-case-5e/openzeppelin-lifecycle/openzeppelin-lifecycle-evaluation-package-20260620T025202Z.md`
- Metadata:
  `docker/client-harness/evidence/use-case-5e/openzeppelin-lifecycle/openzeppelin-lifecycle-metadata-20260620T025202Z.json`
- Structural verifier:
  `docker/client-harness/evidence/use-case-5e/openzeppelin-lifecycle/openzeppelin-lifecycle-verifier-20260620T025202Z.json`
- Semantic evaluator: Kepler `019ee2f1-a2f2-7f80-85e8-5b03afdb035a`,
  PASS 100/100.

GitHub source: issue #264, "Decompose #247: openzeppelin-solidity-contracts
readiness and apply proof."

Parent umbrella: issue #247, "Ordinary use case 05: Add a useful project
service with plan and approval."

Prerequisites:

- UC5a / #270 service localization taxonomy.
- UC5b / #259 helper-offered service readiness matrix.
- UC5c / #260 Context7 first service lifecycle proof.
- UC5d / #263 mentality repo-local/static lifecycle proof.

Downstream slices: remaining #261-#268 per-service readiness, #269
selection-shape validation, and #247 umbrella acceptance.

## Method Binding

This package localizes the reusable method in
`holistic_orchestrated_pipeline_spec.md`,
`docs/use-cases/dependency-mesh.md`, and
`docker/client-harness/DIALOGUE_EVALUATION_METHOD.md`.

UC5e is a source/docs/tests service-lifecycle slice. It proves the
`openzeppelin-solidity-contracts` shared-canonical project-local
plan/apply/readback substrate for Pi and OpenCode. It does not prove the full
#247 ordinary dialogue, curated multi-service selection, all-services apply,
post-refresh target-client visibility, or actual OpenZeppelin tool invocation.

## Ordering Rationale

`openzeppelin-solidity-contracts` is selected after Context7 and mentality
because it is the lowest-dependency remaining service slice: shared canonical,
credential-free, known-safe, and not browser/session/project-provisioning
scoped. The safety boundary is code-generation preview only, with no
deployment, wallet, RPC, key, audit, or project file mutation claim.

## Full Story

1. Refresh live GitHub issue/PR context for #247, #264, #259, #260, #263, #270,
   and PR #271.
2. Preserve accepted lower-layer evidence from UC1, UC2, UC3, UC4, UC7, UC5a,
   UC5b, UC5c, and UC5d.
3. Inspect the readiness matrix row for `openzeppelin-solidity-contracts` and
   confirm it is owned by #264, has taxonomy type `shared_canonical`, and
   carries no-deployment/no-wallet/no-security-claim non-actions.
4. Exercise source-level single-service lifecycle tests for Pi and OpenCode
   using a current-worktree venv.
5. For Pi, approve/apply `openzeppelin-solidity-contracts:canonical` through
   the helper and assert: project state is written, no `opencode.json` is
   written, target-client status is installed, lifecycle activation is shared
   ContextForge service, tool policy is safe-call preview only, and the flow
   stops at the Pi reload boundary.
6. For OpenCode, approve/apply `openzeppelin-solidity-contracts:canonical`
   through the helper and assert: project state plus project-local
   `opencode.json` are written, target-client status is installed, lifecycle
   activation is shared ContextForge service, tool policy is safe-call preview
   only, and the flow stops at the new-session boundary.
7. Assemble an evaluation package with issue context, artifacts, test output,
   structural verifier output, and scorecard.
8. Dispatch a non-Spark semantic evaluator to judge whether the evidence
   satisfies #264 and safely advances toward #247 without overclaiming.

## Terminal Boundary

UC5e ends when OpenZeppelin shared-canonical project-local lifecycle/apply proof
is accepted as a sufficient prerequisite for later #247 multi-service work. It
does not accept #247, #269, remaining #261-#268 services, actual post-refresh
target-client tool visibility, generated-code correctness, security/audit
claims, deployment, or chain/RPC behavior.

## Expected Artifact Story

- The readiness matrix identifies `openzeppelin-solidity-contracts` as shared
  canonical and routes it to #264.
- The source test covers both Pi and OpenCode lifecycle behavior.
- The helper mutates only approved project-local artifacts.
- Pi apply writes project state only and stops at reload-required.
- OpenCode apply writes project state plus project-local `opencode.json` and
  stops at new-session-required.
- No per-project backend, bridge, port, service unit, server-instance, wallet,
  key, RPC, deployment, or project Solidity file is created.
- Tool policy is safe-call preview only and forbids deployment, project
  mutation, wallet/private-key, chain/RPC, and security/audit proof
  substitutions.
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

Expected: Evidence includes current issue/PR readback for #247, #264, #259,
#260, #263, #270, and PR #271.

Fail if: package acceptance relies only on stale dependency-mesh text.

### readiness_matrix_binding (15 pts)

Expected: The matrix row for `openzeppelin-solidity-contracts` points to #264,
has taxonomy type `shared_canonical`, and carries no-deployment/no-wallet/non-
audit non-actions.

Fail if: readiness is inferred from menu presence alone or the row does not
route to #264.

### pi_lifecycle_apply (20 pts)

Expected: The Pi source test proves approved
`openzeppelin-solidity-contracts:canonical` apply writes only project state,
records shared ContextForge service lifecycle, marks the target-client layer
installed, preserves safe-call preview policy, and stops at reload-required.

Fail if: Pi apply writes OpenCode config, global client config, project Solidity
files, trust state, secrets, registry state, or a post-install probe result.

### opencode_lifecycle_apply (20 pts)

Expected: The OpenCode source test proves approved
`openzeppelin-solidity-contracts:canonical` apply writes project state plus
project-local `opencode.json`, records shared lifecycle activation, preserves
safe-call preview policy, marks OpenCode binding status, and stops at new-
session-required.

Fail if: OpenCode apply mutates global config, live ContextForge, project
Solidity files, secrets, trust state, or a post-install probe result.

### safe_preview_boundary (15 pts)

Expected: The service record preserves safe-call ERC-20 preview policy and
forbids deployment, project mutation, generated-code audit claims,
wallet/private-key, chain/RPC, and secret-bearing input substitutions.

Fail if: the package treats generated Solidity as security/audit proof or
allows deployment/project mutation as ordinary readiness proof.

### source_boundary (10 pts)

Expected: The evidence is honest that UC5e is source/docs/tests lifecycle proof
only, not a target-client dialogue pass or post-refresh tool call.

Fail if: the package claims #247, #269, remaining services, generated-code
correctness, deployment, or tool-use success.

### deterministic_boundary (10 pts)

Expected: Deterministic tests and verifier remain structural and source-level;
semantic adequacy is judged by the evaluator.

Fail if: deterministic code scores prose meaning, uses regex/string matching as
a semantic gate, or replaces the evaluator.

## Acceptance Commands

```text
run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_openzeppelin_single_service_lifecycle -v
run/test-venvs/project-init-workflow/bin/python docker/client-harness/scripts/run-use-case-5e-openzeppelin-lifecycle.py
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
- unsafe preview boundary: repair service policy and source behavior to
  preserve no-deployment/no-wallet/no-project-mutation boundaries;
- target-client overclaim: revise state/readback wording and package criteria;
- deterministic prose gate: move checks to structured JSON and evaluator
  criteria;
- evaluator fails semantic adequacy: remediate source artifacts, rerun tests and
  source evidence package, then dispatch a new non-Spark evaluator.
