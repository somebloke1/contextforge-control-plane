# ContextForge Service Onboarding Helper

Issue #52 requests a stateful helper process for onboarding new MCP services
into the cf-controlplane service offering. This document records the source-only
contract and current deterministic record/resume CLI for that helper. It is not
a runtime daemon or live service implementation. Its durable session storage is
opt-in and limited to project-local ignored files under `run/`; it must not
mutate ContextForge, Docker, client, global, service, registry, systemd, hook,
trust, secret, Pi, or legacy archive state.

## Outcome

The helper should lead the operator and the model through a predictable
dialogue that turns a service idea into a reviewable integration plan. The
plan must identify sources, classify the service, assess feasibility, choose a
ContextForge integration paradigm, record approval boundaries, and describe the
implementation and lifecycle footprint before any runtime work starts.

The broader onboarding process may begin with very little input: a source lead.
An upstream documentation URL or GitHub repository URL is preferred, but package
names, local paths, issue references, documentation phrases, and other concrete
leads are acceptable. A read-only research agent or tool pass should turn those
leads into source evidence, transport facts, credential/state boundaries, likely
tool families, and a draft compact abstract service spec before the
deterministic helper packages the record. The helper remains a no-mutation
record builder; it does not browse, register, run, or probe services by itself.

The initial generic onboarding how-to is a helper-delivered product surface,
not a client-local harness prompt. The helper loads it from
`CONTEXTFORGE_SERVICE_ONBOARDING_HOW_TO_URL`, or the repository default URL when
that variable is unset, and client adapters should inject the text as hidden
agent context where the client supports hidden prompts. User-visible helper
responses must not include the how-to text, and ordinary onboarding use must not
publish or upsert that prompt on every run.

## Dialogue States

The helper is stateful. Each session should advance through named states and
be resumable from the last recorded state:

| State | Purpose | Required evidence |
| --- | --- | --- |
| `intake` | Name the candidate service, operator goal, expected users, and initial source hints. | User statement, issue link, or discovery note. |
| `research_plan` | If only source leads are available, describe the read-only research pass needed before deterministic onboarding can complete. | Seed leads, allowed read-only actions, and required evidence outputs. |
| `source_discovery` | Locate upstream docs, packages, repositories, executable entrypoints, config files, credential surfaces, and native transport docs. | Exact URLs, package names, commands, or local paths. |
| `feasibility_review` | Check whether the service can be registered directly, needs a package bridge/transceiver, needs a dev Docker proof, or should be deferred. | Transport facts, dependency facts, credential/state facts, and known risks. |
| `classification` | Assign typed classifications that drive implementation and approval boundaries. | `plan_type`, `localization_type`, `functional_type`, and other relevant dimensions. |
| `strategy_selection` | Select the ContextForge implementation paradigm and explain why alternatives were rejected. | Chosen strategy, rejected strategies, and evidence gaps. |
| `footprint_plan` | List source files, manifests, scripts, Docker surfaces, tests, docs, runtime state, backend home, and cleanup/rollback expectations. | Reviewable file and system surface list. |
| `guidance_plan` | Generate or carry the compact service abstract spec and its ContextForge publication target. | Draft or reviewed abstract spec plus `contextforge://service-specs/<service>/abstract/v1` resource URI. |
| `approval_gate` | Stop before any runtime/global/live mutation and emit exact approval text when required. | Required approvals and non-actions. |
| `handoff` | Produce durable issue/PR-ready output with residual risks and next steps. | Structured onboarding record and GitHub links. |

## Classification Dimensions

The helper should always ask enough questions to populate these dimensions.
Unknown values are acceptable only when paired with the next evidence step.

### `plan_type`

- `read_only_audit`
- `source_only_scaffolding`
- `dev_docker_proof`
- `runtime_registration`
- `client_validation`
- `cleanup_migration`
- `compatibility_decision`
- `release_hardening`

### `localization_type`

- `shared_canonical`
- `credential_scoped`
- `user_scoped`
- `project_scoped`
- `client_local_session_scoped`
- `remote_native_hosted`
- `dev_only`
- `gateway_integrated_exception`

### `functional_type`

- `code_intelligence`
- `search_retrieval`
- `browser_automation`
- `governance_memory`
- `shell_process_control`
- `filesystem_content`
- `remote_api_tool`
- `client_adapter`
- `model_inference`
- `observability_diagnostics`
- `service_management`
- `time_timezone`

### `transport_type`

- `stdio`
- `sse`
- `streamable_http`
- `rest_openapi`
- `native_hosted`
- `bridge_required`
- `mixed`

### `state_type`

- `stateless`
- `local_filesystem_state`
- `project_metadata`
- `credential_state`
- `cache_index_state`
- `registry_state`
- `runtime_evidence_state`

### `approval_type`

- `source_only`
- `local_ignored_state`
- `docker_dev_surface`
- `contextforge_dev_registry`
- `live_runtime_service`
- `global_config_client_install`
- `pi_client_mutation`
- `destructive_cleanup`

## Integration Paradigms

The helper should map each candidate service to one primary paradigm and any
secondary validation paradigms:

| Paradigm | Use when | Default boundary |
| --- | --- | --- |
| Direct native registration | The backend already exposes validated SSE or streamable HTTP. | Register native endpoints through ContextForge only after approval. |
| Package-provided bridge/transceiver | The backend is stdio-only, SSE-only, or HTTP-only and needs a missing transport exposed. | Run the transceiver beside the backend, not inside the gateway image by default. |
| Managed npm-stdio host | The service is an npm-published MCP server with stdio transport and no service-specific host isolation requirement. | One shared Docker service owns npm package install/run/bridge lifecycle; helper CRUD manages per-service records and transparently registers exposed endpoints in ContextForge. |
| Dev Docker sidecar | The service needs repeatable isolated development validation before live registration. | ContextForge dev Docker surface only. |
| Project-scoped backend | The service reads or writes project-local state such as source files, project metadata, code indexes, or language-server state. | One backend or transceiver per project. |
| Credential-scoped backend | The service cannot safely multiplex credentials or account-local state. | One backend or transceiver per credential or user boundary. |
| Client-local or session-scoped backend | The service depends on client-local/session state and runtime behavior materially differs per client/session. | One backend or transceiver per client-local state boundary when required. |
| Gateway-image exception | A backend-local container or host transceiver is insufficient. | Deferred until explicitly justified and approved. |

## Required Onboarding Record

Each completed helper session should emit a structured record with:

- candidate service name and operator goal;
- source evidence and unresolved source questions;
- selected classifications;
- feasibility verdict and confidence;
- chosen integration paradigm and rejected alternatives;
- proposed `server-instances/<service-slug>/` home or documented equivalent;
- expected transports, endpoints, and bridge/transceiver needs;
- required files, scripts, docs, tests, fixtures, Docker surfaces, and generated artifacts;
- `guidance_plan.abstract_service_spec`, generated from the descriptor when no
  reviewed spec is supplied, with the intended ContextForge resource URI and
  publication requirement;
- explicit runtime, global, client, Pi, registry, service, systemd, hook, trust,
  secret, and cleanup approval boundaries;
- non-actions already preserved;
- residual risks, retirement conditions, and next issue/PR steps.

## Pre-Runtime Workflow Gate

Every onboarding record includes a compact `pre_runtime_workflow_gate` before
any runtime work. The gate is source-only and always records
`runtime_work_allowed: false`. It summarizes:

- known and missing dimensions for source evidence, canonical service identity,
  scope/locality, transport, credential boundary, state footprint, approval
  boundary, validation-probe plan, and abstract service spec generation;
- required pre-runtime evidence for each dimension;
- planned validation probe layers such as native transport contract readback,
  bridge transport smoke plan, credential scope negative readback, client session scope probe,
  state footprint readback, approval-scoped runtime readback, and generated
  artifact review;
- stable blockers and questions for missing source, scope, transport,
  credential, state, approval, or probe-plan evidence.

The gate only plans probes. It does not call ContextForge, start services, run Docker,
mutate registries, write client/global config, or execute validation commands.
Runtime registration or client readiness remains incomplete until the compact
abstract service spec is published as a ContextForge resource and associated
with the service. Clients then load that abstract spec proactively and load
detailed tool guidance only when a specific task requires it.

## Managed npm-stdio Host Target

The current first implementation target is a single Docker service that hosts
npm-published stdio MCP services centrally. The helper should treat this as the
default path when source or MCP Registry metadata shows:

- `packages[].registryType == "npm"`;
- `packages[].transport.type == "stdio"`;
- package identity, version or version policy, runtime hint, command
  arguments, and required environment variables are known or explicitly marked
  as questions.

The helper owns CRUD for these hosted service records, including onboarding,
update, disable, delete, and readback. A CRUD operation must also plan or carry
the corresponding ContextForge registration changes: gateway registration or
update, gateway tool refresh/readback, virtual-server creation or update, and
rollback targets. The helper must not imply that the stock ContextForge API
installs npm packages directly. ContextForge registers reachable HTTP/SSE or
streamable-HTTP endpoints; the shared Docker host is the runtime substrate that
installs/runs npm stdio packages and bridges them into ContextForge-consumable
endpoints.

Per-service onboarding should normally emit a managed npm-stdio service record
plus a ContextForge API JSON plan. A Dockerfile is required for the reusable
host substrate itself, not for every npm service hosted by that substrate.

The helper is a gate, not the researcher. It may remind the code assistant
which fields are required and why they matter, but it must not perform source
research on the assistant's behalf during install/register packaging. Before
onboarding, the assistant must supply source-derived values for the exact npm
package, package registry type, version policy, transport, package/runtime
arguments, environment variables, required secret names, tool schemas, and
prompt-library content. The standard prompt-library content is mandatory:
one compact abstract prompt for proactive loading and one or more lazy-loaded
detail prompts for specific use guidance.

If a hosted install, start, bridge, ContextForge registration, tool refresh, or
virtual-server association fails, the helper should return the observed or
sanitized error and the failed stage. It must not tell the assistant which
service-specific package argument, env var, tool schema, or prompt content to
change. The assistant remains responsible for researching and determining the
correction, then resubmitting a complete field set.

All hosted-service CRUD must be idempotent. Repeating create/update/delete with
the same target record must converge on the same state without duplicate npm
installs, duplicate bridge endpoints, duplicate ContextForge gateways, duplicate
virtual servers, or duplicate prompt-library entries. Runtime/apply must be
transactional: if any step fails after partial mutation, the executor must
cleanly uninstall/remove the partially created hosted npm service, bridge
endpoint, ContextForge gateway/tool/server associations, and prompt-library
entries before returning the error. The returned failure report must include
the failed stage, sanitized error, rollback actions attempted, rollback result,
and any residual cleanup risk.

## Source Helper CLI

The first executable helper surface is source-only:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/control_plane_service_onboarding_helper.py \
  --descriptor tests/fixtures/control_plane_service_onboarding_cases.json \
  --case serena_project_scoped_stdio_dev_docker_gate \
  --project-root /home/dgk/workspace/cf-controlplane \
  --issue '#52' \
  --pretty
```

The CLI reads a JSON descriptor and emits a deterministic onboarding record. It
does not write session state, register services, call ContextForge, start
containers, edit client config, or mutate runtime state.

## Approved Continuation Boundary

When a client transcript already contains a source-only onboarding plan and the
operator explicitly approves implementation, registration, or runtime
continuation for an uncataloged service, the project-init continuation route is
the wrong abstraction. The client should use the uncataloged-service
continuation helper instead. That helper consumes only source-derived facts
already present in the dialogue and emits a service-management handoff plus a
non-mutating catalog plan.

The continuation is still fail-closed:

- it does not call ContextForge APIs;
- it does not start, stop, build, or rebuild Docker containers;
- it does not write client or project activation config;
- it does not claim target-client-visible service availability.

Its purpose is to route the conversation from `source_ready` into the
service-management workflow without falling back to cataloged project-init
activation. Runtime provisioning, ContextForge registry mutation, reload or
new-session handling, target-client-visible list-tools, and safe calls remain
separate approved surfaces until a later generic apply path produces evidence.
Approval language such as "approve catalog promotion" or "metadata-only
promotion" for an uncataloged service remains inside this service-management
continuation boundary. It must not be interpreted as a cataloged project-init
approval, and clients must not respond by showing the existing-service
activation menu. Until a separate service-management apply surface exists, the
correct outcome is an honest plan-only boundary and a reusable generic-support
gap, not a fallback to project activation.

## Source-Only Resume Envelope

Resumption is explicit and still no-mutation. The emitted `current_state`,
`next_questions`, and `source_descriptor` tell the operator or model what
evidence to add before rerunning the helper. A later turn may pass the previous
record and an updated descriptor patch:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/control_plane_service_onboarding_helper.py \
  --descriptor updated-service-evidence.json \
  --previous-record previous-onboarding-record.json \
  --session-id svc-onboarding-example \
  --project-root /home/dgk/workspace/cf-controlplane \
  --issue '#52'
```

The helper merges the previous record's redacted `source_descriptor` with the
new descriptor and emits `dialogue_session` metadata containing:

- `session_id`;
- `turn_index`;
- `state_history`;
- `answered_questions`;
- `decision_log`;
- `storage_mode: stdout_only`;
- `write_persistence: false`.

This resume envelope makes stateful human-agent dialogue reviewable without
introducing hidden local files, daemon state, ContextForge API calls, Docker
mutation, client/global config writes, or secret handling.

## Local Ignored Session Store

The helper can optionally persist the emitted record under the project-local
ignored `run/service-onboarding-sessions/` directory:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/control_plane_service_onboarding_helper.py \
  --descriptor updated-service-evidence.json \
  --session-id svc-onboarding-example \
  --project-root /home/dgk/workspace/cf-controlplane \
  --issue '#52' \
  --save-session
```

A later turn may resume by stable session id instead of passing a previous
record path:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/control_plane_service_onboarding_helper.py \
  --descriptor updated-service-evidence.json \
  --resume-session svc-onboarding-example \
  --project-root /home/dgk/workspace/cf-controlplane \
  --issue '#52' \
  --save-session
```

When `--save-session` is present, `dialogue_session` records
`storage_mode: local_ignored_session_file`, `write_persistence: true`, and the
exact `session_record_path`. Session identifiers are restricted to safe
letters, digits, dots, underscores, and dashes, and the session directory must
resolve inside the project-local ignored `run/` tree. Without `--save-session`,
the helper remains stdout-only and does not create files.

## Session Status Readback

Saved sessions can be inspected without a descriptor and without rewriting the
session record:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/control_plane_service_onboarding_helper.py \
  --project-root /home/dgk/workspace/cf-controlplane \
  --session-status svc-onboarding-example
```

This emits a compact status summary for agent-human resumption, including:

- `session_id`, `status`, `current_state`, `turn_index`, and `state_history`;
- known and open classification dimensions;
- primary and secondary integration paradigms;
- approval requirement and required approval types;
- compact `pre_runtime_workflow_gate` state, including known/missing
  dimensions and planned validation probe layers;
- answered questions, next questions, next resume inputs, residual risks, and
  next issue/PR steps;
- `mutation_allowed: false`.

`--session-status` is read-only. It cannot be combined with descriptor input,
previous-record input, session resume input, or `--save-session`.

Saved sessions can also be listed without descriptor input and without rewriting any session record:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/control_plane_service_onboarding_helper.py \
  --project-root /home/dgk/workspace/cf-controlplane \
  --list-sessions
```

`--list-sessions` returns a deterministic `service_onboarding_session_list`
containing compact status summaries sorted by saved session record name. An
absent session directory returns an empty list. It is read-only and cannot be
combined with descriptor input, previous-record input, session resume input,
single-session status input, or `--save-session`.

Saved sessions can also emit a read-only resume template for the next
agent-human turn:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/control_plane_service_onboarding_helper.py \
  --project-root /home/dgk/workspace/cf-controlplane \
  --session-template svc-onboarding-example
```

`--session-template` returns a deterministic
`service_onboarding_resume_template` containing compact session context, next
questions, a descriptor patch scaffold for missing source evidence,
classification values, feasibility notes, footprint fields, and missing pre-runtime gate inputs
such as credential boundary, scope boundary, state footprint, or validation probe plan,
plus rerun guidance for `--resume-session`.
It is read-only, does not rewrite the session record, and cannot be combined
with descriptor input, previous-record input, session resume input,
single-session status input, list input, or `--save-session`.

Saved sessions can also emit a sealed read-only research packet for a delegated
research agent:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/control_plane_service_onboarding_helper.py \
  --project-root /home/dgk/workspace/cf-controlplane \
  --research-packet svc-onboarding-example
```

`--research-packet` returns a deterministic
`service_onboarding_research_packet` containing:

- session context and source-level claim boundary;
- seed leads and research-agent instruction;
- allowed read-only actions and forbidden mutations;
- required evidence outputs;
- descriptor patch contract for rerunning the helper after research;
- final stepwise narrative requirement so the controller can distinguish
  research-agent execution problems from package or client behavior.

The research agent must assume the seed lead is all it knows at handoff time.
Starting from that URL, package, path, issue, phrase, or other concrete clue, it
must perform enough read-only source research to infer package identity,
executable or bridge entrypoints, native transport, tool contracts, configuration
knobs, state footprint, auth boundary, upstream tests, implementation decision
candidates, unresolved questions, and the compact abstract spec. These facts
must be cited to source evidence and returned as descriptor-ready output; the
agent must not substitute controller memory, runtime probes, registry reads, or
client behavior for source research.

The research packet is source-only. It must not be used to claim
`backend_ready`, `contextforge_ready`, `target_client_ready`, verified runtime
behavior, operator workflow success, or semantic acceptance.

This local store is for resumable planning records only. It is not a daemon,
registry, service runtime, Docker state, client installation, secret store,
hook state, or approval bypass. Long-running helper behavior and richer
session management remain later slices that need their own evidence and
approval boundaries.

## Onboarding Development Foil Ladder

Use this ordered MCP service ladder as development foils for building and
proving the onboarding process, from simplest to most complex. This is not a
canonical post-development service set. Each foil should first pass through the
source-lead research packet and deterministic onboarding record before any
runtime or target-client proof is attempted. Perfect onboarding of the current
foil before starting the next one; `time` must be completed before `fetch`
begins.

The foil output is prototype evidence for the factory method, not a service-
specific blueprint to memorize. When Time is brought from seed URL to running
ContextForge service, the controller must extract the generic operations that a
future onboarding agent needs to perform from only a seed lead: source research,
package and executable discovery, transport and bridge choice, sidecar or
equivalent runtime generation, registration script generation, direct and
virtual probe generation, target-client proof planning, evidence capture, and
claim-boundary recording. Any step that depends on controller prior knowledge
instead of source evidence becomes an onboarding-factory gap to encode before
advancing to the next foil.

A foil is not complete merely because the controller or an informed agent can
build it. Completion requires a blind semantic end-to-end onboarding trial: a
real Pi and OpenCode target-client assistants receive only the source lead and
generic onboarding support, while a separate simulated human responder answers
only questions those assistants ask. The responder must have a declared
knowledge persona, ranging from an ignorant user who asks the assistant to
decide from research to an expert user who can state detailed requirements or
preferences when asked. The trial must succeed from source research through
decision record, implementation, runtime proof, ContextForge registration
proof, target-client-visible safe use, and semantic evaluator narrative across
at least three eligible semantic-test model profiles per target client. The
trial may validate structure, command status, JSON, endpoints, and files
deterministically, but it must not evaluate generated assistant meaning through
string or regex matching. If the blind trial needs Time-specific facts that are
not discoverable from the source lead or generic supports, the foil is not
complete; the missing generic support must be encoded before moving to Fetch.

1. `time` - stateless baseline:
   <https://github.com/modelcontextprotocol/servers/tree/main/src/time>
2. `fetch` - basic network I/O:
   <https://github.com/modelcontextprotocol/servers/tree/main/src/fetch>
3. `sequentialthinking` - state persistence:
   <https://github.com/modelcontextprotocol/servers/tree/main/src/sequentialthinking>
4. `filesystem` - local security constraints:
   <https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem>
5. `sqlite` - structured data handling:
   <https://github.com/modelcontextprotocol/servers/tree/main/src/sqlite>
6. `kubernetes` - dynamic massive schemas and advanced auth:
   <https://github.com/feiskyer/mcp-kubernetes-server>
7. `docker` - system daemon mounting and external process orchestration:
   <https://github.com/ckreiling/mcp-server-docker>

Before implementation or runtime/client work for any foil, the helper must
identify key implementation decisions and present them methodically for user
approval or amendment:

- canonical service identity;
- backend home: default to `server-instances/<service-slug>/` unless a
  source-backed documented equivalent is chosen;
- transport and bridge strategy;
- scope and locality;
- state footprint;
- credential and auth boundary;
- ContextForge registration plan;
- client exposure plan;
- reset and proof strategy;
- rollback and cleanup.

## Fixture Coverage

The source helper is fixture-backed. The fixture set should grow with the
service classes that drive the roadmap, not only with happy-path examples.
Current required examples include:

- `serena_project_scoped_stdio_dev_docker_gate`: project-scoped code
  intelligence with stdio transport, Docker development-surface approval, and
  secondary stock bridge/transceiver validation.
- `serena_source_only_project_scoped_abeyant_provisioning`: source-only Serena
  record that keeps project-scoped provisioning abeyant but hard-required for
  a later approved runtime turn.
- `native_http_shared_docs_source_only`: shared canonical HTTP service that can
  produce a source-only handoff without runtime approval.
- `shared_stdio_bridge_dev_docker_gate`: shared stdio backend that must be
  fronted by a stock package bridge/transceiver before ContextForge dev Docker
  validation.
- `github_credential_scoped_registry_gate`: credential-scoped remote API tool
  binding that must preserve the account, token, installation, or tenant
  boundary before registry mutation.
- `ssh_tmux_client_session_local_bridge`: client/session-local shell-control
  service that records live session authority and client Docker validation
  without claiming durable project ownership.
- `openzeppelin_remote_native_hosted_source_only`: real tracked remote/native
  OpenZeppelin Solidity Contracts service that produces a source-only handoff
  from the tracked manifest and safe-probe contract without claiming live
  client validation, generated-code audit, deployment readiness, or registry
  state.
- `missing_evidence_prompts_questions`: incomplete intake that proves stable
  questions, explicit blockers, and redaction.

For stdio services, the helper should ask for the stock bridge/transceiver command
even when bridge validation is secondary to a project-scoped,
credential-scoped, or client/session-local primary strategy. For
credential-scoped services, it should ask which credential, account, tenant, token, or installation boundary
defines the binding. For client/session-local services, it should ask which
client-local state, live session, caller identity, or process authority defines
the binding.

Serena is modeled as a source-only project-scoped onboarding record when the
backend exists in the repository but provisioning is still abeyant. The helper
must keep that record no-mutation, name the project-scoped backend, and make it
clear that a later approved runtime turn will hard-require the same Serena
backend before live integration. The `pre_runtime_workflow_gate` preserves that
requirement with `required_before_runtime: true` on the Serena backend
provisioning readback probe.

## Non-Mutation Default

The helper must default to source-only planning. It must not register services,
start or stop containers, mutate systemd units, write global/client config,
copy secrets, change trust state, clean registry records, or touch the legacy
`/home/dgk/workspace/legacy-controlplane-archive` checkout unless a later step has explicit
approval for that exact surface.
