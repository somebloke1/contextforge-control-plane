# Evidence And Tests

Primary docs:

- `docs/initiatives/contextforge-control-plane/design-rfc.md`
- `docs/initiatives/contextforge-control-plane/implementation-runbook.md`
- `docs/initiatives/contextforge-control-plane/acceptance-checklist.md`
- `docs/initiatives/contextforge-control-plane/release-readiness-report.md`
- `docs/initiatives/contextforge-control-plane/pi-global-extension-project-init-agent-prompt.md`

Control-plane script families:

- Project init and state: `control_plane_project_state.py`,
  `control_plane_project_init_helper.py`, `project_init_common.py`.
- Service contracts and planning: `control_plane_service_classifier.py`,
  `control_plane_service_provision.py`, `control_plane_service_management.py`,
  `control_plane_contextforge_binding.py`.
- Safety gates: `control_plane_authorization.py`,
  `control_plane_trust_broker.py`, `control_plane_auth_profiles.py`,
  `control_plane_auth_wrappers.py`, `control_plane_redaction.py`,
  `control_plane_remote_exposure.py`, `control_plane_tool_policy.py`.
- Verification/evidence: `control_plane_verification.py`,
  `control_plane_mvs_scenarios.py`, `control_plane_test_harness.py`,
  `control_plane_inference_harness.py`.
- Pi shim: `manage_pi_global_shim.py`, `pi_project_init_helper_cli.py`,
  `pi_contextforge_shim_dry_run.py`, and `pi-extensions/contextforge-global-shim/`.

Current MVS status:

- Wave 12 deterministic and inference evidence exists under ignored `run/`
  paths and is indexed by the runbook/checklist.
- D17 remains pending until full W12 QA and root adjudication pass.
- D18 remains pending for Wave 13 release-readiness work.
- No artifact should claim live ContextForge/systemd/client endpoint proof
  unless a current probe or cited evidence artifact actually proves it.

Fixture discipline:

- Add or update `tests/fixtures/control_plane_*_cases.json` when changing
  contract behavior.
- Keep malicious metadata, redaction, disabled/no-service, sticky-decline,
  trust, remote-exposure, and service-management handoff cases intact unless the
  acceptance criteria explicitly change.
