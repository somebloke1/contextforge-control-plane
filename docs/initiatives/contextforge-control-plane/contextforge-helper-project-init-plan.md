# ContextForge Helper Project-Init Activation Plan

## Summary

Project initialization is driven by a preinstalled user-local MCP service named
`contextforge-helper`. Agents, including remote agents, do not write local MCP
client config, project state, server runtime files, registry entries, catalog
records, trust settings, or secrets directly. Agents call workflow tools exposed
by the helper. The helper presents services, records decisions, mints approval
challenges, consumes immutable consent receipts, applies approved project-local
changes, records state, and returns the installed/reload-required completion.

The helper is the **client-side activation authority** for a project's selected
service set. ContextForge remains the canonical authority for service identity,
hosted virtual servers, catalog descriptors, prompts, and resources. Project
state remains the project-local decision and recovery authority. Client config
is applied-state evidence; it is never service identity.

## Readiness And Bootstrap

Remote-safe activation is possible only when the local client session exposes a
trusted `contextforge-helper` tool surface to the agent. v1 does not silently
bootstrap that helper. If the helper is absent or cannot attest the local
project, the agent must stop at the local bootstrap boundary and must not fall
back to file writes.

Helper readiness states are:

- `available`: helper is callable, trusted for the local session, supports the
  requested client adapter, and attests the local project root.
- `missing`: no helper tool surface is visible.
- `stale`: helper version or protocol is below the minimum required version.
- `untrusted`: helper is visible but not trusted by the local client session.
- `wrong_project_root`: helper cannot bind the request to the active local
  project root.
- `unsupported_client`: the requested target client adapter is unavailable.
- `read_only_plan_only`: helper can inspect and plan but cannot mutate.

Only `available` may proceed to approval or apply. Every other state returns a
single `next_turn` explaining the stop condition and asking for at most one
local remediation choice. Direct writes remain forbidden.

## Remote-To-Local Invocation Model

The remote agent does not reach the filesystem directly. The local Codex/App
session brokers the user-local `contextforge-helper` MCP service into the agent
tool surface. The helper derives or confirms the canonical root from local
session context; a caller-supplied `project_root` is treated as a claim to
verify, not authority.

For every mutating workflow the helper records a local root attestation:

- canonical realpath
- project root hash
- requested display root
- client type
- helper version and protocol version
- session or caller binding when available
- root stability signal when available

Arbitrary remote paths are rejected by default. Serena and other local
project-scoped services are offered only when the helper can read and attest the
local project root that the target client will use.

## Workflow Surface

The helper exposes workflow tools aligned with the RFC control-service surface:

- `get_project_context(project_root, client_type)`
- `list_available_capabilities(project_root, client_type)`
- `propose_project_init(project_root, client_type, selected_services, inputs?)`
- `approve_project_init_plan(project_root, plan_id, approval)`
- `apply_approved_project_init(project_root, plan_id)`
- `get_project_init_job(project_root, job_id)`
- `verify_project_init(project_root, client_type, mode)`
- `inspect_subscription_drift(project_root, client_type)`
- `propose_subscription_reconciliation(project_root, client_type)`
- `apply_approved_reconciliation(project_root, plan_id)`

`apply_approved_project_init` must never mint the consent receipts that
authorize its own mutation. It consumes receipts produced by
`approve_project_init_plan`.

The normal dialogue is state-machine driven. Each helper response that requires
user input includes:

- `next_turn.question_id`
- `next_turn.prompt`
- `next_turn.choices`
- `next_turn.allowed_response_shape`
- `next_turn.must_stop = true`

The agent renders that one question, then stops. Selection, missing inputs,
approval, and conflicts are separate turns. Project init ends after apply.

## Dialogue States

1. `discover`: helper performs read-only discovery from ContextForge readback
   and `server-instances/*/instance.json`, then asks which services to activate.
2. `collect_inputs`: helper asks one required-input question at a time. Serena
   language is collected before approval and becomes part of the plan digest.
3. `present_plan`: helper returns exact effects, non-actions, stale inputs, and
   consent classes, then asks for scoped approval.
4. `apply`: helper applies only a previously approved matching plan.
5. `installed`: helper reports selected tools installed and tells the user to
   reload or start a new session so the tools register.

Config conflicts are their own one-question turn. For an unmanaged
`[mcp_servers.<alias>]` collision, the choices are: skip that service, keep the
existing block and mark activation blocked, or approve replacement only if a
future policy explicitly permits that exact local block replacement.

## Catalog And Descriptor Reality

Stock ContextForge v1 does not natively enforce signed descriptor schemas or
procedure manifests. v1 therefore treats descriptors as a control-plane
convention layered on ContextForge resources/prompts, server-instance manifests,
or another explicitly implemented catalog service.

Descriptor verification is a hard gate before approval:

- canonical JSON bytes and `sha256:` digest
- issuer allowlist and key id when signed
- validity window and catalog revision or etag
- service id, activation class, target client types
- procedure digest bound atomically to the descriptor
- no mutable network-followed refs unless the fetched bytes match the digest

`dialogue_hints` are untrusted display metadata. The helper normalizes labels
and strips imperative text; descriptor hints never override controller policy.

## Procedure And Operation Model

Procedure manifests contain typed operations. Catalog metadata may request only
operations already allowlisted by helper-owned code for the specific
`(service_id, activation_class, operation_id, plugin_version)` tuple. Catalog
manifests cannot provide arbitrary command strings.

Initial operation types:

- `collect_input`
- `call_contextforge_middleware`
- `run_helper_operation`
- `write_managed_client_config`
- `write_project_state`
- `rollback_or_reconcile`

Every operation declares expected inputs and outputs, effect class, stale input
digests, idempotency key, rollback/reconcile behavior, and redaction status.

## Client Adapter Contract

The controller owns workflow semantics, approval checks, apply jobs, project
state, and install completion. Client adapters own client-specific behavior.

Project-init client support is modeled as a registry of local-client adapters,
not as scattered branch-specific file writers. Each adapter declares:

- `client_type`
- display name
- activation surface
- project-local write paths, if any
- state-only activation behavior, if applicable
- whether stale owned config can be safely replaced
- required reload/new-session semantics
- non-actions for global config, trust, restarts, ContextForge registry/catalog,
  and secret material
- post-install reload/new-session instruction
- unsupported behavior and diagnostic-readback limits

The v1 registry covers:

| Client | Surface | Scope | Distinct local behavior |
| --- | --- | --- | --- |
| Codex | `.codex/config.toml` | project-local config | TOML managed blocks with ownership markers. |
| Gemini | `.gemini/settings.json` | project-local config | JSON `mcpServers` entries. |
| OpenCode | `opencode.json` plus user-home ContextForge plugin prerequisite | project-local service config plus global helper trigger bootstrap | JSON `mcp` entries for selected services stay project-local; the first-prompt trigger is a normal user-home OpenCode plugin. |
| Pi | global Pi extension plus `.project/context_forge_state.json` | project state | Project-init records shim metadata only; global shim install/reload is a separate approved workflow. |

Adapter capability flags include `supports_project_local_config`,
`requires_restart`, `trust_scope_model`, and `managed_config_surface`.

## Activation Classes

Shared canonical service activation binds the project-local client to an
existing ContextForge virtual server. It does not provision a backend, mutate
the registry/catalog, create systemd units, open ports, write tokens, or change
user-global trust.

Server-provisioned activation calls an explicitly implemented ContextForge
middleware or provisioner API after approval. The middleware request includes
the plan digest, helper-generated idempotency key, service allowlist, project
binding, quota/rate context, and rollback semantics. If this API is absent, v1
must mark the service blocked rather than pretending stock ContextForge can
provision it.

Client-local project-scoped activation runs a helper-owned local operation
plugin after approval. Serena uses this class in v1 because it needs direct
access to local project files. A missing local root attestation blocks Serena.

## Approval And Consent

Approval is split from apply. The helper presents an immutable plan, then mints
a local approval challenge bound to:

- plan id and canonical plan digest
- project root hash and client type
- selected services and descriptor/procedure digests
- stale input snapshots
- consent classes and persistent targets
- helper version and approval expiry
- local session or UI evidence when available

`approve_project_init_plan` consumes the user's answer and issues one or more
immutable consent receipts. One user-facing approval question may create
multiple receipts, but the receipt set must enumerate each consent class
separately, such as `project_local_config_write`, `project_state_write`, and
`service_provision`. The helper may reject a bundled approval when selected
services cross risk boundaries.

The following always require separate explicit workflows and cannot be bundled
into project init:

- user-global config changes
- user-global trust changes
- real secret values or token material
- network exposure changes
- catalog promotion or mutation

Project-local state is evidence and recovery authority, not approval authority.
A malicious checkout cannot authorize mutation by shipping fabricated
`.project/context_forge_state.json`.

## Apply Jobs And Recovery

Apply is a resumable job with a durable per-project journal. Each step records:

- job id and plan digest
- operation id and idempotency key
- pre-step state/config/catalog digests
- authorization decision and consumed consent receipt refs
- status, output digest, and redaction status
- recovery outcome

Before every mutating step the helper re-reads project state, target-client
config, catalog revision, descriptor digests, and helper operation versions.
Digest mismatches fail closed or enter `fresh_approval_required`.

Recovery states include `server_ready_local_pending`,
`forward_record_required`, `rollback_by_approved_workflow`, `manual_recovery`,
and `fresh_approval_required`. Duplicate backend instances and duplicate config
blocks are forbidden.

## Project State Contract

`.project/context_forge_state.json` records project-local decisions and recovery
state. The v1 state must include or preserve a structured activation section
with:

- immutable plan digest and stale input snapshots
- activation job id, aggregate status, and step statuses
- descriptor/procedure artifact refs or digests
- selected service bindings and activation class
- consent receipt refs by effect class
- client adapter status and local config digest
- installation status and reload/new-session requirement
- non-actions and open items

Installation completion contract:

- `cf_project_init_apply` is the terminal project-init action after approval.
- The helper returns selected service bindings, installed status, and any
  reload/new-session requirement.
- The assistant reports that the selected ContextForge tools are installed and
  that a new session or reload is required before the tools register.
- The assistant stops after reporting the installed/reload-required result.
  Stop there.

Reload state is a three-value contract, not a boolean:

- `not_required`: no project-init reload is pending for this client.
- `reload_required`: installation applied, but the current target-client session
  has not reloaded and installed tools must not be claimed callable. The user
  is told clearly that a reload or new session is required, then reminded only
  when showing intent to use a reload-dependent tool.
- `tools_registered_observed`: post-reload or new-session target-client
  readback shows the installed tools. Only this state can support claims that
  the tools are callable. No user acknowledgement is required or recorded.

Authority precedence:

- ContextForge catalog/descriptors: service identity authority.
- `.project/context_forge_state.json`: project-local decision, activation, and
  recovery authority.
- project-local client config: applied-state evidence.

Reconcile classifies `state_missing_config`, `config_without_state`,
`descriptor_stale`, `unmanaged_conflict`, and `catalog_identity_missing` with
deterministic next turns.

## Completion Boundary

Project init ends after approved apply. The helper does not ask for a
validate-now/presume-working choice, does not require a low-level reload
acknowledgement key from the user, and does not record target-client probe
results as part of the normal interaction. Runtime smoke tests may still be run
by the development harness as project evidence, but they are not user-facing
project-init turns and must not be exposed as a required post-install phase.

## Acceptance Gates

Each gate requires deterministic tests, negative cases, and evidence artifacts
before the workflow is considered complete.

| Gate | Required Evidence |
| --- | --- |
| helper-readiness | helper unavailable states stop without direct writes |
| remote-boundary | remote-agent scenario calls only helper workflow tools |
| one-turn-dialogue | each user-input response has one `next_turn` and `must_stop` |
| approval-provenance | stale/replayed/fabricated approval refs are rejected |
| consent-split | approval receipts are per effect class; forbidden global classes fail |
| catalog-realism | unsigned/stale descriptors and executable command text are rejected |
| state-job-schema | activation jobs, step statuses, digests, and installed status are schema-checked |
| installed-endpoint | project init ends after the installation package is applied |
| no-post-install-validation | agents do not ask for or run validation after apply |
| Serena-locality | missing local root/language blocks Serena before approval |
| read-only-review | review/assessment agents are audited as no file/git/service mutation |

Inference-inclusive tests must evaluate dialogue semantics, not string matches
alone: available services are offered, questions are stepwise, selected services
lead to project-local bindings only, agents do not install/restart/register
unnecessarily, the assistant reports installed tools and the reload/new-session
requirement after apply, and client config is not treated as service identity.

## Implementation Defaults

- `contextforge-helper` is new local control-plane MCP service work, not a
  prompt-only fix and not stock ContextForge behavior.
- v1 may expose pure Python helper functions and fixture-backed CLI/MCP shims
  before full installed service packaging.
- Only `client_type = "codex"` is implemented initially.
- Shared canonical activation is the initial happy path.
- Server-provisioned services remain blocked unless an explicit provisioner API
  exists.
- Serena remains local-only and requires local root attestation plus language
  input before approval.
