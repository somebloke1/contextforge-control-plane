# Use Case 5l Package: Selection-Shape Validation

Issue: #269. Parent: #247.

## Scope

This package validates the source/docs/tests slice for project-init selection
shapes after all helper-offered services have per-service readiness evidence.
It proves that the helper can plan, approve, apply, and read back three
selection shapes for Pi and OpenCode:

- one service;
- a curated multi-service set spanning multiple service classes;
- all helper-offered real services.

This is not the full #247 umbrella acceptance. It does not prove post-refresh
target-client tool visibility, real target-client tool invocation, provider
credential validity, provider runtime behavior, GitHub repository access,
browser runtime behavior, remote SSH connectivity, or Serena LSP/indexing
behavior.

## Dependencies

- #270 taxonomy accepted.
- #259 readiness matrix accepted.
- #260 through #268 per-service source lifecycle slices accepted.
- Current branch contains accepted package artifacts for UC5a through UC5k.

## Target Clients

- Pi.
- OpenCode.

The slice exercises client-specific apply/readback surfaces through focused
source tests:

- Pi writes project state only and requires `/reload`.
- OpenCode writes project-local `opencode.json` plus project state and requires
  a new session.

## Full Specified Story

From a virgin project workspace:

1. The user asks the agent to activate ContextForge services for the project.
2. The helper offers the available service list.
3. The user selects one of the required selection shapes.
4. The agent requests any required service-local input before approval. In the
   all-services shape this includes Serena language input.
5. The helper returns a project-init plan covering exactly the selected real
   services and no silent omissions.
6. The user approves the plan.
7. The helper applies the plan.
8. Pi records project state only and tells the user to reload.
9. OpenCode records project-local config plus project state and tells the user
   to start a new session.
10. The project state readback contains every selected service binding, including
    the resolved project-scoped Serena binding for the all-services shape.
11. The agent reports succinct installation success and the required reload/new
    session boundary. It does not perform post-refresh tool validation in this
    slice.

## Selection Shapes

Single-service:

- `context7:canonical`

Curated multi-service:

- `context7:canonical`
- `mentality:static_repo_local`
- `ssh-tmux:session_scoped`

All services:

- `context7:canonical`
- `exa-search:credential_scoped`
- `github:canonical`
- `mentality:static_repo_local`
- `openzeppelin-solidity-contracts:canonical`
- `playwright:session_scoped`
- `ssh-tmux:session_scoped`
- `web-search:credential_scoped`
- `serena` resolved to the current workspace binding `serena:<project-hash>`

## Minimal Natural Prompt Sequence

The eventual target-client dialogue should use ordinary prompts, not coached
technical probes:

1. `hello`
2. `Set up ContextForge services for this project.`
3. For single-service: `context7`
4. For curated multi-service: `context7, mentality, and ssh-tmux`
5. For all-services: `all services`
6. If Serena language is requested: `python`
7. At plan approval: `approve`

The source-level runner for this package does not conduct target-client
dialogue. It assembles structural evidence proving the helper/source behavior
that the later target-client dialogue depends on.

## Expected User-Visible Replies

The assistant should:

- present a service-selection path without asking for low-level secret values
  already shown by the system;
- request Serena language before approval when needed;
- present a plan for exactly the selected services;
- after approval/apply, report the services installed and state the exact
  reload/new-session requirement;
- avoid claiming that tools are currently visible until a fresh session exists;
- avoid extra validation ceremony.

## Deterministic Setup Contract

- Use a current-worktree venv only.
- Use a virgin temporary workspace under the declared project-state workspace
  root.
- Do not use sibling venv substitution.
- Do not rely on residue-delta cleanup.
- Mock Serena provisioning in this source slice so no live service, systemd
  unit, registry, gateway, or host process is mutated.

## Evidence Contract

The runner must assemble:

- current GitHub issue/PR context for #247, #259, #260-#270, and PR #271;
- artifact summaries for this package, readiness matrix, taxonomy, helper,
  binding, project-state schema, and focused tests;
- focused unittest output for `tests.test_selection_shape_lifecycle`;
- structural verifier output;
- an evaluation package for non-Spark semantic scoring.

Scripts and verifiers may check structured facts only. They must not score
assistant prose meaning, target-client readiness, or #247 umbrella completion.

## Scorecard

- issue_context_refreshed: 10
- shape_coverage_single_curated_all: 20
- pi_apply_readback: 15
- opencode_apply_readback: 15
- no_silent_omissions: 20
- source_boundary: 10
- deterministic_boundary: 10

Fatal failures:

- missing any required selection shape;
- missing Pi or OpenCode coverage;
- all-services selection omits an eligible readiness-matrix service without an
  explicit blocked/non-action result;
- Serena project-scoped language/provisioning boundary is skipped or replaced
  with a live runtime claim;
- global/client-home/trust/secret/live ContextForge mutation;
- provider credential writes or exposure;
- #247 umbrella acceptance claim;
- target-client post-refresh visibility/tool-use claim;
- deterministic semantic scoring of generated prose.

## Evaluator Narrative Template

The evaluator must provide:

1. a stepwise narrative of the package and evidence reviewed;
2. a per-shape assessment for single, curated multi-service, and all-services;
3. a Pi/OpenCode boundary assessment;
4. a no-silent-omissions assessment tied to the readiness matrix;
5. an overclaim/non-action assessment;
6. a scorecard with points and rationale;
7. final PASS or FAIL for #269 source/docs/tests selection-shape validation.

## Remediation Routing

- Package missing or ambiguous: update this package and rerun.
- Helper structured behavior failure: remediate `scripts/control_plane_project_init_helper.py`
  or binding/state code, then rerun focused tests.
- Client-specific write/readback failure: remediate
  `scripts/control_plane_contextforge_binding.py` or project-state code, then
  rerun.
- Evidence/runner/verifier defect: remediate the runner/verifier without
  changing product behavior, then rerun.
- Semantic evaluator rejection: classify the rejection, remediate the smallest
  coherent source or package defect, and rerun from a virgin workspace.

## Acceptance Commands

```sh
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_selection_shape_lifecycle -v
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python docker/client-harness/scripts/run-use-case-5l-selection-shapes.py
```

Controller acceptance also requires non-Spark semantic evaluator PASS and
controller integration of the evidence.
