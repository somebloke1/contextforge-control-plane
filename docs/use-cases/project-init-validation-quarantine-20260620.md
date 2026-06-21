# Project-Init Validation Quarantine - 2026-06-20

Controller: `codex-thread:019ede5e-c2c8-72b0-8665-2effa6288d05`

Related issues: #272, #273, #274, #275, #276, #279.

## Decision

Ordinary project init remains install-only:

1. The helper presents the current ContextForge service menu.
2. The user selects services.
3. The helper returns the installation package / approval request.
4. The user approves.
5. The helper applies project-local activation state.
6. The assistant reports that selected tools are installed and that reload or a
   new session is required.
7. The flow stops.

Post-install service validation, service probing, reload interrogation, and
safe-probe result recording are not part of ordinary project init.

## Patch

`record_project_init_client_reload` is now strictly install-only. Supplying
`validation_mode` to reload acknowledgement raises a helper error instead of
recording reload and returning a post-reload validation continuation.

This removes the remaining reload-acknowledgement path that could transform a
client reload boundary into:

- `run-target-client-validation-probes`;
- `record-presumed-working`;
- `client_reload_recorded_validation_requested`;
- `client_reload_recorded_presume_working_requested`.

The deeper validation/proof data structures are left in place for now because
existing controlled-development, service-readiness, and historical evidence
artifacts still use those names. They are not exposed as the ordinary
project-init endpoint.

## Verification

```text
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_project_init_activation_workflow.ProjectInitActivationWorkflowTests.test_client_reload_acknowledgement_rejects_validation_intent tests.test_project_init_activation_workflow.ProjectInitActivationWorkflowTests.test_client_reload_acknowledgement_rejects_presume_working_intent tests.test_project_init_activation_workflow.ProjectInitActivationWorkflowTests.test_pi_reload_acknowledgement_changes_normal_readback_contract -v
```

Result: 3 tests OK.

```text
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_project_init_activation_workflow -v
```

Result: 118 tests OK.

```text
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_project_init_scripts -v
```

Result: 104 tests OK.

```text
git diff --check
```

Result: passed.

## Residual

#272, #273, #274, #276, and #279 still name old validation-era behavior. This
patch does not claim to close every issue in that cluster. It narrows the
remaining client-invokable surface by preventing reload acknowledgement from
requesting or resuming validation. A later compatibility cleanup can rename or
remove deeper `validation_*` state fields once all accepted evidence packages
and controlled-development workflows have migrated to neutral proof terminology.
