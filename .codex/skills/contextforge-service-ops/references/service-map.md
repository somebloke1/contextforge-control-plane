# Service Map

Gateway:

- Local ContextForge gateway: `http://127.0.0.1:4444`.
- Runtime env belongs in ignored `config/contextforge.env`.
- The local install uses `.venv` and may use ignored
  `upstream/contextforge-v1.0.2/` as a stock-source workaround for the Admin UI
  packaging issue.

Canonical service set:

| Service | Backend home | Transport note |
| --- | --- | --- |
| `mentality` | `server-instances/mentality` | stdio bridged on `127.0.0.1:9100` |
| `ssh-tmux` | `server-instances/ssh-tmux` | stdio bridged on `127.0.0.1:9102` |
| `context7` | `server-instances/context7` | stdio bridged on `127.0.0.1:9103` |
| `playwright` | `server-instances/playwright` | native HTTP/SSE on `127.0.0.1:9104` |
| `exa-search` | `server-instances/exa-search` | local backend bridged on `127.0.0.1:9105` |
| `github` | `server-instances/github` | stdio bridged on `127.0.0.1:9106` |
| `web-search` | `server-instances/web-search` | local backend bridged on `127.0.0.1:9107` |
| `openzeppelin-solidity-contracts` | `server-instances/openzeppelin-solidity-contracts` | remote native streamable HTTP |
| `serena-context-portal` | `server-instances/serena-context-portal` | project-scoped native HTTP, currently `127.0.0.1:9108` |

Important scripts:

- `scripts/inventory_mcp.py`: read-only MCP client config inventory.
- `scripts/install_user_systemd.py`: user systemd unit installation.
- `scripts/register_tool_guidance.py`: prompt/resource guidance registration.
- `scripts/register_*_service.py`: service-specific registration helpers.
- `scripts/contextforge_mcp_wrapper.py`: wrapper for stdio-only clients.

Safety checks:

- Never commit `.env`, generated JWTs, API keys, local DBs, local inventory
  outputs ending in `.local.json`, generated diagnostics, or runtime logs.
- Use direct endpoint probes and ContextForge readback as authority; manifests
  are desired state, not proof of running behavior.
