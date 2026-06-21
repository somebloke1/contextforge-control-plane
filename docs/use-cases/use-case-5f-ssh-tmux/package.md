# Use Case 5f Package: ssh-tmux Session-Scoped Lifecycle

## Status

Queue state: selected after accepted UC1, UC2, UC3, UC4, UC7, UC5a, UC5b,
UC5c, UC5d, and UC5e.

Controller state: accepted for the current branch evidence set.

Acceptance report:
`run/holistic-orchestrator/reports/uc5f-controller-acceptance-20260620T030900Z.md`.

Accepted evidence:

The raw evidence paths below are local ignored artifacts; this package and the
linked GitHub issue/PR updates are the durable tracked summary.

- Source evidence:
  `docker/client-harness/evidence/use-case-5f/ssh-tmux-lifecycle/ssh-tmux-lifecycle-use-case-5f-evidence-20260620T031225Z.md`
- Evaluation package:
  `docker/client-harness/evidence/use-case-5f/ssh-tmux-lifecycle/ssh-tmux-lifecycle-evaluation-package-20260620T031225Z.md`
- Metadata:
  `docker/client-harness/evidence/use-case-5f/ssh-tmux-lifecycle/ssh-tmux-lifecycle-metadata-20260620T031225Z.json`
- Structural verifier:
  `docker/client-harness/evidence/use-case-5f/ssh-tmux-lifecycle/ssh-tmux-lifecycle-verifier-20260620T031225Z.json`
- Semantic evaluator: Chandrasekhar `019ee2ff-c1c0-7b43-a111-a48890048da7`,
  PASS 100/100.

GitHub source: issue #266, "Decompose #247: ssh-tmux service readiness and
apply proof."

Parent umbrella: issue #247, "Ordinary use case 05: Add a useful project
service with plan and approval."

Prerequisites:

- UC5a / #270 service localization taxonomy.
- UC5b / #259 helper-offered service readiness matrix.
- UC5c / #260 Context7 first service lifecycle proof.
- UC5d / #263 mentality repo-local/static lifecycle proof.
- UC5e / #264 OpenZeppelin shared-canonical lifecycle proof.

Downstream slices: remaining #261, #262, #265, #267, #268 per-service
readiness, #269 selection-shape validation, and #247 umbrella acceptance.
The next recommended slice is #265 / Playwright because it is the
lowest-dependency remaining service without provider credentials, while still
requiring isolated controlled fixture-page boundaries.

## Method Binding

This package localizes the reusable method in
`holistic_orchestrated_pipeline_spec.md`,
`docs/use-cases/dependency-mesh.md`, and
`docker/client-harness/DIALOGUE_EVALUATION_METHOD.md`.

UC5f is a source/docs/tests service-lifecycle slice. It proves the
`ssh-tmux:session_scoped` project-local plan/apply/readback substrate for Pi
and OpenCode. It does not prove the full #247 ordinary dialogue, post-refresh
target-client visibility, actual ssh-tmux tool invocation, remote SSH
connectivity, tmux session creation, or command execution.

## Ordering Rationale

`ssh-tmux` is selected after OpenZeppelin because it is credential-free and has
a known safe read-only session-listing policy, while still requiring stricter
session-scoped boundaries than the accepted shared-canonical and repo-local
static slices. It should precede credential-scoped and browser/runtime fixture
services because it has no provider credential, browser, or project
provisioning prerequisite.

## Full Story

1. Refresh live GitHub issue/PR context for #247, #266, #259, #260, #263, #264,
   #270, and PR #271.
2. Preserve accepted lower-layer evidence from UC1, UC2, UC3, UC4, UC7, UC5a,
   UC5b, UC5c, UC5d, and UC5e.
3. Inspect the readiness matrix row for `ssh-tmux` and confirm it is owned by
   #266, has taxonomy type `session_scoped`, and carries read-only
   list-sessions/non-mutation boundaries.
4. Exercise source-level single-service lifecycle tests for Pi and OpenCode
   using a current-worktree venv.
5. For Pi, approve/apply `ssh-tmux:session_scoped` through the helper and
   assert: project state is written, no `opencode.json` is written,
   target-client status is installed, lifecycle activation is shared
   ContextForge service, tool policy is read-only list/get existing-session
   visibility, and the flow stops at the Pi reload boundary.
6. For OpenCode, approve/apply `ssh-tmux:session_scoped` through the helper and
   assert: project state plus project-local `opencode.json` are written,
   target-client status is installed, lifecycle activation is shared
   ContextForge service, tool policy is read-only list/get existing-session
   visibility, and the flow stops at the new-session boundary.
7. Assemble an evaluation package with issue context, artifacts, test output,
   structural verifier output, and scorecard.
8. Dispatch a non-Spark semantic evaluator to judge whether the evidence
   satisfies #266 and safely advances toward #247 without overclaiming.

## Terminal Boundary

UC5f ends when ssh-tmux session-scoped project-local lifecycle/apply proof is
accepted as a sufficient prerequisite for later #247 multi-service work. It
does not accept #247, #269, remaining services, actual post-refresh
target-client tool visibility, opening SSH/tmux sessions, sending commands or
keys, reading or writing remote files, closing sessions, cleanup operations, or
local shell/tmux substitutes.

## Expected Artifact Story

- The readiness matrix identifies `ssh-tmux` as session scoped and routes it to
  #266.
- The source test covers both Pi and OpenCode lifecycle behavior.
- The helper mutates only approved project-local artifacts.
- Pi apply writes project state only and stops at reload-required.
- OpenCode apply writes project state plus project-local `opencode.json` and
  stops at new-session-required.
- No per-project backend, new bridge, port, systemd unit, SSH session, tmux
  session, remote command, remote file read/write, cleanup, or close operation
  is created.
- Tool policy is read-only existing-session visibility only: `list-sessions`
  and `get-snapshot`.
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

Expected: Evidence includes current issue/PR readback for #247, #266, #259,
#260, #263, #264, #270, and PR #271.

Fail if: package acceptance relies only on stale dependency-mesh text.

### readiness_matrix_binding (15 pts)

Expected: The matrix row for `ssh-tmux` points to #266, has taxonomy type
`session_scoped`, and carries no-open/no-send/no-remote-mutation non-actions.

Fail if: readiness is inferred from menu presence alone or the row does not
route to #266.

### pi_lifecycle_apply (20 pts)

Expected: The Pi source test proves approved `ssh-tmux:session_scoped` apply
writes only project state, records shared ContextForge service lifecycle,
marks the target-client layer installed, preserves read-only list/get policy,
and stops at reload-required.

Fail if: Pi apply writes OpenCode config, global client config, trust state,
secrets, registry state, opens sessions, sends commands, or records a
post-install probe result.

### opencode_lifecycle_apply (20 pts)

Expected: The OpenCode source test proves approved `ssh-tmux:session_scoped`
apply writes project state plus project-local `opencode.json`, records shared
lifecycle activation, preserves read-only list/get policy, marks OpenCode
binding status, and stops at new-session-required.

Fail if: OpenCode apply mutates global config, live ContextForge, secrets,
trust state, opens sessions, sends commands, or records a post-install probe
result.

### session_scope_boundary (15 pts)

Expected: The service record remains honest that ssh-tmux is scoped by explicit
session and remote target arguments, not project ownership, and that ordinary
readiness permits only existing-session visibility.

Fail if: the package claims durable project ownership of live SSH/tmux
sessions or treats shell/tmux/backend inspection as service proof.

### source_boundary (10 pts)

Expected: The evidence is honest that UC5f is source/docs/tests lifecycle proof
only, not a target-client dialogue pass or post-refresh tool call.

Fail if: the package claims #247, #269, remaining services, remote SSH
connectivity, or tool-use success.

### deterministic_boundary (10 pts)

Expected: Deterministic tests and verifier remain structural and source-level;
semantic adequacy is judged by the evaluator.

Fail if: deterministic code scores prose meaning, uses regex/string matching as
a semantic gate, or replaces the evaluator.

## Acceptance Commands

```text
run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_ssh_tmux_single_service_lifecycle -v
run/test-venvs/project-init-workflow/bin/python docker/client-harness/scripts/run-use-case-5f-ssh-tmux-lifecycle.py
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
- unsafe session boundary: repair service policy and source behavior to
  preserve no-open/no-send/no-remote-mutation boundaries;
- target-client overclaim: revise state/readback wording and package criteria;
- deterministic prose gate: move checks to structured JSON and evaluator
  criteria;
- evaluator fails semantic adequacy: remediate source artifacts, rerun tests and
  source evidence package, then dispatch a new non-Spark evaluator.
