# Open Questions

This ledger tracks questions that should remain visible without forcing an
immediate answer.

<!-- governance-crud:start id=oq-20260528-0001 -->
## oq-20260528-0001: Which stock ContextForge version and commands are installed locally?

- Ledger: open-questions
- Status: answered
- Repository: /home/dgk/workspace/context-portal
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: contextforge,install,version,verification,answered

Installed and verified stock mcp-contextforge-gateway 1.0.2 in .venv. The local uv version requires dependency installation as uv pip install --python .venv/bin/python <package>. The package exposes console scripts mcpgateway and mcpgateway-server; mcpgateway --version reports 1.0.2 and mcpgateway injects the stock ASGI app mcpgateway.main:app. uv pip check passes for 78 packages.
<!-- governance-crud:end id=oq-20260528-0001 -->

<!-- governance-crud:start id=oq-20260528-0002 -->
## oq-20260528-0002: What is the minimal clean-server proof before external registration?

- Ledger: open-questions
- Status: answered
- Repository: /home/dgk/workspace/context-portal
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: verification,health,admin-api,clean-server,answered

Clean local server proof passed on 2026-05-28 using ignored config/contextforge.env and SQLite database run/contextforge-clean.local.db. mcpgateway --validate-config succeeded, the stock gateway started on 127.0.0.1:4444, GET /health returned 200, GET /admin/login returned 200 HTML, POST /auth/login returned a bearer token for the bootstrap admin, and authenticated GETs to /admin/servers, /admin/gateways, /admin/tools, /admin/resources, and /admin/prompts each returned empty data lists before any external service registration.
<!-- governance-crud:end id=oq-20260528-0002 -->

<!-- governance-crud:start id=oq-20260528-0003 -->
## oq-20260528-0003: What host services should be registered natively?

- Ledger: open-questions
- Status: answered
- Repository: /home/dgk/workspace/context-portal
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: inventory,mcp,clients,registration,deduplication,answered

Read-only inventory is implemented in scripts/inventory_mcp.py and writes ignored report inventory/contextforge-services.local.json. The expanded host inventory currently finds 200 entries, 183 enabled, across AnythingLLM, Claude Code, Claude Desktop, Codex Terminal/project configs, Gemini CLI, OpenCode, PI Coding Assistant package settings, and workspace-local configs under /home/dgk/workspace*. Project-root .claude.json files are included. The current canonical registered service set is mentality, ssh-tmux, context7, playwright, Exa Search, OpenZeppelin Solidity Contracts, GitHub, and web-search. Native transport preservation and bridge requirements are validated in service manifests and by direct plus ContextForge virtual endpoint probes.
<!-- governance-crud:end id=oq-20260528-0003 -->

<!-- governance-crud:start id=oq-20260528-0004 -->
## oq-20260528-0004: Which services actually require bridge or translation support?

- Ledger: open-questions
- Status: answered
- Repository: /home/dgk/workspace/context-portal
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: transport,bridge,sse,http,stdio,answered

Answered by the canonical service set, as revised by dec-20260528-0030, dec-20260528-0034, and dec-20260528-0035. Playwright and OpenZeppelin Solidity Contracts are preserved as native streamable HTTP services. mentality, ssh-tmux, context7, exa-search, github, and web-search use stock mcpgateway.translate because their viable local backends are stdio or otherwise need local transport exposure. Exa Search uses server-instances/exa-search on 127.0.0.1:9105 with both /mcp and /sse. GitHub uses server-instances/github on 127.0.0.1:9106 with both /mcp and /sse. Web-search uses server-instances/web-search on 127.0.0.1:9107 with both /mcp and /sse. Context7 native HTTP mode was checked and rejected for this install because it requires UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN, which were not in the discovered configs.
<!-- governance-crud:end id=oq-20260528-0004 -->

<!-- governance-crud:start id=oq-20260528-0005 -->
## oq-20260528-0005: What proof is required for systemd-controlled completion?

- Ledger: open-questions
- Status: answered
- Repository: /home/dgk/workspace/context-portal
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: systemd,completion,admin-ui,endpoints,answered

Answered by current verification. User-level systemd units contextforge.target, contextforge-gateway.service, contextforge-mentality.service, contextforge-ssh-tmux.service, contextforge-context7.service, contextforge-playwright.service, contextforge-exa-search.service, contextforge-github.service, and contextforge-web-search.service are installed, enabled, and active where local units are required. Remote OpenZeppelin Solidity Contracts is registered through ContextForge and requires no local unit. Verification commands covered gateway health, authenticated registry API state, direct backend /mcp and /sse probes where applicable, virtual server /mcp/ and /sse probes, tool/resource/prompt readback, and client MCP list output.
<!-- governance-crud:end id=oq-20260528-0005 -->

<!-- governance-crud:start id=oq-20260528-0006 -->
## oq-20260528-0006: Where should the self-signed certificate live for the systemd install?

- Ledger: open-questions
- Status: answered
- Repository: /home/dgk/workspace/context-portal
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: https,tls,systemd,install,answered

Answered for the current local user-level systemd install by dec-20260528-0043. No certificate is required for normal operation because contextforge-gateway.service now runs plain loopback HTTP on http://127.0.0.1:4444. The prior self-signed localhost/127.0.0.1 certificate and key may remain in ignored config/tls/ as optional future material, but they are not referenced by the active unit.
<!-- governance-crud:end id=oq-20260528-0006 -->

<!-- governance-crud:start id=oq-20260528-0007 -->
## oq-20260528-0007: Which inventory entries need real secret or auth resolution before bridge startup?

- Ledger: open-questions
- Status: answered
- Repository: /home/dgk/workspace/context-portal
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: inventory,secrets,auth,bridges,answered

Answered by service selection and exclusions, as revised by dec-20260528-0030, dec-20260528-0034, dec-20260528-0035, and dec-20260528-0036. Context7 requires CONTEXT7_API_KEY in ignored server-instances/context7/.env. Exa Search requires EXA_API_KEY and GEMINI_API_KEY in ignored server-instances/exa-search/.env. GitHub obtains GITHUB_PERSONAL_ACCESS_TOKEN at runtime from gh auth token inside server-instances/github/run-bridge.sh and does not store the token in tracked files or client configs. Web-search can use optional provider keys from ignored server-instances/web-search/.env. OpenZeppelin remains a remote native gateway already registered through ContextForge. Fetch, ZAI, Gemini tools, filesystem, code-index, desktop-commander, and node_repl remain excluded. ssh-tmux, mentality, and playwright require no additional secret env file for the current local operation.
<!-- governance-crud:end id=oq-20260528-0007 -->

<!-- governance-crud:start id=oq-20260528-0008 -->
## oq-20260528-0008: What bridge port allocation should server-instances use?

- Ledger: open-questions
- Status: answered
- Repository: /home/dgk/workspace/context-portal
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: server-instances,ports,bridges,operations

Answered for the current canonical service set, as revised by dec-20260528-0030, dec-20260528-0034, and dec-20260528-0035: mentality uses 9100, ssh-tmux uses 9102, context7 uses 9103, playwright uses 9104, exa-search uses 9105, github uses 9106, and web-search uses 9107. Remote native services such as OpenZeppelin Solidity Contracts have documented server-instances homes but no local bridge ports. Future inventory syncs should preserve existing canonical ports unless an operator intentionally rebalances them.
<!-- governance-crud:end id=oq-20260528-0008 -->

<!-- governance-crud:start id=oq-20260528-0009 -->
## oq-20260528-0009: Should ContextForge virtual servers be per-upstream or grouped by client/use case?

- Ledger: open-questions
- Status: answered
- Repository: /home/dgk/workspace/context-portal
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: contextforge,virtual-servers,registration,ux,answered

Answered for the current installation: create one canonical virtual server per canonical upstream service. The live registry has mentality_server, ssh_tmux_server, context7_local_server, playwright_server, exa_search_server, openzeppelin_solidity_contracts_server, github_server, and web_search_server. Client config names are discovery metadata only and are not used for service identity.
<!-- governance-crud:end id=oq-20260528-0009 -->

<!-- governance-crud:start id=oq-20260528-0010 -->
## oq-20260528-0010: When can local source install be replaced by corrected upstream package?

- Ledger: open-questions
- Status: open
- Repository: /home/dgk/workspace/context-portal
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: contextforge,packaging,admin-ui,systemd

The current local runtime depends on an ignored official source checkout because the PyPI 1.0.2 wheel omits the Vite Admin UI bundle. Track whether IBM publishes a corrected wheel or documents a production source-install/build step that should replace the local source checkout approach before final systemd installation.
<!-- governance-crud:end id=oq-20260528-0010 -->

<!-- governance-crud:start id=oq-20260528-0011 -->
## oq-20260528-0011: How should the Admin UI token CSRF collision be resolved upstream?

- Ledger: open-questions
- Status: answered
- Repository: /home/dgk/workspace/context-portal
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: contextforge,admin-ui,csrf,tokens,local-runtime

Answered locally by dec-20260528-0028. ContextForge has two token classes here: interactive session JWTs and cataloged API tokens created by `/tokens`. Live evidence showed that cataloged API token creation through `/tokens` works, but Admin UI cookie-auth requests can fail when the global CSRF middleware receives the admin-page CSRF cookie instead of the HMAC CSRF value tied to the session JWT. The local installation now uses stock `CSRF_EXEMPT_PATHS` for `/api/logs` and `/tokens`, preserving authentication and permission checks while avoiding the cookie-name collision. Upstream may still need to separate or document the Admin UI CSRF and API HMAC CSRF token flows.
<!-- governance-crud:end id=oq-20260528-0011 -->

<!-- governance-crud:start id=oq-20260528-0012 -->
## oq-20260528-0012: Should upstream ContextForge narrow content-security false positives for documentation resources?

- Ledger: open-questions
- Status: open
- Repository: /home/dgk/workspace/context-portal
- Created: 2026-05-28
- Updated: 2026-05-30
- Tags: contextforge,content-security,upstream,prompts,resources

Local prompt/resource writes must keep stock ContextForge content-security validation enabled, preflight generated content, and shape benign Markdown or prose locally rather than disabling validation. The upstream false-positive policy question remains open: track whether IBM narrows those content-security patterns, adds context-aware validation, or documents a safer admin documentation workflow.
<!-- governance-crud:end id=oq-20260528-0012 -->

<!-- governance-crud:start id=oq-20260528-0013 -->
## oq-20260528-0013: Which discovered noncanonical tool backends should become ContextForge services?

- Ledger: open-questions
- Status: open
- Repository: /home/dgk/workspace/context-portal
- Created: 2026-05-28
- Updated: 2026-05-30
- Tags: inventory,candidates,pi,workspace,scope

Noncanonical discovered backends stay candidates or handoffs until service-management deduplicates, plans, approves, and records canonical service identity. The RFC-named seed proof services are Serena and project-inspector; other discovered backends cannot become canonical ContextForge services merely because a client config mentions them.
<!-- governance-crud:end id=oq-20260528-0013 -->

<!-- governance-crud:start id=oq-20260528-0014 -->
## oq-20260528-0014: Should direct HTTP MCP clients use env bearer auth or wait for OAuth repair?

- Ledger: open-questions
- Status: answered
- Repository: /home/dgk/workspace/context-portal
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: contextforge,clients,http,oauth,auth,opencode,gemini-cli,claude-code

Answered by dec-20260528-0043. Do not wait for OpenCode OAuth repair for local operation. Direct-capable clients use authenticated plain HTTP to the local ContextForge virtual-server /mcp endpoints with bearer headers. OpenCode OAuth CSRF behavior can remain a separate upstream/admin-flow concern, but it is not on the operational path for these local MCP entries. Claude Desktop remains wrapper-based because its local config schema is stdio-oriented.
<!-- governance-crud:end id=oq-20260528-0014 -->

<!-- governance-crud:start id=oq-20260528-0016 -->
## oq-20260528-0016: Can OpenCode direct ContextForge HTTPS avoid self-signed certificate failures?

- Ledger: open-questions
- Status: answered
- Repository: /home/dgk/workspace/context-portal
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: contextforge,opencode,http,tls,client-config

Operationally answered by dec-20260528-0043. OpenCode direct remote MCP entries with headers now connect to local ContextForge over plain http://127.0.0.1:4444, with oauth:false, avoiding the self-signed HTTPS failure. The narrower HTTPS trust-store question is no longer blocking local operation; reopen only if local TLS is required again.
<!-- governance-crud:end id=oq-20260528-0016 -->

<!-- governance-crud:start id=oq-20260528-0015 -->
## oq-20260528-0015: Can Claude Code direct ContextForge HTTPS work without launch-specific CA env?

- Ledger: open-questions
- Status: answered
- Repository: /home/dgk/workspace/context-portal
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: contextforge,claude-code,http,tls,client-config

Operationally answered by dec-20260528-0043. Claude Code does support direct HTTP MCP entries with headers, and it now connects to local ContextForge over plain http://127.0.0.1:4444 without launch-specific CA environment. The narrower HTTPS trust-store question is no longer blocking local operation; reopen only if local TLS is required again.
<!-- governance-crud:end id=oq-20260528-0015 -->

<!-- governance-crud:start id=oq-20260528-0017 -->
## oq-20260528-0017: Can Gemini CLI direct ContextForge HTTPS work in normal MCP listing?

- Ledger: open-questions
- Status: answered
- Repository: /home/dgk/workspace/context-portal
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: contextforge,gemini-cli,http,tls,client-config

Operationally answered by dec-20260528-0043. Gemini CLI direct HTTP MCP entries with headers now connect to local ContextForge over plain http://127.0.0.1:4444 without launch-specific CA environment. The narrower HTTPS trust-store question is no longer blocking local operation; reopen only if local TLS is required again.
<!-- governance-crud:end id=oq-20260528-0017 -->

<!-- governance-crud:start id=oq-20260528-0018 -->
## oq-20260528-0018: Should non-assistant workspace REST APIs be considered for ContextForge?

- Ledger: open-questions
- Status: open
- Repository: /home/dgk/workspace/context-portal
- Created: 2026-05-28
- Updated: 2026-05-30
- Tags: inventory,rest-api,workspace,scope

Non-assistant workspace REST APIs are not automatically promoted into ContextForge by the control-plane MVS. Explicit user or service-management intent is required, and unrelated discovered REST services cannot use the built-in seed path. They remain outside this MCP consolidation scope unless separately approved.
<!-- governance-crud:end id=oq-20260528-0018 -->

<!-- governance-crud:start id=oq-20260529-0001 -->
## oq-20260529-0001: Should project-init explicitly manage Codex project trust?

- Ledger: open-questions
- Status: answered
- Repository: /home/dgk/workspace/context-portal
- Created: 2026-05-29
- Updated: 2026-05-30
- Tags: codex,project-init,trust,serena,answered

Codex project trust may be handled only through brokered, separate human approval with receipt-backed evidence and verification through actual config consumption. Generic project-init approval must not silently add trust. Project initialization may surface a trust gap, prepare a separate trust approval request, and wait for verified user-global trust evidence, but it must not bundle trust mutation into Serena provisioning or generic project setup.
<!-- governance-crud:end id=oq-20260529-0001 -->

<!-- governance-crud:start id=oq-20260531-0001 -->
## oq-20260531-0001: Which services need first-class safe ContextForge probes instead of skipped validation?

- Ledger: open-questions
- Status: open
- Repository: /home/dgk/workspace/context-portal
- Created: 2026-05-31
- Updated: 2026-05-31
- Tags: contextforge,project-init,validation,service-probes,skipped-services

Some services can still be skipped during project-init validation when there is no safe default probe payload for the target-client-visible ContextForge route. Future work should decide and implement service-specific safe probes where appropriate, such as harmless search queries, read-only metadata calls, or no-op/list operations, while avoiding built-in-tool substitution, direct backend checks, secret exposure, and mutation. Until those probes exist, skipped services must remain explicitly marked as skipped or presumed working and must not be represented as validated by equivalent local shell or built-in tool behavior.
<!-- governance-crud:end id=oq-20260531-0001 -->
