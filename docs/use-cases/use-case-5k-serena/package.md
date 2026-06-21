# Use Case 5k Package: Serena Project-Scoped Lifecycle

## Status

Queue state: selected after accepted UC1, UC2, UC3, UC4, UC7, UC5a, UC5b,
UC5c, UC5d, UC5e, UC5f, UC5g, UC5h, UC5i, and UC5j.

Controller state: accepted source-level lifecycle slice.

Acceptance evidence:

- Source evidence package:
  `docker/client-harness/evidence/use-case-5k/serena-lifecycle/serena-lifecycle-evaluation-package-20260620T041119Z.md`.
- Source evidence transcript:
  `docker/client-harness/evidence/use-case-5k/serena-lifecycle/serena-lifecycle-use-case-5k-evidence-20260620T041119Z.md`.
- Structural verifier:
  `docker/client-harness/evidence/use-case-5k/serena-lifecycle/serena-lifecycle-verifier-20260620T041119Z.json`,
  with failures `[]`.
- Non-Spark semantic evaluator Poincare
  (`019ee338-f1ea-7f83-88b1-471a9df6294f`) returned PASS, 100/100,
  with no fatal failures.

GitHub source: issue #268, "Decompose #247: Serena service readiness and
apply proof."

Parent umbrella: issue #247, "Ordinary use case 05: Add a useful project
service with plan and approval."

Prerequisites:

- UC5a / #270 service localization taxonomy.
- UC5b / #259 helper-offered service readiness matrix.
- UC5c / #260 Context7 first service lifecycle proof.
- UC5d / #263 mentality repo-local/static lifecycle proof.
- UC5e / #264 OpenZeppelin shared-canonical lifecycle proof.
- UC5f / #266 ssh-tmux session-scoped lifecycle proof.
- UC5g / #265 Playwright session-scoped lifecycle proof.
- UC5h / #261 exa-search credential-scoped lifecycle proof.
- UC5i / #262 GitHub credential-scoped lifecycle proof.
- UC5j / #267 web-search credential-scoped lifecycle proof.

Downstream slices: #269 selection-shape validation and #247 umbrella
acceptance.

## Method Binding

This package localizes the reusable method in
`holistic_orchestrated_pipeline_spec.md`,
`docs/use-cases/dependency-mesh.md`, and
`docker/client-harness/DIALOGUE_EVALUATION_METHOD.md`.

UC5k is a source/docs/tests service-lifecycle slice. It proves the
`serena:<project-root-hash-prefix>` project-local plan/apply/readback substrate
for Pi and OpenCode. It does not prove the full #247 ordinary dialogue,
post-refresh target-client visibility, actual Serena tool invocation, LSP/index
quality, language-server installation, or runtime service health.

## Ordering Rationale

`serena` is selected last among the per-service slices because it is
project-scoped, stateful, and requires explicit language selection plus
project-instance provisioning before client binding.

## Full Story

1. Refresh live GitHub issue/PR context for #247, #268, #259, #260, #261, #262,
   #263, #264, #265, #266, #270, and PR #271.
2. Preserve accepted lower-layer evidence from UC1, UC2, UC3, UC4, UC7, UC5a,
   UC5b, UC5c, UC5d, UC5e, UC5f, UC5g, UC5h, UC5i, and UC5j.
3. Inspect the readiness matrix row for `serena` and confirm it is owned by
   #268, has taxonomy type `project_scoped`, and carries no global config, no
   LSP write, no broad-project-scan boundaries.
4. Exercise source-level single-service lifecycle tests for Pi and OpenCode
   using a current-worktree venv.
5. First prove that selecting Serena without a language stops before approval
   and asks for a concrete language or defer choice.
6. For Pi, approve/apply `serena:<project-root-hash-prefix>` through the helper
   with language input and assert: project-scoped provisioning is modeled before
   client binding, project state is written, no `opencode.json` is written,
   target-client status is installed, provision status is `created`,
   ContextForge gateway readback remains `provisioned_pending_readback`, no
   client-visible tool verification is claimed, and the flow stops at the Pi
   reload boundary.
7. For OpenCode, approve/apply `serena:<project-root-hash-prefix>` through the
   helper with language input and assert: project-scoped provisioning is modeled
   before client binding, project state plus project-local `opencode.json` are
   written, target-client status is installed, provision status is `created`,
   ContextForge gateway readback remains `provisioned_pending_readback`, no
   client-visible tool verification is claimed, and the flow stops at the
   new-session boundary.
8. Assemble an evaluation package with issue context, artifacts, test output,
   structural verifier output, and scorecard.
9. Dispatch a non-Spark semantic evaluator to judge whether the evidence
   satisfies #268 and safely advances toward #247 without overclaiming.

## Terminal Boundary

UC5k ends when Serena project-scoped project-local lifecycle/apply proof is
accepted as a sufficient prerequisite for later #247 multi-service work. It does
not accept #247, #269, actual post-refresh target-client tool visibility,
Serena runtime availability, language-server installation, LSP/index quality,
or tool-use proof.

## Expected Artifact Story

- The readiness matrix identifies `serena` as project scoped and routes it to
  #268.
- The source test covers language-input gating plus Pi and OpenCode lifecycle
  behavior.
- The helper mutates only approved project-local artifacts and the modeled
  project-scoped provision operation.
- Pi apply writes project state only and stops at reload-required.
- OpenCode apply writes project state plus project-local `opencode.json` and
  stops at new-session-required.
- No global client config, trust state, secret, live user-facing runtime claim,
  broad project scan, LSP write, or post-install Serena tool proof is created.
- Tool policy remains skip-without-service-policy until a concrete safe Serena
  probe is defined.
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

Expected: Evidence includes current issue/PR readback for #247, #268, #259,
#260, #261, #262, #263, #264, #265, #266, #270, and PR #271.

Fail if: package acceptance relies only on stale dependency-mesh text.

### readiness_matrix_binding (15 pts)

Expected: The matrix row for `serena` points to #268, has taxonomy type
`project_scoped`, and carries no-global-config/no-LSP-write/no-broad-scan
boundaries.

Fail if: readiness is inferred from menu presence, an existing operator
manifest, or unexercised runtime/LSP behavior.

### pi_lifecycle_apply (15 pts)

Expected: The Pi source test proves language-input gating, approved
`serena:<project-root-hash-prefix>` apply, project-scoped provision-before-bind
ordering, project-state-only write, target-client installed binding state,
`provision_status: created`, and reload-required stop.

Fail if: Pi apply skips language input, writes OpenCode config, global client
config, trust state, secrets, unmanaged registry state, or a post-install Serena
tool/LSP result.

### opencode_lifecycle_apply (15 pts)

Expected: The OpenCode source test proves approved
`serena:<project-root-hash-prefix>` apply, project-scoped provision-before-bind
ordering, project state plus project-local `opencode.json` write,
target-client installed binding state, `provision_status: created`, and
new-session-required stop.

Fail if: OpenCode apply mutates global config, live ContextForge, secrets,
ignored `.env`, trust state, skips language input, or records a post-install
Serena tool/LSP result.

### project_scoped_provisioning_boundary (20 pts)

Expected: The service record remains honest that runtime proof is still pending
after project-scoped provisioning. Source apply may model the approved
provisioning operation, but it must not claim post-refresh client visibility,
Serena runtime health, language-server installation, or LSP/index success.

Fail if: the package treats provisioning as complete runtime verification,
collapses language selection into implicit approval, or reports target-client
Serena proof from source apply alone.

### source_boundary (10 pts)

Expected: The evidence is honest that UC5k is source/docs/tests lifecycle proof
only, not a target-client dialogue pass or post-refresh tool call.

Fail if: the package claims #247, #269, Serena runtime success,
language-server/index quality, target-client post-refresh visibility, or
tool-use success.

### deterministic_boundary (15 pts)

Expected: Deterministic tests and verifier remain structural and source-level;
semantic adequacy is judged by the evaluator.

Fail if: deterministic code scores prose meaning, uses regex/string matching as
a semantic gate, or replaces the evaluator.

## Acceptance Commands

```text
run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_serena_single_service_lifecycle -v
run/test-venvs/project-init-workflow/bin/python docker/client-harness/scripts/run-use-case-5k-serena-lifecycle.py
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
- project-scoped provisioning boundary failure: repair helper/state behavior to
  preserve language-selection, provision-before-bind, and runtime-overclaim
  boundaries;
- target-client overclaim: revise state/readback wording and package criteria;
- deterministic prose gate: move checks to structured JSON and evaluator
  criteria;
- evaluator fails semantic adequacy: remediate source artifacts, rerun tests and
  source evidence package, then dispatch a new non-Spark evaluator.
