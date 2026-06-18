# ContextForge Service Onboarding Helper

Issue #52 requests a stateful helper process for onboarding new MCP services
into the cf-controlplane service offering. This document records the first
source-only contract for that helper. It is not an implementation and it must
not mutate ContextForge, Docker, client, global, service, registry, systemd,
hook, trust, secret, Pi, or legacy archive state.

## Outcome

The helper should lead the operator and the model through a predictable
dialogue that turns a service idea into a reviewable integration plan. The
plan must identify sources, classify the service, assess feasibility, choose a
ContextForge integration paradigm, record approval boundaries, and describe the
implementation and lifecycle footprint before any runtime work starts.

## Dialogue States

The helper is stateful. Each session should advance through named states and
be resumable from the last recorded state:

| State | Purpose | Required evidence |
| --- | --- | --- |
| `intake` | Name the candidate service, operator goal, expected users, and initial source hints. | User statement, issue link, or discovery note. |
| `source_discovery` | Locate upstream docs, packages, repositories, executable entrypoints, config files, credential surfaces, and native transport docs. | Exact URLs, package names, commands, or local paths. |
| `feasibility_review` | Check whether the service can be registered directly, needs a package bridge/transceiver, needs a dev Docker proof, or should be deferred. | Transport facts, dependency facts, credential/state facts, and known risks. |
| `classification` | Assign typed classifications that drive implementation and approval boundaries. | `plan_type`, `localization_type`, `functional_type`, and other relevant dimensions. |
| `strategy_selection` | Select the ContextForge implementation paradigm and explain why alternatives were rejected. | Chosen strategy, rejected strategies, and evidence gaps. |
| `footprint_plan` | List source files, manifests, scripts, Docker surfaces, tests, docs, runtime state, and cleanup/rollback expectations. | Reviewable file and system surface list. |
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
- explicit runtime, global, client, Pi, registry, service, systemd, hook, trust,
  secret, and cleanup approval boundaries;
- non-actions already preserved;
- residual risks, retirement conditions, and next issue/PR steps.

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
containers, edit client config, or mutate runtime state. Resumption is explicit:
the emitted `current_state`, `next_questions`, and `source_descriptor` tell the
operator or model what evidence to add before rerunning the helper.

## Non-Mutation Default

The helper must default to source-only planning. It must not register services,
start or stop containers, mutate systemd units, write global/client config,
copy secrets, change trust state, clean registry records, or touch the legacy
`/home/dgk/workspace/legacy-controlplane-archive` checkout unless a later step has explicit
approval for that exact surface.
