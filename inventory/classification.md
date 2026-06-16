# MCP And Tool Backend Classification

Generated from the current ignored inventory report:
`inventory/contextforge-services.local.json`.

Last refreshed: 2026-06-16 from clean branch
`codex/service-inventory-triage`.

## Inventory Summary

- Total entries: 207
- Enabled entries: 203
- Transport classes: 125 assistant package, 72 stdio, 6 streamable HTTP,
  4 unknown
- Clients/projects covered:
  - AnythingLLM: 1
  - Claude Code: 9 global, 2 project-local
  - Claude Desktop: 7
  - Codex Terminal: 2
  - Codex project-local configs: 52
  - ContextForge repo-local service: 1 (`context-portal` inventory label)
  - Gemini CLI: 1
  - OpenCode: 1 global, 6 project-local
  - Pi Coding Assistant package settings: 125

The generated report is local and drift-prone. Older roadmap, issue, and
ledger counts of 191/187, 197/193, and 200/183 are historical snapshots, not
the current clean-worktree state.

## Current Classification Buckets

| Bucket | Current examples | Disposition |
| --- | --- | --- |
| Already covered by canonical ContextForge services | `mentality`, `ssh_tmux`, `context7`, `playwright`, `exa_search`, `openzeppelin_solidity_contracts`, `github`, `web_search` | Keep deduplicated through the existing `server-instances/<service-slug>/` homes and ContextForge virtual servers. Current inventory has 62 direct canonical-name rows, 60 enabled. |
| Exclude unless scope changes | `desktop-commander`, `desktop-automation`, `filesystem`, `filesystem-project`, `gemini-mcp`, `zai-mcp-server`, `node_repl`, `qwen_delegate` | Do not promote from client config presence alone. Keep out of ContextForge until a new service-management decision changes scope and security posture. |
| Project-local only | `serena`, repo-local `governance_crud`, `mtga_builder_governance` | Preserve local project ownership. These entries carry repo or workspace scope that is not a gateway-wide service identity by default. |
| Service-management candidates | `pi-web-access`, `pi-claude-bridge`, `invoiceapi`, non-assistant workspace REST/API source hints | Keep as handoff candidates requiring backend identity, runtime scope, credential scope, approval, and a concrete `server-instances/<service-slug>/` home or documented equivalent before promotion. |

The four current `unknown` transport rows are OpenCode project rows:
disabled `desktop-automation`, disabled `desktop-commander`, disabled
`playwright` in `saeproj`, and enabled shape-less `playwright` in
`semantic-lab`. They remain triage evidence, not automatic promotion
evidence.

## Candidate Follow-Up Debt

| Candidate | Owner | Impact | Next evidence step | Review trigger | Retirement condition |
| --- | --- | --- | --- | --- | --- |
| `pi-web-access` and `pi-claude-bridge` | ContextForge service-management operator | Pi package rows dominate inventory volume; treating each worktree entry as a service would recreate client-config duplication. | Prove whether each package is a reusable MCP/HTTP backend, assistant-package-only integration, or project-local Pi capability; deduplicate by package/runtime/credential scope. | Pi global shim parity, Pi project-init activation, or explicit user request for centralized Pi web/Claude bridge capability. | Approved canonical service identity with backend home and probes, or explicit exclusion/project-local disposition recorded in service-management docs. |
| `invoiceapi` | Owning project operator for `/home/dgk/workspace/profit-system-agent-currency` | May require project credentials or billing-domain scope; unsafe to promote from Claude project config alone. | Inspect backend package, credential requirements, runtime scope, and read-only probe options in the owning project. | Owning project asks for ContextForge exposure or cross-client use. | Classified as project-local/excluded, or promoted through an approved `server-instances/<service-slug>/` home with sanitized env template and probes. |
| External repo-local governance MCPs | Owning repository maintainers plus ContextForge governance operator | Similar to `mentality`, but ledger scope is repository-local and may not be safe to centralize. | Decide whether cross-repo governance should consolidate into `mentality` or remain separate project-local MCPs. | Cross-repo governance workflow requires centralized access. | Consolidation decision plus migration/probes, or durable project-local classification in the owning repo. |
| Non-assistant workspace REST/API source hints | ContextForge service-management operator | Application internals can look like tool backends but are not MCP client definitions. | Separate application API cataloging from MCP service inventory; identify any real reusable API/tool boundary. | A workspace API is requested as a ContextForge tool or service. | Promoted through approved REST/OpenAPI registration assets, or removed from MCP promotion consideration. |

## Canonical ContextForge Services

| Client-facing name | ContextForge virtual server | Backend home | Status |
| --- | --- | --- | --- |
| `mentality` | `mentality_server` | `server-instances/mentality` | registered |
| `ssh_tmux` | `ssh_tmux_server` | `server-instances/ssh-tmux` | registered |
| `context7` | `context7_local_server` | `server-instances/context7` | registered |
| `playwright` | `playwright_server` | `server-instances/playwright` | registered |
| `exa_search` | `exa_search_server` | `server-instances/exa-search` | registered |
| `openzeppelin_solidity_contracts` | `openzeppelin_solidity_contracts_server` | `server-instances/openzeppelin-solidity-contracts` | registered |
| `github` | `github_server` | `server-instances/github` | registered |
| `web_search` | `web_search_server` | `server-instances/web-search` | registered |

Active client configs use these names without a `contextforge` prefix.

## Scope Contracts

The canonical service manifests now declare whether local-project scope is
required and how that scope is signaled:

| Service | Local project scope required? | Configuration signal |
| --- | --- | --- |
| `mentality` | Yes | Required `repo` tool argument on every governance tool call |
| `ssh_tmux` | No | Explicit SSH/tmux session and remote path arguments |
| `context7` | No | Library/package IDs and topic arguments |
| `playwright` | No | Isolated browser session plus requested URL/page actions |
| `exa_search` | No | Provider credentials plus query/URL arguments |
| `openzeppelin_solidity_contracts` | No | Contract/template tool selection and request arguments |
| `github` | No | Runtime GitHub account plus explicit `owner`/`repo` style arguments |
| `web_search` | No | Provider credentials plus query, URL, PDF, or repository URL arguments |

Project-local governance MCPs in other repositories remain candidates rather
than centralized services because their repo-specific ledger scope has not been
approved for consolidation into `mentality`.

## Old Service Mapping

| Discovered service/backend | Current disposition |
| --- | --- |
| `ssh-mcp`, `@alolite/ssh-mcp` | replaced by canonical `ssh_tmux` through `ssh_tmux_server` |
| `@upstash/context7-mcp` | canonical `context7` through `context7_local_server` |
| `@playwright/mcp` | canonical `playwright` through `playwright_server` |
| Exa/web-search wrappers promoted for this install | canonical `exa_search` through `exa_search_server` |
| OpenZeppelin Solidity Contracts hosted MCP | canonical `openzeppelin_solidity_contracts` through `openzeppelin_solidity_contracts_server` |
| `@modelcontextprotocol/server-github` in OpenCode | canonical `github` through `github_server` |
| `/home/dgk/workspace/web_search/dist/mcp-server.js` | canonical `web_search` through `web_search_server` |
| Repo-local governance MCP in this repo | canonical `mentality` through `mentality_server` |

## Prior Exclusions

Do not promote these unless the scope changes: `fetch-mcp`, `zai-mcp-server`,
`gemini-mcp`, filesystem MCPs, code-index MCPs, `desktop-commander`,
desktop automation, disabled `open-computer-use`, and `node_repl`.

Representative evidence paths:

- `/home/dgk/.config/opencode/opencode.json`
- `/home/dgk/.gemini/settings.json`
- `/home/dgk/.claude.json`
- `/home/dgk/.config/Claude/claude_desktop_config.json`
- `/home/dgk/.codex/config.toml`

## Candidate Services Still Requiring Confirmation

| Candidate | Evidence | Notes |
| --- | --- | --- |
| `pi-web-access` | Multiple `.pi/settings.json` and `.pi-user/settings.json` files under `/home/dgk/workspace*`; `npm view pi-web-access` | PI Coding Assistant package integration, not yet proven as an MCP/HTTP backend suitable for ContextForge registration. Current npm version is `0.10.7`; package description covers web search, URL fetching, GitHub repo cloning, PDF extraction, YouTube understanding, and local video analysis for the Pi coding agent. Inventory versions found include unpinned, `0.10.6`, `0.10.7`, and `^0.10.6`. |
| `pi-claude-bridge` | Multiple `.pi/settings.json` and `.pi-user/settings.json` files under `/home/dgk/workspace*`; `npm view pi-claude-bridge` | PI Coding Assistant package integration, not yet proven as a canonical service. Current npm version is `0.4.0`; package description says it uses Claude Code via Agent SDK as a model provider and adds an AskClaude tool. Inventory versions found include unpinned, `0.3.1`, and `^0.3.1`. |
| `invoiceapi` | `/home/dgk/workspace/profit-system-agent-currency/.claude/settings.json` | Project-local Claude Code stdio MCP: `node /home/dgk/workspace/profit-system-agent-currency/invoiceapi-mcp/dist/index.js`. Needs backend scope and credential review before promotion. |
| External repo-local governance MCPs | `/home/dgk/workspace/cognitive-dimr/.codex/config.toml`, `/home/dgk/workspace/mtga-builder/.codex/config.toml` | Similar governance pattern to `mentality`, but repository-specific ledgers may make them intentionally project-local. |
| Non-assistant workspace REST/API source hints | `/home/dgk/workspace/cognitive_embeddings/src/backend/server.js`, `/home/dgk/workspace/semantic-lab/src/semantic_lab/api/dependencies.py`, noetic/phronesis/pi2 HTTP route and PI web-fetch sources | These are project application internals or PI extension/package implementation files, not current MCP client definitions. Track separately in `oq-20260528-0018` before treating general project REST APIs as ContextForge candidates. |

## PI Coding Assistant MCP Bridge Source

The PI package settings expose `pi-web-access` and `pi-claude-bridge` as package
integrations, not generic MCP service definitions. The actionable PI MCP
definitions found so far are hand-written `mcp-bridge` extension sources that
spawn MCP stdio children and re-export selected tools to PI.

Updated active bridge sources:

- `/home/dgk/.pi/agent/extensions/mcp-bridge/index.ts`: `c7_*` and `pw_*`
  now spawn `scripts/contextforge_mcp_wrapper.py` for
  `context7_local_server` and `playwright_server`.
- `/home/dgk/workspace/noetic-pi/.pi/extensions/mcp-bridge/index.ts`:
  `c7_*`, `pw_*`, `ssh_execute`, and `ssh_connections` now route through
  `context7_local_server`, `playwright_server`, and `ssh_tmux_server`.
- `/home/dgk/workspace/phronesis/.pi/extensions/mcp-bridge/index.ts`:
  same ContextForge routing as `noetic-pi`.

The PI-facing tool names are preserved. The adapter normalizes old upstream
MCP names like `resolve-library-id`, `browser_click`, and `browser_tabs` to the
ContextForge-prefixed tool names exposed by the canonical virtual servers.
`ssh_execute` is adapted to `ssh-tmux-open-session` plus
`ssh-tmux-send-command` when no `session_id` is supplied, and
`ssh_connections` maps to list/close operations on ssh-tmux sessions.

Remaining PI bridge files with direct `@upstash/context7-mcp`,
`@playwright/mcp`, or `@alolite/ssh-mcp` references are in variant, prep,
closure, worktree, or archive directories, including:

- `/home/dgk/workspace/phronesis-variant3/.pi/extensions/mcp-bridge/index.ts`
- `/home/dgk/workspace/noetic-pi-ai0115-prep/.pi/extensions/mcp-bridge/index.ts`
- `/home/dgk/workspace/noetic-pi-v02-closure-exec-20260430/.pi/extensions/mcp-bridge/index.ts`
- hidden worktrees under `/home/dgk/workspace/.noetic-pi-worktrees/` and
  `/home/dgk/workspace/.phronesis-worktrees/`
- public export archives under `/home/dgk/workspace/__archive/`

These are classified as needing confirmation before bulk editing because they
look like generated variants or historical snapshots rather than the active
global/user project bridge source.

## Current Client Replacement State

- OpenCode, Gemini CLI, and Claude Code global canonical services now use direct
  authenticated HTTP entries to the local ContextForge gateway on
  `http://127.0.0.1:4444`.
- AnythingLLM's global `context7` entry now preserves the client-facing name and
  launches `scripts/contextforge_mcp_wrapper.py context7_local_server`, removing
  a duplicate direct `@upstash/context7-mcp` backend from that client config.
- Codex global disabled `exa_web_search` and project-local
  `/home/dgk/workspace/web_search` `web_search` now run
  `scripts/contextforge_mcp_wrapper.py web_search_server`.
- Active target configs no longer contain `ssh-mcp`,
  `@alolite/ssh-mcp`, `@modelcontextprotocol/server-github`, or the inline
  `GITHUB_PERSONAL_ACCESS_TOKEN=$(gh auth token)` command. The remaining
  target config references to `/home/dgk/workspace/web_search` route through
  ContextForge rather than launching `dist/mcp-server.js` directly.
- Direct ContextForge `/mcp` and `/sse` endpoints require authentication.
  OpenCode, Gemini CLI, and Claude Code represent direct bearer-header HTTP
  entries. Plain loopback HTTP is intentionally used for normal local operation
  to avoid client-specific self-signed HTTPS trust workarounds.

## Direct Transport Evaluation

Direct ContextForge streamable HTTP was tested against local virtual-server
endpoints such as
`http://127.0.0.1:4444/servers/898d2179080744ffadd0add57494f197/mcp/`.

| Client | Direct transport support | Auth result | Current action |
| --- | --- | --- | --- |
| OpenCode | `type: "remote"` with `url` and `headers` works | Direct local HTTP connects; `oauth:false` avoids the separate OAuth CSRF path | Use direct HTTP |
| Gemini CLI | `type: "http"` with `url` and `headers` works | Direct local HTTP connects | Use direct HTTP |
| Claude Code | `--transport http` / `type: "http"` with headers works | Direct local HTTP connects | Use direct HTTP |
| Claude Desktop | Local `claude_desktop_config.json` validates only `command`, optional `args`, optional string-valued `env`, and optional `extensionId` for `mcpServers` entries in the installed Desktop app | Direct transport code exists inside the app, but local config `url`/`headers` entries would fail the app's config validation and be skipped | Keep stdio wrapper |

The wrapper remains useful for clients that only have a reliable stdio config
path because it logs in through ignored local ContextForge runtime state. Direct
HTTP clients use the loopback HTTP gateway and do not require local CA handling.

Claude Desktop evidence: the installed `/usr/lib/claude-desktop` package is
Claude Desktop `1.1348.0`. Its packed `app.asar` validates
`claude_desktop_config.json` with a local `mcpServers` schema whose server
config is `{ command: string, args?: string[], env?: Record<string,string>,
extensionId?: string }`. The same app contains internal `SSEClientTransport` and
`StreamableHTTPClientTransport` implementations with request header support, but
those are not exposed by the local JSON config schema inspected here.

## ContextForge Middleware Evaluation

ContextForge middleware is relevant to operating the gateway, but it does not
change the direct-vs-wrapper transport decision. The stock request middleware
handles gateway-wide behavior such as auth context, token scoping, protocol
version checks, validation, request logging, token usage, CSRF, and rate
limiting. Tool plugin bindings add per-tool hook behavior around tool execution
with modes such as sequential, concurrent, transform, audit, and fire-and-forget.

Current implication:

- Direct HTTP/SSE remains preferred where a client supports authenticated
  streamable HTTP to the ContextForge virtual-server `/mcp` endpoint.
- Middleware is the right place to configure gateway policy such as rate
  limits, validation, audit, and future per-tool guardrails.
- Middleware is not a reason to introduce a stdio wrapper for OpenCode, Gemini
  CLI, or Claude Code; direct HTTP requests would already traverse the
  ContextForge middleware stack. Their active entries now use direct loopback
  HTTP.
- Tool plugin bindings may become useful later for per-tool policy or argument
  transformation, but they are not needed for the current local-project scope
  signaling. The only current centralized service requiring local-project scope
  is `mentality`, and its scope is already signaled by the required `repo`
  argument.

Rate limiting is configurable by ContextForge environment settings. The stock
configuration exposes `RATE_LIMITING_ENABLED`, `RATE_LIMITING_REDIS_ENABLED`,
per-tier request-per-minute and burst settings for critical, high, medium, and
low endpoint classes, plus lockout settings. The local ignored
`config/contextforge.env` currently contains rate limiting and lockout entries.
