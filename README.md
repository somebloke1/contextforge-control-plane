# ContextPortal Installation Workspace

This repository is the local source of truth for installing and operating IBM
ContextForge MCP Gateway as a ContextPortal-style, systemd-managed MCP gateway.

Branch policy:

- `main` is protected by tracked Git hooks and should only receive reviewed,
  intentional integration commits.
- `dev-root` is the root branch for agent-created work branches.
- Agent or feature branches should be created from `dev-root`, not `main`.

Local hooks are enabled with:

```sh
git config core.hooksPath .githooks
```

The hooks block direct commits and pushes to `main` unless an explicit
administrative override environment variable is set.
