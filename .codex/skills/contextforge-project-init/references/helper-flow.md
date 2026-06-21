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

Install-only completion policy:

- Project init presents the live service menu, accepts the user's service
  selection, presents the helper-owned installation package, applies only after
  explicit approval, reports that the selected ContextForge tools are installed,
  and stops at the reload/new-session boundary.
- Do not add post-install validation, service probing, reload acknowledgement
  recording, safe-probe payloads, or target-client proof collection to ordinary
  project init.
- Tool-specific smoke checks may be diagnostic work in a separate test or
  service-ops context, but they are not part of the project-init user flow.

Reload rule:

- If the helper says a target client reload or new session is required, report
  that boundary and stop. Do not ask the user to provide low-level keys,
  challenge values, or proof values that the helper already generated.

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
