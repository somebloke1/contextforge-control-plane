# Use Case 5 Controller Acceptance Report

Issue: #247
Date: 2026-06-20
Controller: codex-thread:019ede5e-c2c8-72b0-8665-2effa6288d05

## Decision

Use Case 5 is accepted locally within its install-only boundary.

The accepted boundary is service menu -> natural service selection -> optional
Serena language input -> project-local plan -> explicit approval -> helper
apply -> installed plus reload/new-session boundary.

This acceptance does not claim post-refresh target-client tool visibility,
actual tool invocation, provider runtime behavior, credential validity, GitHub
repository access, mutation readiness, or Serena runtime indexing/LSP behavior.
Those remain downstream use-case surfaces.

## Current Evidence Set

Pi:

- Single: `docker/client-harness/evidence/use-case-5/single/pi/pi-single-evaluation-package-20260620T053059Z.md`
- Curated: `docker/client-harness/evidence/use-case-5/curated/pi/pi-curated-evaluation-package-20260620T053133Z.md`
- All services: `docker/client-harness/evidence/use-case-5/all/pi/pi-all-evaluation-package-20260620T052951Z.md`

OpenCode:

- Single: `docker/client-harness/evidence/use-case-5/single/opencode/opencode-single-evaluation-package-20260620T053204Z.md`
- Curated: `docker/client-harness/evidence/use-case-5/curated/opencode/opencode-curated-evaluation-package-20260620T053251Z.md`
- All services: `docker/client-harness/evidence/use-case-5/all/opencode/opencode-all-evaluation-package-20260620T053339Z.md`

Codex:

- Single: `docker/client-harness/evidence/use-case-5/single/codex/codex-single-evaluation-package-20260620T182041Z.md`
- Curated: `docker/client-harness/evidence/use-case-5/curated/codex/codex-curated-evaluation-package-20260620T182141Z.md`
- All services: `docker/client-harness/evidence/use-case-5/all/codex/codex-all-evaluation-package-20260620T181942Z.md`

Each package links its combined evidence, raw turn artifacts, metadata, and
structural verifier JSON.

## Deterministic Evidence Boundary

The structural verifier passed for all six packages with no failures. The
verifier checks artifact structure, command status, reset JSON shape,
generation-report shape, and runner contract fields. It does not judge meaning
in generated assistant prose.

Current focused source checks also passed:

- `PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_contextforge_docker_harness -v` -> 36 tests OK.
- `PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_project_init_activation_workflow -v` -> 115 tests OK.
- `PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_project_init_scripts -v` -> 99 tests OK.
- `node --check pi-extensions/contextforge-global-shim/index.ts` -> OK.

## Semantic Evaluator Evidence

Pi evaluator:

- Agent: `019ee387-223a-77e2-b767-334c53f4491d`
- Scope: Pi single, curated, and all-services packages listed above.
- Result: 100/100 PASS for all three shapes.
- Fatal failures: none found.

OpenCode evaluator:

- Agent: `019ee387-4688-73c1-9679-e6bb84fa6403`
- Scope: OpenCode single, curated, and all-services packages listed above.
- Result: 100/100 PASS for all three shapes.
- Fatal failures: none found.

Codex evaluator:

- Agent: `019ee62e-0457-7ad1-8e0b-7b4e50244ab3`
- Scope: Codex single, curated, and all-services packages listed above.
- Result: 100/100 PASS for all three shapes.
- Fatal failures: none found.

All evaluators treated verifier output as structural evidence only and supplied
non-Spark semantic judgment over the visible interaction and tool/order evidence.

## Controller Integration

The controller reviewed the evaluator outputs and current evidence summaries.

Accepted observations:

- The target-client home/session state and workspace were reset before each run.
- User prompts were minimal ordinary prompts, not helper/payload coaching.
- Pi, OpenCode, and Codex displayed the service menu before selection.
- Single-service selection installed `context7:canonical`.
- Curated selection installed `context7:canonical`,
  `mentality:static_repo_local`, and `ssh-tmux:session_scoped`.
- All-services selection installed the nine helper-offered real service
  bindings, including project-scoped `serena:4a93a92afaa7`.
- Serena language was requested before approval in all-services flows.
- Project-local plans were visible before approval and included non-actions.
- Apply happened only after explicit user approval.
- Final visible replies reported installation and reload/new-session boundary.
- No accepted run claims post-refresh tool visibility or actual tool use.

Codex-specific remediation before acceptance:

- Codex project-init continuation now records natural replies and calls
  `cf_project_init_continue` without visible helper-mechanics narration.
- Codex continuation plan payloads expose a single plan-bearing public response
  instead of also exposing a generic `next_turn` prompt that the model could
  choose over the plan.
- Serena provisioning uses the existing manifest-only no-systemd mode when
  `systemctl` is absent, which keeps Docker client testing install-only and
  idempotent.
- Public apply messages enumerate installed bindings so the final readback is
  visible without requiring post-refresh tool validation.

## Residual Risks

The final post-apply visible messages are intentionally terse. They report that
selected ContextForge tools are installed and that reload or a new session is
required, but they do not always repeat every installed service binding. The
tool/order evidence and project-state readback provide the exact installed
binding set. This is acceptable for UC5 under the current scorecard and should
not be treated as acceptance of later readback or actual-use surfaces.

The acceptance report covers #247 local controller acceptance only. PR merge,
issue closure, Project board reconciliation, post-refresh visibility, and actual
tool-use behavior remain separate controller decisions.
