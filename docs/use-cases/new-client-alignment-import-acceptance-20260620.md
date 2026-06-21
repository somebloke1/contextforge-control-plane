# New-Client Alignment Import Acceptance - 2026-06-20

## Scope

This report records controller acceptance for #285: align a new supported
client to the existing project service set.

Accepted boundary:

- helper DTO and project-state behavior for a client with missing projection;
- approval-gated alignment/import offer from existing project services;
- explicit representation of project services that cannot currently be
  imported for the target client;
- explicit representation when all project services are unavailable, avoiding
  fallback to the generic first-run service menu;
- explicit representation of non-current target-client projections such as
  partial projection state;
- apply-path proof that the new client projection is added without duplicating
  project service identities or mutating the existing client projection;
- continuation-path proof that a natural client selection from the alignment
  offer builds the normal approval package;
- no Docker/client dialogue claim and no live registry/runtime mutation.

## Controller Judgment

Accepted locally.

When project services already exist for client A and target client B has no
projection, `list_available_capabilities()` now returns an
`alignment_import_offer` instead of the generic first-run service menu. The
offer is project-state backed, names the existing project service bindings,
marks B's projection as missing, and states that no new project service
instance should be created.

If part of the project service set is blocked or unavailable, the helper does
not silently omit it from the alignment contract. Importable services remain
available as choices, while blocked/unavailable project services are reported
under `alignment_import_offer.unavailable_project_services` with bounded
visible language explaining why they are not included in the current import
plan.

If every project service is blocked or unavailable, the helper still returns an
alignment/import readback rather than restarting generic service discovery. The
only selectable user action is `none`, and the blocked project services remain
visible with reasons. If a target client already has a non-current projection
such as `partial`, the helper represents it as repairable alignment rather than
silently treating the client as current.

The read-only availability/readback helpers remain read-only. They report
project service presence, project tool policy, and B's missing projection as
separate facts; they do not claim target-client availability for B before B is
aligned.

## Contract Change

`control_plane_project_init_helper.list_available_capabilities()` now checks
existing project state before generic discovery. If project services exist and
the queried client lacks projections for them, it returns:

- `status: alignment_import_offer`;
- `alignment_import_offer.mode: alignment_import`;
- existing `project_service_bindings`;
- missing target-client projection actions;
- `unavailable_project_services` for blocked/skipped/unavailable project
  services that are not offered as import choices;
- `non_current_target_client_projection` for repairable target-client
  projections that are present but not current;
- `available_services` shaped as import choices for the missing client;
- a `next_turn` asking whether to import the existing project services.

`contextforge_helper_mcp.client_visible_project_init_list_payload()` preserves
the alignment status, visible response, alignment offer, and target-client
projection fields needed by client adapters.

## Evidence

Worker handoff:

- agent: `codex-agent:019ee42d-fbbf-7b41-9dd1-29b5b64f6334`;
- result: partial unverified edits, no tests run;
- controller action: repaired the partial implementation locally and verified.

Controller verification:

```text
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_project_init_activation_workflow.ProjectInitActivationWorkflowTests.test_contextforge_helper_mcp_reports_missing_target_client_projection_without_available_tools tests.test_project_init_activation_workflow.ProjectInitActivationWorkflowTests.test_alignment_import_apply_records_opencode_projection_without_mutating_pi_projection -v
```

Result: 2 passed.

Final expanded focused regression:

```text
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_project_init_activation_workflow.ProjectInitActivationWorkflowTests.test_contextforge_helper_mcp_reports_missing_target_client_projection_without_available_tools tests.test_project_init_activation_workflow.ProjectInitActivationWorkflowTests.test_alignment_import_apply_records_opencode_projection_without_mutating_pi_projection tests.test_project_init_activation_workflow.ProjectInitActivationWorkflowTests.test_alignment_import_continuation_turn_builds_opencode_approval_package tests.test_project_init_activation_workflow.ProjectInitActivationWorkflowTests.test_alignment_import_offer_reports_unavailable_project_services_explicitly tests.test_project_init_activation_workflow.ProjectInitActivationWorkflowTests.test_alignment_import_offer_does_not_fall_back_to_generic_menu_when_all_project_services_unavailable tests.test_project_init_activation_workflow.ProjectInitActivationWorkflowTests.test_alignment_import_offer_represents_non_current_target_client_projection -v
```

Result: 6 passed.

```text
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_project_init_activation_workflow -v
```

Result: 110 passed.

```text
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_contextforge_docker_harness -v
```

Result: 32 passed.

```text
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python -m py_compile scripts/contextforge_helper_mcp.py scripts/control_plane_project_init_helper.py scripts/control_plane_project_state.py scripts/control_plane_contextforge_binding.py tests/test_project_init_activation_workflow.py
```

Result: pass.

```text
git diff --check -- scripts/contextforge_helper_mcp.py scripts/control_plane_project_init_helper.py tests/test_project_init_activation_workflow.py
```

Result: pass.

## Residual Risk

Non-blocking:

- This is helper/state/controller-level acceptance. It does not claim full
  Pi/OpenCode dialogue behavior for the alignment flow.
- Before UC12, UC14, or readiness handoff relies on automatic new-client
  alignment, run targeted UC9/UC10 disparity/alignment evidence through the
  normal dialogue/evaluator method.

## Boundary

This acceptance does not claim user-global client mutation, ContextForge
registry/catalog mutation, backend restart/provisioning, duplicate project
service creation, target-client visibility, interactive tool proof, or final
readiness-report completion.
