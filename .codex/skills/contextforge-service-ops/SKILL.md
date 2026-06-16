---
name: contextforge-service-ops
description: Operate and verify this repository's stock IBM ContextForge gateway and canonical MCP service fleet. Use for inventory, server-instances manifests, bridge/native transport decisions, user systemd units, ContextForge registration scripts, tool guidance registration, health probes, SSE/MCP endpoint checks, and runtime service troubleshooting.
---

# ContextForge Service Ops

Operate stock ContextForge. Do not introduce project-local duplicate gateways,
translator fleets, or service identities named after clients.

## Workflow

1. Read current local files before changing anything:
   - `AGENTS.md`
   - `README.md`
   - `server-instances/README.md`
   - the target `server-instances/<service>/instance.json`
   - relevant `scripts/register_*` or `scripts/install_user_systemd.py`.
2. Inventory client configs read-only with `scripts/inventory_mcp.py` when the
   task concerns discovered services.
3. Deduplicate by backend package/server, runtime scope, credential scope, and
   exposed resource scope. Client config names are not service identity.
4. Preserve native HTTP/SSE services. Bridge only missing transports with
   package-provided `mcpgateway.translate`.
5. Keep every exposed service grounded in `server-instances/<service-slug>/` or
   an explicitly documented equivalent.
6. Change ContextForge-owned state through ContextForge APIs or Admin UI
   behavior only. Direct database writes are diagnostic-only and prohibited for
   mutation.
7. Verify with current command output and endpoint probes before claiming
   completion.

## Commands

Use the repo venv directly:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -p 'test_control_plane_*.py'
```

Install dependencies with:

```sh
uv pip install --python .venv/bin/python <package>
```

Use `scripts/install_user_systemd.py` for user-level unit installation. System
level installs still require root and are not implicit.

## Verification Bar

For runtime claims, collect enough proof for the claim:

- gateway health and authenticated admin/API behavior
- direct bridge or native upstream `/mcp` and `/sse` where applicable
- ContextForge virtual server `/mcp` and `/sse`
- tool/resource/prompt readback where registration is involved
- user systemd unit state for local services

Read [service-map.md](references/service-map.md) for canonical services, ports,
and registration scripts.
