# Cross-Client Disparity Readback Acceptance - 2026-06-20

## Scope

This report records controller acceptance for #286: representing
cross-client service disparity without overstating availability.

Accepted boundary:

- read-only helper DTOs and visible readback vocabulary;
- no client alignment/import mutation;
- no new service instance provisioning;
- no target-client proof claim from project-global service state.

## Controller Judgment

Accepted.

The helper now distinguishes project service presence from current target-client
projection/import state. A project service can be present with known tool
policy while the queried client still has no recorded projection. In that case
the service is not reported as configured/imported/available for the queried
client.

## Contract Change

`project_tool_availability()` now reports:

- `project_services`: project-global service records and their current
  target-client projection status;
- `project_tool_policies`: project-global tool-policy facts;
- `available_tools`: only tools for services with a recorded projection for
  the queried `client_type`;
- `missing_target_client_projection`: bounded recommendations to align/import
  the queried client to the existing project service instance.

`project_state_readback()` now reports:

- `project_tool_policies` separately from `imported_tools`;
- `missing_target_client_projection`;
- per-service `target_client_projection_status`,
  `target_client_visibility_status`, and `target_client_proof_status`;
- a claim-layer boundary that project tool policy alone is not target-client
  availability.

`project_capability_summary()` now derives `available_now` from target-client
projected tools rather than project-global tool policy alone.

## Disparity Case

For a fixture where `context7:canonical` exists for Pi but OpenCode has no
projection, OpenCode readback now says:

- project service: present;
- OpenCode configured/imported tools: none;
- OpenCode projection: missing / `not_recorded`;
- recommended action: align/import OpenCode to the existing project service
  instance;
- boundary: do not create a new project service instance without explicit
  approval;
- interactive proof: not claimed.

## Evidence

Worker report:

- agent: `codex-agent:019ee425-6636-7d90-871e-f1755e08db7a`;
- files changed:
  - `scripts/contextforge_helper_mcp.py`;
  - `tests/test_project_init_activation_workflow.py`.

Controller verification:

```text
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_project_init_activation_workflow -v
```

Result: 108 passed.

```text
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_contextforge_docker_harness -v
```

Result: 32 passed.

```text
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python -m py_compile scripts/contextforge_helper_mcp.py scripts/control_plane_project_state.py scripts/control_plane_project_init_helper.py
```

Result: pass.

```text
git diff --check -- scripts/contextforge_helper_mcp.py tests/test_project_init_activation_workflow.py tests/test_contextforge_docker_harness.py
```

Result: pass.

## Residual Risk

Non-blocking:

- Existing accepted UC9/UC10 evidence remains valid within its pre-aligned
  fixture boundary. After #285 alignment/import behavior is implemented,
  targeted disparity/alignment regressions should be run rather than blanket
  historical reruns.
- #286 does not implement client alignment/import. #285 remains necessary for
  the user-facing helper that aligns a missing client projection to the project
  service graph.

## Boundary

This acceptance does not claim automatic cross-client alignment, target-client
visibility, interactive tool proof, global client mutation, live ContextForge
registry mutation, duplicate service provisioning, or readiness-report
completion.
