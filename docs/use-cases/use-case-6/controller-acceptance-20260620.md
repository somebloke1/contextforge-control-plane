# Use Case 6 Controller Acceptance - 2026-06-20

## Scope

Use Case 6 covers the ordinary negative-choice path for project-init service
offers:

- user declines an offered shared service;
- user defers a project-scoped service;
- the client confirms the local decision, performs no active import, and keeps
  the project usable with available capabilities;
- the decision remains visible in project-local readback.

Target clients accepted in this cycle:

- Pi
- OpenCode
- Codex

## Controller Judgment

Accepted.

Controller acceptance is based on full CLI dialogue evidence, structured state
readback, non-deterministic semantic evaluation by a non-Spark evaluator, and
post-remediation local tests. Deterministic checks were limited to structure and
state shape; generated prose meaning was not scored by string or regex matching.

## Dialogue Evidence

- Pi decline:
  `docker/client-harness/evidence/use-case-6/decline/pi/pi-decline-use-case-6-evidence-20260620T055555Z.md`
- OpenCode decline:
  `docker/client-harness/evidence/use-case-6/decline/opencode/opencode-decline-use-case-6-evidence-20260620T055638Z.md`
- Pi defer:
  `docker/client-harness/evidence/use-case-6/defer/pi/pi-defer-use-case-6-evidence-20260620T055741Z.md`
- OpenCode defer:
  `docker/client-harness/evidence/use-case-6/defer/opencode/opencode-defer-use-case-6-evidence-20260620T055821Z.md`
- Codex decline:
  `docker/client-harness/evidence/use-case-6/decline/codex/codex-decline-use-case-6-evidence-20260620T183802Z.md`
- Codex defer:
  `docker/client-harness/evidence/use-case-6/defer/codex/codex-defer-use-case-6-evidence-20260620T183848Z.md`

Each run used a clean client reset, virgin workspace state, a non-ephemeral
client container, minimal natural-language prompts, stepwise generation
reporting, final generation reporting, structured readback, and an evaluator
package.

## Semantic Evaluation

Evaluator agent `019ee39d-38b2-7243-8ebd-20ecda3e573e` reviewed all four
packages as semantic evidence only. Verdicts:

- Pi decline: PASS, 100/100, no fatal failures.
- OpenCode decline: PASS, 100/100, no fatal failures.
- Pi defer: PASS, 100/100, no fatal failures.
- OpenCode defer: PASS, 100/100, no fatal failures.

The evaluator found no package, runner, verifier, client, implementation,
environment, or inconclusive failure.

Evaluator agent `019ee655-82a9-74a1-9d4a-fd1da94e2281` reviewed the fresh
Codex packages as semantic evidence only. Verdicts:

- Codex decline: PASS, 100/100, no fatal failures.
- Codex defer: PASS, 100/100, no fatal failures.

The Codex evaluator found no package, runner, verifier, client,
implementation, environment, or inconclusive failure. It treated Docker reset
and dangerous execution flags as harness evidence-generation mechanics, not as
visible assistant behavior inside the dialogue under evaluation.

## Structured State Findings

Decline shape:

- `context7:canonical` recorded as `declined`.
- no active service record exists for the declined binding.
- no target-client active import exists.
- project state is `initialized`.

Defer shape:

- `serena:<project-hash>` recorded as `deferred`.
- no active service record exists for the deferred binding.
- no target-client active import exists.
- project state is `initialized`.

## Remediation Included

- Added project-init decision persistence for declined and deferred services.
- Routed natural `decline` and `defer` continuation turns through the helper.
- Routed Codex normal-use state readback prompts to the read-only helper
  readback response instead of project-init continuation or visible preambles.
- Preserved descriptor-shaped pending input for project-scoped services.
- Exposed declined/deferred services as skipped/unavailable in readback.
- Suppressed active tool availability when a local declined/deferred/disabled
  decision exists, including malformed mixed states where an active service
  record is also present.
- Added UC6 package, runner, structural verifier wrapper, evaluator package
  generation, Codex runner/verifier support, and focused regression coverage.

## Verification

Fresh post-remediation verification:

```text
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python -m py_compile scripts/control_plane_project_state.py scripts/control_plane_project_init_helper.py scripts/contextforge_helper_mcp.py docker/client-harness/scripts/run-use-case-6-dialogue.py docker/client-harness/scripts/verify-use-case-6-e2e-evidence.py docker/client-harness/scripts/dialogue_structural_verifier.py
```

Result: pass.

```text
python3 -m py_compile scripts/codex_project_init_hook.py docker/client-harness/scripts/run-use-case-6-dialogue.py docker/client-harness/scripts/verify-use-case-6-e2e-evidence.py tests/test_project_init_scripts.py tests/test_use_case1_e2e_gate.py
```

Result: pass.

```text
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_project_init_activation_workflow.ProjectInitActivationWorkflowTests.test_declined_service_decision_blocks_active_import_and_remains_readable tests.test_project_init_activation_workflow.ProjectInitActivationWorkflowTests.test_declined_service_decision_suppresses_inconsistent_active_service_state tests.test_project_init_activation_workflow.ProjectInitActivationWorkflowTests.test_mcp_continuation_decline_records_cached_plan_decision tests.test_project_init_activation_workflow.ProjectInitActivationWorkflowTests.test_mcp_continuation_defer_records_pending_serena_decision -v
```

Result: 4 passed.

```text
run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_use_case1_e2e_gate.UseCase1E2EGateTests.test_use_case6_runner_and_verifier_support_codex tests.test_use_case1_e2e_gate.UseCase1E2EGateTests.test_use_case6_verifier_accepts_codex_structural_metadata
```

Result: 2 passed.

```text
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_project_init_activation_workflow -v
```

Result: 115 passed.

```text
run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_project_init_scripts -v
```

Result: 101 passed.

```text
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_contextforge_docker_harness -v
```

Result: 36 passed.

```text
node --check pi-extensions/contextforge-global-shim/index.ts && node --check docker/client-harness/config/opencode/plugins/contextforge-project-init.js
```

Result: pass.

## Residual Risk

No blocking residual risk for Use Case 6 acceptance. The accepted behavior is
bounded to project-local decline/defer decisions and does not claim global
suppression, service deletion, registry mutation, or permanent backend policy.
