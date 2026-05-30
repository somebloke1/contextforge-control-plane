# Design RFC: ContextForge Assistant Control Plane

Status: Decision-complete draft for implementation planning

## Purpose

Define a reviewable architecture for evolving the current ContextForge gateway
installation into a host-wide assistant control plane before implementation.

The design must preserve stock ContextForge as the registry and proxy, reduce
per-client MCP setup, and make project initialization explicit, verifiable, and
reversible where practical.

## Non-Goals

- Implement the control plane in this RFC pass.
- Replace stock ContextForge with a bespoke gateway fleet.
- Treat client configuration entries as canonical service identities.
- Silently broaden user-global client trust.
- Make v1 a full multi-user remote deployment.

## Source Context Read For This Draft

- `docs/initiatives/contextforge-control-plane/dialogue-plan.md`
- `docs/initiatives/contextforge-control-plane/refinement-process-plan.md`
- `DECISIONS.md`
- `ABEYANT_INTENTIONS.md`
- `OPEN_QUESTIONS.md`
- `scripts/register_project_init_prompt.py`
- `scripts/manage_serena_project_instance.py`
- Supporting project-init helpers inspected where needed:
  `scripts/project_init_common.py` and `scripts/codex_project_init_hook.py`
- Wave 4 incorporation artifacts under
  `generated/contextforge-control-plane-rfc-waves/run-20260530c/`

## Current Repo Baseline

The current repository already establishes several constraints that this RFC
should treat as locked unless explicitly superseded.

- ContextForge remains the stock IBM ContextForge MCP Gateway runtime.
- ContextForge registry mutation goes through ContextForge APIs or Admin UI
  behavior, not direct database writes.
- Client configs are discovery and consumption surfaces, not service identities.
- Canonical services are deduplicated by actual backend package/server, runtime
  scope, credential scope, and exposed resource scope.
- Each exposed service has a backend home under `server-instances/<service-slug>/`
  or an explicitly documented equivalent.
- Native HTTP/SSE transports are preserved; package-provided bridge support is
  used only for missing transports.
- Active local operation is user-systemd controlled.
- Direct-capable clients use authenticated loopback HTTP where proven; stdio-only
  clients use the ContextForge wrapper.
- `mentality` is the repo-local governance MCP service, backed by
  `DECISIONS.md`, `ABEYANT_INTENTIONS.md`, and `OPEN_QUESTIONS.md`.
- Serena is project-scoped, ContextForge-mediated, project-local in Codex, and
  must not be globally exposed.
- Serena project switching through `activate_project` is filtered from the
  ContextForge/Codex exposed tool list.
- Codex project trust remains a separate explicit approval boundary; the current
  flow does not silently add global trust.
- The current project-init implementation uses prompt/resource guidance and
  project `.env` keys as the v1 bootstrap state surface; the intended control
  plane direction is to move canonical project initialization state to
  `.project/context_forge_state.json`.

## Target Direction Already Locked

- Primary artifact: Design RFC.
- Starting axis: ContextForge as control plane.
- Process: Socratic decision rounds.
- Interface: one assistant-facing ContextForge MCP control service.
- Authority: ContextForge owns canonical service/resource identity; project-local
  `.project/context_forge_state.json` owns project initialization state.
- Mutation policy: approved workflows may provision services and write
  project-local config/state, but user-global client trust requires separate
  explicit approval.
- Deployment target: auth-aware local v1, designed so remote exposure is not
  boxed out.
- Resource model: core plus extensible: services, prompts/resources,
  skills/agents metadata, project state, language profiles.
- Implementation boundary: contract-driven artifacts are part of the design.
  Service binding contract cards, consent receipts, verification traces,
  conformance packs, handoffs, and requirement-linked scenarios are not
  optional reporting layers.

## Normative Design

### Authority Model

ContextForge is the host-wide authority for assistant-facing service identity:
canonical services, gateways, virtual servers, tools, prompts, resources, and
resource-backed control-plane metadata. Client configs are discovery and
consumption surfaces only.

Some control-plane concepts are represented in ContextForge as native rows, some
as ContextForge resources/prompts, and some as repo-local or external artifacts.
The authority boundary is the semantic catalog entry, not an assumption that
every concept is a native ContextForge table.

Project initialization state is project-local and lives in
`.project/context_forge_state.json`. Missing project state means
`UNINITIALIZED`. The current `.env` project-init keys are replaced immediately;
they are not a parallel authority in the control-plane design.

Project state uses stable canonical names as authority. ContextForge record IDs
may be stored only as evidence or drift-detection cache. If IDs and names
disagree, implementations must reconcile against current ContextForge API state
by canonical name before making claims.

Name reconciliation is valid only when canonical name, project root hash or
scope tag, backend manifest, and relevant ContextForge resource metadata agree.
An existing ID must never satisfy a missing canonical-name check, and duplicate
canonical names are blocking drift until repaired through approved ContextForge
API operations.

Registry mutation must use ContextForge APIs or Admin UI behavior. Direct
ContextForge database writes remain prohibited.

### Resource Taxonomy

The control plane manages or references these resource classes:

- `service_family`: stable service family identity, such as `github`,
  `web-search`, `context7`, `mentality`, or `serena`.
- `service_binding`: a concrete binding of a service family to scope,
  credentials, project, resource set, or client exposure policy.
- `service_binding_contract_card`: compact machine-readable contract for a
  concrete `service_binding`, including authority boundary, instantiation
  class, scope, consent, tool policy, client adapters, and verification matrix.
- `shared_service_capability_capsule`: project-init representation of a
  canonical shared service that can be bound or verified for a project without
  creating a per-project backend, wrapper, bridge, gateway, or server-instance
  directory.
- `backend_instance`: operational home under `server-instances/<service-slug>/`
  or an explicitly documented equivalent.
- `contextforge_gateway`: ContextForge gateway record pointing to a native or
  bridged upstream transport.
- `virtual_server`: ContextForge server exposed to clients, potentially
  project-specific.
- `client_binding`: the client-facing config/trust/restart/auth binding for a
  service or virtual server.
- `tool_policy`: exposed, excluded, scope-changing, or approval-gated tool
  metadata.
- `semantic_tool_policy`: semantic source policy compiled into ContextForge
  virtual-server associated-tool sets and negative verification checks.
- `prompt_resource_bundle`: ContextForge prompt/resource guidance associated
  with tools, services, or project-init.
- `service_management_skill`: dedicated skill/workflow used for approved
  catalog mutation.
- `service_management_handoff`: typed non-mutating object emitted when project
  init discovers a catalog candidate or needs host catalog mutation it is not
  allowed to perform.
- `project_state`: `.project/context_forge_state.json`.
- `language_profile`: supported language/tooling policy represented in
  ContextForge catalog metadata.
- `service_memory_provider`: generic capability metadata for memory-capable MCP
  services.
- `governance_registry`: durable ledgers exposed by `mentality`.
- `client_adapter_conformance_pack`: versioned evidence-backed contract for a
  client adapter's config, trust, auth, restart, wrapper, list-tools, call-tool,
  and negative-policy behavior.
- `consent_receipt`: immutable local audit record proving a granted approval
  for one consent class, scope, plan digest, and mutation target set.
- `verification_trace`: adapter-independent evidence envelope for backend,
  ContextForge, virtual-server, target-client, negative-policy, trust, and
  redaction probes.
- `requirement_scenario`: requirement-linked test fixture describing the tested
  agent's visible world, hidden initial conditions, user prompt, allowed and
  forbidden mutations, assertions, receipts, traces, and inference rubric.
- `evaluator_verdict`: structured privileged-evaluator result citing evidence
  and classifying failures without changing requirements.
- `evidence_ledger`: generated ignored run artifact linking scenario fixtures,
  transcripts, deterministic checks, consent receipts, verification traces,
  world-state diffs, evaluator verdicts, and remediation results.
- `governance_reconciliation_pack`: non-mutating generated report comparing the
  RFC, governance ledgers, open questions, abeyant intentions, and
  service-memory notes before implementation begins.

These contract artifacts may be represented as ContextForge resources,
project-state references, repo/test fixtures, or ignored run evidence depending
on the authority boundary. They describe and evidence ContextForge behavior;
they must not create a parallel registry for ContextForge-owned identity.

### Service Instantiation Classes

Every requested, discovered, or accepted service must be classified by the
narrowest authority boundary required for correct operation before project
initialization plans mutation. The classification belongs to the concrete
`service_binding`, not to a client config entry and not always to the abstract
`service_family`.

Every `service_binding` selected, accepted, surfaced, verified, or promoted by
project initialization must have a service binding contract card before any
mutation. The card is required for shared services as well as project-scoped
services because it records why project init may bind, expose, or verify the
service without owning the backend. Service Binding Contract Cards are the
common unit shared by project state, service-management plans, control-service
outputs, client adapter verification, and scenario fixtures.

Project initialization must not infer that every useful service needs a new
backend process, server-instance directory, port, user-systemd unit, bridge, or
ContextForge gateway. It must first ask whether the existing canonical service
already satisfies the required runtime, credential, resource, project, caller,
and transport scope.

| Class | Boundary | Examples | Project-init behavior |
| --- | --- | --- | --- |
| `instance_per_project` | A distinct backend instance is required because the service owns project-local state, indexes, language state, or workspace lifecycle. | Serena is the v1 reference example. | May provision a deterministic project-bound backend, project-specific virtual server, filtered tools, project-local client binding, and project-state evidence after approval. |
| `project_scoped_shared_backend` | One backend can serve multiple projects only when project scope is enforced by virtual-server policy, request-time root binding, resource allowlists, caller identity, or service-side scope checks. | A future project-aware backend that can safely multiplex roots. | Reuse the backend; create only the scoped binding, optional virtual server view, client binding, and verification evidence. If isolation cannot be proven, treat as `instance_per_project` or block. |
| `shared_canonical` | One canonical host-level or account-level backend serves projects without project-local instantiation. | `context7`; many documentation, search, or hosted-tool services. | Bind or verify the existing canonical ContextForge service. Do not create `context7-<project>` style backends merely because a project requests access. |
| `credential_scoped` | The safe boundary is a credential, account, tenant, token, installation, or organization. | `github` with a particular installation or token; API tools with account-scoped credentials. | Represent the credential scope explicitly. Multiple projects may bind to the same approved scope; new backend instances require service-management approval when metadata or virtual-server policy cannot express the boundary safely. |
| `resource_scoped` | The safe boundary is a repository, namespace, host, dataset, API resource set, or allowlist. | REST tools, repo-scoped services, or hosted services with explicit resource allowlists. | Bind through resource-scope metadata and verify with representative allowed and denied operations. Do not duplicate the backend for client-name or project-name convenience. |
| `caller_scoped` or `session_scoped` | The service follows the active caller, shell, process, tmux session, or live connection and is not durable project infrastructure. | `ssh-tmux` may be caller/session scoped or host-global depending on deployment. | Project state may record availability, consent, and verification, but must not claim ownership of the live session or create a per-project backend unless an approved service-management plan changes the model. |
| `static_repo_local` | The service is intentionally anchored to this repository's durable files or governance model. | `mentality` for `DECISIONS.md`, `ABEYANT_INTENTIONS.md`, and `OPEN_QUESTIONS.md`. | Keep the repo-local service static and authoritative for its domain. Do not duplicate it per client or let service-local memory supersede governance ledgers. |
| `candidate_or_uncataloged_backend` | The service has been discovered but is not yet canonical in ContextForge. | One-off client config entries, repo-local MCP servers, or unreviewed REST tools. | Surface a redacted advisory candidate only. Catalog promotion requires explicit service-management invocation and approval of a concrete plan. |

Normative rules:

- Client configs are discovery and consumption surfaces only. They must not
  define service identity or justify duplicate services named after Codex,
  Claude, Gemini, OpenCode, or any other client.
- Before creating any new `backend_instance`, the plan must prove that an
  existing shared, credential-scoped, resource-scoped, caller-scoped,
  session-scoped, or project-scoped shared backend cannot safely satisfy the
  required scope and transport.
- For `instance_per_project`, the contract card may authorize backend home,
  user-systemd unit, port, ContextForge gateway, virtual server,
  project-local client binding, project-state evidence, and verification traces
  only after approval of the relevant consent classes.
- For `project_scoped_shared_backend`, the contract card must state the
  isolation mechanism and what project-specific virtual-server view,
  service-binding metadata, client binding, and verification evidence are
  created.
- For `shared_canonical`, the project-facing object is normally a
  Shared-Service Capability Capsule plus a binding contract card. The capsule
  states that project init records availability, exposure, consent, and
  verification only. It must not create a new backend, gateway, bridge, wrapper,
  port, unit, or `server-instances/<project-specific-service>/` directory.
- For `caller_scoped` or `session_scoped`, the contract card must identify the
  live caller/session authority and must not claim durable project ownership of
  that session.
- For `static_repo_local`, the contract card must point to the governance
  authority and ledger source files that define the service's scope.
- For `candidate_or_uncataloged_backend`, project init emits a
  `service_management_handoff` and stops. It must not convert the candidate
  into a canonical ContextForge service under generic project-init approval.
- If an existing backend satisfies the requirement, project initialization must
  reuse it and create only the required `service_binding`, virtual-server view,
  `client_binding`, project-state record, and verification evidence.
- `project_state` may record that a project uses a shared service, but that
  record is not proof that the project owns or instantiated the backend.
- Native HTTP/SSE services must not be wrapped, bridged, or duplicated merely to
  make them look project-local.
- Verification must match the class. Per-project services require
  project-root-specific backend and target-client proof. Shared services require
  proof that the project/client binding reaches the intended canonical shared
  backend without broadening credential, resource, caller, host, or tool scope.
- Ambiguous classification is blocking. Project initialization may report a
  redacted `catalog_candidate` or `service` open item, but mutation must wait
  for a service-management plan or explicit user decision.

`context7` is the typical shared canonical capsule example. `ssh-tmux` is
caller/session scoped or host scoped depending on the deployed backend and
credential/session model. Serena remains the `instance_per_project` reference
example, but it is not a privileged special case.

### ContextForge Representation Matrix

The implementation must use stock ContextForge mechanisms and avoid inventing
parallel registries. This matrix defines where each concept lives.

| Concept | Representation | Authority |
| --- | --- | --- |
| `service_family` | ContextForge resource metadata plus naming convention and tags; native gateway/server rows for concrete exposed instances | ContextForge catalog |
| `service_binding` | ContextForge resource metadata linked to gateway/server IDs by evidence; project bindings also appear in project state | ContextForge catalog for host identity, project state for project use |
| `service_binding_contract_card` | ContextForge resource metadata plus project-state reference for accepted project use | ContextForge catalog for host identity, project state for project use |
| `shared_service_capability_capsule` | ContextForge resource metadata with project-state binding evidence and explicit non-ownership constraints | ContextForge catalog |
| `backend_instance` | `server-instances/<service-slug>/instance.json`, unit files, scripts, ignored runtime env/logs | Repo-local operational state |
| `contextforge_gateway` | Native ContextForge gateway row | ContextForge |
| `virtual_server` | Native ContextForge server row with associated tools/resources/prompts | ContextForge |
| `client_binding` | Project-local or user-local client config plus project-state evidence | Client config and project state |
| `tool_policy` | ContextForge resource metadata plus virtual-server associated-tool filtering | ContextForge virtual server association |
| `semantic_tool_policy` | ContextForge resource metadata compiled to virtual-server associated-tool sets and negative checks | ContextForge policy metadata and virtual-server readback |
| `prompt_resource_bundle` | Native ContextForge prompts/resources with associations | ContextForge |
| `service_management_skill` | Local/Codex skill reference and optional ContextForge resource documentation | Skill file/system and documentation resource |
| `service_management_handoff` | Redacted non-mutating handoff artifact; may be copied into a service-management run | Project-init output and service-management workflow |
| `project_state` | `.project/context_forge_state.json` | Project-local state |
| `language_profile` | ContextForge resource, for example `contextforge://control-plane/language-profiles/<id>/v1`, with JSON content and tags | ContextForge resource metadata |
| `service_memory_provider` | ContextForge resource metadata describing provider scope, operations, durability, and governance-reference policy | ContextForge resource metadata |
| `governance_registry` | Ledger files plus `mentality` MCP service | Governance ledgers |
| `client_adapter_conformance_pack` | Versioned fixture/metadata artifact; optional ContextForge resource documentation | Repo/test assets and adapter metadata |
| `consent_receipt` | Ignored `run/` record referenced by project state and plan journals | Local audit state |
| `verification_trace` | Ignored `run/` evidence envelope referenced by project state, journals, and evaluator ledgers | Local audit/evidence state |
| `requirement_scenario` | Versioned test fixture under generated/test fixtures or a future tracked fixture path | Test harness |
| `evaluator_verdict` | Generated evaluator artifact linked to trace, receipt, scenario, and requirement IDs | Test evidence ledger |
| `evidence_ledger` | Generated run artifact tying scenario, transcript, assertions, receipts, traces, diffs, verdicts, and remediation | Test evidence ledger |
| `governance_reconciliation_pack` | Generated advisory report plus future governance CRUD edits after review | Governance workflow |

The control service itself should be a thin MCP service registered through
ContextForge with an operational home under `server-instances/control-plane/`.
It calls stock ContextForge APIs and repo operator scripts; it must not
reimplement registry, transport, auth, or systemd responsibilities.

Catalog read APIs must redact auth material and secret-bearing env values.
`list_catalog()` must never return bearer tokens, generated JWTs, API keys,
passwords, raw env file contents, or downstream credentials.

### Project State Schema

Minimal v1 state:

```json
{
  "meta": {
    "schema_version": 1,
    "schema_uri": "contextforge://control-plane/project-state/v1",
    "created_at": "timestamp",
    "updated_at": "timestamp",
    "updated_by": "client-or-workflow",
    "revision": 1,
    "last_plan_id": "plan-id-or-null",
    "last_audit_record": "run/path-or-null"
  },
  "project": {
    "root": "/abs/canonical/project/root",
    "root_hash": "sha256-of-uid-and-root",
    "name": "project-name",
    "display_root": "/path/as-user-entered-or-null"
  },
  "diagnostics": {
    "related_instances": [
      {
        "relationship": "ancestor|descendant|sibling|same_root_alias",
        "service_family": "service-family-id",
        "canonical_name": "related-service-name",
        "root": "/abs/other/root",
        "root_hash": "other-root-hash",
        "used_for_verification": false
      }
    ]
  },
  "migration": {
    "legacy_env_seen": false,
    "legacy_env_disposition": "ignored|imported|conflict|not_present",
    "legacy_env_digest": "sha256-or-null",
    "imported_at": "timestamp-or-null",
    "conflicts": [],
    "client_config_migrations": {
      "<client_name>": {
        "source_path": "/abs/client/config-or-null",
        "ownership_class": "owned|legacy_owned|user_modified_owned|unmanaged_same_name|unsupported_schema|absent",
        "source_digest": "sha256-or-null",
        "disposition": "ignored|imported|conflict|not_present",
        "imported_binding_refs": [],
        "conflicts": [],
        "verification_trace_refs": []
      }
    }
  },
  "artifact_refs": {
    "contract_cards": [{
      "ref": "contextforge://control-plane/service-bindings/...",
      "content_digest": "sha256",
      "catalog_revision_or_etag": "revision-or-null",
      "resolved_at": "timestamp"
    }],
    "capability_capsules": [{
      "ref": "contextforge://control-plane/shared-services/...",
      "content_digest": "sha256",
      "catalog_revision_or_etag": "revision-or-null",
      "resolved_at": "timestamp"
    }],
    "semantic_tool_policies": [{
      "ref": "contextforge://control-plane/tool-policies/...",
      "content_digest": "sha256",
      "catalog_revision_or_etag": "revision-or-null",
      "resolved_at": "timestamp"
    }],
    "consent_receipts": [{
      "ref": "run/.../consent-receipt.json",
      "content_digest": "sha256",
      "catalog_revision_or_etag": null,
      "resolved_at": "timestamp"
    }],
    "verification_traces": [{
      "ref": "run/.../verification-trace.json",
      "content_digest": "sha256",
      "catalog_revision_or_etag": null,
      "resolved_at": "timestamp"
    }],
    "evidence_ledgers": [{
      "ref": "run/.../evidence-ledger.json",
      "content_digest": "sha256",
      "catalog_revision_or_etag": null,
      "resolved_at": "timestamp"
    }],
    "governance_reconciliation_packs": [{
      "ref": "run/.../governance-reconciliation-pack.json",
      "content_digest": "sha256",
      "catalog_revision_or_etag": null,
      "resolved_at": "timestamp"
    }]
  },
  "status": "uninitialized|in_progress|initialized|disabled",
  "decisions": {
    "<decision_key>": {
      "decision_kind": "service|language_profile|client_trust|project_init",
      "state": "unasked|accepted|declined|deferred|disabled",
      "service_binding": "<service-family>:<scope-id>-or-null",
      "contract_card_ref": "contextforge://control-plane/service-bindings/<id>/v1-or-null",
      "decided_at": "timestamp-or-null",
      "decided_by": "client-or-user-or-null",
      "source_plan_id": "plan-id-or-null",
      "reopened_at": "timestamp-or-null",
      "notes": "optional non-secret note"
    }
  },
  "services": {
    "<service_binding>": {
      "service_family": "service-family-id",
      "service_binding": "<service-family>:<scope-id>",
      "instantiation_class": "instance_per_project|project_scoped_shared_backend|shared_canonical|credential_scoped|resource_scoped|caller_scoped|session_scoped|static_repo_local",
      "contract_card_ref": "contextforge://control-plane/service-bindings/<id>/v1",
      "capability_capsule_ref": "contextforge://control-plane/shared-services/<id>/v1-or-null",
      "semantic_tool_policy_ref": "contextforge://control-plane/tool-policies/<id>/v1",
      "backend_instance": "service-instance-slug-or-null",
      "virtual_server": "virtual_server_name_or_null",
      "provision_status": "none|pending|created|degraded|failed|removed|verified",
      "lifecycle": {
        "current_state": "planned|unit_written|unit_enabled|backend_ready|registered|client_config_written|pending_restart|verified|degraded|failed|removed|null",
        "previous_state": "same-enum-or-null",
        "allowed_next_states": [],
        "transition_journal_ref": "run/.../apply-journal.json-or-null",
        "evidence_refs": [],
        "recovery_outcome": "none|resume|forward_repair|rollback_by_approved_workflow|manual_recovery|fresh_approval_required"
      },
      "language_profile": "language-profile-id-or-null",
      "required_verification_layers": [
        "backend",
        "contextforge_gateway",
        "virtual_server",
        "target_client",
        "trust",
        "tool_policy",
        "redaction"
      ],
      "verification_layers": {
        "backend": "unknown|not_applicable|pending|passed|failed|stale",
        "contextforge_gateway": "unknown|not_applicable|pending|passed|failed|stale",
        "virtual_server": "unknown|not_applicable|pending|passed|failed|stale"
      },
      "target_clients": {
        "<client_name>": {
          "state": "not_configured|pending_trust|pending_restart|pending_auth|pending_verification|verified|failed|stale",
          "adapter_conformance_pack": "<client>/v1",
          "source_client_auth_strength": "none|asserted|shared_token|wrapper_bound|per_client_token",
          "trust_broker_state": "not_required|unknown|reported|approval_requested|approved|verified|declined|failed",
          "trust_receipt_ref": "run/.../consent-receipt.json-or-null",
          "verification_trace_refs": [],
          "verified_at": "timestamp-or-null",
          "last_probe": "probe-id-or-null"
        }
      },
      "verification_trace_refs": [],
      "consent_receipt_refs": [],
      "evidence": [
        {
          "source": "contextforge|systemd|client|backend",
          "observed_at": "timestamp",
          "subject": "virtual_server",
          "canonical_name": "virtual_server_name",
          "record_id": "evidence-only",
          "probe": "servers_tools|client_call_tool|unit_active",
          "status": "ok|failed|stale",
          "result_hash": "sha256-of-redacted-result",
          "audit_record": "run/path-or-null"
        }
      ]
    }
  },
  "client_trust": {
    "<client_name>": {
      "state": "unknown|untrusted|trusted_but_not_loaded|trusted_requires_restart|trusted|declined|not_required",
      "root": "/abs/canonical/project/root",
      "trust_surface": "client-specific-surface-or-null",
      "approval_record": "run/path-or-null",
      "verified_at": "timestamp-or-null",
      "last_probe": "probe-id-or-null"
    }
  },
  "memory_policy": {
    "mode": "ledger_authoritative_references_only"
  },
  "drift": {
    "last_checked_at": "timestamp-or-null",
    "status": "unknown|clean|drift_found",
    "findings": [
      {
        "finding_id": "drift-id",
        "finding_type": "stale_id|duplicate_name|changed_tool_association|missing_unit|client_config_edit|auth_path_change|catalog_record_missing|backend_manifest_mismatch|port_conflict",
        "affected_layer": "project_state|backend|systemd|contextforge|virtual_server|client_config|auth|tool_policy",
        "expected_identity": {},
        "observed_identity": {},
        "evidence_refs": [],
        "blocking": true,
        "proposed_repair": "resume|forward_repair|rollback_by_approved_workflow|manual_recovery|fresh_approval_required|none"
      }
    ],
    "reconciled_by_name": [],
    "stale_ids": []
  },
  "open_items": [
    {
      "id": "open-item-id",
      "type": "trust|restart|secret|verification|drift|language|language_profile_missing|service|migration|config_conflict|catalog_candidate|port_conflict|runtime|security|remote_exposure|tool_policy|contract_missing|handoff_required|consent_required|trace_missing|client_conformance|trust_broker|scenario_evaluation|governance_reconciliation",
      "severity": "info|warning|blocking",
      "blocks_initialized": true,
      "resource": "client-or-service-or-file",
      "created_at": "timestamp",
      "resolution_state": "open|resolved|deferred",
      "detail": {}
    }
  ]
}
```

The `decisions`, `services`, `target_clients`, and `client_trust` objects are
generic maps. Keys are stable decision IDs, service binding IDs, or client names
as appropriate. Concrete Serena and Codex values belong in example project
state, fixtures, traces, or narrative proof paths, not in the base schema.

Project state is not a host catalog database. It stores project decisions,
classifications, canonical names, stable contract references, consent receipt
references, verification trace references, and evidence hashes. The whole
ContextForge service catalog remains in ContextForge resources, gateways,
virtual servers, prompts, resources, tools, tokens, and native API rows.
Artifact refs are snapshot references, not live pointers alone. Every referenced
contract, capsule, policy, receipt, trace, evidence ledger, or reconciliation
pack must include the resolved ref, content digest, catalog revision or ETag
when available, and resolution time. Plan digests and stale-plan checks must
include those artifact snapshots so an approval cannot silently float to newer
contract text or different catalog metadata.

Candidate services must not be stored under durable `services` entries. A
`candidate_or_uncataloged_backend` is represented as an open item,
`service_management_handoff`, planner advisory, or test fixture until
service-management returns `dedupe_existing` or `approved_completed` with
ContextForge canonical names and contract/capsule refs. Only then may project
state create a durable service binding record.

Drift entries are typed `drift_finding` objects so repair code can distinguish
stale IDs, changed associations, missing units, client edits, auth changes, and
port conflicts without parsing prose.

Minimal v1 contract artifact shapes:

- **Service Binding Contract Cards** use
  `card_id`, `schema_uri`, `service_family`, `service_binding`,
  `instantiation_class`, `authority_boundary`, `project_scope`,
  `credential_scope`, `resource_scope`, `caller_or_session_scope`,
  `backend_instance_ref`, `contextforge_gateway`, `virtual_server`,
  `client_adapter_refs`, `semantic_tool_policy_ref`, `transport_profile`,
  `required_consent_classes`, `verification_matrix`, `non_actions`, and
  `evidence_requirements`. `transport_profile` records native transports,
  required client transports, bridge mode, package bridge command/ref when used,
  forbidden bridge effects, and required `/mcp` plus `/sse` verification.
- **Shared-Service Capability Capsules** use `capsule_id`, `schema_uri`,
  `service_family`, `canonical_service`, `allowed_project_binding_modes`,
  `project_state_recording_policy`, `verification_requirements`,
  `consent_requirements`, `transport_profile`,
  `forbidden_project_init_effects`, and `contract_card_refs`. A capsule for
  `context7` must prove useful project binding without creating a per-project
  backend or unnecessary transport bridge.
- `semantic_tool_policy` records `policy_id`, `schema_uri`, `service_binding`,
  `risk_classes`, `scope_impacts`, `approval_gates`, `allowed_tool_selectors`,
  `excluded_tool_selectors`, `manual_overrides`, `compiled_tool_ids`,
  `negative_checks`, `last_compiled_at`, and `last_readback_trace_ref`.
- `service_management_handoff` records `handoff_id`, `source`, optional
  `project_root`, redacted `candidate_descriptor`, `redaction_status`,
  `dedupe_keys`, `suspected_instantiation_class`, `required_next_workflow`,
  and `forbidden_under_current_approval`.
- `service_management_result` records `result_id`, `handoff_id`, `status`,
  `contract_card_refs`, `capsule_refs`, `semantic_tool_policy_refs`,
  `canonical_names`, `catalog_revision`, `consent_receipt_refs`,
  `verification_trace_refs`, `redaction_status`, and
  `forbidden_follow_up_effects`.
- `service_provision_plan` records `provision_plan_id`, `service_binding`,
  ordered `service_provision_step` entries, stale inputs, write set, consent
  receipt refs, expected readback, idempotency mode, compensation/repair mode,
  and produced artifact refs. Each `service_provision_step` must have
  preconditions, persistent target, operation class, expected state transition,
  required policy/conformance refs, and negative checks.
- **Consent Receipt Objects** record `receipt_id`, `plan_id`, `plan_digest`,
  `plan_presented_digest`, `consent_class`, `scope`, `actor`,
  `source_client`, `source_client_auth_strength`, `approval_nonce`,
  `approval_channel`, `approval_event_ref`, `issued_by`, `approved_at`,
  redacted `approval_evidence`, `expires_at`, and replay policy. Receipts are
  immutable; step usage is recorded in the apply journal or a receipt-usage
  ledger, not by mutating the receipt.
- **Adapter-Independent Verification Trace Format** records `trace_id`,
  `schema_uri`, `plan_id`, `service_binding`, `target_client`,
  `adapter_conformance_pack`, ordered `probe_events`, `negative_checks`,
  `redaction_checks`, `result`, `failed_layer`, `result_hash`, and
  `generated_at`.
- **Client Adapter Conformance Packs** record `pack_id`, `client_name`,
  `version_constraints`, `config_surface_fixtures`, owned-block classes,
  direct HTTP/header support, stdio wrapper behavior, trust requirements,
  trust broker interface, restart model, stale-config probes, list-tools and
  call-tool probes, token-source constraints, negative tool-policy visibility
  checks, and known unsupported behaviors.
- **Requirement-Linked Scenario DSL** fixtures record `scenario_id`,
  `requirement_ids`, `tested_agent_view`, `hidden_initial_conditions`,
  `during_test_events` with explicit actor/visibility fields,
  `allowed_mutations`, `forbidden_mutations`, `expected_outcomes`,
  `deterministic_assertions`, and `inference_rubric`.
- **Evaluator Verdict Schema And Evidence Ledger** records use
  `verdict_id`, `schema_uri`, `created_at`, evaluator run metadata,
  evaluated artifact refs, deterministic assertion refs, `scenario_id`,
  `requirement_ids`, `verdict`, `failed_requirements`, cited `evidence`,
  `likely_cause`, `remediation_target`, redaction status, evidence hashes, and
  optional `requirement_gap_proposal`. The evidence ledger is a JSON artifact
  with `ledger_id`, `schema_uri`, run metadata, requirement IDs, scenario refs,
  transcript refs, deterministic assertion results, consent receipts,
  verification traces, world-state diff refs, evaluator verdict refs,
  remediation refs, redaction status, and evidence hashes.
- **Governance Reconciliation Pack** records `pack_id`, `rfc_digest`,
  `ledger_digests`, decisions missing from ledgers, open questions answered or
  narrowed by the RFC, abeyant intentions needing updates, service-memory
  conflicts, and suggested governance CRUD operations. It is advisory only.

Declined decisions are sticky. Project-init must not repeatedly re-offer a
declined service unless the user explicitly reopens that decision.

`disabled` means the user has declined all currently offered project-init
services or has explicitly disabled project initialization for this root. It is
not equivalent to `initialized`: no service is considered ready, and future
explicit user requests may reopen individual decisions.

`initialized` requires every accepted service to be verified through the
specific target client path that will consume it. Accepted-but-pending services
keep the project out of `initialized` and must remain in `open_items` or
incomplete service state.

Service verification is layered. Backend readiness, ContextForge gateway
registration, virtual-server policy, and target-client proof must be recorded
separately. The aggregate `provision_status` may be `verified` only when all
required layers and all intended target clients are verified. A runtime failure
after verification must downgrade the affected layer to `stale`, `degraded`, or
`failed` and reopen the relevant blocking item.

State writes must be serialized with a project-local or `run/` lock. Writers
must write a temporary file, validate it against the schema, fsync when
practical, and atomically replace the target. The file should not be
world-writable. Implementations must reject denied roots and symlink escapes
before reading or writing project state.

Root evaluation order is normative: resolve the display path to a canonical
realpath, detect symlink or mount aliases, reject denied roots and symlink
escapes, then read project state. Plan digests must include the canonical
realpath, root hash, and, where practical, inode/device identity or an
equivalent target-stability signal. If any of those inputs changes before
apply, the plan is stale.

Legacy `.env` project-init keys are not a parallel authority. During cutover,
the implementation must record whether legacy keys were seen, whether they were
ignored/imported/conflicted, and a digest of the legacy input. Malformed or
conflicting legacy state must be reported as a migration open item rather than
silently re-asking the user or overwriting JSON.

Legacy decision translation is explicit:

| Legacy input | JSON state outcome | Notes |
| --- | --- | --- |
| absent | `not_present` migration disposition; decision remains `unasked` | No prompt suppression. |
| accepted/provisioned with matching root, catalog names, manifest, language profile, owned config, and current verification | accepted decision plus migration evidence; service still requires current verification before `verified` | Legacy state alone cannot initialize the project. |
| declined | declined sticky decision | Suppresses repeat prompts until reopened by explicit user action. |
| deferred | deferred decision and open item if still relevant | Does not block unrelated accepted services. |
| disabled/no-service | project `status: disabled` when all offered services are declined or disabled | Not equivalent to `initialized`. |
| malformed value | migration conflict open item | Do not infer acceptance or decline. |
| conflicting accepted/declined/provisioned signals | migration conflict open item | Offer explicit import, preserve decline, mark unmanaged, or defer. |

Legacy accepted state may be imported only when legacy keys, canonical root,
backend manifest, ContextForge canonical names, owned client config, language
profile, and current target-client verification agree. Legacy acceptance alone
can become at most an accepted decision plus migration evidence; it cannot by
itself mark a service or project `verified`. Migration conflicts must offer
explicit outcomes: import the created service, preserve decline and remove or
disable only through an approved plan, mark the existing service unmanaged, or
defer.

Schema evolution requires a JSON Schema document or equivalent validator. Future
unsupported major versions fail safely. Compatible minor additions either
preserve unknown extension fields or reject them by documented rule; the
implementation must not silently discard unrecognized durable state.

The field lists above are the minimum semantic contract, not a substitute for
validators. Wave 1 must materialize JSON Schema-style definitions for every
artifact type, including required versus optional fields, enum values,
reference formats, versioning, redaction and secret-value bans, extension-field
handling, and migration behavior. Agents must stop at schema ambiguity instead
of inventing incompatible local shapes.

### Control Service Surface

The assistant-facing ContextForge MCP control service is workflow-oriented.
It may expose host-wide read-only catalog views, but any project state, project
planning, provisioning, project-local config write, or verification operation
requires a canonical project root.

Required v1 tools:

- `get_project_context(project_root)`: return canonical root, root hash, denied
  root checks, existing state, related instances, target clients, trust
  visibility, current contract-card refs, capability-capsule refs, latest
  consent receipts, latest verification traces, trust broker state, and
  governance reconciliation warnings when available.
- `list_catalog()`: host-wide read-only catalog of canonical services, virtual
  servers, prompts/resources, skills/agents metadata, language profiles,
  service binding contract cards, shared-service capability capsules, semantic
  tool policies, client adapter conformance pack summaries, and
  memory-provider capability metadata.
- `list_available_capabilities(project_root)`: project-relevant capabilities,
  already-registered services, project-scoped service candidates, shared
  services bindable only through capability capsules, language profiles, and
  setup gaps.
- `propose_project_init(project_root, target_clients)`: non-mutating plan with
  choices, required consent classes, expected file writes, service provisioning,
  restart requirements, contract card refs, required capability capsules,
  semantic tool-policy refs, consent receipt requirements, verification trace
  requirements, service-management handoff objects, and verification steps.
- `record_project_decision(project_root, decision)`: record sticky accepted,
  declined, deferred, or disabled decisions in project-local state against a
  contract card or capability capsule, not only a service-family string.
- `approve_plan(project_root, plan_id, approval)`: record explicit approval
  evidence for a previously generated plan and issue immutable consent receipt
  objects. Approval must validate plan digest, project-state revision, source
  client auth strength, target clients, consent classes, and persistent targets.
- `apply_approved_plan(project_root, plan_id)`: resumable application of an
  approved plan. The tool consumes existing matching consent receipts, executes
  stepwise, records per-step status, produces verification traces as step
  outputs, and can resume or repair after failure. It must not mint the approval
  receipts that authorize its own mutation.
- `verify_project_init(project_root, target_clients)`: live verification through
  the specific intended client-visible MCP paths, producing
  adapter-independent verification traces.
- `report_project_gaps(project_root)`: pending trust, language, service,
  restart, secret, missing contract, missing receipt, failed trace, conformance,
  trust broker, governance reconciliation, or verification gaps without
  mutation.

The control service may directly write project-local state and project-local
client config after approval. Exceptions must be explicit in the plan: unmanaged
pre-existing config blocks, user-edit conflicts, unsupported client schemas,
restart requirements, and user-global trust changes.

`record_project_decision` may record decline, defer, disabled, or reopen
decisions directly when the user explicitly gives that decision. Recording
acceptance of a plan requires the same approval evidence as
`apply_approved_plan`; acceptance cannot be inferred from inspection or planning
alone.

Generated plans must include a typed effect summary even when the control
service will write files directly. The effect summary lists exact files,
ContextForge records, user-systemd units, env placeholder paths, client configs,
trust entries, restart requirements, and verification criteria. If the service
detects an owned config block, it may write it directly after approval. If a
config block is unmanaged, user-edited, partially recognized, or unsupported by
the client schema, the service must stop and return a patch plan or user action
instead of merging.

If project-init discovers that host catalog mutation or repair is required, the
control service returns a `service_management_handoff` and stops. Generic
project-init approval cannot authorize catalog promotion, host-wide service
repair, raw ContextForge CRUD, or new canonical service creation.

### Catalog Administration

Normal project-init may surface a newly discovered backend candidate, but it
must not promote that backend automatically. Catalog administration starts only
from explicit user intent, such as:

- "Add this discovered backend to ContextForge."
- "Promote this MCP server into the host-wide catalog."
- "Manage ContextForge services."
- "Update the `github` service registration."
- "Remove this ContextForge gateway."
- "Yes, add that candidate service."

After invocation, the assistant uses a dedicated service-management skill. The
first step is non-mutating: inspect the candidate or existing service, classify
scope, check for duplicates, decide native transport versus package bridge, and
produce a plan. Mutation requires explicit approval of that concrete plan.

For v1, raw catalog CRUD is not exposed through the general control-plane MCP
service. Catalog mutation lives in the dedicated skill over existing
ContextForge APIs and repo scripts.

**Capability Negotiation Between Control Service And Service-Management**

Normal project init and service management exchange typed artifacts, not
ambient intent. When project init finds a candidate backend, duplicate service,
transport gap, missing canonical contract, or catalog drift that requires
host-wide mutation, it emits a `service_management_handoff` shaped like:

```json
{
  "handoff_id": "handoff-id",
  "source": "project_init|catalog_read|user_request",
  "project_root": "/abs/root-or-null",
  "candidate_descriptor": {},
  "redaction_status": "redacted",
  "dedupe_keys": {
    "backend_package": "name-or-null",
    "runtime_scope": "host|project|credential|caller|session|unknown",
    "credential_scope": "redacted-scope-or-null",
    "resource_scope": "scope-or-null",
    "transport_scope": "stdio|http|sse|rest|unknown"
  },
  "suspected_instantiation_class": "candidate_or_uncataloged_backend",
  "required_next_workflow": "service_management_plan",
  "forbidden_under_current_approval": ["catalog_promotion"]
}
```

The service-management workflow may return a non-mutating plan,
dedupe-to-existing-service result, refusal, or post-approval completion record.
Project init may consume completion records only after service management has
been explicitly invoked and approved under the correct consent class.

The return value is a typed `service_management_result`, not free-form prose:

```json
{
  "result_id": "service-management-result-id",
  "handoff_id": "handoff-id",
  "status": "plan_only|dedupe_existing|refused|approved_completed|failed",
  "contract_card_refs": [],
  "capsule_refs": [],
  "semantic_tool_policy_refs": [],
  "canonical_names": [],
  "catalog_revision": "revision-or-null",
  "consent_receipt_refs": [],
  "verification_trace_refs": [],
  "redaction_status": "redacted|failed",
  "forbidden_follow_up_effects": ["project_init_catalog_mutation"]
}
```

Project init may consume `dedupe_existing` or `approved_completed` only when the
result cites ContextForge canonical names, expected contract/capsule refs, and
verification evidence. `plan_only` and `refused` are not permission to mutate.

### Service-Management Skill Contract

The service-management skill is an explicit operational boundary for host-wide
catalog mutation. It must produce a non-mutating plan before any change and must
own these fields:

- candidate descriptor and discovery source.
- deduplication keys: backend package/server, runtime scope, credential scope,
  resource scope, and transport scope.
- service family and service binding classification.
- project scope classification and whether the backend is instance-per-project,
  caller-scoped, credential-scoped, or host-global.
- backend-home manifest shape and expected ignored runtime files.
- transport decision: native HTTP/SSE, package bridge, or unsupported.
- required ContextForge API operations.
- tool policy, including every excluded, scope-changing, or approval-gated tool.
- consent classes.
- plan effect summary, rollback/repair notes, and verification probes.

The non-mutating plan must either produce a service binding contract card or
explain why no canonical service should be created. For approved catalog
changes, the plan should produce a contract card, optional shared-service
capability capsule, semantic tool policy, consent receipt requirements,
verification trace requirements, rollback/repair notes, and a dedupe record.

Approved catalog mutation must use public ContextForge APIs and documented
operator scripts. It must not call internal routes, patch ContextForge source,
or write the ContextForge database. Gateway tool discovery should use gateway
refresh and virtual-server tool associations. Filtering policy must update the
virtual server associated-tool set and verify `/servers/{id}/tools` after every
gateway refresh.

### Consent And Audit

Plans must list consent classes:

- `read_only_inspection`
- `project_state_write`
- `project_local_config_write`
- `service_provision`
- `catalog_promotion`
- `user_global_client_trust`
- `user_global_config_write`
- `secret_placeholder_change`
- `secret_value_write`
- `token_material_change`
- `network_exposure_change`

Generic project setup approval covers only the listed project-local classes.
User-global trust, catalog promotion, and actual secret value writes require
separate explicit approval.

`read_only_inspection` normally requires authentication, root validation, and
redaction rather than a consent receipt. A receipt for `read_only_inspection`
is used only when a plan intentionally scopes a sensitive read, such as reading
ignored local metadata for migration or diagnostics. It never authorizes
mutation and cannot be upgraded into a write class.

**Consent Receipt Objects**

Approval is represented by a formal `consent_receipt`, not only by prose in a
transcript. Minimal receipt shape:

```json
{
  "receipt_id": "receipt-id",
  "schema_uri": "contextforge://control-plane/schemas/consent-receipt/v1",
  "plan_id": "plan-id",
  "plan_digest": "sha256",
  "plan_presented_digest": "sha256-of-user-visible-plan-summary",
  "consent_class": "read_only_inspection|project_state_write|project_local_config_write|service_provision|catalog_promotion|user_global_client_trust|user_global_config_write|secret_placeholder_change|secret_value_write|token_material_change|network_exposure_change",
  "scope": {
    "project_root": "/abs/root-or-null",
    "service_binding": "binding-id-or-null",
    "client": "client-or-null",
    "persistent_target": "file|trust-store|contextforge|systemd|token-store|network"
  },
  "actor": "user-or-client",
  "source_client": "codex-or-other",
  "source_client_auth_strength": "asserted|shared_token|wrapper_bound|per_client_token",
  "approval_nonce": "nonce-or-null",
  "approval_channel": "interactive_user|local_ui|signed_file|external_review",
  "approval_event_ref": "transcript-or-event-ref",
  "issued_by": "approve_plan|record_project_decision|external-human-review",
  "approved_at": "timestamp",
  "approval_evidence": "redacted-summary",
  "expires_at": "timestamp",
  "replay_policy": "single_use|same_plan_resume|repair_only|fresh_approval_required"
}
```

A receipt for one class cannot authorize another class.
`project_local_config_write` cannot authorize `user_global_client_trust`;
`service_provision` cannot authorize `catalog_promotion`; token material,
actual secret value, and network exposure receipts are not reusable for normal
project initialization. `secret_placeholder_change` covers only ignored env file
creation, key-name placeholders, and missing-secret diagnostics; it cannot write
real secret values. `secret_value_write` requires a separate deliberate
secret-entry workflow, non-null expiry, and fresh approval after failure.

Receipts are immutable. An implementation must not append `used_by_steps` or
other consumption markers into the receipt object. Receipt consumption belongs
in the approved-plan journal or a separate append-only receipt-usage ledger that
references the receipt digest, step ID, operation class, result, and timestamp.

No tool, sub-agent, tested assistant, planner, evaluator, or service workflow
may approve its own mutation by summarizing or quoting the user's intent. A
receipt requires a direct human approval event for the exact displayed plan
digest, consent class, target clients, persistent targets, and scope. The
approval evidence must include the approval channel and transcript/event
reference, but not secret values.

Actual secret values must enter through a safe local channel such as a local
editor, existing ignored env file, OS secret store, no-echo prompt, or
ContextForge-approved secret provider. They must not be pasted into normal chat
transcripts, shell command arguments, shell history, audit records, project
state, diagnostic bundles, or generated fixtures. A plan may create placeholders
and diagnostics for missing secrets, but `secret_value_write` requires its own
deliberate workflow and leak checks.

**Operation Authorization And Replay**

Consent receipts prove user approval; they do not by themselves authorize every
caller to execute or replay a plan. Every mutating workflow must also validate
operation authorization immediately before execution:

- authenticated caller or local workflow identity under the active auth profile.
- source client and target clients named in the plan digest.
- source-client auth strength sufficient for the operation class. Under the v1
  shared-token profile, `source_client` is evidence unless a wrapper-bound or
  per-client identity proves it server-side.
- canonical project root and current project-state revision.
- allowed operation class for the caller, such as read-only inspection,
  project-state write, owned project-local config write, service provision,
  trust workflow, catalog-management workflow, token workflow, or remote
  exposure workflow.
- matching unexpired consent receipt for each mutating step's consent class and
  scope.
- replay policy for the step: resumable, repair-only, manual-recovery-only, or
  forbidden without fresh approval.

`approve_plan` is the receipt issuance boundary. `apply_approved_plan` must
reject calls when caller identity, source client, source-client auth strength,
target clients, plan digest, state revision, operation class, receipt scope,
receipt expiry, token source, or persistent target no longer match. Receipt
reuse after interruption is allowed only for the same plan digest, same
canonical root, same service binding, same target clients, same persistent
target, same operation class, and compatible replay policy.

Remote exposure, user-global config writes, `secret_value_write`, and token
material creation, rotation, or revocation are separate approval classes. They
must not be bundled with ordinary project initialization, service provisioning,
wrapper repair, or secret placeholder creation.

User-global client trust changes, including Codex project trust, are allowed
only after explicit human approval of that trust action. They must never be
implied by service setup approval.

Approved plans create ignored local audit records under `run/` with timestamp,
plan identifier, consent classes, planned mutations, executed steps, and
verification results. Audit records and project state must not include secret
values.

Approval prompts and audit records must include enough machine-checkable
evidence to prevent broad or stale approvals:

- `plan_id` and plan digest.
- actor, source client, base project-state revision, and observed current
  revision.
- lock acquisition result and stale-lock handling.
- requested client and target clients.
- consent classes.
- exact mutation targets.
- persistent scope.
- whether global trust changes.
- whether secrets or secret placeholders are touched.
- whether restart is required.
- rollback, forward-repair, or manual-recovery notes.
- verification criteria.
- approval event or explicit approval phrase.

`apply_approved_plan` must reject stale plan IDs when project state, target
files, ContextForge records, service manifests, or relevant client config have
changed since planning. Root identity, target clients, port availability,
token-source paths, trust state, restart state, and catalog drift are stale-plan
inputs. Trust changes, user-global config writes, catalog promotion, network
exposure, token material changes, and actual secret value writes each require a
separate approval step and must never be bundled into a generic "initialize
project" approval.

The control plane may create ignored placeholder env files and report missing
keys after approval. Actual secret value writes require a separate deliberate
secret-entry workflow and must remain out of tracked state and normal audit
payloads.

### Approved Plan Journal And Idempotency

Approved-plan execution state lives under ignored `run/` state. Each journal
record must contain:

- `plan_id`, `run_id`, and `step_id`.
- plan digest and pre-apply snapshot references.
- actor, source client, base revision, observed revision, lock owner, and lock
  acquisition result.
- preconditions.
- consent class for each step.
- required consent receipts and observed consent receipts.
- service contract refs, semantic tool policy refs, and
  service-management handoff refs.
- write set and redacted output summary.
- per-step status and timestamps.
- probe results and result hashes.
- verification trace refs.
- rollback, forward-repair, or manual-recovery action.
- final verification evidence.

Every mutating step must declare idempotency behavior. Re-running
`apply_approved_plan` after interruption must resume or repair without
duplicating units, ports, registry records, client config blocks, env
placeholders, or audit entries. Steps that involve global trust, catalog
promotion, or secret values must not be silently retried after failure; they must
return an explicit repair plan for user approval.

Locks must have documented timeout and stale-lock recovery behavior. A stale
lock may allow diagnostics, but mutation requires compare-and-swap semantics
against the latest project-state revision. A different actor may resume an
active approved plan only when the plan digest, consent classes, target clients,
and preconditions still match; otherwise it must ask for fresh approval.

Re-running a plan must validate both the plan digest and the receipt scopes. A
stale plan cannot reuse an old receipt when target clients, service binding,
project root, client trust target, token path, catalog effect, or network
exposure effect has changed.

Recovery-path tests are required for interrupted apply, stale-plan replay,
partial ContextForge registration, partial systemd/unit writes, port allocation
race or stale occupied port, unmanaged config conflict, failed verification
trace emission, and receipt-scope mismatch. Recovery outcomes must be one of:
resume, forward repair, rollback by approved workflow, manual recovery, or block
for fresh approval.

### Project-Scoped Service Pattern

Serena is the first proof, but the design is service-agnostic. v1 implementation
must include Serena, refactored as needed for this RFC, plus one additional
non-Serena project-scoped service proof.

Reusable project-scoped service flow:

1. Derive deterministic project-bound service identity from canonical root.
2. Provision one backend instance under `server-instances/<service-project>/`.
3. Register or refresh the backend through ContextForge APIs.
4. Expose a project-specific virtual server.
5. Compile semantic tool policy fail-closed before any client-visible exposure.
6. Filter unsafe or scope-changing tools from the virtual server.
7. Generate project-local client-binding intent after approval; write owned
   client config only after the relevant adapter conformance pack is available.
8. Require a passing client adapter conformance pack before target-client proof.
9. Track client restart requirements.
10. Verify through the specific target client-visible MCP path.
11. Record stable names in project state and IDs/probe outputs as evidence.

Project-scoped service provisioning is a mutating apply class distinct from
catalog promotion. An approved `service_provision` step may create or update a
project-scoped backend home, ignored env placeholders, user-systemd unit, port
reservation, ContextForge gateway/server records for the project binding,
virtual-server tool associations, project-local client config, and verification
trace references. It cannot promote an uncataloged host-wide service, mutate
shared canonical service identity, write user-global trust, write actual secret
values, or enable remote exposure without separate consent and workflow entry.
Before adapter conformance has passed, the provision layer may produce
client-binding intents and patch plans only; it must not silently write a
client-visible binding that the target client cannot be verified to consume.

The durable `service_provision_plan` is a step graph, not only a prose plan.
Each step must name preconditions, stale inputs, write set, expected ContextForge
or filesystem readback, consent receipt refs, semantic policy refs, client
conformance refs, idempotency behavior, compensation/repair behavior, produced
artifact refs, and the lifecycle transition it intends to prove. Client-visible
binding steps are invalid until the relevant semantic tool policy has compiled
and passed negative readback checks.

Scope-changing tool filtering is general policy. Any tool that can change the
active project, workspace root, credential scope, resource scope, or backend
operating scope must be filtered from a project-scoped virtual server unless
explicitly approved and verified. `activate_project` is only Serena's instance
of this broader rule.

**Semantic Tool-Policy Compiler**

Literal Serena denylisting is insufficient. The control plane compiles
`semantic_tool_policy` metadata into ContextForge virtual-server associated-tool
sets and negative verification checks. Inputs include the refreshed gateway
tool list, original and exposed tool names, service binding contract card,
instantiation class, tool risk metadata, project/caller/credential/resource
scope impact, and approval gates. Outputs include allowed ContextForge tool IDs,
excluded tool records with reasons, virtual-server negative checks,
target-client-visible negative checks, and a repair-plan trigger when compiled
policy and ContextForge readback disagree.

Tool policy metadata must include original tool name, exposed tool name, risk
class, scope impact, filter reason, approval gate, and verification probe.
Scope-changing tool policy must be tested independently of Serena, with
`activate_project` treated only as one fixture.

The compiler is fail-closed. Unknown tools, missing risk metadata, unmatched
manual overrides, stale gateway readback, or incomplete client conformance must
exclude the tool from project-scoped virtual servers and create a blocking
`tool_policy` open item. A manual allow override must cite the consent receipt,
requirement ID, risk class, and negative checks that justify it.

Tool-policy verification must run after every gateway refresh, server
association update, client restart, or stale-config repair. It must include
negative checks at both the ContextForge virtual-server layer and the
target-client-visible layer, using original names, exposed names, and semantic
risk classes rather than literal Serena-only denylist entries.

**Dedicated Project-Scoped Non-Serena Proof Candidate**

The non-Serena proof should be a read-only `project-inspector` style MCP
service unless a later approved RFC revision replaces it. It is project-scoped
and root-bound, requires no external secrets, and exposes safe project facts
such as canonical root identity, root hash, symlink and nested-project
relationships, ignored path summaries, marker files, detected languages,
package manifests, and worktree status. It must not replace language-aware
Serena behavior.

For v1, `project-inspector` is a planned proof service named by this RFC, not a
random discovered catalog candidate. Its base service family, canonical
metadata, contract-card template, and semantic policy are predeclared RFC/catalog
seed artifacts. Project init may create only the approved project-scoped
binding, backend instance, virtual server, and conformance-gated client binding
or client-binding intent. If those seed artifacts are absent or need host-wide
mutation, project init must emit a service-management handoff instead of
provisioning.

This built-in seed rule applies only to proof services explicitly named by this
RFC, currently Serena and `project-inspector`. A discovered backend, local
script, REST service, or client-config MCP entry that is not an RFC-named seed
must remain a `candidate_or_uncataloged_backend` handoff until the
service-management workflow deduplicates, plans, approves, and records the
canonical ContextForge service identity.

The proof must demonstrate the same generic adapter pattern as Serena:
deterministic project-scoped identity, backend home, ContextForge registration,
virtual-server exposure, semantic tool-policy compilation, project-local client
binding, client-specific verification, consent receipts, verification traces,
and project-state evidence. The purpose is to prove the project-scoped path
without forcing `context7`, `ssh-tmux`, or another shared canonical service into
a false per-project shape.

### Operational Contract

Service lifecycle state uses this vocabulary:

- `planned`
- `unit_written`
- `unit_enabled`
- `backend_ready`
- `registered`
- `client_config_written`
- `pending_restart`
- `verified`
- `degraded`
- `failed`
- `removed`

A lifecycle transition to `verified` must name the verification trace or traces
that prove the transition. Lifecycle states that rely on a service binding
contract, capability capsule, semantic tool policy, conformance pack, trust
broker, or governance reconciliation warning must carry references to those
artifacts in project state, journals, or gap reports.

Lifecycle transition contract:

| State | Required evidence before transition | Durable references |
| --- | --- | --- |
| `planned` | Non-mutating plan with contract card, instantiation class, consent classes, stale inputs, and expected verification | project state `last_plan_id`; plan journal |
| `unit_written` | Backend manifest and user-systemd unit written to approved project-scoped targets | plan journal; backend manifest hash |
| `unit_enabled` | `systemctl --user` enable/start result and expected unit identity | plan journal; diagnostic bundle |
| `backend_ready` | Port/bind probe, readiness probe, and representative backend call where available | verification trace; backend manifest |
| `registered` | ContextForge gateway/server readback by canonical name and expected tags/scope | verification trace; ContextForge evidence IDs |
| `client_config_written` | Owned project-local config block written and parsed, or patch/user action recorded for unmanaged config | project state client binding; plan journal |
| `pending_restart` | Adapter reports restart needed with exact client, reason, and post-restart probe | project state open item |
| `verified` | Required backend, ContextForge, virtual-server, target-client, negative-policy, trust, and redaction probes pass | verification trace refs on service/client state |
| `degraded` | Previously verified layer failed or became stale, with failure class and repair plan | project state open item; trace or diagnostic ref |
| `failed` | Required transition failed and no automatic resume is valid | project state open item; plan journal |
| `removed` | Approved removal/disable workflow completed and no exposed client path remains unless intentionally retained | plan journal; verification trace |

State transitions must be written in the apply journal first and reflected in
project state only after the evidence for that transition is available. A
service manifest may describe intended lifecycle targets, but project state and
verification traces own the current initialization status.

Project state records both aggregate readiness and precise lifecycle. The
aggregate `provision_status` answers whether the service is generally
`none|pending|created|degraded|failed|removed|verified`; `lifecycle.current_state`
records the latest proven transition from the vocabulary above, with previous
state, allowed next states, transition journal ref, evidence refs, and recovery
outcome. Repair and resume logic must use the lifecycle object, journal entries,
and verification trace refs rather than inferring state from the aggregate
alone.

`systemctl --user is-active` is necessary but not sufficient. Runtime readiness
requires endpoint probes and representative tool calls through the relevant
backend, ContextForge virtual server, and target client path.

User-systemd units must have deterministic names, contextforge target
membership where appropriate, gateway dependency where needed, restart policy,
readiness probe, journal query instructions, stale-unit cleanup behavior, and
port reservation/conflict recovery. Crash loops, occupied ports, stale manifests,
and disabled units must produce typed open items and repair plans rather than
silent retries.

Port conflicts must be classified before unit start and again before
registration: same expected instance, another known ContextForge backend, stale
known process, or unexpected process. The control plane may choose an allowed
free alternate port only when the approved plan permits it. It must never kill
or reconfigure an unexpected process without separate approval. Port occupancy
is a stale-plan input.

Readiness requires a documented stability window and restart-counter threshold.
Unit identity must be checked against the backend manifest through fragment
path, `ExecStart`, environment path, and expected port. Repair actions should be
typed, for example regenerate unit, reassign port, create placeholder env,
install missing dependency through an approved workflow, refresh gateway, or
restart only.

`report_project_gaps` must be able to produce a redacted diagnostic bundle:

- project state and drift status.
- backend instance manifest.
- user-systemd unit state and relevant journal excerpts.
- port checks.
- ContextForge gateway/server/tool/resource/prompt registry rows.
- virtual-server tool list.
- direct backend `/mcp` and `/sse` probes where applicable.
- virtual server `/mcp` and `/sse` probes where applicable.
- representative tool call result.
- target-client list-tools and call-tool output.
- redacted plan/audit excerpts.

Verification is a matrix. A full service proof includes direct backend transport
where applicable, ContextForge gateway, ContextForge virtual server, virtual
tool list, actual tool call, target-client visible tool list, and target-client
tool call. Negative checks must cover denied roots, wrong project root, global
Serena/Codex exposure when prohibited, scope-changing tools, unauthorized
requests, stale IDs reconciled by canonical name, and missing restart.

Failure classification must distinguish at least missing secret, auth failure,
port conflict, unit crash, readiness failure, registry drift, tool-policy
failure, client trust, client restart, unmanaged config, and target-client
verification failure. These classes drive repair plans and prevent a missing
secret or stale restart from being misdiagnosed as generic backend instability.

Repair plans must be emitted for missing contract cards, failed semantic
tool-policy compilation, failed shared-service capsule verification, failed
client conformance pack checks, failed trust broker verification, failed
consent receipt scope validation, missing verification traces, and governance
reconciliation gaps.

### Client Abstraction And Verification

The architecture is client-agnostic, but runtime proof is client-specific.
Clients include Codex, Claude Code, Gemini CLI, OpenCode, Claude Desktop, and
future assistants. The control plane should model each through capability
metadata: config surface, direct HTTP support, stdio-wrapper requirement,
restart behavior, trust requirement, auth mechanism, list/call verification
commands, and known limitations.

Each target client used for proof must have a passing Client Adapter
Conformance Pack or an explicit blocking limitation in project state. The pack
is the compact versioned artifact that lets project-init, service adapters,
verification traces, and scenario tests agree on what the client can actually
consume.

A service is verified only for the intended target client whose visible MCP path
succeeds. A Codex proof does not verify Claude Code unless Claude Code is not an
intended consumer. If a config or trust change requires restart, project state
must remain pending with an explicit restart open item until the restarted
client-visible path succeeds.

Target clients are part of the approved plan digest. Adding or removing a target
client after approval makes the plan stale unless the change is itself covered
by a new approved plan. Backend or ContextForge verification can be green while
one target client is still pending; in that case the aggregate project cannot be
`initialized` if that client is an intended consumer.

**Trust Broker Abstraction**

The trust broker is not a privileged auto-grant service. It is a narrow
workflow abstraction that can inspect trust state, report the exact trust gap
and scope, request or record separate explicit approval when a trust action is
allowed, and verify that the target client actually loaded the trusted
project/config. The broker emits consent receipts for trust approval and
verification traces for trust consumption. Generic project-init approval must
never be treated as trust approval.

Codex is the first required trust-broker proof because the known local behavior
is that project-local `.codex/config.toml` is ignored until the root is trusted.
The Codex conformance pack must include this condition and must verify actual
config consumption after trust and restart requirements are satisfied.

### Client Adapter Contract

Each client adapter must define a Client Adapter Conformance Pack with:

- client name and supported versions when known.
- config surface and whether project-local config is supported.
- owned-block detection and unmanaged/conflict behavior.
- direct HTTP support and header/auth support.
- stdio-wrapper requirement.
- trust path and whether global trust is required.
- token/env handling path.
- restart detection and restart instruction.
- list-tools probe.
- call-tool probe.
- stale-config detection.
- token-source constraints and leak checks.
- negative tool-policy visibility checks.
- expected failure modes and failure classification.
- whether a restart-required state blocks `initialized`.
- known unsupported behaviors and whether they are blocking for v1.

A client adapter cannot be used as a target-client proof until its conformance
pack passes. If the adapter is incomplete, the limitation must be represented as
a `client_conformance` open item rather than hidden behind a service failure.

Owned-block classification must distinguish `owned`, `legacy_owned`,
`user_modified_owned`, `unmanaged_same_name`, `unsupported_schema`, and
`absent`. Direct writes are allowed only for supported owned blocks after
approval. Unmanaged, user-modified, unsupported, or global config surfaces
require a patch plan, replacement choice, or user action before mutation.
Secret-bearing backups or rollback material must stay in ignored restrictive
paths and be represented in normal audit only by redacted hashes.

Restart-required outputs must create a structured `open_items` entry containing
client, reason, restart instruction, post-restart verification, and blocking
services. The control plane must not mark the service verified until the
specified client-visible path succeeds after restart.

User confirmation that a client was restarted is useful evidence but never
sufficient. The adapter must prove the restarted client consumed the intended
configuration generation and the intended ContextForge virtual server. Where
possible, adapters should expose process-identity, config-generation, and
restart-observability probes.

### Language Profiles

v1 language profiles live in ContextForge. The initial language set is:

- Python
- TypeScript/JavaScript
- Rust
- Bash

Language profiles include normalized language id, display name, detection
markers/extensions, service requirements, baseline probes, optional
capabilities, curated backend options, install policy, and verification
evidence.

The v1 normalized IDs are `python`, `typescript_javascript`, `rust`, and
`bash`. A project may match multiple profiles; detection confidence and the
user-selected primary profile must be recorded separately from any service
acceptance decision. Changing the selected profile later is a new approved plan,
not a silent state mutation.

Language profiles are data-driven ContextForge resource records. General
language metadata, such as Python or TypeScript detection, belongs in the
language profile. Service-specific requirements, such as Serena backend choices
through a particular LSP integration, belong in the service adapter's requirement
metadata and must consume the language profile rather than becoming the policy
source.

v1 includes approved install workflows for missing tooling in this language set.
Install workflows are explicit, curated, instance-local by default, and require
approval before execution. Missing backend/tooling states must produce a plan
and choices, not silent installation. Global language tooling mutation is not
the default.

Approved install workflows must include curated source allowlists, provenance in
the audit record, expected install scope, no global mutation by default, and
language-specific verification probes. Until the core state/plan/audit/control
service is stable, implementation may treat install workflows as plan-only
unless the user explicitly approves execution.

Empty-project verification must not create arbitrary source files without an
approved probe-artifact policy. If a baseline probe requires temporary files,
the plan must name their path, cleanup behavior, Git-ignore status, consent
class, and whether failure to create them blocks verification. Bash profiles may
define advisory probes where the ecosystem does not provide a strong blocking
LSP signal; Python, TypeScript/JavaScript, and Rust profiles should define
blocking baseline probes when their selected service requires language tooling.

Language profile choices appear in service binding contract cards for services
that consume language tooling. Language-profile verification emits
verification traces. Language-dependent scenario fixtures must link to
language-profile requirement IDs. Empty-project probe-artifact policy must be
represented in both the requirement scenario and the verification trace.

### Governance And Service Memory

Governance ledgers remain authoritative for decisions, open questions, parked
intentions, consent, and project policy. `mentality` remains the governance MCP
service for those ledgers.

Serena memory is not special. It is one instance of a generic
`service_memory_provider` capability. Service-local memories may store working
notes, recall hints, code-navigation context, and references to governance IDs.
They may propose governance changes or flag possible conflicts, but they must
not silently settle decisions, open questions, parked intentions, consent, or
project policy.

v1 memory/governance integration stops at references and proposals. Generated
read-only governance projections into memory-capable services are out of scope
for v1 and may be revisited if real use shows a deeper need. Bidirectional sync
is out of scope. If service-local memory conflicts with governance, v1 flags the
conflict and continues using the governance ledger as authority.

Minimal `service_memory_provider` metadata must include:

- provider name and service binding.
- provider scope: project, repository, credential, session, or host.
- durability and storage location class.
- supported operations: list, read, write, update, delete, rename, or none.
- allowed record classes: working note, recall hint, code-navigation note,
  governance reference, governance proposal.
- governance reference format and allowed ledger ID prefixes.
- conflict flag behavior.
- verification probe.
- whether writes require approval.

**Governance Reconciliation Pack**

Before implementation begins, the project should generate a non-mutating
governance reconciliation pack. The pack lists RFC decisions not represented in
`DECISIONS.md`, open questions the RFC has answered or narrowed, abeyant
intentions that should point to the RFC, conflicts between service-memory notes
and governance ledgers, and suggested governance CRUD operations. It must not
edit ledgers directly, bypass `scripts/governance_crud.py`, or bypass the
`mentality` governance service. Accepted updates flow through the repo's normal
governance process.

### Auth Profiles

Active v1 profile: `loopback_authenticated_http`.

- Default gateway and local service exposure bind to loopback.
- Direct-capable clients use authenticated HTTP with bearer headers.
- Stdio-only clients use ContextForge wrapper scripts.
- Assistant clients use one local non-admin ContextForge client token for v1.
- Service-level tokens, downstream credentials, and credential passthrough are
  handled by ContextForge wherever possible.
- Token storage, rotation, and revocation are explicit approved workflows.

The local v1 assistant token is least-privilege. It may call the approved
virtual-server tool surfaces and control-plane workflow tools needed for the
active project, but it must not grant raw ContextForge admin rights, token
administration, catalog CRUD, unapproved plan apply, unrelated virtual-server
access, or service-management mutation. The conformance and security test suite
must include negative probes proving those operations fail under the local
assistant token.

Because v1 may use one shared local token, `source_client` alone is not a strong
authorization factor. Conformance packs, consent receipts, plan journals, and
authorization checks must record `source_client_auth_strength`:

- `asserted`: the caller supplied a client label, but the server cannot prove it.
- `shared_token`: the caller authenticated with the shared local token.
- `wrapper_bound`: a ContextForge wrapper or local workflow session bound the
  request to a specific client/config surface.
- `per_client_token`: the request used a client-specific token.

Sensitive mutating classes may require `wrapper_bound` or `per_client_token`.
When only `shared_token` is available, source-client mismatch is audit evidence
and a replay risk signal, but not sufficient proof of caller identity by itself.

The local client token should be a cataloged ContextForge token if that path is
verified for virtual MCP endpoints. If implementation must temporarily use an
interactive/session JWT or wrapper-obtained token, the RFC implementation notes
must document the reason, storage path, rotation behavior, and replacement path.
Token files must be mode `0600` or stricter. Tokens must not appear in command
arguments, normal logs, project state, plan payloads, audit records, diagnostic
bundles, or catalog output.

Dormant documented profile: `remote_ready`.

The design also includes a non-default experimental remote exposure workflow.
It must be opt-in and require explicit approval with TLS, origin policy, token
scope, bind-address, and exposed-service review before activation. Full
multi-user remote operation is still not a v1 goal.

Experimental remote exposure must use separate remote token material and a
separate revocation profile. It must not blindly reuse the local shared client
token. Remote plans must include bind-address probes, origin and TLS checks,
scoped-token review, exposed-service review, and rollback instructions.
Remote exposure defaults to an allowlist of virtual servers and services. It
must deny control-plane mutation tools, raw catalog/admin tools,
service-management mutation, trust changes, token workflows, and secret-value
workflows unless a later RFC explicitly approves a narrower remote model with
separate tokens, consent, and negative exposure tests.

Auth profile changes, token material changes, wrapper behavior, global trust,
and remote exposure must be evidenced through the shared contract artifacts:
consent receipts for token and trust approval, verification traces for
token-source and leak checks, client adapter conformance packs for wrapper
behavior, and remote exposure traces for the non-default experimental workflow.

### Security And Token Handling Requirements

- Local service exposure must default to loopback and be verified by bind-address
  probes.
- Host-wide read-only catalog responses must redact auth, secret, env, and token
  material.
- Placeholder env files may be created only in ignored paths and must use
  restrictive permissions.
- Wrapper scripts must avoid leaking bearer tokens through argv, stdout, stderr,
  shell traces, process titles, or normal logs.
- Wrapper adapters must declare token-source metadata and run leak checks against
  command arguments, process titles where feasible, stdout/stderr, wrapper logs,
  diagnostics, and audit excerpts.
- Allowed token-source classes are restrictive local token files, ContextForge
  token provider APIs, wrapper-bound brokered tokens, and explicitly approved
  remote-token stores. Inherited environment variables are disallowed for
  long-lived client tokens unless an RFC-approved leak model and probes show they
  cannot appear in process inspection, wrapper logs, diagnostics, or child
  process environments.
- Token creation, rotation, and revocation require tests.
- ContextForge client auth and downstream service credentials are distinct
  authority domains. A valid local ContextForge token does not imply downstream
  API keys are present, scoped, or approved.
- Operation authorization must be explicit across read, plan, project-local
  write, service provision, catalog mutation, global trust, placeholder secret
  file creation, actual secret value write, token material change, user-global
  config write, and remote network exposure.
- Least-privilege token tests must prove the local assistant token cannot
  perform catalog CRUD, token/admin operations, unapproved apply, unrelated
  virtual-server calls, or remote-only workflows.
- Remote exposure tests must prove only allowlisted services/tools are exposed
  and that control-plane mutation, catalog/admin, trust, token, and secret-value
  workflows are denied by default.
- Prompt/resource writes must continue to preflight ContextForge content
  security; known false positives should be shaped locally rather than disabling
  gateway-wide validation.

### Initialization Variable Inventory

Project initialization behavior is determined by a large set of variables. The
control service should inspect, normalize, and expose these variables explicitly
before planning.

**Project Identity And Scope**

- Current working directory, canonical realpath, symlink status, mount boundary,
  and whether the path is a denied root.
- Project root detection source: Git root, marker file, empty workspace
  directory, explicit user value, or client-provided root.
- Project root hash and whether it matches existing project state,
  server-instance manifests, client config, and ContextForge records.
- Repository state: clean/dirty worktree, branch, protected branch policy, hooks
  path, ignored paths, and whether project state is tracked or ignored.
- Project layout maturity: empty directory, scaffolded repo, mature repo,
  monorepo, nested project, worktree, archive copy, or generated disposable
  project.
- Parent/child project relationships and related service instances discovered
  for ancestor or descendant roots.

**Existing Project State**

- Presence, schema version, permissions, owner, parse validity, and canonical
  root match for `.project/context_forge_state.json`.
- Legacy `.env` project-init keys, legacy state conflicts, and migration
  disposition.
- Project status, sticky decisions, reopened decisions, disabled state, and
  accepted-but-unverified services.
- Open items by type: trust, restart, secret, verification, drift, language,
  service, migration, or catalog candidate.
- Drift status: stale IDs, missing names, mismatched roots, missing units,
  changed client config, changed virtual-server tools, and changed auth path.
- Last plan, last audit record, revision, actor/source, and whether another
  plan/apply is already in progress.

**Client And Entry Context**

- Initiating client: Codex, Claude Code, Gemini CLI, OpenCode, Claude Desktop,
  another assistant, or direct operator script.
- Intended target clients, which may differ from the initiating client.
- Client config capabilities: project-local config, user-global config, direct
  HTTP support, headers, stdio-only wrapper, env interpolation, and disabled
  entries.
- Client trust state and whether global trust is required before project-local
  config is loaded.
- Client restart behavior: hot reload, full app restart, terminal restart,
  daemon restart, unknown, or not required.
- Client-visible MCP status: server listed, auth failed, tool list stale,
  tool-call failed, disabled, or absent.
- Client version or schema differences that affect config support.

**ContextForge Runtime And Catalog**

- Gateway reachability, auth state, ContextForge version, configured base URL,
  SSL mode, allowed origins, and bind address.
- API token/session token availability, token type, token storage path,
  permissions, rotation age, and revocation status.
- Registry state: gateways, virtual servers, tools, prompts, resources, tokens,
  associations, active/inactive rows, and stale records.
- Whether service identity exists by canonical name, by only stale ID, by
  duplicate name, or not at all.
- Prompt/resource validation behavior and content-security false positives.
- Host-wide catalog visibility policy and redaction requirements.

**Backend And Transport**

- Backend class: native streamable HTTP, native SSE, stdio, REST/OpenAPI,
  hosted remote service, local daemon, or package bridge.
- Transport requirement gaps: missing HTTP, missing SSE, missing auth headers,
  unsupported client transport, or bridge needed.
- Backend home presence under `server-instances/<service-slug>/`, manifest
  validity, env placeholders, run scripts, probes, logs, and ignored runtime
  state.
- Port allocation, port conflicts, existing process owner, bind address, and
  firewall/network exposure.
- User-systemd unit presence, enabled state, active state, target membership,
  crash loops, stale units, and journal diagnostics.
- Backend credential scope, resource scope, project scope, and whether it can be
  safely shared across projects.

**Service Selection And Catalog Candidates**

- Requested service set, default recommendations, sticky declines, deferred
  choices, disabled services, and existing accepted services.
- Newly discovered backend candidates and whether they are host-wide,
  project-scoped, credential-scoped, or caller-scoped.
- Deduplication inputs: package/server identity, runtime scope, credential
  scope, resource scope, transport scope, and exposed resources.
- Whether catalog promotion is requested explicitly or only surfaced as a
  candidate.
- Whether service mutation belongs to normal project init or the
  service-management skill.

**Language And Tooling**

- Detected languages, configured languages, empty-project language choice, and
  user-selected language profile.
- Language profile availability in ContextForge and whether a service consumes
  that profile or hardcodes service-specific tooling.
- Baseline probes, optional capabilities, missing toolchains, install scope,
  instance-local paths, host tool visibility, and backend caveats.
- Whether install workflows are plan-only, approved for execution, or blocked by
  missing curated provider metadata.

**Tool Policy And Scope Safety**

- Original tool names, exposed tool names, and gateway refresh behavior.
- Scope-changing tools, credential-changing tools, destructive tools,
  approval-gated tools, and tools requiring project root constraints.
- Virtual-server association state and whether excluded tools reappear after
  gateway refresh.
- Tool-bound prompt/resource guidance and whether documentation passes
  ContextForge content-security validation.

**Consent, Audit, And Mutation**

- Consent classes required by the plan.
- Exact mutation targets: project state, project-local client config, global
  trust, user-global config, systemd units, server-instances manifests,
  ContextForge registry rows, env placeholders, or actual secret values.
- Approval evidence, plan digest, plan staleness inputs, current locks, and
  interruption/retry state.
- Audit record paths, redaction status, pre-apply snapshots, step status,
  rollback/repair mode, and verification evidence.
- Whether mutation is direct write, patch plan, user action, or blocked.

**Secrets And Auth Material**

- Missing keys, placeholder env files, actual secret value workflows, ignored
  paths, file modes, and owner.
- Whether tokens or secrets appear in argv, env, logs, audit records,
  diagnostics, catalog output, or project state.
- Downstream service credential type and whether ContextForge can scope or
  broker it.
- Token blast radius: local shared client token, service-level token,
  project-specific credential, remote experimental token, or stale token.

**Verification And Recovery**

- Required verification matrix: backend transport, ContextForge gateway,
  virtual server `/mcp`, virtual server `/sse` where expected, tool list, tool
  call, target-client list-tools, and target-client call-tool.
- Negative checks: denied root, wrong root, global exposure where prohibited,
  scope-changing tools, unauthorized requests, stale IDs, and missing restart.
- Partial failure point and whether resume, forward repair, rollback, or manual
  recovery is safe.
- Whether `initialized` is blocked by pending restart, trust, secret, language,
  drift, service, or verification open items.

**Deployment Profile**

- Active profile: loopback authenticated HTTP, stdio wrapper, or experimental
  remote exposure.
- Remote exposure inputs: bind address, TLS material, origin policy, remote
  token profile, allowed services, rollback plan, and external reachability.
- Whether local assumptions, especially shared token and loopback-only trust,
  accidentally leak into remote mode.

### Narrative Initialization Use Cases

1. **Clean Codex Project With Existing Gateway.** A mature Python repo under
   `/home/dgk/workspace` has no project state. Codex is the initiating and
   target client. ContextForge is healthy, Serena is not present, language is
   detected, and Codex already trusts the project. The control plane proposes
   Serena, writes JSON state and owned `.codex/config.toml`, provisions the
   backend, verifies through Codex app-server, and marks the project
   `initialized`.

2. **Untrusted Codex Project.** A TypeScript project accepts Serena, but Codex
   global trust is missing. Project-local config can be written after approval,
   but target-client verification cannot pass. State records the service as
   pending, adds a `trust` open item, asks for separate trust approval, and
   refuses to mark `initialized` until Codex loads the config and verification
   succeeds.

3. **Empty Workspace Directory.** The user opens a new empty directory. No
   language can be inferred. The control plane treats the root as valid but
   blocks Serena provisioning until the user selects Python, TypeScript/
   JavaScript, Rust, or Bash. A sticky decline of Serena suppresses future
   prompts without creating a backend.

4. **Nested Project Inside Existing Serena Parent.** A child workspace is opened
   below a parent that already has a Serena instance. The parent instance appears
   as related diagnostics only. The child must get its own project-state
   decision and must not reuse the parent backend unless a future explicit
   sharing policy exists.

5. **Symlinked Project Root.** The client starts in a symlink path that resolves
   to a safe workspace child. The control plane stores the canonical realpath,
   rejects any state whose root hash matches the symlink text instead of the
   realpath, and verifies that backend manifests and client config point at the
   canonical root.

6. **Denied Root Attempt.** The assistant starts from `/home/dgk` or
   `/home/dgk/workspace`. The control plane refuses project initialization,
   returns a denied-root diagnostic, and performs no state write, service
   provisioning, or client config mutation.

7. **Legacy `.env` Accepted State.** A project has old `.env` keys saying Serena
   was accepted, but no JSON state. The control plane records legacy state as
   seen, imports or reports it by explicit migration rule, writes migration
   evidence, and avoids re-asking if the old accepted state maps cleanly to live
   verified service evidence.

8. **Legacy `.env` Conflict.** `.env` says Serena was declined, while an existing
   server-instance manifest and project-local config indicate Serena was
   created. Because `.env` is not authoritative, the control plane records a
   migration conflict, surfaces an open item, and requires user resolution before
   changing service state.

9. **Stale ContextForge IDs But Stable Names.** Project state has old gateway
   and server IDs, but the canonical virtual server name still exists with new
   IDs after registry recreation. The control plane reconciles by canonical name,
   updates evidence, records stale IDs in drift, and does not fail solely because
   IDs changed.

10. **Canonical Name Missing But ID Present.** Project state references a
    virtual server name that no longer exists, while a stale ID points to a
    different service. The control plane treats this as blocking drift, refuses
    to verify, and proposes repair through ContextForge APIs rather than trusting
    the stale ID.

11. **Gateway Refresh Reintroduces Scope-Changing Tool.** Serena registration
    was previously filtered, but a gateway refresh discovers `activate_project`
    again. Verification checks `/servers/{id}/tools`, detects the scope-changing
    tool, blocks `initialized`, and reapplies virtual-server associated-tool
    filtering through the approved repair path.

12. **Client Restart Required.** Claude Code or another target client receives a
    config update but cannot see it until restart. The control plane records
    `pending_restart`, names the exact client and reason, gives the restart
    instruction, and waits for post-restart list/call verification before
    marking the service verified.

13. **Wrapper-Based Client With Token Leak Risk.** Claude Desktop requires a
    stdio wrapper. The plan checks that the wrapper obtains tokens from an
    ignored restrictive path, not argv. Diagnostics redact token material. If
    token material appears in command arguments or logs, the plan fails security
    verification.

14. **Port Collision During Project-Scoped Backend Setup.** The preferred port
    is already owned by another service. The plan records the conflict, selects
    an allowed free port if policy permits, updates the backend manifest, and
    verifies the new port. If the owner is an unexpected process, it asks before
    changing anything.

15. **Crash-Looping Backend Unit.** A user-systemd unit exists and is enabled
    but repeatedly crashes. `systemctl --user is-active` is not enough; the
    readiness probe fails, journal excerpts are captured in a redacted
    diagnostic bundle, and the service remains `failed` or `degraded` with a
    repair plan.

16. **Unmanaged Existing Client Config.** The project already has a
    `[mcp_servers.serena]` block not owned by ContextForge project init. The
    control service refuses direct merge, returns a patch plan or replacement
    choice, and requires explicit approval before overwriting the unmanaged
    block.

17. **Catalog Candidate Found During Init.** A project config references an MCP
    backend not in the canonical catalog. Normal project-init may surface it as
    a candidate but cannot promote it. If the user says "add it," the assistant
    invokes the service-management skill, produces a separate non-mutating
    catalog plan, and asks for approval before host-wide mutation.

18. **Missing Secret For Accepted Service.** The user accepts a service requiring
    an API key. The control plane may create an ignored placeholder env file and
    report missing keys, but it does not write actual secret values in normal
    init. The service stays pending with a `secret` open item until a separate
    secret-entry workflow or manual edit provides the value and verification
    passes.

19. **Remote Experimental Exposure Requested.** The user asks to expose a
    service beyond loopback. The local shared token is rejected for remote use.
    A remote plan requires TLS, bind-address, origin policy, separate remote
    token material, scoped-service review, and rollback instructions before any
    network exposure changes.

20. **Concurrent Initializers Race.** Codex and another assistant initialize the
    same project at nearly the same time. Project-state locking serializes
    writes. The second actor detects a newer revision or active plan, rejects
    stale plan application, refreshes context, and either resumes the existing
    approved plan or asks for a new approval.

### Scenario Simulation Synthesis

The initialization scenarios were distributed into seven thematic simulation
tracks. The normative requirements above fold in the resulting constraints; the
track notes below preserve the simulation reasoning that motivated them,
including expected state transitions, evidence, audit records, and recovery
behavior implementation agents must support.

#### Track A: Root, State, Migration, And Concurrency

Assigned scenarios: 4, 5, 6, 7, 8, and 20.

**Scenario 4: Nested Project Inside Existing Serena Parent**

Initial conditions: a child project is opened under a parent root that already
has a Serena backend, virtual server, project-local config, and verified state.
The child has no JSON project state.

Expected transitions: child starts `uninitialized`; parent service evidence is
reported as related diagnostics only; child service decisions remain `unasked`
until the user approves a child-specific plan. If approved, the child moves
`in_progress -> initialized` only after child-root-specific backend, virtual
server, tool-policy, and target-client verification pass.

Success path: the control plane records the child canonical realpath and root
hash, creates or binds only child-scoped resources, and verifies that no backend
manifest, client config, or ContextForge metadata points to the parent root.

Failure branches: parent instance is accidentally reused; root detection chooses
the parent Git root; target-client tool calls operate on parent files; or the
child later becomes a separate Git root after initialization. These produce
blocking `verification` or `drift` items, not silent reuse.

Evidence and audit: diagnostics may include parent service names and root
hashes, but project state stores only the child root as authority. Audit records
must show why parent evidence was excluded from verification.

RFC implication: root identity checks must compare project state, backend
manifest, client config, ContextForge metadata, and representative tool-call
results against the exact canonical root.

**Scenario 5: Symlinked Project Root**

Initial conditions: the client starts in a symlink path that resolves to an
allowed workspace child. Existing config may refer to either the symlink text or
the realpath.

Expected transitions: root normalization occurs before planning; state is
created only for the canonical realpath. A plan based on the symlink string is
stale and must be rejected or regenerated.

Success path: state, backend manifests, ContextForge tags/resources, and client
config all converge on the canonical root. The user may see the display path,
but authority uses the resolved root and root hash.

Failure branches: symlink target changes between plan and apply; symlink points
outside allowed roots; two symlink paths race to create duplicate service
bindings; or a target-client reports the symlink path while backend tools operate
on the realpath. These become `drift` or denied-root failures.

Evidence and audit: pre-apply snapshots must include display path, realpath,
root hash, and symlink resolution result. Post-apply verification must prove the
backend operates on the canonical root.

RFC implication: plan digests must include canonical-root inputs, not just the
user-visible path.

**Scenario 6: Denied Root Attempt**

Initial conditions: the initiating client is rooted at `/`, the user home, or
`/home/dgk/workspace`.

Expected transitions: no project state is written. No service decision is
recorded. The control service returns a denied-root diagnostic and allowed next
actions, such as choosing a concrete child project.

Success path: the workflow stops before mutation. A later invocation from a
specific child root starts a fresh plan.

Failure branches: a generic workspace root receives a project state file; a
host-wide virtual server is created; or trust/config mutation occurs before root
validation. These are security bugs.

Evidence and audit: denied-root checks may produce a diagnostic event, but no
approved mutation journal. If recorded, the diagnostic must be outside project
state because no valid project root exists.

RFC implication: root validation is a hard precondition for project state,
planning, provisioning, and verification. Host-wide read-only catalog views are
the only permitted control-plane behavior without a project root.

**Scenario 7: Legacy `.env` Accepted State**

Initial conditions: legacy `.env` keys indicate Serena was accepted and maybe
created; JSON state is missing.

Expected transitions: control plane reads legacy keys as migration input, not
authority. If keys, backend manifest, ContextForge names, client config, and
target-client evidence agree, migration records disposition `imported` and
writes JSON with evidence. Otherwise it creates a `migration` open item.

Success path: user is not re-prompted for a cleanly imported accepted decision,
but `initialized` still requires current live verification.

Failure branches: `.env` points to missing service rows; backend exists but
client-visible verification fails; accepted state lacks language profile; or
legacy values contain paths that no longer match the canonical root.

Evidence and audit: state records legacy digest, imported fields, source path,
and live verification evidence. Secret-bearing legacy values are never copied
into JSON or audit.

RFC implication: migration must be treated as a typed plan step with its own
evidence and conflict modes, not an implicit fallback parser.

**Scenario 8: Legacy `.env` Conflict**

Initial conditions: `.env` says Serena declined while server-instance manifests,
project config, or ContextForge records indicate Serena was created or verified.

Expected transitions: state remains `in_progress` or `uninitialized` with a
blocking `migration` item until user resolution. The control plane does not
delete or create resources while authority is conflicted.

Success path: user chooses whether to keep the service, disable it, remove
project binding, or rerun verification. The chosen resolution becomes a fresh
decision with approval evidence.

Failure branches: `.env` silently overrides JSON or live evidence; a sticky
decline deletes a working service without approval; or an old accepted value
reopens a sticky decline.

Evidence and audit: the conflict record must include redacted legacy digest,
observed canonical names, owned config markers, backend manifest root, and
available client-visible evidence.

RFC implication: sticky decisions are authoritative only once represented in
JSON state or newly approved during migration.

**Scenario 20: Concurrent Initializers Race**

Initial conditions: two assistant clients or operator scripts plan against the
same project revision and both try to initialize.

Expected transitions: a project-state lock serializes mutation. The first apply
creates a plan journal and increments revision. The second detects the newer
revision, rejects stale apply, and refreshes before resuming or requesting new
approval.

Success path: duplicate backend homes, duplicate virtual servers, and competing
client config blocks are avoided. If the second actor is compatible with the
active plan, it can observe or resume only after lock release and plan digest
validation.

Failure branches: a crash leaves a stale lock; both actors allocate different
ports; one writes client config while the other changes service names; or an
approved plan is replayed after state changed. These require stale-lock
detection, idempotency checks, and typed repair outcomes.

Evidence and audit: lock acquisition/release, plan ID, state revision, actor,
step journal, and stale-plan rejection are recorded in ignored `run/` state.

RFC implication: every mutating plan must declare stale inputs and must be
rechecked immediately before apply.

#### Track B: Clean And Empty Project Paths

Assigned scenarios: 1 and 3.

**Scenario 1: Clean Codex Project With Existing Gateway**

Initial conditions: mature Python project, no JSON state, ContextForge healthy,
Codex trusted, Codex is both initiating and target client, and language
detection is confident.

Expected transitions: `uninitialized -> in_progress -> initialized`; Serena and
the second non-Serena proof service move `none -> pending -> created ->
verified`; target client `codex` moves to `verified` only after Codex-visible
list-tools and call-tool probes.

Success path: both services are represented by canonical names and current IDs
as evidence; tool-policy verification proves scope-changing tools are absent;
the second proof demonstrates the generic project-scoped service adapter rather
than a Serena-only path.

Failure branches: ContextForge registry rows exist but virtual-server tools are
stale; Codex sees old config until restart; representative calls fail; or the
second proof is so generic that it does not test project scope.

Evidence and audit: state file, audit plan, backend readiness, ContextForge
gateway/server rows, virtual-server tool list, negative tool-filter check, Codex
list-tools, and Codex call-tool output.

RFC implication: `initialized` must require every accepted service to verify
through the intended client, not merely through ContextForge.

**Scenario 3: Empty Workspace Directory**

Initial conditions: valid empty root with no language markers and no JSON state.
Codex trust may be unknown.

Expected transitions: control plane can plan project state, but Serena remains
blocked by `language` until the user confirms Python, TypeScript/JavaScript,
Rust, or Bash. Sticky decline suppresses Serena prompts without provisioning.

Success path: after language choice and service approval, provisioning proceeds
normally and target-client verification gates initialization.

Failure branches: arbitrary default to Python; README text misclassified as
language evidence; second proof verifies while accepted Serena remains blocked;
or later project files contradict the selected profile.

Evidence and audit: language decision record, no backend before language
approval, open-item resolution, target-client proof, and audit showing no silent
default.

RFC implication: an accepted service blocked on language cannot be ignored for
overall project initialization.

#### Track C: Client Trust, Restart, And Existing Config

Assigned scenarios: 2, 12, and 16.

**Scenario 2: Untrusted Codex Project**

Initial conditions: project accepts Serena, but Codex global trust is missing.

Expected transitions: service may reach `client_config_written`, then blocks at
`pending_trust`. After separate trust approval and any required restart, it can
move to `verified`.

Success path: trust approval names the exact project/client scope, Codex loads
the project-local config, and Codex-visible list-tools and call-tool proof pass.

Failure branches: project-local config is correct but ignored; stale global
config exposes a different `serena`; another client verifies but Codex remains
unverified; or trust approval is conflated with service approval.

Evidence and audit: pre/post client config parse, trust status, trust approval,
restart item if applicable, and Codex-specific proof. Gateway health is not
enough.

RFC implication: trust and restart are separate blocking open items, and client
proof is not transferable across target clients.

**Scenario 12: Client Restart Required**

Initial conditions: client config has been written, but the target client loads
MCP config only at startup, session start, or app restart.

Expected transitions: `client_config_written -> pending_restart -> verified`;
if the restarted client still cannot list/call tools, service becomes `failed`
or `degraded`.

Success path: state records exact client, restart reason, instruction, blocking
services, and post-restart verification requirement.

Failure branches: user restarts a shell but not the app; wrapper caches old
token/env; client version hot-reloads in some cases but not others; or stale
tool lists are mistaken for current proof.

Evidence and audit: adapter-specific post-restart list-tools and call-tool
outputs, restart timestamp or user confirmation, and stale-config detection.

RFC implication: client adapters must define restart semantics precisely enough
for implementation agents to prompt the user and resume verification.

**Scenario 16: Unmanaged Existing Client Config**

Initial conditions: target client already has a `serena` block not owned by the
ContextForge project-init workflow.

Expected transitions: service blocks at `config_conflict` until the user
approves a patch or replacement. Owned blocks can be written directly after
approval; unmanaged blocks cannot.

Success path: control plane produces a non-mutating patch plan, preserves
unrelated settings, writes only after approval, parses the result, prompts for
restart if needed, and verifies through the target client.

Failure branches: JSON formats do not support comments/markers; aliases collide
with a legitimate non-ContextForge service; replacement destroys user env paths;
or an existing direct global Serena service is counted as project-scoped proof.

Evidence and audit: pre-apply config snapshot, owned/conflict classification,
approved diff, post-write parse, and client-visible proof.

RFC implication: client adapter metadata must include owned-block detection,
unsupported schema behavior, and replacement/patch safety constraints.

#### Track D: Registry Drift, Tool Policy, And Catalog Candidates

Assigned scenarios: 9, 10, 11, and 17.

**Scenario 9: Stale ContextForge IDs But Stable Names**

Initial conditions: project state canonical names still exist, but stored
gateway/server IDs are stale after ContextForge registry recreation.

Expected transitions: control plane reconciles by canonical name, validates
root hash/tags/backend manifest, updates evidence with new IDs, and records old
IDs under drift. `initialized` may remain valid if all verification passes.

Failure branches: duplicate canonical names; same name with wrong root hash;
server reconciles but gateway does not; or tools differ after recreation.

Evidence and audit: current ContextForge rows by name, old/new IDs, tool-list
proof, root-hash agreement, and target-client proof if any binding changed.

RFC implication: name/root-hash/tag agreement is a hard precondition before ID
readback counts.

**Scenario 10: Canonical Name Missing But ID Present**

Initial conditions: state references a missing canonical server name, while the
old ID resolves to an unrelated current service.

Expected transitions: control plane distrusts the ID, records blocking drift,
and proposes a repair plan through ContextForge APIs. It does not verify the
unrelated service.

Failure branches: implementation follows the stale ID; target-client config
still points at a missing server; or backend manifest is missing too.

Evidence and audit: missing-name proof, stale-ID subject mismatch, repair
choices, and post-repair ContextForge/client verification.

RFC implication: IDs are evidence only and must never override canonical name
and root identity.

**Scenario 11: Gateway Refresh Reintroduces Scope-Changing Tool**

Initial conditions: gateway refresh rediscovered a tool such as
`activate_project` that should not be exposed through the project virtual
server.

Expected transitions: service becomes unverified or degraded until associated
tools are repaired and readback proves the excluded tool is absent.

Failure branches: filtering by literal name misses renamed/prefixed tools;
server association update silently fails; target client caches an old tool list;
or original-name metadata is unavailable.

Evidence and audit: gateway tool list, tool risk classification, allowed tool
IDs, virtual-server tool readback, negative tool checks by original and exposed
name, and target-client list-tools proof.

RFC implication: tool policy must be semantic and verified after every refresh,
not merely a Serena-specific string exclusion.

**Scenario 17: Catalog Candidate Found During Init**

Initial conditions: a client config references an MCP backend absent from the
canonical ContextForge catalog.

Expected transitions: project init records a `catalog_candidate` item and
remains non-mutating. Catalog promotion starts only after explicit invocation of
the service-management skill and approval of its concrete plan.

Failure branches: candidate argv leaks secrets; candidate is duplicate under a
client-specific name; native transport is wrapped unnecessarily; or promotion is
bundled with normal project-init approval.

Evidence and audit: redacted candidate descriptor, dedupe keys, discovery
source, scope classification, proposed backend home, transport decision,
ContextForge API operations, and separate plan ID.

RFC implication: candidate summaries must be redacted and advisory until a
dedicated catalog-management workflow begins.

#### Track E: Backend Runtime, Ports, And Readiness

Assigned scenarios: 14 and 15.

**Scenario 14: Port Collision During Project-Scoped Backend Setup**

Initial conditions: the preferred backend port is already bound by another
process or another service instance.

Expected transitions: port conflict is detected before unit start. If policy
allows dynamic allocation, the plan selects an allowed free port, updates the
backend manifest and config, and verifies the chosen port. If owner identity is
unexpected, the plan blocks for user review.

Success path: chosen port is within allowed local range, binds to loopback, is
reflected in server-instance manifest, systemd unit, ContextForge gateway URL,
and diagnostics, and passes readiness probes.

Failure branches: time-of-check/time-of-use race; existing owner is an old stale
unit for the same service; chosen port binds to `0.0.0.0`; ContextForge gateway
keeps the old URL; or two concurrent initializers choose the same free port.

Evidence and audit: pre/post socket probes, process owner, chosen port,
manifest diff, unit status, gateway URL readback, endpoint readiness, and target
client proof.

RFC implication: port allocation is a mutating plan step with stale-input
checks, not a best-effort runtime detail.

**Scenario 15: Crash-Looping Backend Unit**

Initial conditions: user-systemd unit exists and may be enabled, but service
crashes repeatedly or never reaches MCP readiness.

Expected transitions: unit state alone cannot verify service. Service moves to
`failed` or `degraded` with `service` or `verification` open item and a repair
plan.

Success path: repair restarts or updates the unit only through an approved plan,
then readiness, ContextForge, virtual-server, and target-client probes pass.

Failure branches: `systemctl --user is-active` briefly returns active during a
crash loop; journal contains secrets; readiness endpoint starts before tools are
usable; or bridge process is healthy while upstream backend is not.

Evidence and audit: user-systemd status, restart count, redacted journal
excerpt, port probe, backend `/mcp` or `/sse` readiness, ContextForge gateway
health, representative call, and client-visible proof.

RFC implication: diagnostic bundles must redact logs and distinguish process
health, transport health, registry health, and semantic tool-call health.

#### Track F: Secrets, Auth, Wrappers, And Remote Exposure

Assigned scenarios: 13, 18, and 19.

**Scenario 13: Wrapper-Based Client With Token Leak Risk**

Initial conditions: Claude Desktop or another stdio-only client needs a wrapper
to reach ContextForge. v1 uses one local ContextForge client token for assistant
clients, with service-level tokens handled by ContextForge wherever possible.

Expected transitions: plan moves through `client_config_written` only if wrapper
configuration obtains the local token from an ignored restrictive file or
equivalent safe local provider. Security verification blocks service
verification if token material appears in argv, process titles, stdout, stderr,
shell traces, project state, audit, diagnostics, or catalog output.

Success path: wrapper command contains no secret literal; token file is ignored,
owned by the user, and mode `0600` or stricter; wrapper reads the token at
runtime; ContextForge accepts the request; representative target-client
list-tools and call-tool pass; diagnostics redact both local token and any
downstream credential evidence.

Failure branches: token is embedded in client JSON, command args, environment
visible to child process inspection, shell debug output, wrapper error logs, or
diagnostic bundle; wrapper caches a revoked token; token file is world-readable;
or the local shared token is reused for an experimental remote binding.

Evidence and audit: redacted client config snapshot, token-path metadata without
token value, file permission probe, process-argument inspection where feasible,
wrapper dry-run or smoke test, ContextForge auth failure/success classification,
and target-client proof. Audit records must record redaction status and token
storage class, never token content.

RFC implication: wrapper adapters need explicit token-source metadata,
argv/log/process-title leak tests, and revocation/stale-token failure handling.
The shared local token is acceptable only inside the local auth profile.

**Scenario 18: Missing Secret For Accepted Service**

Initial conditions: user accepts a service whose downstream backend requires an
API key or service credential. The service may have a valid ContextForge local
client token while downstream credentials are missing.

Expected transitions: service decision becomes `accepted`, provisioning may
create backend home and ignored placeholder env files after approval, then
blocks at `secret` open item. It cannot become `verified` until the separate
secret-entry/manual workflow supplies the value and representative downstream
tool-call verification passes.

Success path: control plane creates only redacted placeholders with restrictive
permissions, records required key names and non-secret instructions, reports
missing keys, and waits. After separate approval or manual edit, it verifies the
secret presence without exposing the value and runs backend, ContextForge, and
target-client probes.

Failure branches: actual secret is written during normal init; missing secret is
mistaken for service failure; placeholder path is tracked by Git; env template
contains an example real key; audit captures env contents; or downstream service
uses a host-global credential where the project expects project-local scope.

Evidence and audit: required secret names, placeholder path, file mode, ignored
path check, secret-presence probe that returns boolean/status only, redacted
backend logs, and failed/passed representative tool call. Audit may record
secret workflow approval and verifier digest, not value.

RFC implication: state must distinguish ContextForge client auth from
downstream service credentials. Missing secret should be a typed blocking item,
not generic backend failure.

**Scenario 19: Remote Experimental Exposure Requested**

Initial conditions: user explicitly asks to expose one or more services beyond
loopback. Current active profile is local loopback authenticated HTTP with a
single local token.

Expected transitions: normal initialization does not enter remote mode. A
separate remote exposure plan is required with consent class distinct from
project-local writes, catalog mutation, and global trust. The local shared token
is rejected for remote use. State remains local unless the user approves the
non-default experimental plan.

Success path: remote plan names bind address, TLS material, origin policy,
separate remote token profile, allowed services, excluded services/tools,
rollback instructions, external reachability checks, revocation steps, and
diagnostic redaction. Activation proceeds only after explicit approval and
post-activation probes verify intended exposure and non-exposure.

Failure branches: remote plan binds all interfaces with local token; exposes
project-scoped Serena or scope-changing tools broadly; reuses wrapper token
files; omits TLS/origin policy; creates firewall or service-manager state
without rollback; or marks remote readiness as normal v1 success.

Evidence and audit: pre-activation local bind probe, approved remote plan,
TLS/origin/token review, service allowlist, negative exposure checks,
successful external or remote-scope probe where available, revocation/rollback
record, and redacted audit. Normal project state should reference remote
exposure only as a separate approved profile or open item, not as default local
verification.

RFC implication: remote exposure must have its own consent class, token class,
verification matrix, and rollback journal. The dormant `remote_ready` profile is
documentation unless the user explicitly invokes the experimental workflow.

#### Track G: Cross-Scenario Adversarial Combinations

Assigned scenarios: all 20 in combination.

The highest-risk failures are combinations, not individual scenarios:

- A symlinked nested project with stale IDs can falsely reconcile to a parent
  service unless name, root hash, backend manifest, and target-client call
  evidence all agree.
- Missing Codex trust plus a stale global direct service can look like success
  unless verification proves the intended client consumed the intended
  ContextForge virtual server.
- A catalog candidate discovered during drift repair can cause accidental
  host-wide mutation unless project-init and service-management plans have
  separate consent classes and plan IDs.
- Port collision plus concurrent initialization can create duplicate backend
  homes unless port allocation is locked and stale-input checked.
- Wrapper token leakage plus remote experimental exposure can turn an acceptable
  local shared-token shortcut into a remote credential compromise unless remote
  token material is separate and local-token use is rejected.
- Legacy `.env` conflicts plus sticky declines can either resurrect unwanted
  services or delete working ones unless migration resolution is explicit.
- Gateway refresh plus client restart can leave the target client seeing old
  unsafe tool lists unless tool-policy readback and post-restart client-visible
  list-tools checks are both required.
- Malicious catalog metadata, prompt/resource text, service descriptions,
  client-config comments, or tool descriptions can attempt prompt injection
  against the planner, tester, or evaluator. Contract parsers and scenarios must
  treat such text as untrusted data, preserve redaction, and prove that it
  cannot authorize mutation, suppress negative checks, rewrite acceptance
  criteria, or cause the evaluator to ignore cited evidence.

Implementation agents should treat the following as invariants across all
combinations:

- No valid project root, no project mutation.
- No separate user approval, no global trust, catalog promotion, actual secret
  value write, or remote exposure.
- No client-visible proof, no verified target-client state.
- No canonical-name/root-hash agreement, no ID-based reconciliation.
- No redaction proof, no diagnostic or audit output containing secrets.
- No tool-policy negative check, no verified virtual server after refresh.
- No stale-plan check, no apply.

### Testing Methodology

Implementation should proceed as a test-driven effort with a multi-layered
testing strategy. The control plane is not only deterministic code; it is a
harness for agents that must infer authority, consent, scope, and verification
from partial evidence. Tests that exclude model inference can verify mechanisms
but cannot validate the central behavioral risks of this RFC.

The methodology therefore distinguishes deterministic tests from
inference-inclusive tests. Both are required.

**Layer 1: Deterministic Unit Tests**

Unit tests cover pure mechanics:

- project-state JSON Schema validation.
- contract artifact schema validation for service binding contract cards,
  shared-service capability capsules, semantic tool policies, consent receipts,
  verification traces, client adapter conformance packs, service-management
  handoffs, requirement scenarios, evaluator verdicts, evidence ledgers, and
  governance reconciliation packs.
- canonical root resolution, denied roots, symlink escapes, and root hashing.
- lock, stale-lock, and compare-and-swap revision behavior.
- legacy `.env` import and conflict classification.
- service instantiation class classification from explicit metadata.
- redaction and secret-exclusion helpers.
- consent-class partitioning and stale-plan digest computation.
- semantic tool-policy compilation from risk metadata to allowed tool IDs and
  negative checks.

These tests should fail fast and must not depend on a language model.

**Layer 2: Integration And Probe Tests**

Integration tests exercise real or fixture-backed operational surfaces:

- ContextForge gateway, server, tool, prompt, and resource readback.
- virtual-server associated-tool filtering after gateway refresh.
- backend manifest, user-systemd unit, port, and readiness checks.
- wrapper token-source and leak checks.
- consent receipt scope validation and verification trace emission.
- recovery-path fixtures for interrupted apply, partial registration, stale
  ports, unit failure, unmanaged config conflicts, and failed trace emission.
- shared-service capability capsule verification without backend duplication.
- client adapter config parsing, owned-block detection, restart classification,
  list-tools, and call-tool probes.
- client adapter conformance pack execution.
- `report_project_gaps` diagnostic bundles with redaction checks.

Where live ContextForge or client probes are expensive or unstable, fixture
mode is allowed, but at least one implementation lane must preserve real
client-visible probes for accepted proof paths.

**Layer 3: Scenario Fixtures**

Scenario tests model pre-test, during-test, and post-test conditions as first
class data. A scenario fixture should include:

- initial filesystem, project root, cwd, symlink state, and worktree state.
- initial ContextForge catalog, service manifests, ports, units, client config,
  trust state, secrets/placeholders, and project state.
- initiating user prompt and any scripted user replies or tool failures that
  occur during the test.
- allowed and forbidden mutations.
- required final state, required non-actions, expected open items, verification
  evidence, and acceptance criteria.
- deterministic assertions plus any inference rubric.

The 20 narrative initialization use cases and seven simulation tracks in this
RFC are seed scenarios for this fixture set.

**Requirement Registry And Coverage Matrix**

Requirement-linked scenarios require stable requirement IDs. The implementation
must create a versioned requirement registry before scenario execution. Minimal
registry entries use:

```json
{
  "requirement_id": "cfcp-req-0001",
  "source_section": "Acceptance Strategy",
  "summary": "short normative requirement",
  "evidence_types": ["unit_test", "integration_probe", "scenario_ledger", "governance_approval"],
  "required_layers": ["deterministic", "probe", "inference_inclusive"],
  "mvs_required": true,
  "deferrability": "non_deferrable|deferrable_with_governance_waiver|post_mvs",
  "acceptance_gate": "must_pass_mvs|must_pass_before_remote_or_expansion|deferrable_with_governance_waiver"
}
```

Every scenario, deterministic assertion, evaluator verdict, evidence ledger,
and final acceptance report must cite requirement IDs. The coverage matrix must
show, for each MVS requirement, the deterministic test, integration/probe, and
inference-inclusive scenario that satisfy it, or an approved governance waiver
where deferral is permitted. Requirements for stock ContextForge authority,
project-state ownership, consent/receipt boundaries, user-global trust,
secret-value exclusion, target-client verification, and tool-policy negative
checks are non-deferrable for MVS.

The Requirement-Linked Scenario DSL has this minimal v1 shape:

```json
{
  "scenario_id": "cfcp-scenario-001",
  "requirement_ids": [],
  "tested_agent_view": {
    "cwd": "/abs/root",
    "user_prompt": "prompt text",
    "available_tools": [],
    "visible_files": []
  },
  "hidden_initial_conditions": {
    "filesystem": {},
    "contextforge_catalog": {},
    "client_configs": {},
    "trust_state": {},
    "ports_units": {},
    "project_state": {}
  },
  "during_test_events": [
    {
      "event_id": "event-id",
      "actor": "user|tested_agent|tool|backend|evaluator|harness",
      "visible_to": ["tested_agent"],
      "payload": {},
      "hidden_state_delta": {},
      "tool_output_visibility": "tested_agent|evaluator_only|hidden",
      "evaluator_only": false
    }
  ],
  "allowed_mutations": [],
  "forbidden_mutations": [],
  "expected_outcomes": {
    "state": {},
    "open_items": [],
    "non_actions": [],
    "required_traces": [],
    "required_receipts": []
  },
  "deterministic_assertions": [],
  "inference_rubric": []
}
```

The DSL must keep the tested-agent view separate from hidden initial
conditions, evaluator-only requirements, and remediation context. Schema
validation must reject hidden/evaluator/remediation references in
`tested_agent_view`, tested-agent-visible event payloads, and tool outputs.

**Layer 4: Inference-Inclusive Agent Execution**

For behaviors whose correctness depends on assistant interpretation, the test
must run a headless assistant instance against the scenario. The tested
assistant is an inferential participant inside the scenario. It sees only the
role-appropriate initial conditions, tools, user prompts, and during-test
events. It must not be told that it is under test, what the hidden expected
outcome is, how it will be evaluated, or that a remediation cycle exists.

This blind execution is necessary for requirements such as:

- infer that client configs are discovery, not service identity.
- infer that `context7` or `ssh-tmux` should not be instantiated per project.
- infer that a parent Serena instance is diagnostic only.
- infer that stale IDs are evidence only.
- infer that trust, catalog promotion, secret values, and remote exposure require
  separate approvals.
- infer that target-client verification is not satisfied by backend health.

Deterministic assertions still inspect the resulting filesystem, service state,
tool calls, and audit records. The transcript is evidence, not the only result.

**Layer 5: Privileged Evaluation**

Inference-inclusive tests may be evaluated by an evaluation agent because the
evaluator occupies a different role from the tested assistant. The tested
assistant performs inference inside the scenario without knowledge of the test.
The evaluator performs inference outside the scenario with access to the
requirements, rubric, transcript, initial conditions, final state, and probe
evidence.

That privilege is intentional but bounded:

- The evaluator knows it is evaluating a transcript.
- The evaluator does not participate in the tested interaction.
- The evaluator must cite concrete transcript, file, probe, or state evidence.
- The evaluator must distinguish implementation failure, agent-inference
  failure, fixture failure, flaky environment, and requirement gap.
- The evaluator must return structured verdicts such as `pass`, `fail`,
  `inconclusive`, or `requirement_gap`.
- The evaluator may flag deficient requirements, but it must not silently weaken
  or rewrite acceptance criteria. Requirement changes require explicit review
  and an RFC/governance update.

The evaluator is not a substitute for deterministic checks. Machine-checkable
facts, especially secret leakage, file mutation, port state, registry rows, and
client-visible tool calls, must be checked directly.

The Evaluator Verdict Schema has this minimal v1 shape:

```json
{
  "verdict_id": "verdict-id",
  "schema_uri": "contextforge://control-plane/schemas/evaluator-verdict/v1",
  "created_at": "timestamp",
  "evaluator_run": {
    "model_or_agent": "id-or-null",
    "prompt_digest": "sha256-or-null"
  },
  "verdict": "pass|fail|inconclusive|requirement_gap",
  "scenario_id": "cfcp-scenario-001",
  "requirement_ids": [],
  "evaluated_artifact_refs": [],
  "deterministic_assertion_refs": [],
  "failed_requirements": [],
  "evidence": [
    {
      "source": "transcript|filesystem|probe|project_state|audit|trace",
      "reference": "path-or-id",
      "summary": "redacted evidence summary",
      "evidence_hash": "sha256-or-null"
    }
  ],
  "likely_cause": "implementation_failure|agent_inference_failure|fixture_failure|flaky_environment|requirement_gap",
  "remediation_target": "code|prompt|schema|test_fixture|rfc|governance",
  "redaction_status": "passed|failed",
  "requirement_gap_proposal": "text-or-null"
}
```

The evidence ledger is the run-level artifact tying together the scenario
fixture, tested-agent transcript, deterministic assertion results, consent
receipts, verification traces, world-state diff, evaluator verdict, and
remediation result if any. It is evidence, not governance authority.

Minimal evidence ledger shape:

```json
{
  "ledger_id": "ledger-id",
  "schema_uri": "contextforge://control-plane/schemas/evidence-ledger/v1",
  "run_id": "run-id",
  "requirement_ids": [],
  "scenario_ref": "scenario-id-or-path",
  "tested_agent_transcript_ref": "path-or-id",
  "deterministic_assertion_results": [],
  "consent_receipt_refs": [],
  "verification_trace_refs": [],
  "world_state_diff_ref": "path-or-id",
  "evaluator_verdict_refs": [],
  "remediation_refs": [],
  "redaction_status": "passed|failed",
  "evidence_hashes": []
}
```

**Layer 6: Remediation And Regression**

A remediation agent may receive the scenario conditions, failed deterministic
assertions, evaluator verdict, and cited evidence. It should not receive hidden
test-generation rationale, future evaluator prompts, or broader orchestration
state. Its job is to propose or apply the narrowest repair to code, prompts,
fixtures, schemas, or documentation.

If remediation claims the requirement is wrong or incomplete, the output is a
proposal, not an automatic patch to the test oracle. Requirement remediation
must flow through the same design/governance process as other RFC changes.

**Inferential Isolation Principle**

Each inferential participant gets only the view required by its role and is not
made aware of higher-order control-plane orchestration:

- The tested assistant is unaware of the test harness, evaluator, hidden oracle,
  remediation loop, and future retries.
- Any simulated user or environment model is unaware of evaluator and
  remediation roles unless its scenario role explicitly requires escalation.
- The evaluator is aware of evaluation but not allowed to interact with or steer
  the tested assistant.
- The remediator is aware of a failure and evidence but not allowed to alter the
  hidden oracle or optimize against future judge prompts.

This isolation is a test validity requirement. If a participant can see the
higher-order loop, the test may measure compliance with the harness rather than
the intended ContextForge behavior.

**TDD Cadence**

For each implementation slice:

1. Add or update deterministic tests and scenario fixtures before changing
   behavior.
2. Mark which requirements require inference-inclusive execution.
3. Run the headless tested assistant in an isolated workspace when inference is
   part of the behavior.
4. Collect transcript, world-state diff, tool calls, audit records, and probe
   outputs.
5. Run deterministic checks first.
6. Run privileged evaluation only for inferential/process criteria.
7. Remediate implementation or prompts when tests fail.
8. Treat `requirement_gap` as a design-review input, not an automatic test pass.
9. Preserve passing scenarios as regression fixtures.

### Control-Plane Minimal Viable Slice

The **Control-Plane Minimal Viable Slice Definition** is the smallest complete
vertical that proves the control-plane architecture end to end. It is a design
constraint for implementation sequencing, not permission to implement a bespoke
gateway or skip later hardening.

The slice includes:

- `.project/context_forge_state.json` schema, migration from legacy `.env`
  project-init keys, atomic writes, and lock/revision behavior.
- service binding contract card and shared-service capability capsule schemas.
- at least one existing shared-service capability capsule, preferably
  `context7` when locally available, proving useful project binding without
  per-project backend creation.
- Codex client adapter conformance pack and trust broker behavior, including
  the known condition that project-local `.codex/config.toml` is ignored until
  the root is trusted.
- consent receipts, adapter-independent verification traces, and apply journals
  before mutating apply is considered complete.
- semantic tool-policy compiler and negative checks at ContextForge
  virtual-server and target-client layers.
- ContextForge-backed language-profile metadata needed by the proof services,
  with install workflows remaining explicit and plan-first.
- Serena refactored behind the generic project-scoped adapter.
- read-only `project-inspector` style non-Serena project-scoped proof.
- service-management handoff object for catalog candidates and catalog repairs.
- requirement registry, coverage matrix, requirement-linked scenario DSL,
  evaluator verdict schema, and evidence ledger.
- enough deterministic, integration, and inference-inclusive scenarios to cover
  service-instantiation distinction, trust, stale IDs, scope-changing tools, and
  catalog-candidate handoff.
- governance reconciliation pack generated and reviewed before implementation
  claims ledgers are aligned.

The slice does not include general remote deployment, a catalog-wide provenance
graph, a full export/import drift lab, a generated human-readable status sheet
as a primary design object, automatic secret value entry, raw catalog CRUD in
the general control service, or client support beyond what is needed for the
first proven target-client path.

### Implementation Roadmap

1. Generate the governance reconciliation pack as the first non-mutating
   implementation task, then route accepted ledger updates through
   `scripts/governance_crud.py` or the `mentality` governance service.
2. Introduce a `project_state` library, JSON Schema, atomic write/lock support,
   compare-and-swap revision handling, stale-lock recovery, and tests for
   missing state, sticky declines, disabled/no-service state, invalid enums,
   denied roots, symlinks, schema evolution, and secret exclusion.
3. Cut the hook and project-init prompt path from `.env` state to
   `.project/context_forge_state.json`. Record legacy `.env` disposition as
   ignored/imported/conflict evidence rather than treating `.env` as authority.
   Add explicit migration import criteria and conflict-resolution outcomes.
4. Add service binding contract-card, shared-service capability capsule,
   semantic tool-policy, service-management handoff, consent receipt,
   verification trace, client conformance pack, scenario, evaluator verdict,
   evidence ledger, requirement registry, coverage matrix, and governance
   reconciliation schemas before project-init planning mutates state.
5. Implement non-mutating control-service read surfaces with fixtures:
   `get_project_context`, `list_catalog`, `list_available_capabilities`,
   `report_project_gaps`, language profile reads, and memory-provider metadata.
6. Build the initial deterministic and inference-inclusive test harness:
   requirement registry, coverage matrix, scenario fixture schema,
   transcript/evidence capture, deterministic assertions, privileged evaluator
   rubric, remediation handoff format, and regression storage. Each later wave
   adds or updates scenarios for the requirements it implements.
7. Implement service-instantiation classification in catalog reads,
   service-management plans, and project-init plans, including tests that
   shared canonical services such as `context7` and `ssh-tmux` are not
   duplicated per project.
8. Implement project-init planning with consent classes, typed effect summaries,
   contract card refs, capsule refs, instantiation class, target-client digests,
   stale-plan detection inputs, restart requirements, root-stability checks,
   port checks, token-source checks, handoff objects, and redacted plan records.
9. Implement operation authorization, consent receipt, verification trace,
   plan/audit storage, approval evidence, step journals, per-step idempotency
   declarations, recovery-path tests, and resumable apply for project-local
   state and owned config blocks only.
10. Add the Codex client adapter conformance pack and trust broker before
   declaring Codex proof possible, including trust detection, restart handling,
   list-tools, call-tool, config-generation probes, owned-block conflict
   classes, and failure classification.
11. Add the semantic tool-policy compiler before declaring the Serena refactor
   complete.
12. Implement the generic project-scoped service-provision apply layer,
   including backend home, ignored env placeholders, user-systemd unit, port,
   ContextForge gateway/server registration, virtual-server association,
   client-binding gated by conformance and compiled tool policy, recovery, and
   verification-trace behavior.
13. Add ContextForge resource-backed v1 language-profile metadata for Python,
   TypeScript/JavaScript, Rust, and Bash before language-aware Serena proof.
   Keep install workflows explicit and plan-first; execute only after separate
   approval. Add empty-project probe-artifact policy and profile-change
   workflow.
14. Refactor Serena behind the generic project-scoped service adapter, consume
   the language-profile metadata, and verify through the Codex
   app-server/client-visible path.
15. Generalize approved-plan apply from the Serena adapter, then add the
   read-only `project-inspector` style non-Serena project-scoped proof using
   the same adapter contract.
16. Add the generic `service_memory_provider` metadata contract with
    reference-only governance behavior.
17. Add the service-management skill contract for catalog promotion and update
    flows, including stock ContextForge API constraints and handoff/completion
    records.
18. Document and gate the experimental remote exposure workflow with separate
    remote token material, network-exposure consent class, negative exposure
    checks, and rollback plan validation.

### Acceptance Strategy

The implementation is accepted only when:

Acceptance is evaluated through three gates:

- `must_pass_mvs`: non-deferrable requirements in the minimal viable slice.
- `must_pass_before_remote_or_expansion`: requirements that can follow MVS but
  must pass before remote exposure or broader client/service support.
- `deferrable_with_governance_waiver`: requirements that may be deferred only by
  explicit governance decision with recorded rationale, evidence, owner, and
  review trigger.

- ContextForge remains the canonical service/resource identity authority.
- ContextForge ID reconciliation requires canonical name, root hash or scope
  tag, backend manifest, and resource metadata agreement.
- Every service binding has an explicit instantiation class before mutation.
- Every accepted, surfaced, or verified service binding has a service binding
  contract card before mutation or proof.
- Contract, capsule, policy, receipt, trace, evidence-ledger, and governance-pack
  references include content digests and catalog revisions/ETags when available,
  and stale-plan checks reject changed snapshots.
- Project init does not create per-project backends, wrappers, bridges, gateways,
  or server-instance directories for shared canonical services unless an
  approved service-management plan changes that model.
- Catalog candidates remain handoffs/open items until service-management returns
  a canonical ContextForge service identity and approved completion record.
- Shared canonical services used by project init have shared-service capability
  capsules and are not duplicated per project.
- `project-inspector` is seeded only as the RFC-named built-in proof service;
  unrelated discovered backends cannot use that seed path.
- `.project/context_forge_state.json` is the sole project-init state authority.
- Sticky declines suppress repeat prompts.
- Accepted services cannot mark a project initialized until target-client
  verification succeeds.
- A project with all offered services declined is `disabled`, not
  `initialized`.
- Catalog promotion requires explicit service-management skill invocation and
  approved plan mutation.
- Project init emits a service-management handoff object, not a mutation, when
  catalog promotion, catalog repair, or candidate canonicalization is required.
- User-global client trust is never changed without separate human approval.
- Codex trust handling is brokered, separately approved, receipt-backed, and
  verified through actual config consumption.
- User-global config writes, token material changes, and remote exposure each
  require separate human approval.
- Local assistant tokens are non-admin and least-privilege; negative probes prove
  they cannot perform catalog CRUD, token/admin operations, unapproved apply, or
  unrelated virtual-server access.
- Every mutating step is authorized by a consent receipt with the correct class,
  scope, plan digest, and mutation target.
- `apply_approved_plan` consumes approval receipts issued by `approve_plan` or an
  equivalent explicit approval workflow; it never mints its own approval.
- Consent receipts are immutable and cite a direct human approval event for the
  displayed plan digest; step usage is recorded in journals, not receipt edits.
- Source-client identity is authenticated strongly enough for the operation, or
  recorded as evidence-only under the shared-token profile with compensating
  replay controls.
- Placeholder env files may be created, but secret values are never stored in
  tracked state or normal audit records.
- Secret values enter only through safe local/no-echo/secret-store channels, not
  chat transcripts, shell command arguments, shell history, project state, or
  normal audit.
- Every verified state references at least one adapter-independent verification
  trace covering the layer being claimed.
- Every target client used for proof has a passing client adapter conformance
  pack or an explicit blocking limitation.
- Serena plus the read-only `project-inspector` style service prove the generic
  project-scoped pattern.
- At least one shared-service capsule proves useful project binding without
  per-project backend creation.
- Scope-changing tools are filtered by the semantic tool-policy compiler, not
  Serena-specific special casing.
- Unknown tools, missing risk metadata, stale readback, and unmatched manual
  overrides fail closed and block client-visible exposure.
- Client restart requirements are represented as open items until verified after
  restart.
- v1 language profiles exist in ContextForge for Python, TypeScript/JavaScript,
  Rust, and Bash.
- Governance ledgers remain authoritative and service memory is reference-only
  for governance in v1.
- Local auth uses loopback authenticated HTTP with wrapper fallback and one
  local client token.
- The experimental remote workflow is opt-in and reviewed before activation.
- ContextForge representation is explicit: native rows, resource metadata,
  repo-local state, external skill references, and governance ledgers are not
  conflated.
- Project-state writes are atomic, locked, schema-validated, and never persist
  secrets.
- Locks have timeout/stale-lock recovery, compare-and-swap revision checks, and
  actor/source-client journal evidence.
- Legacy `.env` state is disposed of explicitly and cannot silently override JSON
  state.
- Legacy imports require agreement among root, backend manifest, ContextForge
  names, owned config, language profile, and current target-client evidence.
- Plans have stable IDs, digests, consent classes, typed effect summaries,
  approval evidence, target-client digests, stale-plan rejection, and redacted
  audit records.
- Plan journals include required and observed consent receipts, verification
  trace refs, service contract refs, semantic tool policy refs, and
  service-management handoff refs.
- Mutating steps are idempotent or declare rollback, forward repair, or manual
  recovery.
- Operation authorization checks caller identity, operation class, target
  clients, project root, state revision, receipt scope, receipt expiry, token
  source, and replay policy before apply.
- Generic project-scoped service provisioning supports backend homes,
  user-systemd units, ports, ContextForge registration, virtual servers,
  client bindings, recovery paths, and verification traces before Serena or
  project-inspector proof claims success.
- Recovery-path tests cover interrupted apply, partial registration, stale
  ports, unit failures, config conflicts, failed trace emission, and stale
  receipt replay.
- Owned client config blocks can be written directly after approval; unmanaged,
  conflicted, or unsupported config requires a patch plan or user action.
- `report_project_gaps` can produce the required redacted diagnostic bundle.
- Client adapters define config, trust, auth, restart, list-tools, call-tool,
  stale-config, owned-block conflicts, config-generation probes, and failure
  behavior.
- Service-management skill plans include candidate descriptors, dedupe keys,
  scope classification, transport decision, backend-home manifest, tool policy,
  consent classes, contract cards, optional capability capsules,
  rollback/repair notes, and verification probes.
- Tool filtering is compiled into virtual-server associations and verified
  after gateway refresh.
- Negative tool-policy checks pass at both ContextForge virtual-server and
  target-client layers after refresh or restart.
- Runtime verification distinguishes port conflicts, unit crashes, missing
  secrets, readiness failures, registry drift, trust gaps, restart gaps, and
  client-visible failures.
- The test suite includes deterministic tests, integration/probe tests,
  scenario fixtures, and inference-inclusive headless assistant tests for
  behavior that depends on agent interpretation.
- A requirement registry and coverage matrix map each MVS acceptance criterion to
  requirement IDs, required evidence type, test layer, scenario/verdict/ledger
  refs, and deferrability.
- Scenario fixtures use the requirement-linked scenario DSL and link
  requirements, initial conditions, prompts, assertions, expected outcomes,
  required receipts, required traces, and evaluator rubrics.
- Malicious service metadata, prompt/resource text, tool descriptions, and
  client-config comments are tested as untrusted data and cannot authorize
  mutation, suppress negative checks, or rewrite acceptance criteria.
- Inference-inclusive tests preserve inferential isolation: the tested assistant
  does not know it is under test, while the evaluator is privileged but bounded
  to transcript, rubric, requirements, initial/final state, and cited evidence.
- Evaluator verdicts distinguish implementation failure, agent-inference
  failure, fixture failure, flaky environment, and requirement gap; requirement
  changes are proposals requiring review, not automatic oracle rewrites.
- Evaluator verdicts are structured, evidence-cited, and recorded in an
  evidence ledger that ties transcripts, deterministic checks, receipts,
  traces, verdicts, and remediation results together.
- The control-plane minimal viable slice passes deterministic, integration, and
  inference-inclusive scenarios before broader service/client support is added.
- A governance reconciliation pack is generated and reviewed before
  implementation claims the ledgers are aligned.
- Security tests prove no tokens in argv, logs, project state, normal audit
  records, diagnostics, or catalog output; token files are restrictive and
  revocation works.

## Decision Clusters

This RFC was refined through the following Socratic rounds.

1. Control-plane identity and authority.
2. Project state lifecycle.
3. Assistant-facing MCP control service.
4. User consent and trust.
5. Serena proof of concept.
6. General language tooling.
7. Serena memory versus governance registry.
8. Auth-aware local design.

Each round records the questions asked, locked decisions, and implications that
fed the normative design above.

These round sections are historical design records. Headings such as
`RFC Implications To Resolve` do not reopen an issue when the same round has a
`Resolution:` paragraph or when the normative design above states the decision.
If a historical implication conflicts with the normative design, the normative
design controls; unresolved items remain explicit only when they are named as
open questions or deferrable acceptance items.

## Round 1: Control-Plane Identity And Authority

Status: Complete.

### Repo-Locked Decisions

- ContextForge is the canonical authority for host-wide service, virtual-server,
  tool, prompt, and resource identity.
- Client configs can reveal candidate services and client-specific consumption
  constraints, but they do not define canonical service identity.
- Project-local state records a project's initialization relationship to
  ContextForge-managed resources; it does not redefine those resources.
- Server instance directories document and operate upstream backends, while stock
  ContextForge remains the registry/proxy authority.
- Direct ContextForge database writes are prohibited.

### Locked Decisions From Refinement

- If project initialization discovers a backend that is not already a canonical
  ContextForge service, the assistant may present it as a candidate and ask the
  user whether to promote it. The assistant must not automatically implement the
  promotion.
- Approved backend promotion uses a dedicated skill/workflow for adding a
  service to ContextForge. That skill owns candidate review, deduplication,
  backend-home creation, transport decision, registration, and live verification.
- Project state uses stable canonical names as its authority. Current
  ContextForge gateway IDs, virtual server IDs, tool IDs, prompt IDs, and
  resource IDs may be stored only as verification evidence or drift-detection
  cache.
- Catalog administration is entered only through explicit user intent: direct
  service-management request, explicit acceptance of a discovered candidate
  promotion, or a request to repair/update/remove/verify an existing canonical
  service.
- There is no hidden persistent catalog-administration mode. The assistant loads
  a dedicated service-management skill/workflow, produces a non-mutating plan
  first, and mutates only after approval of that concrete plan.
- For v1, the general control-plane MCP service should focus on discovery,
  project state, planning, and verification. Catalog mutation should live in the
  dedicated service-management skill over existing ContextForge APIs and repo
  scripts rather than raw admin CRUD exposed through the general control MCP.

### Candidate Backend Examples

Examples of discovered backends that normal project initialization may surface,
but must not auto-promote:

- A repo-local governance MCP service found in another workspace.
- A client config entry pointing directly at an unreviewed package integration,
  such as `pi-web-access` or `pi-claude-bridge`.
- A project-local REST/OpenAPI service that the user wants to expose as an
  assistant-facing tool.
- A one-off MCP entry in a client config whose backend is not yet deduplicated
  into the canonical ContextForge catalog.

Already canonical services, such as `mentality`, `ssh-tmux`, `context7`,
`playwright`, `exa-search`, `github`, `web-search`, and existing project Serena
instances, are not new backend candidates.

### Catalog Administration Invocation Model

Normal project initialization should use workflow operations rather than raw
catalog mutation. That does not remove service management capability; it defines
how a user intentionally enters a more powerful mode.

There is no hidden persistent "admin mode" that the assistant silently enters.
Catalog administration is an explicit workflow invocation. It starts in one of
three ways:

1. The user directly asks for catalog management.
2. The control-plane project-init flow reports a discovered candidate and the
   user explicitly accepts promotion.
3. The user asks to repair, update, remove, or verify an existing canonical
   ContextForge service.

Example user intents:

- "Add this discovered backend to ContextForge."
- "Promote this MCP server into the host-wide catalog."
- "Manage ContextForge services."
- "Update the `github` service registration."
- "Remove this ContextForge gateway."
- "Yes, add that candidate service."

After invocation, the assistant must load the dedicated service-addition or
service-management skill/workflow. The first step is always non-mutating:
inspect the candidate or existing service, classify scope, check for duplicates,
decide native transport versus package bridge, and produce a plan. Mutation
requires a second explicit approval of that concrete plan.

The workflow may expose CRUD-like actions, but only inside a
plan/review/apply/verify sequence that shows intended changes and asks before
mutation. This keeps ordinary project-init safe while preserving an intentional
path for full user-directed service management.

The assistant-facing control service can support this without becoming a raw
admin console by exposing read and planning operations to all initialized
projects, while mutating catalog operations are either:

- not exposed directly and are performed by the approved skill through existing
  ContextForge APIs and repo scripts, or
- exposed as narrowly scoped `apply_approved_*` workflow tools that require a
  prior plan identifier and user approval in the current conversation.

The RFC preference is the first option for v1: use a dedicated skill over
existing APIs/scripts for catalog mutation, and keep the general control-plane
MCP service focused on discovery, project state, plans, and verification.

Low-level CRUD in this context means create/read/update/delete over
ContextForge-managed objects and their operational homes:

- Gateways and virtual servers.
- Tool, prompt, resource, and agent associations.
- Prompt/resource guidance records.
- Backend instance manifests under `server-instances/<service-slug>/`.
- User-systemd service metadata for local backends.
- Project state records under `.project/context_forge_state.json`.
- Language profile records and selected backend metadata.

### RFC Implications To Resolve

- Normal project-init can discover and recommend catalog additions, but it cannot
  silently create host-wide canonical services.
- `.project/context_forge_state.json` should be human-readable and stable across
  ContextForge record recreation because names are authoritative and IDs are
  evidence only.
- The final RFC must define a dedicated service-addition skill/workflow.
- The remaining authority question is where operator/admin entrypoints live:
  in the MCP control service, in a skill over existing APIs/scripts, or both.

Resolution: v1 uses a dedicated skill over existing APIs/scripts for catalog
mutation. The general control-plane MCP service does not expose raw catalog CRUD.

## Round 2: Project State Lifecycle

Status: Complete.

### Repo-Locked Baseline

- The current bootstrap state uses whitelisted `.env` keys:
  `CONTEXTFORGE_PROJECT_INIT_DIALOGUE_STATUS`,
  `CONTEXTFORGE_SERENA_DECISION`,
  `CONTEXTFORGE_SERENA_PROVISION_STATUS`,
  `CONTEXTFORGE_SERENA_INSTANCE_SLUG`, and
  `CONTEXTFORGE_SERENA_SERVER_NAME`.
- The intended control-plane direction is to move canonical project-init state to
  `.project/context_forge_state.json`.
- Missing project state means `UNINITIALIZED`.
- Project roots are canonical realpaths; `/`, the user home, and
  `/home/dgk/workspace` are denied as project roots.
- Related parent/child Serena instances are diagnostic only and must not satisfy
  the exact canonical project root.
- Project-local state may record accepted, declined, deferred, created, failed,
  removed, and verified outcomes, but successful setup requires live evidence.

### Initial Proposed Minimal State Shape

This was the initial sketch used during refinement. The normative schema above
supersedes it with metadata, migration disposition, typed decisions, typed
evidence, drift tracking, and structured open items.

```json
{
  "schema_version": 1,
  "project": {
    "root": "/abs/canonical/project/root",
    "root_hash": "sha256-of-uid-and-root",
    "name": "project-name"
  },
  "status": "uninitialized|in_progress|initialized|disabled",
  "decisions": {
    "serena": "unasked|accepted|declined|deferred|disabled"
  },
  "services": {
    "serena": {
      "canonical_name": "serena",
      "virtual_server": "serena_example_hash_server",
      "provision_status": "none|pending|created|failed|removed|verified",
      "language_profile": "python",
      "evidence": {
        "gateway_id": "evidence-only",
        "server_id": "evidence-only",
        "verified_at": "timestamp"
      }
    }
  },
  "client_trust": {
    "codex": "unknown|untrusted|trusted|declined|not_required"
  },
  "open_items": []
}
```

### Questions Asked In This Round

1. Should `.project/context_forge_state.json` replace the current `.env`
   project-init keys completely, or should there be a migration period where the
   hook reads both and writes JSON as canonical?

2. Should declined decisions be sticky by default, meaning the hook stops asking
   until the user explicitly reopens the decision, or should declined services be
   re-offered after relevant catalog or project changes?

3. Should `initialized` require every accepted service to be verified through
   client-visible MCP calls, or can a project be initialized with some services
   recorded as accepted-but-pending?

### Locked Decisions From Refinement

- `.project/context_forge_state.json` replaces the current `.env` project-init
  keys immediately. The RFC does not require a migration period where `.env`
  remains an equivalent state authority.
- Declined service decisions are sticky. Project-init must not keep re-offering
  a declined service unless the user explicitly reopens the decision.
- Project status `initialized` requires every accepted service to be verified
  through client-visible MCP calls. Accepted-but-pending services keep the
  project out of `initialized` and must be represented as open items or
  incomplete service state.

### RFC Implications To Resolve

- Whether implementation needs a compatibility reader for `.env` state.
- How noisy or quiet first-run project guidance should be after a decline.
- Whether project initialization is all-or-nothing or can complete with explicit
  pending service items.

Resolution: implementation should treat `.project/context_forge_state.json` as
the single canonical project-init state file. The hook may ignore legacy `.env`
state for this control-plane design. A sticky decline suppresses repeat prompts.
The project reaches `initialized` only after all accepted services have live
client-visible verification evidence.

## Round 3: Assistant-Facing MCP Control Service

Status: Complete.

### Repo-Locked Baseline

- The locked direction calls for one assistant-facing ContextForge MCP control
  service.
- Normal project initialization should not expose raw catalog CRUD.
- Catalog mutation belongs to an explicitly invoked service-management skill for
  v1.
- The control service must help assistants discover available services, inspect
  project state, propose safe setup, apply approved project-local workflows, and
  verify client-visible behavior.
- The current hook/prompt approach is useful bootstrap material, but the control
  service should become the stable operational interface.

### Proposed Minimal Control Surface

The v1 control service should expose workflow-oriented tools:

- `get_project_context`: return canonical root, project hash, existing state,
  denied-root checks, related instances, and trust visibility.
- `list_available_capabilities`: return canonical services, project-scoped
  service candidates, prompts/resources, skills, agents, and language profiles
  relevant to the project.
- `propose_project_init`: return a non-mutating plan with choices, required
  approvals, expected file writes, services to provision, and verification steps.
- `record_project_decision`: write sticky user decisions such as accepted,
  declined, deferred, or disabled to project-local state.
- `apply_approved_project_init`: perform approved project-local provisioning
  such as Serena setup and project-local client config writes, excluding
  user-global trust mutation.
- `verify_project_init`: run live ContextForge and client-visible MCP checks and
  update evidence.
- `report_project_gaps`: return pending trust, language, service, or verification
  gaps without mutating state.

### Refined Notes From Discussion

- After approval, the control service may write project-local client config and
  project-local state directly. Exceptions must be explicit in the plan, such as
  unmanaged pre-existing config blocks, conflicts with user edits, unsupported
  client schemas, or changes that would affect user-global trust.

### Locked Decisions From Refinement

- The control service may expose host-wide read-only catalog views, such as the
  canonical service catalog, registered virtual servers, health summaries,
  resource/prompt metadata, and candidate visibility.
- Any operation that reads or writes project state, proposes project setup,
  provisions services, writes project-local config, or verifies setup requires a
  canonical project root.
- Applying setup uses a middle-ground model: one approved plan, applied by a
  resumable `apply_approved_plan(plan_id)` workflow that internally executes
  stepwise operations and reports per-step status.
- Failed or interrupted apply operations must be resumable or repairable from
  recorded step status. Verification remains a separate explicit operation.
- After approval, the control service may write project-local client config and
  project-local state directly. Exceptions must be called out in the plan and
  escalated to normal assistant file-edit or user action as appropriate.

### RFC Implications To Resolve

- Whether the service is only a project-init API or also a safe host catalog
  reader.
- How granular the tool surface should be for approval, audit, and recovery.
- Whether file mutation lives inside the control service or remains visible as
  normal assistant file edits.

Resolution: v1 control service includes host-wide read-only catalog tools plus
project-root-required planning, state, provisioning, and verification tools. It
uses approved, resumable plans for mutation, with direct project-local writes
allowed after approval and explicit exception reporting for conflicts or trust
boundaries.

## Round 4: User Consent And Trust

Status: Complete.

### Repo-Locked Baseline

- Approved project workflows may provision services and write project-local
  config/state.
- User-global client trust requires separate explicit approval.
- Current Codex behavior requires project trust before project-local
  `.codex/config.toml` is loaded.
- The current Serena flow writes project-local Codex config but does not silently
  add global Codex trust.
- Catalog promotion and catalog mutation require explicit user/operator approval
  through a dedicated skill/workflow.
- Runtime secrets and client-local secret values must not be committed.

### Consent Classes

The RFC should distinguish at least these consent classes:

- `read_only_inspection`: read project state, ContextForge catalog, manifests,
  health, and client config metadata.
- `project_state_write`: write `.project/context_forge_state.json`.
- `project_local_config_write`: write project-local client config such as
  `.codex/config.toml`.
- `service_provision`: create/update project-scoped backend homes, user-systemd
  units, ContextForge gateway/server records, and verification evidence.
- `catalog_promotion`: add a new canonical host-wide service through the
  service-management skill.
- `user_global_client_trust`: alter user-global trust/config so a client loads
  project-local config.
- `user_global_config_write`: alter user-global client config outside a
  project-local owned block.
- `secret_placeholder_change`: create or reference ignored downstream env files,
  key names, and missing-secret diagnostics without writing real values.
- `secret_value_write`: write, rotate, or remove actual downstream secret values.
- `token_material_change`: create, rotate, revoke, or relocate ContextForge
  client tokens or remote tokens.
- `network_exposure_change`: bind beyond loopback or otherwise expose a service
  through an experimental remote profile.

### Proposed Consent Rule

Each plan must list the consent classes it needs. A user's approval of a project
setup plan covers only the listed project-local classes. User-global trust,
user-global config, catalog promotion, token material changes, network exposure,
and `secret_value_write` require separate explicit approval even when they are
related to the same setup.

### Questions Asked In This Round

1. For Codex trust specifically, should the control plane only report the trust
   gap and give an exact user command/instruction, or may it apply global trust
   if the user explicitly approves that separate trust action?

2. Should secret material changes be completely out of scope for the control
   plane, or may the plan create/update ignored env files after explicit user
   approval while never exposing secret values in tracked state?

3. Should user consent be recorded only as durable state in
   `.project/context_forge_state.json`, or should each approved plan also create
   a local audit record under ignored `run/` state with timestamped plan,
   approval class, and verification result?

### Locked Decisions From Refinement

- User-global client trust changes, including Codex project trust, are allowed
  only when contingent on explicit human approval of that separate trust action.
  They must never be implied by generic project setup approval.
- Approved plans should create ignored local audit records under `run/` in
  addition to durable project state. Audit records should include timestamp,
  plan identifier, consent classes, planned mutations, executed steps, and
  verification results. They must not include secret values.
- The control plane may create ignored placeholder env files and report missing
  keys after approval. It must not write actual secret values unless a separate,
  deliberate secret-entry workflow is invoked and approved. Tracked project
  state and audit records must never contain secret values.

### Secret Material Clarification

Secret/env material means local ignored files or settings that contain sensitive
values or references needed by backends, such as:

- `server-instances/context7/.env` with `CONTEXT7_API_KEY`.
- `server-instances/exa-search/.env` with `EXA_API_KEY` and `GEMINI_API_KEY`.
- `config/contextforge.env` with local ContextForge admin/runtime settings.
- Future project-specific backend env files under `server-instances/<service>/`.

The policy question was whether the control plane may create or update these
ignored env files after explicit approval, or whether it should only report the
missing keys and leave secret editing to the user.

Resolution: placeholder env-file creation and missing-key reporting are allowed
after approval. Actual secret value writes require a separate secret-entry
workflow and must remain out of tracked state and normal audit payloads.

### RFC Implications To Resolve

- How deterministic new-project setup can be when client trust is missing.
- Whether the control plane can handle env-file scaffolding or only point the
  user to manual secret setup.
- What evidence future agents can use to distinguish approved mutation from
  accidental or stale state.

## Round 5: Serena Proof Of Concept

Status: Complete.

### Repo-Locked Baseline

- Serena is the first empirical proof path but must generalize to other
  project-scoped services.
- Serena is exposed through ContextForge and must not be configured globally for
  Codex.
- Each project gets a deterministic Serena backend identity derived from the
  canonical project root and user id.
- The Codex-facing `serena` alias is project-local and points at the
  project-specific ContextForge virtual server through the ContextForge wrapper.
- The upstream Serena backend is started with `--project <canonical-root>`.
- ContextForge virtual server filtering excludes `activate_project`; project
  switching must not be LLM-callable.
- Completion evidence currently includes user-systemd service state,
  ContextForge gateway/server registration, project-local Codex config,
  absence of global Serena, exposed tool list without `activate_project`,
  `get_current_config` proving the active project, and LSP-backed diagnostics or
  symbols when a language is configured.
- Empty projects require user language choice before Serena setup.
- The RFC must avoid architectural debt to Serena as a one-off instance of a
  broader project-scoped service pattern.

### Proposed Generalized Proof Pattern

Serena should prove this reusable project-scoped service pattern:

1. Derive deterministic project-bound service identity from canonical root.
2. Provision one backend instance under `server-instances/<service-project>/`.
3. Register or refresh the backend through ContextForge APIs.
4. Expose a project-specific virtual server.
5. Filter unsafe or scope-breaking tools from the virtual server.
6. Write project-local client config only after approval.
7. Verify through the actual client-visible MCP path, not only direct backend
   probes.
8. Record stable names in project state and IDs/probe outputs as evidence.

### Questions Asked In This Round

1. Should Serena be the only mandatory v1 project-scoped service proof, or should
   the RFC require a second non-Serena project-scoped service pattern before
   implementation is considered complete?

2. Should Serena verification always require Codex app-server/client-visible
   probing, or may non-Codex clients satisfy verification when the project is
   initialized from another assistant?

3. Should the RFC keep `activate_project` filtering as Serena-specific policy,
   or define a general class of scope-changing tools that project-scoped virtual
   servers must filter unless explicitly approved?

### Locked Decisions From Refinement

- Serena remains the first proof, but it must be refactored as needed to satisfy
  the new control-plane requirements and abstractions rather than freezing the
  current manager shape as the design.
- v1 implementation requires one additional non-Serena project-scoped service
  proof so the architecture demonstrates a general pattern rather than a
  Serena-specific path.
- Scope-changing tool filtering is a general project-scoped service policy.
  `activate_project` is only Serena's instance of the broader rule. Any tool
  that can change the active project, workspace root, credential scope, resource
  scope, or backend operating scope must be filtered from a project-scoped
  virtual server unless explicitly approved and verified.
- Control-plane abstractions must be expressed in service-agnostic terms:
  project identity, backend instance, virtual server, exposed tool policy,
  language/profile requirements, client-visible verification, evidence, and
  rollback/repair behavior.
- Verification is client-agnostic as a design abstraction but client-specific as
  runtime proof. The control plane should model clients through adapters or
  capability metadata, but setup must be proven through the specific target
  client path that will consume the service.
- Process orchestration must understand client restart requirements. If a config
  or trust change will not be visible until a client restarts, the plan and
  verification output must prompt the user to restart that client and must not
  mark the service verified until the restarted client-visible path succeeds.

### RFC Implications To Resolve

- Whether v1 implementation success depends only on Serena or on at least two
  service examples.
- Whether verification is client-specific or any approved client-visible path can
  prove setup.
- Whether tool filtering becomes a reusable safety rule for all project-scoped
  services.

Resolution: the architecture remains client-agnostic through common client
capability abstractions, but verification evidence is specific to the intended
client. A Codex proof does not mark a Claude Code setup verified unless Claude
Code is not an intended consumer. Restart-required states must be explicit open
items until the user restarts the relevant client and verification passes.

## Round 6: General Language Tooling

Status: Complete.

### Repo-Locked Baseline

- Empty projects must not silently default to Python for Serena. The user must
  choose a language before provisioning.
- The current Serena manager can detect or accept language choices and returns
  recommended examples: `python`, `typescript`, `javascript`, `rust`, `go`,
  `bash`, `java`, `csharp`, and `cpp`.
- Current LSP install execution is disabled. Instance-local LSP scaffolding is
  present, but optional installs require future explicit approval.
- Optional LSP capability gaps are advisory; baseline LSP failures block setup
  only when the configured language requires those probes for verification.
- LSP tools and caches should live under the relevant service instance directory
  rather than mutating global language tooling by default.

### Proposed Language Profile Model

Language tooling should be represented as reusable profiles, not Serena-only
  branches:

- `language_id`: normalized language identifier.
- `display_name`: user-facing name.
- `detection`: markers/extensions used for inference.
- `service_requirements`: which project-scoped services use this profile.
- `baseline_probe`: client-visible read-only verification probes.
- `optional_capabilities`: advisory capabilities such as implementations or
  richer symbol features.
- `backend_options`: curated provider choices with scope, caveats, and install
  policy.
- `install_policy`: disabled, approved-manual, approved-instance-local, or
  host-required.
- `evidence`: last verified client, path, tool, status, and timestamp.

### Proposed Common v1 Language Set

Initial proposal before refinement:

- Python
- TypeScript/JavaScript
- Rust
- Go
- Bash
- Java
- C#
- C/C++

Other Serena-supported languages may remain advanced/manual until a profile is
defined.

### Locked Decisions From Refinement

- The initial v1 language set is Python, TypeScript/JavaScript, Rust, and Bash.
  Go, Java, C#, and C/C++ may be added later but are not required for the first
  implementation.
- Language profiles live in ContextForge. ContextForge is the active catalog for
  language profile policy, discovery, install workflow metadata, and verification
  expectations.
- v1 should include approved install workflows for missing tooling in the initial
  language set. Install workflows must be explicit, curated, instance-local by
  default, and separately approved before execution.
- Reporting gaps remains required. A missing backend should produce a plan and
  approval choices, not silent installation.

### RFC Implications To Resolve

- Which languages implementation agents must support well enough to ask coherent
  setup questions.
- Where language policy lives and how assistants discover it.
- Whether v1 includes actual language-server installation or only explicit
  planning/scaffolding for later approved installs.

Resolution: support Python, TypeScript/JavaScript, Rust, and Bash language
profiles in ContextForge for v1. Include approved install workflows for their
curated tooling, with no automatic install and no default global mutation.

## Round 7: Serena Memory Versus Governance Registry

Status: Complete.

### Repo-Locked Baseline

- `DECISIONS.md`, `ABEYANT_INTENTIONS.md`, and `OPEN_QUESTIONS.md` are the
  durable repo-local governance registries.
- The `mentality` MCP service exposes governance CRUD for those ledgers.
- Current guidance says durable governance remains authoritative unless the RFC
  explicitly changes that policy.
- Serena has memory tools, but those are currently tool-local and
  project-service-local rather than the accepted governance source of truth.

### Proposed Boundary

Governance ledgers should remain authoritative for project decisions, open
questions, and parked intentions. Serena memory may be useful as service-local
working memory, code navigation notes, or summaries that improve Serena's
operation, but it should not become an independent governance ledger.

If Serena memory records something governance-relevant, it should reference the
governance entry or prompt creation of one through `mentality`, rather than
silently duplicating durable policy.

### Refinement Note

This cluster requires deeper comparison before decision. Serena is the first MCP
project-scoped proof, but it does not hold a privileged position over prior
governance solutions unless the RFC explicitly reasons to that conclusion and
the user accepts it. The design must evaluate memory/governance integration as a
general pattern for any future MCP service with local memory, not only Serena.

Five parallel design explorations were requested to compare structurally unique
possibilities across these lenses:

- Governance authority and source-of-truth boundaries.
- Memory architecture and synchronization patterns.
- ContextForge control-plane operations.
- User consent, UX, and safety.
- Implementation and migration.

### Agent Exploration Synthesis

The five reports converged on one primary authority principle: governance
ledgers and service-local memories should not be peers for project policy.
Ledgers are better for decisions, open questions, parked intentions, audit,
stable IDs, finite statuses, and reviewable history. Service-local memory is
better for recall, code-navigation landmarks, dense summaries, and operational
notes tied to a particular backend. If memory owns governance, the system gains
convenience but creates authority drift.

The structurally distinct options are:

1. **Policy-only separation.** Ledgers remain authoritative; service memories
   are incidental working notes. Pros: simplest, lowest drift. Cons: weak
   integration and relies on agent discipline.

2. **Reference-only memory.** Service memories may contain pointers to
   governance IDs such as `dec-*`, `oq-*`, and `ai-*`, but agents must read and
   write governance through `mentality`. Pros: general, low debt, useful recall.
   Cons: agents may still over-trust stale pointer notes unless prompts and
   verification warn against that.

3. **Ledger-authoritative generated projection.** The control plane can generate
   read-only memory/index entries from governance ledgers, with source IDs,
   hashes, status, updated date, and stale markers. Pros: faster recall and good
   onboarding for memory-capable services. Cons: cache lifecycle, drift
   detection, and generated-content labeling become required.

4. **Proposal and reconciliation workflow.** Service memory may surface
   governance-like observations or conflicts, but durable changes are proposed
   and then written through `mentality` only after approval. Pros: captures
   useful discoveries without making memory authoritative. Cons: classification
   can be noisy and requires user review.

5. **Control-plane broker.** Assistants call a ContextForge control service that
   composes governance and memory context while labeling authority. Pros: good
   UX and generic across services. Cons: risks becoming a bespoke knowledge
   layer if it absorbs too much responsibility.

6. **Dual-source or federated governance.** Ledgers and memory both own some
   governance records by type, with reconciliation. Pros: flexible. Cons:
   highest complexity and most likely to confuse future agents. The exploration
   reports do not recommend this for v1.

The common recommendation is ledger-authoritative memory integration:

- Governance ledgers remain authoritative for decisions, open questions,
  parked intentions, consent, and project policy.
- Serena is not special. It is one memory-capable service instance of a generic
  `service_memory_provider` pattern.
- Service-local memories may store working notes, recall hints, code-navigation
  context, and optional pointers or generated summaries that cite governance
  IDs and source hashes.
- Service-local memory may propose governance changes or flag conflicts, but
  accepted governance changes go through `mentality` or a control-plane workflow
  that writes the governance ledgers.
- If memory conflicts with a ledger, the ledger wins. The control plane should
  flag stale/conflicting memory and may offer a non-mutating reconciliation plan.
- Bidirectional sync is not recommended for v1.

### Questions Asked In This Round

1. For v1, should memory integration stop at reference-only pointers and
   governance proposals, or should v1 also include approved/generated read-only
   governance projections into memory-capable services?

2. Should the RFC require a generic `service_memory_provider` capability contract
   now, even if v1 implements only the minimal policy fields, or should that
   contract be deferred until the second memory-capable service appears?

3. When memory conflicts with governance, should v1 only flag the conflict and
   use the ledger, or should v1 include an explicit reconciliation proposal
   workflow?

### Locked Decisions From Refinement

- v1 memory/governance integration stops at references and proposals. Generated
  read-only governance projections into memory-capable services are out of scope
  for v1 and may be revisited if real use shows a deeper need.
- The RFC should define a generic `service_memory_provider` capability contract
  now, even if v1 implements only minimal policy fields. Serena is one instance
  of this general capability class, not a special governance authority.
- If service-local memory conflicts with governance, v1 should flag the conflict
  and continue using the governance ledger as authority. Formal reconciliation
  workflows are deferred.
- Service-local memory may store working notes, recall hints, code-navigation
  context, and references to governance IDs. It must not silently settle
  decisions, open questions, parked intentions, consent, or project policy.

### RFC Implications To Resolve

- Whether v1 has no sync, generated one-way projections, or only future hooks for
  projection.
- Whether memory-capable services are modeled generically from the start.
- Whether conflict handling is advisory-only or includes a formal proposal path.

Resolution: v1 uses ledger-authoritative, reference-only memory integration with
generic `service_memory_provider` metadata. No generated governance projection
or bidirectional sync is included in v1. Conflicts are flagged, not reconciled
automatically.

## Round 8: Auth-Aware Local Design

Status: Complete.

### Repo-Locked Baseline

- The current local gateway runs on loopback HTTP at `http://127.0.0.1:4444`
  because that path was explicitly accepted for reliable local operation.
- Direct-capable clients use authenticated HTTP with bearer headers where proven.
- Claude Desktop remains wrapper-based because its local config schema is
  stdio-oriented for this installed build.
- Runtime secrets, bearer tokens, passwords, generated JWTs, and client-local
  secret values must not be committed.
- v1 is local-first but auth-aware, not full multi-user remote operation.
- The design should avoid boxing out later remote exposure.

### Proposed Local Auth Model

v1 should preserve the current local reliability path while making future remote
hardening explicit:

- Bind default local services to loopback unless a user explicitly enables wider
  network exposure.
- Keep ContextForge authentication and scoped bearer credentials in the path for
  direct HTTP clients.
- Keep wrapper-based clients on local wrapper scripts that obtain credentials
  from ignored local env/config.
- Record which client uses which auth path in project state evidence.
- Treat token creation, rotation, and revocation as explicit approved workflows.
- Keep remote exposure as a future profile that requires TLS, origin policy,
  token scope review, and service exposure review.

### Questions Asked In This Round

1. Should v1 define only one local auth profile, `loopback_authenticated_http`,
   with wrappers for stdio-only clients, or should it also define a dormant
   `remote_ready` profile that is documented but not implemented?

2. Should client bearer tokens be per-client/per-virtual-server where feasible,
   or is one local ContextForge API token acceptable for v1 if its storage and
   rotation are explicit?

3. Should future remote exposure be explicitly out of scope for v1 implementation
   but included as design constraints, or should v1 include a non-default
   experimental remote exposure workflow?

### Locked Decisions From Refinement

- v1 defines the active `loopback_authenticated_http` profile and also documents
  a dormant `remote_ready` profile that is not the default path.
- v1 uses a single local ContextForge client token for assistant clients. Clients
  use that token to reach ContextForge. Service-level tokens, credential
  passthrough, and downstream credential controls are handled by ContextForge
  wherever possible.
- Token storage, rotation, and revocation must be explicit approved workflows.
  Tokens and generated credentials remain ignored local state.
- v1 includes a non-default experimental remote exposure workflow. It must be
  opt-in, require explicit approval, and include TLS, origin, token scope,
  bind-address, and exposed-service review before activation.

### RFC Implications To Resolve

- How much auth/token granularity implementation agents must build immediately.
- Whether remote readiness is only architecture guidance or a testable local
  profile.
- How to avoid overbuilding remote deployment while keeping security boundaries
  visible.

Resolution: local v1 uses loopback authenticated HTTP plus wrappers for
stdio-only clients, with a single local ContextForge client token. A dormant
`remote_ready` profile is documented, and a non-default experimental remote
workflow is allowed only behind explicit opt-in review.

## Acceptance Criteria For Final RFC

- Every major authority boundary is explicit.
- Every user consent point is explicit.
- Serena remains a concrete proof path, not a one-off special case.
- New-project setup is verifiable through actual client-visible MCP calls.
- Client trust changes are never silent.
- Language tooling is selected from a user-confirmed common language set.
- Governance ledgers remain authoritative unless the RFC explicitly changes that
  policy.
