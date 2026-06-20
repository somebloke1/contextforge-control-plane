# Use Case 5i Package: GitHub Credential-Scoped Lifecycle

## Status

Queue state: selected after accepted UC1, UC2, UC3, UC4, UC7, UC5a, UC5b,
UC5c, UC5d, UC5e, UC5f, UC5g, and UC5h.

Controller state: accepted source-level lifecycle slice.

Acceptance evidence:

- Source evidence package:
  `docker/client-harness/evidence/use-case-5i/github-lifecycle/github-lifecycle-evaluation-package-20260620T034826Z.md`.
- Source evidence transcript:
  `docker/client-harness/evidence/use-case-5i/github-lifecycle/github-lifecycle-use-case-5i-evidence-20260620T034826Z.md`.
- Structural verifier:
  `docker/client-harness/evidence/use-case-5i/github-lifecycle/github-lifecycle-verifier-20260620T034826Z.json`,
  with failures `[]`.
- Non-Spark semantic evaluator Lorentz
  (`019ee322-0e0b-7892-87df-882a7b809bd6`) returned PASS, 100/100,
  with no fatal failures.

GitHub source: issue #262, "Decompose #247: github service readiness and apply
proof."

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

Downstream slices: remaining #267 and #268 per-service readiness, #269
selection-shape validation, and #247 umbrella acceptance.

## Method Binding

This package localizes the reusable method in
`holistic_orchestrated_pipeline_spec.md`,
`docs/use-cases/dependency-mesh.md`, and
`docker/client-harness/DIALOGUE_EVALUATION_METHOD.md`.

UC5i is a source/docs/tests service-lifecycle slice. It proves the
`github:canonical` project-local plan/apply/readback substrate for Pi and
OpenCode while preserving GitHub as credential scoped. The binding suffix is a
stable identifier only; the lifecycle authority is the taxonomy/instantiation
class.

It does not prove the full #247 ordinary dialogue, post-refresh target-client
visibility, live GitHub API behavior, token validity, account scope, repository
access, or mutation readiness.

## Ordering Rationale

GitHub is selected after exa-search because it is the next narrow
credential-scoped surface with a clear read-only metadata boundary. It should
be handled before broader multi-provider `web-search`; Serena remains later
because project-scoped provisioning, language selection, and LSP/index state
are more dependent.

## Full Story

1. Refresh live GitHub issue/PR context for #247, #262, #259, #260, #261, #263,
   #264, #265, #266, #270, and PR #271.
2. Preserve accepted lower-layer evidence from UC1, UC2, UC3, UC4, UC7, UC5a,
   UC5b, UC5c, UC5d, UC5e, UC5f, UC5g, and UC5h.
3. Inspect the readiness matrix row for `github` and confirm it is owned by
   #262, has taxonomy type `credential_scoped`, and carries no-mutation/no-token
   boundaries.
4. Exercise source-level single-service lifecycle tests for Pi and OpenCode
   using a current-worktree venv.
5. For Pi, approve/apply `github:canonical` through the helper and assert:
   project state is written, no `opencode.json` is written, target-client
   status is installed, lifecycle activation is shared ContextForge service,
   tool policy is read-only-if-credentials-available, no token material is
   written, and the flow stops at the Pi reload boundary.
6. For OpenCode, approve/apply `github:canonical` through the helper and assert:
   project state plus project-local `opencode.json` are written, target-client
   status is installed, lifecycle activation is shared ContextForge service,
   tool policy is read-only-if-credentials-available, no token material is
   written, and the flow stops at the new-session boundary.
7. Assemble an evaluation package with issue context, artifacts, test output,
   structural verifier output, and scorecard.
8. Dispatch a non-Spark semantic evaluator to judge whether the evidence
   satisfies #262 and safely advances toward #247 without overclaiming.

## Terminal Boundary

UC5i ends when GitHub credential-scoped project-local lifecycle/apply proof is
accepted as a sufficient prerequisite for later #247 multi-service work. It
does not accept #247, #269, remaining services, actual post-refresh
target-client tool visibility, token validity, GitHub API availability,
repository access, or mutation readiness.

## Expected Artifact Story

- The readiness matrix identifies `github` as credential scoped and routes it
  to #262.
- `server-instances/github/instance.json` preserves stable
  `service_binding: github:canonical`, while helper discovery records
  `instantiation_class: credential_scoped`.
- The source test covers both Pi and OpenCode lifecycle behavior.
- The helper mutates only approved project-local artifacts.
- Pi apply writes project state only and stops at reload-required.
- OpenCode apply writes project state plus project-local `opencode.json` and
  stops at new-session-required.
- No GitHub token, API key, OAuth value, ignored `.env`, global client config,
  live ContextForge registry state, direct GitHub API probe, or post-install
  read/mutation proof is created.
- Tool policy is read-only metadata only unless later issue work explicitly
  approves mutation.
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

Expected: Evidence includes current issue/PR readback for #247, #262, #259,
#260, #261, #263, #264, #265, #266, #270, and PR #271.

Fail if: package acceptance relies only on stale dependency-mesh text.

### readiness_matrix_binding (15 pts)

Expected: The matrix row for `github` points to #262, has taxonomy type
`credential_scoped`, and carries no-token/no-mutation/no-local-gh-proof
boundaries.

Fail if: readiness is inferred from menu presence, local `gh` auth, or the row
does not route to #262.

### pi_lifecycle_apply (15 pts)

Expected: The Pi source test proves approved `github:canonical` apply writes
only project state, records credential-scoped instantiation, records shared
ContextForge service lifecycle, marks the target-client layer installed,
preserves read-only metadata policy, and stops at reload-required.

Fail if: Pi apply writes OpenCode config, global client config, trust state,
token material, registry state, ignored `.env`, or post-install GitHub output.

### opencode_lifecycle_apply (15 pts)

Expected: The OpenCode source test proves approved `github:canonical` apply
writes project state plus project-local `opencode.json`, records
credential-scoped instantiation, preserves read-only metadata policy, marks
OpenCode binding status, and stops at new-session-required.

Fail if: OpenCode apply mutates global config, live ContextForge, token
material, ignored `.env`, trust state, issue/PR/repo state, or post-install
GitHub output.

### credential_boundary (20 pts)

Expected: The service record remains honest that runtime proof is conditional
on scoped GitHub credentials and explicit repository/request arguments. Source
apply must not copy, print, invent, commit, or validate GitHub tokens.

Fail if: the package claims GitHub account readiness, repository access,
mutation readiness, API runtime success, or target-client GitHub proof from
source apply alone.

### source_boundary (10 pts)

Expected: The evidence is honest that UC5i is source/docs/tests lifecycle proof
only, not a target-client dialogue pass or post-refresh tool call.

Fail if: the package claims #247, #269, remaining services, GitHub runtime
success, token validity, repository access, or tool-use success.

### deterministic_boundary (15 pts)

Expected: Deterministic tests and verifier remain structural and source-level;
semantic adequacy is judged by the evaluator.

Fail if: deterministic code scores prose meaning, uses regex/string matching as
a semantic gate, or replaces the evaluator.

## Acceptance Commands

```text
run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_github_single_service_lifecycle -v
run/test-venvs/project-init-workflow/bin/python docker/client-harness/scripts/run-use-case-5i-github-lifecycle.py
```

The runner produces source evidence, verifier JSON, evaluation-package
Markdown, and semantic-evaluator-ready criteria.

## Remediation Routing

- matrix row mismatch: repair `docs/contextforge-service-readiness-matrix.json`
  and rerun UC5b regression if semantics change materially;
- helper classification failure: repair manifest/discovery mapping so stable
  `github:canonical` can still be credential-scoped;
- Pi lifecycle failure: repair helper/project-state binding behavior and rerun
  source tests;
- OpenCode lifecycle failure: repair project-local config planning/apply and
  rerun source tests;
- credential boundary failure: repair service policy and source behavior to
  preserve no-token/no-runtime-overclaim boundaries;
- target-client overclaim: revise state/readback wording and package criteria;
- deterministic prose gate: move checks to structured JSON and evaluator
  criteria;
- evaluator fails semantic adequacy: remediate source artifacts, rerun tests and
  source evidence package, then dispatch a new non-Spark evaluator.
