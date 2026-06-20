# Helper Flow Reference

Core repo files:

- `AGENTS.md`: project-wide constraints and verification policy.
- `.project/context_forge_state.json`: project-init authority when readable.
- `.codex/config.toml`: project-local Codex activation surface.
- `scripts/contextforge_helper_mcp.py`: helper MCP entrypoint.
- `scripts/control_plane_project_init_helper.py`: project-init planning logic.
- `scripts/manage_serena_project_instance.py`: Serena project-instance status and provisioning helper.
- `schemas/control-plane/project-state.schema.json`: project-state schema.

Service classes currently seen for this repo:

- Shared/canonical bindings: `context7`, `github`, `openzeppelin-solidity-contracts`.
- Hosted or scoped shared bindings: `mentality`, `playwright`, `ssh-tmux`, `web-search`, `exa-search`.
- Project-scoped provisioning: `serena` for the current repository root:
  `/home/dgk/workspace/cf-controlplane`.

Root authority:

- Treat `/home/dgk/workspace/cf-controlplane` as the only active helper,
  wrapper, client-cwd, project-state, and Serena provisioning root.
- Any copied, migration, or legacy checkout path in `.codex/config.toml`,
  `.project/context_forge_state.json`, generated prompt resources, or
  server-instance metadata is a blocker to repair, not a usable target.

Post-init service-tool checks:

- Project init does not include service probing, validation recording, or reload
  acknowledgement recording.
- The project-init endpoint is: helper-approved install/apply succeeds, then
  the assistant tells the user reload/new session is required and stops.
- Separate service-tool checks, when explicitly requested after reload/new
  session, must use only safe read/list/search operations.
- `mentality`: list or read governance entries only.
- `context7`: resolve library id or docs lookup only.
- `web-search` and `exa-search`: search/fetch-like read probes only.
- `playwright`: inert page inspection or tool listing only when semantics allow.
- `ssh-tmux`: list sessions or read existing session visibility only; opening
  sessions or sending commands needs explicit approval.
- `serena`: validate only through an approved target-client-visible policy; do
  not invent backend-only proof.

Reload rule:

- If the helper says a target client reload or new session is required, tell the
  user the selected ContextForge tools are installed and that reload/new session
  is required before the tools register, then stop.

Recovery tool routing:

- If `cf_project_init_propose` returns `status=config_conflict` and includes a
  `recovery_plan`, do not reconstruct or abbreviate that plan. Use its exact
  `approval_challenge.challenge_id` and `plan_digest` with
  `cf_project_init_recovery_approve`.
- After `cf_project_init_recovery_approve`, continue with
  `cf_project_init_recovery_apply`. This cached apply tool is the intended
  continuation for helper-owned recovery plans and cached receipts.
- `apply_project_init_recovery` is the low-level full-plan endpoint. Use it only
  when passing the complete helper-returned recovery plan object and full receipt
  objects. Passing only `plan_id`, `plan_digest`, or receipt ids is invalid
  because the helper recomputes the digest from full plan contents.
- For project-scoped Serena conflicts, recovery may include both managed wrapper
  replacement and `service_provision`; keep them together under the helper
  approval/apply path.
