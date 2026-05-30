# Systematic Refinement Plan: ContextForge Control Plane Vision

## Summary

Create a Design RFC that turns the tentative ContextForge control-plane vision into a coherent, reviewable architecture before implementation. The refinement should proceed in Socratic rounds, starting from the control-plane model, then deriving project-init flows, Serena proof requirements, language tooling policy, and cross-client behavior.

Locked direction:

- Primary artifact: Design RFC.
- Starting axis: ContextForge as control plane.
- Process: Socratic decision rounds.
- Interface: one assistant-facing ContextForge MCP control service.
- Authority: ContextForge owns canonical service/resource identity; project-local `.project/context_forge_state.json` owns project initialization state.
- Mutation policy: approved workflows may provision services and write project-local config/state, but user-global client trust requires separate explicit approval.
- Deployment target: auth-aware local v1, designed so remote exposure is not boxed out.
- Resource model: core plus extensible: services, prompts/resources, skills/agents metadata, project state, language profiles.

## Key Refinement Work

- Create a Design RFC under `docs/initiatives/contextforge-control-plane/`, leaving the current dialogue plan as the lightweight agenda.
- Structure the RFC around decision clusters:
  - Control-plane identity and authority: service identity, resource ownership, client config as discovery input, ContextForge as canonical registry.
  - Project state lifecycle: `.project/context_forge_state.json`, default `UNINITIALIZED`, accepted/declined/deferred service choices, evidence-backed completion.
  - Assistant-facing MCP control service: discovery, status, CRUD, project-init guidance, service provisioning, health verification, and rollback/reporting commands.
  - User consent and trust: separate consent for service setup versus client trust changes; no silent trust broadening.
  - Serena proof of concept: project-scoped backend, ContextForge-mediated access, `activate_project` filtering, app-server verification, language/LSP advisory handling.
  - General language tooling: research common language support, define user-confirmed language set, model instance-local curated backend options without auto-installing.
  - Serena memory versus governance registry: decide durable governance authority, tool-local memory role, sync/reference policy, and conflict avoidance.
  - Auth-aware local design: token/scopes/secrets/network boundaries suitable for later remote exposure, while keeping v1 single-user local.

## Interface And Schema Questions To Resolve In RFC

- Minimal `.project/context_forge_state.json` shape:
  - project identity and canonical root hash.
  - initialization status.
  - selected/declined/deferred services.
  - service-specific provisioning evidence.
  - language profile selections.
  - client trust status as separate state.
- Minimal MCP control service surface:
  - list available resources/services.
  - inspect project state.
  - propose initialization plan.
  - apply approved project-local changes.
  - verify exposed client-visible tool paths.
  - report unresolved trust or language/tooling decisions.
- Resource taxonomy:
  - MCP services and virtual servers.
  - prompts and resources.
  - REST/OpenAPI tools.
  - skills and agents as metadata-backed capabilities.
  - language profiles and optional tooling providers.
  - governance artifacts.

## Test And Acceptance Strategy

- RFC acceptance:
  - Every major authority boundary is explicit.
  - Every user consent point is explicit.
  - No implementer must decide whether ContextForge, project files, or client configs are authoritative for a given state class.
  - Serena remains a concrete proof path, not a one-off special case.
- Future implementation acceptance criteria defined by RFC:
  - A new uninitialized project receives consistent guidance through the MCP control service.
  - User choices are recorded in project-local state.
  - Project-local provisioning can be verified through actual client-visible MCP calls.
  - Client trust changes are never silent.
  - Language tooling is selected from a user-confirmed common language set.
  - Governance ledgers remain authoritative unless the RFC explicitly changes that policy.

## Assumptions

- `main` remains protected; design and implementation work proceeds from `dev-root`.
- v1 is local-first but auth-aware, not full multi-user remote operation.
- The first implementation proof remains Serena, but the RFC must generalize the pattern across services and languages.
- ContextForge should reduce per-client MCP setup, not become a bespoke replacement gateway fleet.
