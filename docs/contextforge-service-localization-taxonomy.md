# ContextForge Service Localization Taxonomy

Issues: #270, #259, #247

Structured contract:
`docs/contextforge-service-localization-taxonomy.json`.

This taxonomy defines how ContextForge control-plane work distinguishes a
service's real lifecycle boundary before claiming project activation readiness.
It is a source/docs/tests contract. It does not authorize runtime, registry,
service, Docker, client-global, secret, hook-trust, helper apply, or Serena
provisioning mutation.

Use this taxonomy when filling service readiness matrices, writing project-init
plans, and reporting whether a service is shared, user-scoped, project-scoped,
session-scoped, or only a client bootstrap surface.

## Types

| Type | Meaning | Instantiation rule | Readiness evidence |
| --- | --- | --- | --- |
| `shared_canonical` | One reusable ContextForge virtual server or native backend can serve many projects. Project init binds the project/client to that existing service. | Instantiate once per canonical backend unless transport, credential, or safety boundaries prove another instance is needed. | Manifest identity, ContextForge virtual server identity, project-local binding plan, and target-client-visible list/call proof when a safe probe exists. |
| `credential_scoped` | The backend behavior depends on a provider credential, user account, or quota boundary. | Instantiate per credential/user only when the backend cannot safely multiplex or when the credential boundary is the service boundary. | Credential boundary described without secret disclosure, redaction/cost/rate-limit constraints, and safe read-only target-client proof or explicit blocker. |
| `project_scoped` | The backend behavior depends on a specific project root, code index, language server, cache, or project-local state. | Instantiate per project, or bind only to a previously approved project-specific instance. | Project root, instance identity, provisioning/readback status, and target-client proof against the selected project instance. |
| `session_scoped` | The backend behavior depends on an ephemeral client/session runtime such as a browser or shell/tmux session. | Instantiate per session/runtime boundary only when required by the backend behavior. | Controlled session lifecycle, safe read/list probe, and explicit non-actions for unsafe runtime mutation. |
| `repo_local_static` | The service source lives in this repository and is stable, but its tool calls may require an explicit repo argument or governance boundary. | Reuse the repo-local backend or transceiver; do not duplicate state into another source of truth. | Source path, stable tool contract, and read-only target-client proof that does not mutate repo ledgers. |
| `client_global_bootstrap` | A user-home or container-user client hook, plugin, shim, or helper bootstrap that starts the project-init conversation. It is not itself a project service. | Installed or seeded per client user/home surface through its own approval path; project init must not silently write it. | Client-visible helper/plugin/shim readback, separate from service binding readiness. |
| `not_a_service` | A user-flow option such as `None`, skip, defer, or decline. | No backend, service binding, registry identity, or validation probe. | Flow records user choice and non-actions only. |

## Mapping Rules

- Client configs are consumption surfaces, not service identity.
- Service binding suffixes such as `canonical` or `credential_scoped` are
  stable identifiers. `taxonomy_type` is the authoritative lifecycle and
  localization class.
- Project-local activation may bind to a shared service without creating a
  per-project backend.
- User-global Pi/OpenCode/Codex/Gemini hooks and helper bootstraps trigger or
  facilitate initialization. They must not be counted as selected project
  services.
- Credential-scoped services must never claim readiness from the presence of a
  token, environment variable, or host auth alone. The credential boundary and
  safe proof path must be named without exposing secret material.
- Project-scoped services must not be activated from another project's backend
  identity unless compatibility is explicitly documented and validated.
- Session-scoped services must not use unsafe side effects, arbitrary browsing,
  remote shell commands, or cleanup actions as ordinary validation proof.
- Backend health, direct bridge checks, and registry readback can support lower
  readiness layers, but target-client readiness requires evidence from the
  target client surface.

## Current Menu Examples

| Menu item | Taxonomy type | Notes |
| --- | --- | --- |
| `context7` | `shared_canonical` | Global documentation lookup scoped by tool arguments; first #260 single-service slice. |
| `exa-search` | `credential_scoped` | Provider-key, quota, cost, and redaction boundaries must be explicit before runtime proof. |
| `github` | `credential_scoped` | GitHub account/token boundary; read-only proof only unless a later issue approves writes. |
| `mentality` | `repo_local_static` | Repo-local governance MCP; validation must list/read governance only and must not mutate ledgers. |
| `openzeppelin-solidity-contracts` | `shared_canonical` | Remote native template/documentation service; safe proof is constrained preview generation only. |
| `playwright` | `session_scoped` | Isolated browser runtime; proof must use a controlled fixture page. |
| `ssh-tmux` | `session_scoped` | Existing-session visibility only; no opening sessions or sending commands without separate approval. |
| `web-search` | `credential_scoped` | Provider/request scoped; safe low-cost query only after credential and redaction boundaries are bounded. |
| `serena` | `project_scoped` | Project-specific code intelligence; provisioning and language choice remain explicit approval boundaries. |
| `None` | `not_a_service` | Covered by decline/defer flow, not service readiness. |

## Relationship To #247

#247 is the umbrella for adding useful project service access through helper
selection, plan, approval, apply, and readback. This taxonomy prevents #247
from treating all menu choices as equivalent. #259 uses the taxonomy to build
the readiness matrix, #260 proves the first `context7` path, and #269 later
validates single, curated multi-service, and all-services selection shapes.
