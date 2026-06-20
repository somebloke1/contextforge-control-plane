# Use Case 5g Package: Playwright Session-Scoped Lifecycle

## Status

Queue state: selected after accepted UC1, UC2, UC3, UC4, UC7, UC5a, UC5b,
UC5c, UC5d, UC5e, and UC5f.

Controller state: accepted for the current branch evidence set.

Acceptance report:
`run/holistic-orchestrator/reports/uc5g-controller-acceptance-20260620T032000Z.md`.

Accepted evidence:

The raw evidence paths below are local ignored artifacts; this package and the
linked GitHub issue/PR updates are the durable tracked summary.

- Source evidence:
  `docker/client-harness/evidence/use-case-5g/playwright-lifecycle/playwright-lifecycle-use-case-5g-evidence-20260620T032302Z.md`
- Evaluation package:
  `docker/client-harness/evidence/use-case-5g/playwright-lifecycle/playwright-lifecycle-evaluation-package-20260620T032302Z.md`
- Metadata:
  `docker/client-harness/evidence/use-case-5g/playwright-lifecycle/playwright-lifecycle-metadata-20260620T032302Z.json`
- Structural verifier:
  `docker/client-harness/evidence/use-case-5g/playwright-lifecycle/playwright-lifecycle-verifier-20260620T032302Z.json`
- Semantic evaluator: Singer `019ee30a-53e1-7950-b205-d902e6fe3917`,
  PASS 100/100.

GitHub source: issue #265, "Decompose #247: playwright service readiness and
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

Downstream slices: remaining #261, #262, #267, #268 per-service readiness,
#269 selection-shape validation, and #247 umbrella acceptance. The next
recommended slice is #261 / exa-search because it is the narrowest remaining
credential-scoped service.

## Method Binding

This package localizes the reusable method in
`holistic_orchestrated_pipeline_spec.md`,
`docs/use-cases/dependency-mesh.md`, and
`docker/client-harness/DIALOGUE_EVALUATION_METHOD.md`.

UC5g is a source/docs/tests service-lifecycle slice. It proves the
`playwright:session_scoped` project-local plan/apply/readback substrate for Pi
and OpenCode. It does not prove the full #247 ordinary dialogue, post-refresh
target-client visibility, actual browser tool invocation, arbitrary browsing,
screenshot behavior, code execution, or fixture-page runtime proof.

## Ordering Rationale

`playwright` is selected after ssh-tmux because it is the lowest-dependency
remaining service without provider credentials. It still carries browser
runtime risk, so proof must be constrained to isolated controlled fixture-page
semantics and must not exercise arbitrary browsing, screenshots of unknown
pages, unsafe code execution, or host browser/global config mutation.

## Full Story

1. Refresh live GitHub issue/PR context for #247, #265, #259, #260, #263, #264,
   #266, #270, and PR #271.
2. Preserve accepted lower-layer evidence from UC1, UC2, UC3, UC4, UC7, UC5a,
   UC5b, UC5c, UC5d, UC5e, and UC5f.
3. Inspect the readiness matrix row for `playwright` and confirm it is owned by
   #265, has taxonomy type `session_scoped`, and carries controlled
   fixture-page/no-arbitrary-browser boundaries.
4. Exercise source-level single-service lifecycle tests for Pi and OpenCode
   using a current-worktree venv.
5. For Pi, approve/apply `playwright:session_scoped` through the helper and
   assert: project state is written, no `opencode.json` is written,
   target-client status is installed, lifecycle activation is shared
   ContextForge service, tool policy is conditional read-only list/snapshot
   only, and the flow stops at the Pi reload boundary.
6. For OpenCode, approve/apply `playwright:session_scoped` through the helper
   and assert: project state plus project-local `opencode.json` are written,
   target-client status is installed, lifecycle activation is shared
   ContextForge service, tool policy is conditional read-only list/snapshot
   only, and the flow stops at the new-session boundary.
7. Assemble an evaluation package with issue context, artifacts, test output,
   structural verifier output, and scorecard.
8. Dispatch a non-Spark semantic evaluator to judge whether the evidence
   satisfies #265 and safely advances toward #247 without overclaiming.

## Terminal Boundary

UC5g ends when Playwright session-scoped project-local lifecycle/apply proof is
accepted as a sufficient prerequisite for later #247 multi-service work. It
does not accept #247, #269, remaining services, actual post-refresh
target-client tool visibility, browser navigation, screenshots, arbitrary page
inspection, unsafe code execution, or fixture-page runtime proof.

## Expected Artifact Story

- The readiness matrix identifies `playwright` as session scoped and routes it
  to #265.
- The source test covers both Pi and OpenCode lifecycle behavior.
- The helper mutates only approved project-local artifacts.
- Pi apply writes project state only and stops at reload-required.
- OpenCode apply writes project state plus project-local `opencode.json` and
  stops at new-session-required.
- No per-project backend, new bridge, port, systemd unit, browser state, host
  browser config, arbitrary URL navigation, screenshot, or unsafe code
  execution is created.
- Tool policy remains conditional: list tools or inspect an inert controlled
  fixture page only when a later runtime slice explicitly performs that proof.
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

Expected: Evidence includes current issue/PR readback for #247, #265, #259,
#260, #263, #264, #266, #270, and PR #271.

Fail if: package acceptance relies only on stale dependency-mesh text.

### readiness_matrix_binding (15 pts)

Expected: The matrix row for `playwright` points to #265, has taxonomy type
`session_scoped`, and carries no-arbitrary-browsing/no-unsafe-code/no-host-
browser-config non-actions.

Fail if: readiness is inferred from menu presence alone or the row does not
route to #265.

### pi_lifecycle_apply (20 pts)

Expected: The Pi source test proves approved `playwright:session_scoped` apply
writes only project state, records shared ContextForge service lifecycle,
marks the target-client layer installed, preserves conditional list/snapshot
policy, and stops at reload-required.

Fail if: Pi apply writes OpenCode config, global client config, trust state,
secrets, registry state, host browser config, browser runtime state, or a
post-install probe result.

### opencode_lifecycle_apply (20 pts)

Expected: The OpenCode source test proves approved `playwright:session_scoped`
apply writes project state plus project-local `opencode.json`, records shared
lifecycle activation, preserves conditional list/snapshot policy, marks
OpenCode binding status, and stops at new-session-required.

Fail if: OpenCode apply mutates global config, live ContextForge, secrets,
trust state, host browser config, browser runtime state, or a post-install
probe result.

### controlled_fixture_boundary (15 pts)

Expected: The service record remains honest that Playwright runtime proof is
conditional and must use an isolated controlled fixture page in a later slice.

Fail if: the package claims arbitrary browsing, screenshots, unsafe code
execution, host browser state mutation, or runtime page proof from source
apply alone.

### source_boundary (10 pts)

Expected: The evidence is honest that UC5g is source/docs/tests lifecycle proof
only, not a target-client dialogue pass or post-refresh tool call.

Fail if: the package claims #247, #269, remaining services, browser runtime
success, fixture-page proof, or tool-use success.

### deterministic_boundary (10 pts)

Expected: Deterministic tests and verifier remain structural and source-level;
semantic adequacy is judged by the evaluator.

Fail if: deterministic code scores prose meaning, uses regex/string matching as
a semantic gate, or replaces the evaluator.

## Acceptance Commands

```text
run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_playwright_single_service_lifecycle -v
run/test-venvs/project-init-workflow/bin/python docker/client-harness/scripts/run-use-case-5g-playwright-lifecycle.py
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
- unsafe browser boundary: repair service policy and source behavior to
  preserve no-arbitrary-browsing/no-unsafe-code/no-host-browser-state
  boundaries;
- target-client overclaim: revise state/readback wording and package criteria;
- deterministic prose gate: move checks to structured JSON and evaluator
  criteria;
- evaluator fails semantic adequacy: remediate source artifacts, rerun tests and
  source evidence package, then dispatch a new non-Spark evaluator.
