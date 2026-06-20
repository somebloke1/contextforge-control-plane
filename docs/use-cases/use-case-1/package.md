# Use Case 1 Package: Project-Local ContextForge Activation

## Status

Queue state: controller-accepted for the current branch evidence set after the
structure-not-meaning verifier rule was applied and fresh Pi/OpenCode evidence
was generated. Codex parity has now been added for the same UC1 story with a
fresh authenticated Docker runner package.

Controller state: accepted for UC1 only. Pi and OpenCode passed from virgin
client starts with structural verifier metadata and delegated semantic
evaluator narratives. Codex passed from a virgin Docker client start with
structural verifier metadata and a contained OAuth-backed Codex semantic
fallback evaluator because the subagent evaluator path hit an external
refresh-token boundary. The broader SuperLoop remains active for UC2..UCn.

## Method Binding

This package localizes the reusable method in
`holistic_orchestrated_pipeline_spec.md` and
`docker/client-harness/DIALOGUE_EVALUATION_METHOD.md`.

Durable Case 1 gate:

- `docker/client-harness/USE_CASE_1_E2E_GATE.md`

Current runner/verifier:

- `docker/client-harness/scripts/run-use-case-1-dialogue.py`
- `docker/client-harness/scripts/verify-use-case-1-e2e-evidence.py`

Current target clients:

- Pi client harness.
- OpenCode client harness.
- Codex client harness.

## Full Story

1. Start from a virgin harness workspace and a fresh non-ephemeral target-client
   container with target-client home/session state reset.
2. User sends a minimal first prompt such as `hello`.
3. Assistant presents the available ContextForge services for this project.
4. User selects `context7:canonical` with a minimal natural response such as
   `1`.
5. Assistant presents the installation package or approval request, with clear
   planned project-local effects and non-actions.
6. User approves with a minimal natural response such as `approve`.
7. Helper-owned activation applies the selected service binding.
8. Assistant replies clearly and succinctly that the selected ContextForge tools
   are installed and that a new session or reload is required before the tools
   register.
9. The flow ends.

## Terminal Boundary

The terminal boundary is installed plus reload/new-session-required. The test
must not continue into post-install validation, service probing, low-level key
challenges, reload interrogation, or presumed-working records.

## Minimal Prompt Sequence

```text
hello
1
approve
```

These prompts are intentionally sparse. Passing evidence must show the client
guidance and helper surface are sufficient without coaching tool names, payload
keys, or internal ordering.

## Deterministic Setup

Required setup for each client attempt:

```text
python3 docker/client-harness/scripts/reset-client-harness-state.py --client <pi|opencode|codex-cli> --reset-home-volume
docker compose -f docker/client-harness/compose.yml build base <client-service>
docker compose -f docker/client-harness/compose.yml run --name <fresh-name> --no-deps -d <client-service> sleep infinity
```

The runner may wrap these commands, but it must preserve the same guarantees:

- stale target-client containers removed;
- target-client home/session volume reset when requested;
- `/workspace` reset to the allowlisted virgin fixture;
- fresh non-ephemeral target-client container;
- stable session or explicit continuation chain;
- at least 90 seconds allowed for local-model responses when needed.

Codex-specific setup:

- use runner client `codex`, reset client `codex-cli`, build service
  `codex-cli`, and runtime service `codex-cli-authenticated`;
- use OAuth/ChatGPT subscription auth only through
  `contextforge-client-codex-cli:authenticated`;
- keep the default model pinned to `gpt-5.4-mini`;
- keep host API-key environment variables out of the container runtime;
- run noninteractive Codex turns with hook trust and approval bypass only inside
  the externally sandboxed Docker harness.

## Venv Contract

Host-side source checks must run in a current-worktree runtime.

Current suite runtime:

```text
run/test-venvs/project-init-workflow/bin/python
```

Observed dependencies installed there:

- `mcp`
- `mcp-contextforge-gateway`

Sibling checkout venvs are not valid acceptance evidence.

## Current Evidence

Focused deterministic suite:

```text
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_project_init_activation_workflow tests.test_superloop_agent_orchestration_skills tests.test_use_case1_e2e_gate -v
```

Observed current status:

```text
Ran 117 tests in 3.442s
OK
```

Dialogue runner evidence:

- Pi: `docker/client-harness/evidence/use-case-1/pi/pi-evaluation-package-20260620T010227Z.md`
- Pi verifier: `docker/client-harness/evidence/use-case-1/pi/pi-verifier-20260620T010227Z.json`
- Pi metadata: `docker/client-harness/evidence/use-case-1/pi/pi-metadata-20260620T010227Z.json`
- Pi combined evidence: `docker/client-harness/evidence/use-case-1/pi/pi-use-case-1-evidence-20260620T010227Z.md`
- OpenCode: `docker/client-harness/evidence/use-case-1/opencode/opencode-evaluation-package-20260620T010301Z.md`
- OpenCode verifier: `docker/client-harness/evidence/use-case-1/opencode/opencode-verifier-20260620T010301Z.json`
- OpenCode metadata: `docker/client-harness/evidence/use-case-1/opencode/opencode-metadata-20260620T010301Z.json`
- OpenCode combined evidence: `docker/client-harness/evidence/use-case-1/opencode/opencode-use-case-1-evidence-20260620T010301Z.md`
- Codex: `docker/client-harness/evidence/use-case-1/codex/codex-evaluation-package-20260620T101210Z.md`
- Codex verifier: `docker/client-harness/evidence/use-case-1/codex/codex-verifier-20260620T101210Z.json`
- Codex metadata: `docker/client-harness/evidence/use-case-1/codex/codex-metadata-20260620T101210Z.json`
- Codex combined evidence: `docker/client-harness/evidence/use-case-1/codex/codex-use-case-1-evidence-20260620T101210Z.md`
- Codex fallback semantic evaluator:
  `docker/client-harness/evidence/use-case-1/codex/codex-semantic-evaluator-fallback-20260620T101501Z.md`

All three runner outputs reported harness/package success, empty
`turn_failures`, and empty `verifier_failures`. That status is evidence only;
semantic acceptance came from the evaluator reports below.

Semantic evaluator evidence:

- Pi evaluator verdict: pass, 100/100, no fatal failures, using
  `pi-evaluation-package-20260620T010227Z.md`.
- OpenCode evaluator verdict: pass, 100/100, no fatal failures, using
  `opencode-evaluation-package-20260620T010301Z.md`.
- Codex fallback evaluator verdict: pass, 100/100, no fatal failures, using
  `codex-evaluation-package-20260620T101210Z.md`. The ordinary subagent
  evaluator path was unavailable because the subagent refresh token had been
  revoked; this fallback was run in the authenticated Codex Docker image and is
  recorded as fallback semantic evidence rather than a delegated subagent
  report.
- Controller integration report:
  `run/holistic-orchestrator/reports/uc1-controller-acceptance-20260620T010301Z.md`.
- Codex parity controller supplement:
  `run/holistic-orchestrator/reports/uc1-codex-parity-acceptance-20260620T121626Z.md`.

Residual risk:

- Both semantic evaluators noted hidden/tool result `next_turn` structures about
  reload/new-session. Controller accepts this as hidden audit state because the
  visible assistant answer stopped at installed plus reload/new-session-required
  and did not continue into reload acknowledgement, probing, or validation.
- Pi generation token usage remains zero in the captured report. This is a
  telemetry limitation, not a UC1 semantic failure.
- Live ContextForge service-menu sourcing is not claimed by UC1 acceptance.
  Deferred owner: https://github.com/somebloke1/contextforge-control-plane/issues/288.

Generation reporting requirement for future reruns:

- Every agent/model-dependent turn must have a step generation report and the
  full session must have a total generation report.
- The runner may validate command facts, artifacts, and declared structured
  output, but it must not deterministically score the semantic quality of
  free-form assistant replies unless the output is a declared structured
  artifact and the deterministic check is coupled with agent evaluation.
- The evaluator must score each generation step and the total interaction from
  the evidence package.

## Remediation History

Earlier loop entries failed because stale validation-era behavior remained in
source, prompts, tests, and client-visible helper output. High-signal retired
artifacts included:

- `Choose 1 to validate now`
- `*-client-reload-before-validation`
- validation recording helpers that have been removed from the intended Use
  Case 1 flow
- prompt/docs that still say to record validation results

The latest Pi-specific failure was a model-visible helper output leak:
`validation_plan`, validation records, and safe-probe fields entered the Pi raw
transcript even though the visible dialogue stopped correctly at the
installed/reload boundary. The Pi shim now narrows project-init tool results
before returning them to the model-visible transcript.

The latest OpenCode-specific failure was semantic: the model initially reduced
the Turn 2 plan to `Approve` or `Approve or decline?`. The OpenCode continuation
prompt now requires copying `assistant_visible_response`, and the helper returns
a narrow plan DTO with that visible response first. Whether the visible Turn 2
reply satisfies the project-local effects and non-actions story is evaluator
judgment, not deterministic verifier judgment.

## Acceptance Commands

Minimum source/package checks before client acceptance:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_use_case1_e2e_gate -v
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_project_init_activation_workflow -v
```

Client dialogue acceptance requires fresh runner/evaluator evidence for each
target client:

```text
python3 docker/client-harness/scripts/run-use-case-1-dialogue.py --client pi
python3 docker/client-harness/scripts/run-use-case-1-dialogue.py --client opencode
python3 docker/client-harness/scripts/run-use-case-1-dialogue.py --client codex
```

The runner output and verifier output are evidence only. Controller acceptance
also requires semantic review of the real transcript and scorecard.

## Remediation Routing

- stale validation/reload-before-validation assertions: update tests and source
  expectations to the install-only terminal boundary;
- direct validation helpers exposed to clients: remove or keep non-client-facing
  only if required by other non-UC1 flows and explicitly documented;
- runner/verifier mismatch: update deterministic package, then rerun;
- target client fails under `hello`, `1`, `approve`: fix prompt/guidance/helper
  surface, then rerun from virgin state;
- dependency failure: create or repair current-worktree isolated venv, then
  rerun.
