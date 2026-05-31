# ContextForge Helper Project-Init Activation Plan

## Summary

Project initialization should be driven by a preinstalled user-global MCP
service named `contextforge-helper`. Agents, including remote agents, do not
write local MCP client config or server-side runtime files directly. They call
helper workflow tools. The helper orchestrates service presentation, selection,
approval, activation, local client subscription, project-state recording, and
validation.

The helper is the client-side authority for a project's subscribed service set.
ContextForge remains the canonical authority for service identity, catalog
descriptors, prompts, resources, and hosted virtual servers.

## Locked Decisions

- `contextforge-helper` orchestrates activation workflows.
- ContextForge catalog/middleware provides signed service descriptors and
  procedure manifests.
- `.project/context_forge_state.json` remains the project initialization
  authority.
- Per-client adapters localize client-specific behavior. Initially only
  `client_type = "codex"` is implemented.
- The helper controller owns dialogue flow and asks one question at a time.
- Catalog descriptors provide labels, required inputs, and service-specific
  dialogue hints.
- Validation is controller-owned and must prove target-client-visible MCP
  behavior when validation is selected.
- Broad provisioning is represented with typed helper operations only.
- Catalog procedures cannot provide arbitrary local shell commands.
- Serena remains local-only in v1 because it needs direct project file access.

## Architecture

The workflow has three authority zones:

1. Agent:
   - Presents choices and relays user decisions.
   - Calls `contextforge-helper` workflow tools.
   - Does not directly edit client config, project state, server runtime files,
     ContextForge registry entries, or trust settings.

2. Client-side `contextforge-helper`:
   - Runs on the user's machine as a user-global MCP service.
   - Canonicalizes and attests the local project root.
   - Reads signed ContextForge catalog descriptors.
   - Builds and applies approved activation plans.
   - Writes project-local client config through per-client adapters.
   - Writes `.project/context_forge_state.json`.
   - Runs local project-scoped provisioning operations such as Serena.
   - Runs or coordinates target-client-visible validation.

3. ContextForge catalog and middleware:
   - Owns canonical service identity and descriptor publication.
   - Provides signed service descriptors and procedure manifests.
   - Provides hosted service bindings and virtual server metadata.
   - Performs server-side provisioning only for services whose activation class
     explicitly requires server-side execution.

## Helper Workflow Surface

The helper should expose workflow-oriented MCP tools, not raw file-edit or
catalog CRUD tools, as the normal agent interface:

- `get_project_context(client_type, project_root)`
- `list_available_services(client_type, project_root)`
- `propose_service_activation(client_type, project_root, selected_services, inputs?)`
- `apply_activation_plan(plan_id, approval_ref)`
- `get_activation_job(job_id)`
- `validate_activation(project_root, service_bindings, mode)`
- `reconcile_project_subscriptions(client_type, project_root)`

The normal dialogue is:

1. The agent calls `list_available_services`.
2. The helper returns shared canonical services and project-scoped options.
3. The agent asks which services to activate.
4. The agent calls `propose_service_activation` with the selected services.
5. The helper returns a concrete plan with exact effects and required approval.
6. The agent asks one scoped approval question.
7. The agent calls `apply_activation_plan`.
8. The helper starts or resumes a job and returns step status.
9. After apply succeeds, the agent asks whether to validate now or presume
   working.
10. The helper validates or records presumed status.

## Catalog Descriptor Schema

Catalog descriptors should be signed or pinned by the configured ContextForge
catalog and include:

- `service_id`
- `service_family`
- `display_name`
- `activation_class`
- `client_types`
- `procedure_ref`
- `procedure_digest`
- `signature`
- `required_inputs`
- `approval_effects`
- `client_binding_intent`
- `validation_profile`
- `dialogue_hints`

`activation_class` must be explicit. Initial classes:

- `shared_canonical`: existing ContextForge-hosted virtual server. No backend
  provisioning.
- `server_provisioned`: helper calls ContextForge middleware to provision or
  reuse a server-side service instance.
- `client_local_project_scoped`: helper runs a trusted local operation plugin
  because the service needs local project files or local client state.

The descriptor is service identity and procedure metadata. It is not executable
code.

## Procedure Manifest Model

Procedure manifests contain typed operations. The helper only executes operation
types implemented and allowlisted in helper code. Catalog manifests cannot
provide arbitrary command strings.

Initial operation types:

- `collect_input`
- `call_contextforge_middleware`
- `run_helper_operation`
- `write_managed_client_config`
- `write_project_state`
- `validate_target_client_mcp`
- `record_presumed_validation`
- `rollback_or_reconcile`

Each operation must declare:

- operation id
- operation type
- inputs
- expected outputs
- approval effect class
- stale-input digests
- rollback or reconciliation behavior
- redaction status

## Client Adapter Model

The helper uses a controller/view split:

- The controller owns workflow semantics, plan construction, approval checks,
  job state, project-state updates, and validation sequencing.
- Client adapters are the localization layer for concrete MCP clients.

The initial `CodexAdapter` implements:

- `client_type = "codex"`
- rendering managed `.codex/config.toml` blocks
- detecting unmanaged `[mcp_servers.*]` conflicts
- computing local client config digests
- applying managed project-local MCP config
- checking target-client-visible MCP proof
- rendering any Codex-specific dialogue labels or restart/trust gaps

Future clients add adapters without changing controller semantics.

## Service Activation Semantics

Shared canonical service activation:

- Helper reads the descriptor from ContextForge.
- Helper plans a project-local subscription to the existing virtual server.
- Helper writes managed client config through the client adapter after approval.
- Helper records the selected binding in project state.
- No backend, registry, catalog, systemd, port, token, or user-global trust
  mutation occurs.

Server-provisioned activation:

- Helper reads the descriptor and procedure manifest.
- Helper requests server-side provisioning through ContextForge middleware after
  approval.
- Middleware provisions or reuses the server-side service instance.
- Middleware returns canonical binding and virtual server metadata.
- Helper writes local client subscription and project state.

Client-local project-scoped activation:

- Helper reads the descriptor and procedure manifest.
- Helper runs an allowlisted local operation plugin after approval.
- Helper writes local client subscription and project state.
- Serena uses this path in v1.

## Serena V1 Behavior

Serena remains `client_local_project_scoped` in v1.

Reason: Serena needs direct access to local project files, language state, and
workspace lifecycle. A server-side Serena instance without a project-file bridge
does not satisfy that requirement.

The catalog may advertise Serena as a project-scoped option and provide:

- display labels
- required language inputs
- validation profile
- local operation plugin id
- client binding intent

The catalog must not provide shell commands for Serena. The helper invokes a
trusted local Serena operation plugin implemented with helper-owned code.

## Approval Model

One scoped approval may authorize an exact activation plan when the plan lists
all effects. That approval may cover:

- server-side provisioning through ContextForge middleware
- local project-scoped provisioning through helper operation plugins
- project-local client config writes
- `.project/context_forge_state.json` writes

The following always require separate explicit approvals and cannot be bundled
into project init:

- user-global config changes
- user-global trust changes
- token material changes
- secret value writes
- remote or network exposure
- catalog mutation outside signed descriptor consumption

Approval records must include:

- plan id
- selected service bindings
- client type
- project root hash
- descriptor and procedure digests
- exact write/provision effect classes
- non-actions

## Apply Job Model

Activation apply is a resumable job workflow.

`apply_activation_plan` starts or resumes a job and returns:

- job id
- plan id
- current status
- completed steps
- pending steps
- failed steps
- reconciliation hints
- next required user action, if any

The helper must be able to resume safely after interruption. A repeated apply
call with the same approved plan must not duplicate backend instances, duplicate
config blocks, or lose project-state evidence.

## Project State

`.project/context_forge_state.json` records:

- selected service bindings
- service activation class
- descriptor and procedure digests
- activation job id and step statuses
- client type
- client adapter status
- local client config digest
- validation mode and validation result
- non-actions
- skipped validation reasons
- open items

Helper-local cache is permitted for performance, but it is not authoritative.
Reconciliation must use project state and current client/catalog readback.

## Validation

Validation is controller-owned. Catalog descriptors provide safe validation
metadata, but the helper decides how to prove target-client-visible behavior
through the client adapter.

Validation defaults:

- Use read/list/search-like operations only.
- Never call mutating service tools during default validation.
- Do not mark target-client verification passed from backend health alone.
- If a safe probe cannot run because credentials or semantics are missing,
  record validation skipped with reason.

Codex validation must prove the selected service is visible through the Codex
target-client MCP path.

## Tests

Deterministic tests:

- signed descriptor validation rejects unsigned or stale descriptors
- procedure validation rejects arbitrary commands
- helper refuses unknown operation types
- Codex adapter renders only managed project-local config blocks
- unmanaged Codex MCP block conflicts block apply
- one scoped approval covers only exact listed effects
- separate approval classes cannot be bundled
- Serena descriptor uses `client_local_project_scoped`
- shared canonical descriptor never provisions a backend
- apply jobs resume after partial completion
- reconcile uses project state as authority

Integration or fixture-backed tests:

- fake ContextForge middleware returns a server-provisioned binding
- fake Codex adapter proves target-client-visible validation
- Serena local operation plugin is invoked by helper operation id, not catalog
  command text
- remote-agent scenario calls helper workflow and never writes files directly

Inference-inclusive tests:

- remote agent selects services and calls helper workflows
- agent asks one question at a time
- agent distinguishes shared canonical, server-provisioned, and client-local
  project-scoped services
- agent does not treat catalog descriptors as executable shell
- agent does not claim validation success without target-client proof

## Implementation Defaults

- `contextforge-helper` and the Codex hook are presupposed installed for this
  plan.
- Only `client_type = "codex"` is implemented initially.
- ContextForge middleware is the server-side extension point for
  server-provisioned services.
- Serena remains local-only in v1.
- Catalog descriptors and procedure manifests must be signed or pinned before
  helper execution.
