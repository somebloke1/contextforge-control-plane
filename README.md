# ContextForge Installation Workspace

This repository is the local operator workspace for installing and operating a
clean, stock IBM ContextForge MCP Gateway as a ContextForge-style,
systemd-managed MCP gateway. ContextForge registry/catalog records own the
assistant-facing service offering truth; repository manifests and scripts
support backend runtime and provisioning.

Branch policy:

- `main` is protected by tracked Git hooks and should only receive reviewed,
  intentional integration commits.
- `dev-root` is the root branch for agent-created work branches.
- Agent or feature branches should be created from `dev-root`, not `main`.

Local hooks are enabled with:

```sh
git config core.hooksPath .githooks
```

Python environment:

```sh
uv venv .venv
uv pip install --python .venv/bin/python mcp-contextforge-gateway
```

Current local ContextForge install:

- Keep using `uv venv .venv` and `uv pip install --python .venv/bin/python ...`.
- The intended stock install path is the PyPI package above.
- The current verified local runtime uses the official IBM `v1.0.2` source tag
  under ignored `upstream/contextforge-v1.0.2/`, installed into `.venv` after
  running the stock Admin UI build. This is a temporary upstream-packaging
  workaround: the PyPI `1.0.2` wheel includes the Vite manifest but omits the
  referenced `bundle-*.js`, which breaks the Admin UI sidebar.

Current operating direction:

- Keep the governance CRUD ledgers and `mentality` MCP service.
- Follow `dec-20260625-0001`: ContextForge registry/catalog records plus helper
  metadata own the known-service offering menu; `server-instances` remains
  backend runtime/provisioning support.
- Use stock ContextForge/package mechanisms for gateway operation, registration,
  and bridge/translation behavior.
- Keep one backend home for each exposed service under
  `server-instances/<service-slug>/`, containing sanitized backend launch/probe
  assets and any REST/OpenAPI definition ContextForge registers. These files
  are operational support, not the product service menu.
- Treat external MCP client configs as discovery sources only. Do not name or
  duplicate services after Codex, Claude, Gemini, or OpenCode unless runtime
  behavior is materially different.
- Register services natively when they already expose suitable transports.
- Bridge only missing transports for stdio, SSE-only, or HTTP-only services.
- Verify the clean gateway before registering external services.
- The current canonical service set is `mentality`, `playwright`, `ssh-tmux`,
  `context7`, `exa-search`, `openzeppelin-solidity-contracts`, `github`, and
  `web-search`.
- `scripts/install_user_systemd.py` installs user-level systemd units for the
  local ContextForge gateway and local canonical backends, including
  `exa-search`, `github`, and `web-search`. Remote services such as
  `openzeppelin-solidity-contracts` have no local unit.
- `scripts/register_tool_guidance.py` registers one reusable prompt and one
  documentation resource for each active canonical tool through the ContextForge
  API, then associates them with the corresponding virtual server. It preflights
  generated content with ContextForge's stock content-security validator and
  shapes documentation text to avoid known false positives without relaxing
  gateway-wide validation.
- The local ContextForge gateway runs on loopback HTTP at
  `http://127.0.0.1:4444`. OpenCode, Gemini CLI, and Claude Code use direct
  authenticated ContextForge HTTP entries for canonical virtual servers. Claude
  Desktop remains on `scripts/contextforge_mcp_wrapper.py` because the installed
  local Desktop config schema only exposes command/args/env-style MCP entries.
- ContextForge middleware and plugin bindings are gateway policy hooks, not a
  replacement for direct MCP transports. Use them for rate limiting, validation,
  audit, auth context, and future per-tool guardrails; do not add wrappers solely
  to reach middleware behavior when a client can call the ContextForge `/mcp`
  endpoint directly.

Runtime env files, tokens, databases, logs, generated inventories, and installed
systemd state are local operational state and must stay out of Git.
