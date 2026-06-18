# Readiness Claim Guardrails

Issue: #161

This document defines the status vocabulary agents must use when reporting
ContextForge source, backend, gateway, and client readiness. It is a
source/docs/tests contract. It does not validate runtime behavior, mutate
project state, approve service changes, or replace issue/PR/runtime evidence.
It does not approve service changes.

Use `docs/evidence-surface-labels.md` for the canonical #158
`exercised_surface` values that verification traces attach to readiness
evidence.

## Purpose

Readiness claims must name the layer that was actually exercised. A source
test, backend health check, ContextForge registry readback, and target-client
tool call are different evidence classes. They must not collapse into a single
generic "validated", "ready", or "done" claim.

Use the most specific accurate status. If the evidence spans several layers,
name each layer separately and cite the weakest unproven boundary.

## Vocabulary

| Status | Meaning | Required evidence | Not enough |
| --- | --- | --- | --- |
| `planned` | The work is selected or designed, but no artifact or runtime change exists. | Issue, roadmap, branch plan, or documented acceptance criteria. | Treating an accepted plan as implementation. |
| `created` | The artifact exists, but no consumption or runtime proof is claimed. | Tracked file, generated local artifact, branch, PR, config block, service definition, or package output readback. | Claiming use by ContextForge or a client. |
| `pending_restart` | A config, service, or client change exists but has not been reloaded or consumed. | Exact changed surface plus missing restart/reload/open-project boundary. | Backend health or old-session behavior. |
| `initialized` | Project or service state has a schema-valid initial record. | State file, manifest, fixture, or helper readback with schema/version evidence. | Claiming runtime or client visibility. |
| `source_ready` | Tracked source/docs/tests for a slice pass locally. | Focused tests, compile/static checks where relevant, full discovery when warranted, and diff/readback evidence. | Runtime health, gateway registration, or client use. |
| `backend_ready` | The upstream backend process or hosted service responds as expected. | Backend-specific health/listener/API probe for the named surface. | ContextForge registry presence or target-client use. |
| `contextforge_ready` | ContextForge can see and route the intended service/tool path. | Gateway/API/registry/virtual-server/tool readback plus endpoint proof on the named surface. | Backend health alone or client config presence. |
| `target_client_ready` | The intended client can list and, where safe, call the intended ContextForge-backed tool path. | Target-client-visible list-tools evidence and safe call result for the named client and surface. | Backend health, ContextForge-only proof, source fixtures, or another client's proof. |
| `presumed_working` | The operator explicitly accepted proceeding without current proof for a bounded reason. | Operator choice, reason, missing proof class, and retirement trigger. | Silent skip, stale evidence, or "probably works" language. |
| `verified` | All required layers for the specific claim passed. | Layer-specific evidence references for the exact scope being claimed. | Passing evidence for a broader or different scope. |
| `degraded` | The path works with a documented limitation or reduced capability. | Passing evidence plus limitation, impact, and recovery/retirement trigger. | Treating partial proof as full success. |
| `failed` | The attempted proof did not pass. | Failed command/probe/readback, error class, and next repair boundary. | Rewording failure as pending validation. |
| `removed` | The artifact or runtime surface was intentionally removed and absence was verified. | Removal action plus post-action absence/readback evidence. | Deleting a branch/config without checking active references. |

## Layer Ordering

The usual promotion order is:

1. `planned`
2. `created`
3. `initialized`
4. `source_ready`
5. `backend_ready`
6. `contextforge_ready`
7. `target_client_ready`
8. `verified`

Not every slice needs every layer. A source-only PR should usually stop at
`source_ready`. A backend service may stop at `backend_ready` until
ContextForge registration is in scope. A target-client claim must not skip the
client-visible layer.

`pending_restart`, `presumed_working`, `degraded`, `failed`, and `removed` are
cross-cutting states. They must name the layer where they apply.

## Forbidden Collapses

Do not claim:

- `verified` from `source_ready`;
- `target_client_ready` from `contextforge_ready`;
- `contextforge_ready` from `backend_ready`;
- `backend_ready` from tracked source or Dockerfile presence;
- host Pi readiness from Pi client Docker proof;
- Pi or OpenCode readiness from a Codex hook banner;
- Codex readiness from Pi or OpenCode helper behavior;
- runtime readiness from roadmap, issue, PR, or Project #6 state;
- service removal from branch deletion alone;
- validation success from a skipped probe unless the claim is explicitly
  `presumed_working`.

## Claim Template

When reporting readiness, use this shape:

```text
<object> is <status> for <surface/scope> based on <evidence>. It is not
<stronger-status> because <missing proof or boundary>.
```

Examples:

- `The service-onboarding helper is source_ready for the deterministic CLI
  surface based on focused helper tests and full unittest discovery. It is not
  contextforge_ready because no service was registered.`
- `Pi client Docker helper visibility is target_client_ready for the dev
  Docker surface based on Pi-visible shim readback. It is not host Pi ready
  because host Pi install/reload remains #3.`
- `The registry plan is presumed_working for a bounded migration step only
  because the operator accepted proceeding without target-client proof; the
  missing proof is target_client_ready readback.`

## Evidence Requirements

Every readiness claim must include:

- object or service name;
- layer/status;
- exercised surface;
- current evidence command, issue comment, PR, trace, or artifact;
- missing stronger layer, if any;
- non-actions and boundaries where the claim could be misread.

If a claim spans more than one surface, list the surfaces separately. Evidence
from one surface cannot prove another surface unless the bridge is itself
current and evidenced.

`scripts/control_plane_readiness_claim_linter.py` provides source_ready
local_source coverage for these prose guardrails by flagging missing evidence
references, missing canonical surface labels, stale evidence promoted as
current, and backend-only proof promoted to target-client readiness.

## Non-Actions

This guardrail does not approve runtime/client validation, Docker/container
start/stop/rebuild, ContextForge registry mutation, service/process/systemd
mutation, client/Pi/global config changes, hook trust/state changes,
secret/OAuth/trust-token handling, helper/project-init approve/apply/recovery
mutation, Serena provisioning, `.project/context_forge_state.json` rewrites,
destructive git operations, or retired legacy checkout mutation.
