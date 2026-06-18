# ContextForge Registry Mutation Discipline

Issue: #140

Registry-changing helper code must use public ContextForge APIs or documented
Admin behavior. It must not write the ContextForge database directly, patch
ContextForge internals, or treat stored IDs as canonical authority over names,
URLs, URIs, backend manifests, and scope metadata.

## Current Helper Surfaces

| Helper | Covered registry surface | Mutation path |
| --- | --- | --- |
| `scripts/apply_contextforge_registry_recreation.py` | gateways, gateway tool refresh, servers, server tool/resource/prompt/agent associations | public ContextForge gateway/server/tool APIs after `--apply` |
| `scripts/register_tool_guidance.py` | prompts, resources, and server prompt/resource associations | public ContextForge prompt/resource/server APIs |

The shared source guard lives in
`scripts/control_plane_registry_discipline.py`. It allows only the current
public ContextForge API paths used by these helpers and rejects unsupported
registry-operation paths before a helper calls the gateway wrapper.

## Authority Rules

- Match existing gateways by canonical name and URL before using stored IDs as
  transport references.
- Match existing servers by canonical server name before updating associations.
- Match prompts by name and resources by URI before update.
- Use tool IDs only after refreshing or listing tools through the ContextForge
  API and tying the IDs back to the intended gateway/tool names.
- Treat stored IDs as readback evidence and request targets, never as canonical
  service identity by themselves.

## Non-Actions

This contract does not approve live registry mutation, service registration,
Docker/container mutation, runtime service/process/systemd changes,
client/Pi/global config writes, hook trust/state mutation, secrets/OAuth/token
handling, helper project-init approve/apply/recovery mutation, Serena
provisioning, `.project/context_forge_state.json` rewrites, governance ledger
mutation, or retired legacy checkout mutation.
