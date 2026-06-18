# Evidence Surface Labels

Issue: #158

Verification traces must label the surface that actually produced the evidence.
The label is evidence metadata, not approval to mutate that surface and not proof
for any stronger layer by itself.

## Canonical Labels

| Label | Surface | Valid use |
| --- | --- | --- |
| `legacy_live_read_only` | Legacy/live ContextForge read-only | Non-mutating health, readiness, config, process, socket, log, diagnostic, and comparison evidence from the active operator substrate. |
| `contextforge_dev_docker` | ContextForge dev Docker | Isolated mutable development gateway, bridge, endpoint, registry, and resettable integration evidence. |
| `pi_client_docker` | Pi client Docker | Pi client-foil evidence against the ContextForge dev Docker surface. |
| `opencode_client_docker` | OpenCode client Docker | OpenCode client-foil evidence against the ContextForge dev Docker surface. |
| `local_source` | Local source | Tracked source, docs, fixtures, static checks, and local unit tests. |
| `target_client` | Target client | A named target client's own visible list/call/readback path. |
| `generated_run_evidence` | Generated run evidence | Ignored `run/` or generated evidence artifacts that explicitly cite the exercised layer and source surface. |

## Claim Boundary

Evidence from one surface cannot prove readiness on another surface without an
explicit bridge and current readback. For example, Pi client Docker evidence may
support a Pi client-visible claim for the dev Docker validation path, but it
does not prove host Pi readiness, legacy/live ContextForge routing, or OpenCode
behavior.

Verification traces enforce this boundary by storing `exercised_surface` and
blocking lifecycle claims when a trace's surface cannot support the required
verification layer.

## Non-Actions

This label standard does not approve runtime/client validation,
Docker/container start/stop/rebuild, ContextForge registry mutation,
service/process/systemd mutation, client/Pi/global config changes, hook
trust/state changes, secret/OAuth/trust-token handling, helper/project-init
approve/apply/recovery mutation, Serena provisioning,
`.project/context_forge_state.json` rewrites, destructive git operations, or
retired legacy checkout mutation.
