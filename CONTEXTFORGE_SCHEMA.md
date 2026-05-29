# ContextForge API Schema

This file is the local operator reference for the ContextForge API used by
ContextForge. It is intentionally API-first: use these HTTP/API surfaces before
touching any ContextForge-owned database table.

Authoritative sources in this checkout:

- Live schema: `GET /openapi.json` on the running gateway, authenticated in the
  local ContextForge install.
- Interactive docs: `GET /docs` and `GET /redoc` when enabled by the running
  FastAPI application and reachable through local auth.
- Route definitions: `upstream/contextforge-v1.0.2/mcpgateway/main.py` and
  `upstream/contextforge-v1.0.2/mcpgateway/routers/*.py`.
- Request and response models:
  `upstream/contextforge-v1.0.2/mcpgateway/schemas.py`,
  `upstream/contextforge-v1.0.2/mcpgateway/routers/tokens.py`, and related
  router model modules.

## Operating Rules

- Direct ContextForge database mutations are prohibited by
  `dec-20260528-0029`. Direct database reads are allowed for diagnosis and
  verification only.
- Registry changes must use the JSON API or the Admin UI behavior that calls
  that API.
- Prefer JSON API routes such as `/gateways`, `/servers`, `/tools`,
  `/resources`, `/prompts`, `/tokens`, and `/teams` for automation.
- Treat `/admin/...` routes as browser/Admin UI implementation endpoints unless
  there is no JSON API equivalent.
- For MCP upstreams, register the upstream as a ContextForge gateway, let
  ContextForge discover gateway tools, then expose those tools through a virtual
  server. Do not hand-insert MCP tools.
- A gateway-discovered MCP tool's `team_id` and `owner_email` are inherited at
  discovery time. `ToolUpdate` can change `visibility` but does not accept
  `team_id` or `owner_email`; if ownership must be rebuilt, use an API-supported
  gateway/tool lifecycle such as delete and recreate.
- Do not print or commit bearer tokens, generated JWTs, passwords, API keys, or
  upstream auth material.

## Authentication And Tokens

There are two token classes in this installation:

- Session/authentication JWTs: created by login flows and used for interactive
  or bearer-authenticated API access.
- Cataloged API tokens: created by `/tokens`, stored by hash in the token
  catalog, revocable by JTI, and optionally scoped to a server, team, IP range,
  permission set, time restriction, or usage limit.

Important auth routes:

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/auth/csrf-token` | Issue/read CSRF material for API flows that require it. |
| `POST` | `/auth/login` | Main username/password login; returns an authentication response/JWT. |
| `POST` | `/auth/logout` | End the authenticated session. |
| `POST` | `/auth/email/login` | Email-auth login flow. |
| `POST` | `/auth/email/register` | Register an email-auth user when enabled. |
| `POST` | `/auth/email/change-password` | Change password for the current authenticated user. |
| `POST` | `/auth/email/forgot-password` | Start password reset. |
| `GET` | `/auth/email/reset-password/{token}` | Validate a password reset token. |
| `POST` | `/auth/email/reset-password/{token}` | Complete password reset. |
| `GET` | `/auth/email/me` | Read the current authenticated email user profile. |
| `GET` | `/auth/email/events` | Read auth events for the current user. |
| `GET` | `/auth/email/admin/users` | Admin list users. |
| `POST` | `/auth/email/admin/users` | Admin create user. |
| `GET` | `/auth/email/admin/users/{user_email}` | Admin read a user. |
| `PATCH` | `/auth/email/admin/users/{user_email}` | Admin update a user. |
| `PUT` | `/auth/email/admin/users/{user_email}` | Deprecated full user update. |
| `DELETE` | `/auth/email/admin/users/{user_email}` | Admin delete user. |
| `POST` | `/auth/email/admin/users/{user_email}/unlock` | Unlock a locked user. |

Cataloged API token routes:

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/tokens` | Create a personal cataloged API token and return the one-time raw token. |
| `GET` | `/tokens` | List personal tokens and visible team tokens. |
| `GET` | `/tokens/{token_id}` | Read one token catalog record. |
| `PUT` | `/tokens/{token_id}` | Update token metadata, active state, tags, or scope. |
| `DELETE` | `/tokens/{token_id}` | Revoke a token the caller owns or is authorized to revoke. |
| `GET` | `/tokens/{token_id}/usage` | Read token usage statistics. |
| `GET` | `/tokens/admin/all` | Admin list all cataloged tokens. |
| `DELETE` | `/tokens/admin/{token_id}` | Admin revoke any cataloged token. |
| `POST` | `/tokens/teams/{team_id}` | Create a team-scoped cataloged API token. |
| `GET` | `/tokens/teams/{team_id}` | List team-scoped tokens. |

Token create/update scope shape:

- `name`: unique token name for the user and team scope.
- `description`: optional human explanation.
- `expires_in_days` or equivalent expiry field: optional unless the server
  requires token expiration.
- `team_id`: present for team-scoped tokens.
- `scope.server_id`: optional virtual server limitation.
- `scope.permissions`: explicit permissions. Empty or omitted scope inherits
  behavior according to the token service and caller authorization.
- `scope.ip_restrictions`: allowed IPs or CIDR ranges.
- `scope.time_restrictions`: time/day/timezone limits.
- `scope.usage_limits`: request or usage ceilings.
- `tags`: organizational labels.

## Core Registry API

### Gateways

Gateways are upstream MCP servers, REST aggregations, or remote gateway
endpoints known to ContextForge. For ContextForge service exposure, a gateway
usually points at a backend under `server-instances/<service-slug>/` or at a
documented remote native MCP endpoint.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/gateways` and `/gateways/` | List registered gateways. Supports pagination/filtering in the schema. |
| `POST` | `/gateways` and `/gateways/` | Register a gateway and discover/cache its MCP tools when applicable. |
| `GET` | `/gateways/{gateway_id}` | Read one gateway. |
| `PUT` | `/gateways/{gateway_id}` | Update gateway metadata, URL, transport, auth, visibility, TLS, or mode. |
| `DELETE` | `/gateways/{gateway_id}` | Delete a gateway and its owned discovered objects according to service logic. |
| `POST` | `/gateways/{gateway_id}/state` | Set enabled state explicitly. |
| `POST` | `/gateways/{gateway_id}/toggle` | Deprecated toggle helper; prefer `/state`. |
| `POST` | `/gateways/{gateway_id}/tools/refresh` | Re-read upstream capabilities and add/update/remove gateway-discovered tools. |

`GatewayCreate` and `GatewayUpdate` fields that matter operationally:

- `name`: unique gateway name.
- `url`: upstream endpoint, such as `http://127.0.0.1:9103/sse` or a remote
  streamable HTTP MCP endpoint.
- `description`: human explanation.
- `transport`: `SSE` or `STREAMABLEHTTP`.
- `auth_type`: `basic`, `bearer`, `authheaders`, `oauth`, `query_param`, or
  none.
- `auth_username`, `auth_password`, `auth_token`, `auth_header_key`,
  `auth_header_value`, `auth_headers`, `auth_query_param_key`,
  `auth_query_param_value`, `oauth_config`: upstream authentication material.
- `one_time_auth`: use auth only for registration/discovery rather than storing
  it.
- `passthrough_headers`: client request headers allowed through to upstream.
- `tags`: categorization.
- `team_id`, `owner_email`, `visibility`: ownership and access control.
- `refresh_interval_seconds`: per-gateway discovery refresh interval, minimum
  60 seconds when supplied.
- `gateway_mode`: `cache` or `direct_proxy`.
- `ca_certificate`, `ca_certificate_sig`, `signing_algorithm`, `client_cert`,
  `client_key`: TLS or mTLS configuration for upstream calls.
- `identity_propagation`: per-gateway user identity forwarding/signing config.

### Tools

Tools are callable capabilities. MCP tools should normally be discovered from a
gateway. Manual tool creation is for REST/A2A/pass-through cases unless the
source explicitly permits the MCP creation path.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/tools` and `/tools/` | List tools. |
| `POST` | `/tools` and `/tools/` | Create a manual tool, primarily REST/A2A/pass-through. |
| `GET` | `/tools/{tool_id}` | Read a tool. |
| `PUT` | `/tools/{tool_id}` | Update tool metadata, schema, URL, auth, tags, or visibility. |
| `DELETE` | `/tools/{tool_id}` | Delete a tool. |
| `POST` | `/tools/{tool_id}/state` | Set enabled state explicitly. |
| `POST` | `/tools/{tool_id}/toggle` | Deprecated toggle helper; prefer `/state`. |

`ToolCreate` fields:

- `name`: unique tool name.
- `displayName`, `title`, `description`: UI and MCP metadata.
- `url`: callable endpoint.
- `integration_type`: `REST`, `MCP`, or `A2A`.
- `request_type`: `GET`, `POST`, `PUT`, `DELETE`, `PATCH`, `SSE`, `STDIO`, or
  `STREAMABLEHTTP`.
- `headers`: invocation headers.
- `input_schema`, `output_schema`: JSON Schema validation.
- `annotations`: MCP behavior hints such as read-only or destructive.
- `jsonpath_filter`: response filter.
- `auth`: basic, bearer, or custom auth for invocation.
- `gateway_id`: owning gateway, when applicable.
- `team_id`, `owner_email`, `visibility`: ownership and access control on
  create.
- `base_url`, `path_template`, `query_mapping`, `header_mapping`,
  `timeout_ms`, `expose_passthrough`, `allowlist`, `plugin_chain_pre`,
  `plugin_chain_post`: REST pass-through mapping and policy.
- `tags`, `deprecated`: organization and lifecycle metadata.

`ToolUpdate` differences and limitation:

- It accepts most metadata, schema, auth, URL, REST pass-through, tags,
  `deprecated`, `gateway_id`, and `visibility` fields.
- It does not accept `team_id` or `owner_email`.
- Its `request_type` model is HTTP-method-only (`GET`, `POST`, `PUT`,
  `DELETE`, `PATCH`), so do not rely on `PUT /tools/{tool_id}` to repair MCP
  transport type for discovered MCP tools.

### Virtual Servers

Servers are ContextForge-facing virtual MCP servers. They group associated
tools, resources, prompts, and A2A agents and expose virtual MCP transports.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/servers` and `/servers/` | List virtual servers. |
| `POST` | `/servers` and `/servers/` | Create a virtual server. |
| `GET` | `/servers/{server_id}` | Read one virtual server. |
| `PUT` | `/servers/{server_id}` | Update metadata, ownership, OAuth config, and associations. |
| `DELETE` | `/servers/{server_id}` | Delete a virtual server. |
| `POST` | `/servers/{server_id}/state` | Set enabled state explicitly. |
| `POST` | `/servers/{server_id}/toggle` | Deprecated toggle helper; prefer `/state`. |
| `GET` | `/servers/{server_id}/sse` | Expose the virtual server through MCP SSE. |
| `POST` | `/servers/{server_id}/message` | SSE message endpoint for the virtual server. |
| `POST` | `/servers/{server_id}/mcp/` | Streamable HTTP MCP endpoint handled by the application transport. |
| `GET` | `/servers/{server_id}/tools` | List tools exposed by this server. |
| `GET` | `/servers/{server_id}/resources` | List resources exposed by this server. |
| `GET` | `/servers/{server_id}/prompts` | List prompts exposed by this server. |
| `GET` | `/servers/{server_id}/.well-known/oauth-protected-resource` | Per-server OAuth protected-resource metadata. |
| `GET` | `/servers/{server_id}/.well-known/{filename}` | Per-server well-known files. |

`ServerCreate` and `ServerUpdate` fields:

- `id`: optional custom UUID.
- `name`: server name.
- `description`, `icon`: UI metadata.
- `associated_tools`, `associated_resources`, `associated_prompts`,
  `associated_a2a_agents`: IDs to expose through this server.
- `team_id`, `owner_email`, `visibility`: ownership and access control.
- `oauth_enabled`, `oauth_config`: optional OAuth protection for MCP clients.
- `tags`: categorization.

### Resources

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/resources` and `/resources/` | List resources. |
| `POST` | `/resources` and `/resources/` | Create a resource. |
| `GET` | `/resources/{resource_id}` | Read resource content. |
| `GET` | `/resources/{resource_id}/info` | Read resource metadata. |
| `PUT` | `/resources/{resource_id}` | Update resource metadata/content. |
| `DELETE` | `/resources/{resource_id}` | Delete a resource. |
| `POST` | `/resources/{resource_id}/state` | Set enabled state explicitly. |
| `POST` | `/resources/{resource_id}/toggle` | Deprecated toggle helper; prefer `/state`. |
| `GET` | `/resources/templates/list` | List resource templates. |
| `POST` | `/resources/subscribe` | Subscribe to resource updates. |

`ResourceCreate` and `ResourceUpdate` fields:

- `uri`: unique resource URI.
- `name`, `description`, `title`: metadata.
- `mimeType`/`mime_type`: content type.
- `uri_template`: parameterized resource template.
- `content`: text or binary content.
- `gateway_id`: owning/discovering gateway, when applicable.
- `team_id`, `owner_email`, `visibility`: ownership and access control.
- `tags`: categorization.

### Prompts

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/prompts` and `/prompts/` | List prompts. |
| `POST` | `/prompts` and `/prompts/` | Create a prompt. |
| `GET` | `/prompts/{prompt_id}` | Read prompt metadata without argument rendering. |
| `POST` | `/prompts/{prompt_id}` | Get/render a prompt with arguments. |
| `PUT` | `/prompts/{prompt_id}` | Update prompt metadata/template/arguments. |
| `DELETE` | `/prompts/{prompt_id}` | Delete a prompt. |
| `POST` | `/prompts/{prompt_id}/state` | Set enabled state explicitly. |
| `POST` | `/prompts/{prompt_id}/toggle` | Deprecated toggle helper; prefer `/state`. |

`PromptCreate` and `PromptUpdate` fields:

- `name`: unique prompt name.
- `custom_name`, `display_name`, `title`: invocation/UI metadata.
- `description`: human explanation.
- `template`: prompt template text.
- `arguments`: typed prompt arguments.
- `gateway_id`: owning/discovering gateway, when applicable.
- `team_id`, `owner_email`, `visibility`: ownership and access control.
- `tags`: categorization.

### Roots

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/roots` and `/roots/` | List roots. |
| `POST` | `/roots` and `/roots/` | Add a root. |
| `GET` | `/roots/export` | Export root configuration. |
| `GET` | `/roots/changes` | Subscribe to root changes. |
| `GET` | `/roots/{root_uri}` | Read one root by URI. |
| `PUT` | `/roots/{root_uri}` | Update one root. |
| `DELETE` | `/roots/{uri}` | Remove one root. |

### Tags, Metrics, Import, Export, Health

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/tags` and `/tags/` | List tags. |
| `GET` | `/tags/{tag_name}/entities` | Find entities with a tag. |
| `GET` | `/metrics` | Read application metrics. |
| `POST` | `/metrics/reset` | Reset metrics. |
| `GET` | `/metrics/prometheus` | Prometheus metrics endpoint, enabled only when configured. |
| `GET` | `/export` | Export full configuration. |
| `POST` | `/export/selective` | Export selected configuration entities. |
| `POST` | `/import` | Import configuration. |
| `GET` | `/import/status/{import_id}` | Read one import status. |
| `GET` | `/import/status` | List import statuses. |
| `POST` | `/import/cleanup` | Remove old import status records. |
| `GET` | `/health` | Basic health check. |
| `GET` | `/ready` | Readiness check. |
| `GET` | `/health/security` | Security-health diagnostics. |
| `GET` | `/version` | Version and diagnostics, admin-gated. |

## MCP Protocol And Invocation API

ContextForge exposes both MCP protocol helper routes and virtual-server
transport routes. In normal ContextForge use, clients consume
`/servers/{server_id}/mcp/` or `/servers/{server_id}/sse`; operators use the
registry routes above.

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/protocol/initialize` | MCP initialize helper. |
| `POST` | `/protocol/ping` | MCP ping helper. |
| `POST` | `/protocol/notifications` | MCP notification handler. |
| `POST` | `/protocol/completion/complete` | MCP completion handler. |
| `POST` | `/protocol/sampling/createMessage` | MCP sampling handler. |
| `POST` | `/rpc` and `/rpc/` | Generic JSON-RPC/MCP call endpoint. |
| `GET` | `/sse` | Utility/global SSE endpoint. |
| `POST` | `/message` | Utility/global SSE message endpoint. |
| `POST` | `/logging/setLevel` | Set MCP logging level. |

Internal MCP/A2A routes under `/_internal/...` implement transport bridging,
authorization, tool calls, metrics, and server-to-server mediation. They are
part of the OpenAPI route set but should not be the first choice for normal
ContextForge automation. Use public registry and virtual server endpoints
unless debugging ContextForge internals.

Internal MCP route families:

- `/_internal/mcp/authenticate`
- `/_internal/mcp/rpc`
- `/_internal/mcp/initialize`
- `/_internal/mcp/session`
- `/_internal/mcp/notifications/*`
- `/_internal/mcp/tools/list`
- `/_internal/mcp/tools/call`
- `/_internal/mcp/tools/call/resolve`
- `/_internal/mcp/tools/call/metric`
- `/_internal/mcp/resources/*`
- `/_internal/mcp/prompts/*`
- `/_internal/mcp/roots/list`
- `/_internal/mcp/completion/complete`
- `/_internal/mcp/sampling/createMessage`
- `/_internal/mcp/logging/setLevel`
- authz variants ending in `/authz`

Internal A2A route families:

- `/_internal/a2a/authenticate`
- `/_internal/a2a/invoke/authz`
- `/_internal/a2a/list/authz`
- `/_internal/a2a/get/authz`
- `/_internal/a2a/agents/{agent_name}/resolve`
- `/_internal/a2a/agents/{agent_name}/card`
- `/_internal/a2a/tasks/*`
- `/_internal/a2a/push/*`
- `/_internal/a2a/events/*`

## A2A Agents

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/a2a` and `/a2a/` | List A2A agents. |
| `POST` | `/a2a` and `/a2a/` | Create an A2A agent registration. |
| `GET` | `/a2a/{agent_id}` | Read one A2A agent. |
| `PUT` | `/a2a/{agent_id}` | Update an A2A agent. |
| `DELETE` | `/a2a/{agent_id}` | Delete an A2A agent. |
| `POST` | `/a2a/{agent_id}/state` | Set enabled state explicitly. |
| `POST` | `/a2a/{agent_id}/toggle` | Deprecated toggle helper; prefer `/state`. |
| `POST` | `/a2a/{agent_name}/invoke` | Invoke an A2A agent by name. |
| `POST` | `/a2a/invoke` | Invoke an A2A agent by request payload. |

## Teams And RBAC

Team routes:

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/teams/` | Create a team. |
| `GET` | `/teams/` | List teams. |
| `GET` | `/teams/discover` | Discover public/joinable teams. |
| `GET` | `/teams/{team_id}` | Read a team. |
| `PUT` | `/teams/{team_id}` | Update a team. |
| `DELETE` | `/teams/{team_id}` | Delete a team. |
| `GET` | `/teams/{team_id}/members` | List team members. |
| `POST` | `/teams/{team_id}/members` | Add a team member. |
| `PUT` | `/teams/{team_id}/members/{user_email}` | Update a team member role/status. |
| `DELETE` | `/teams/{team_id}/members/{user_email}` | Remove a team member. |
| `POST` | `/teams/{team_id}/invitations` | Invite a team member. |
| `GET` | `/teams/{team_id}/invitations` | List team invitations. |
| `POST` | `/teams/invitations/{token}/accept` | Accept an invitation. |
| `DELETE` | `/teams/invitations/{invitation_id}` | Cancel an invitation. |
| `POST` | `/teams/{team_id}/join` | Request to join a team. |
| `DELETE` | `/teams/{team_id}/leave` | Leave a team. |
| `GET` | `/teams/{team_id}/join-requests` | List join requests. |
| `POST` | `/teams/{team_id}/join-requests/{request_id}/approve` | Approve a join request. |
| `DELETE` | `/teams/{team_id}/join-requests/{request_id}` | Reject a join request. |

RBAC routes:

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/rbac/roles` | Create a role. |
| `GET` | `/rbac/roles` | List roles. |
| `GET` | `/rbac/roles/{role_id}` | Read one role. |
| `PUT` | `/rbac/roles/{role_id}` | Update a role. |
| `DELETE` | `/rbac/roles/{role_id}` | Delete a role. |
| `POST` | `/rbac/users/{user_email}/roles` | Assign a role to a user. |
| `GET` | `/rbac/users/{user_email}/roles` | List a user's roles. |
| `DELETE` | `/rbac/users/{user_email}/roles/{role_id}` | Revoke a role from a user. |
| `POST` | `/rbac/permissions/check` | Check a permission. |
| `GET` | `/rbac/permissions/user/{user_email}` | List one user's effective permissions. |
| `GET` | `/rbac/permissions/available` | List available permissions. |
| `GET` | `/rbac/my/roles` | List current user's roles. |
| `GET` | `/rbac/my/permissions` | List current user's permissions. |

## OAuth, SSO, Well-Known

Gateway OAuth routes:

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/oauth/authorize/{gateway_id}` | Start OAuth flow for a gateway. |
| `GET` | `/oauth/callback` | Complete gateway OAuth flow. |
| `GET` | `/oauth/status/{gateway_id}` | Read gateway OAuth status. |
| `POST` | `/oauth/fetch-tools/{gateway_id}` | Fetch tools after OAuth authorization. |
| `GET` | `/oauth/registered-clients` | List OAuth registered clients. |
| `GET` | `/oauth/registered-clients/{gateway_id}` | Read OAuth client for a gateway. |
| `DELETE` | `/oauth/registered-clients/{client_id}` | Delete OAuth registered client. |

SSO routes:

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/auth/sso/providers` | List enabled SSO providers. |
| `GET` | `/auth/sso/login/{provider_id}` | Start SSO login. |
| `GET` | `/auth/sso/callback/{provider_id}` | Complete SSO login. |
| `POST` | `/auth/sso/admin/providers` | Admin create SSO provider. |
| `GET` | `/auth/sso/admin/providers` | Admin list SSO providers. |
| `GET` | `/auth/sso/admin/providers/{provider_id}` | Admin read SSO provider. |
| `PUT` | `/auth/sso/admin/providers/{provider_id}` | Admin update SSO provider. |
| `DELETE` | `/auth/sso/admin/providers/{provider_id}` | Admin delete SSO provider. |
| `GET` | `/auth/sso/pending-approvals` | List pending SSO approvals. |
| `POST` | `/auth/sso/pending-approvals/{approval_id}/action` | Approve/reject SSO approval. |

Well-known routes:

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/.well-known/oauth-protected-resource` | RFC 9728 protected-resource metadata. |
| `GET` | `/.well-known/oauth-protected-resource/{path}` | Path-specific protected-resource metadata. |
| `GET` | `/.well-known/{filename}` | Generic well-known file serving. |
| `GET` | `/admin/well-known` | Admin well-known status page/API. |

## LLM API

LLM configuration routes, mounted under `/llm`:

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/llm/providers` | Create an LLM provider. |
| `GET` | `/llm/providers` | List LLM providers. |
| `GET` | `/llm/providers/{provider_id}` | Read one provider. |
| `PATCH` | `/llm/providers/{provider_id}` | Update one provider. |
| `DELETE` | `/llm/providers/{provider_id}` | Delete one provider. |
| `POST` | `/llm/providers/{provider_id}/state` | Enable/disable provider. |
| `POST` | `/llm/providers/{provider_id}/health` | Check provider health. |
| `POST` | `/llm/models` | Create an LLM model. |
| `GET` | `/llm/models` | List LLM models. |
| `GET` | `/llm/models/{model_id}` | Read one model. |
| `PATCH` | `/llm/models/{model_id}` | Update one model. |
| `DELETE` | `/llm/models/{model_id}` | Delete one model. |
| `POST` | `/llm/models/{model_id}/state` | Enable/disable model. |
| `GET` | `/llm/gateway/models` | List gateway-visible LLM models. |

LLM proxy routes, mounted at the configured `settings.llm_api_prefix`:

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `{llm_api_prefix}/chat/completions` | OpenAI-compatible chat completions proxy. |
| `GET` | `{llm_api_prefix}/models` | OpenAI-compatible model listing. |

LLM chat helper routes:

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/llmchat/connect` | Connect a chat session. |
| `POST` | `/llmchat/chat` | Send chat message. |
| `POST` | `/llmchat/disconnect` | Disconnect chat session. |
| `GET` | `/llmchat/status/{user_id}` | Read chat session status. |
| `GET` | `/llmchat/config/{user_id}` | Read chat config. |
| `GET` | `/llmchat/gateway/models` | Read gateway model list for chat. |

## Observability, Logs, Compliance, Maintenance

Log routes:

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/logs/search` | Search stored logs. |
| `GET` | `/api/logs/trace/{correlation_id}` | Trace logs by correlation ID. |
| `GET` | `/api/logs/security-events` | List security events. |
| `GET` | `/api/logs/audit-trails` | List audit trails. |
| `GET` | `/api/logs/performance-metrics` | List performance metrics. |

Observability routes:

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/observability/traces` | List traces. |
| `POST` | `/observability/traces/query` | Query traces with advanced filters. |
| `GET` | `/observability/traces/{trace_id}` | Read one trace with spans. |
| `GET` | `/observability/spans` | List spans. |
| `DELETE` | `/observability/traces/cleanup` | Clean old traces. |
| `GET` | `/observability/stats` | Read observability stats. |
| `POST` | `/observability/traces/export` | Export traces. |
| `GET` | `/observability/analytics/query-performance` | Query performance analytics. |

Metrics maintenance routes:

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/metrics/cleanup` | Trigger metrics cleanup. |
| `POST` | `/api/metrics/rollup` | Trigger metrics rollup. |
| `GET` | `/api/metrics/stats` | Read metrics maintenance stats. |
| `GET` | `/api/metrics/config` | Read metrics maintenance config. |

Compliance routes:

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/compliance/frameworks` | List compliance frameworks. |
| `POST` | `/compliance/reports` | Generate a compliance report. |
| `GET` | `/compliance/reports` | List compliance reports. |
| `GET` | `/compliance/reports/{report_id}` | Read a compliance report. |
| `GET` | `/compliance/reports/{report_id}/export` | Export a compliance report. |

SIEM routes:

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/admin/siem/health` | Read SIEM health. |
| `GET` | `/admin/siem/destinations` | List SIEM destinations. |
| `POST` | `/admin/siem/destinations` | Add SIEM destination. |
| `PUT` | `/admin/siem/destinations` | Replace SIEM destinations. |
| `POST` | `/admin/siem/test/{destination_name}` | Test one SIEM destination. |

Cancellation routes:

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/cancellation/cancel` | Cancel a tracked request/run. |
| `GET` | `/cancellation/status/{request_id}` | Read cancellation status. |

## Plugins And Tool Operations

Plugin binding routes:

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/v1/tools/plugin_bindings/` | Upsert tool plugin binding. |
| `GET` | `/v1/tools/plugin_bindings/` | List tool plugin bindings. |
| `GET` | `/v1/tools/plugin_bindings/{team_id}` | List tool plugin bindings for a team. |
| `DELETE` | `/v1/tools/plugin_bindings/` | Delete tool plugin bindings by reference. |
| `DELETE` | `/v1/tools/plugin_bindings/{binding_id}` | Delete one tool plugin binding. |
| `POST` | `/v1/a2a-agents/plugin-bindings/` | Upsert A2A agent plugin binding. |
| `GET` | `/v1/a2a-agents/plugin-bindings/` | List A2A agent plugin bindings. |
| `GET` | `/v1/a2a-agents/plugin-bindings/{team_id}` | List A2A agent plugin bindings for a team. |
| `DELETE` | `/v1/a2a-agents/plugin-bindings/` | Delete A2A agent plugin bindings by reference. |
| `DELETE` | `/v1/a2a-agents/plugin-bindings/{binding_id}` | Delete one A2A agent plugin binding. |

Toolops routes:

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/toolops/validation/generate_testcases` | Generate validation test cases for a tool. |
| `POST` | `/toolops/validation/execute_tool_nl_testcases` | Execute natural-language tool validation test cases. |
| `POST` | `/toolops/enrichment/enrich_tool` | Enrich tool metadata/schema. |

## Reverse Proxy API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/reverse-proxy/sessions` | List reverse-proxy sessions. |
| `DELETE` | `/reverse-proxy/sessions/{session_id}` | Disconnect a reverse-proxy session. |
| `POST` | `/reverse-proxy/sessions/{session_id}/request` | Send request through a reverse-proxy session. |
| `GET` | `/reverse-proxy/sse/{session_id}` | Reverse-proxy SSE endpoint. |

## Admin UI Routes

The `/admin/...` surface is broad and mixes HTML partials, form handlers, and
JSON helpers. Use it for UI/browser interactions and only automate it when no
JSON API route exists.

Important Admin UI route families:

- `/admin/login`, `/admin/logout`, `/admin/forgot-password`,
  `/admin/reset-password/{token}`, `/admin/change-password-required`.
- `/admin/servers`, `/admin/gateways`, `/admin/tools`, `/admin/resources`,
  `/admin/prompts`, `/admin/a2a`, `/admin/roots` for UI list/detail/create/edit,
  state, delete, search, ID lookup, and partial HTML rendering.
- `/admin/tokens/partial`, `/admin/tokens/search`,
  `/admin/tokens/{token_id}` for token UI search and revocation.
- `/admin/teams`, `/admin/users`, and nested team/member/join-request routes.
- `/admin/metrics`, `/admin/events`, `/admin/logs`, `/admin/export`,
  `/admin/import`.
- `/admin/plugins`, `/admin/mcp-registry`, `/admin/system/stats`,
  `/admin/support-bundle/generate`, `/admin/maintenance/partial`.
- `/admin/observability/*` and `/admin/performance/stats`.
- `/admin/grpc/*`.
- `/admin/runtime/mcp-mode`, `/admin/runtime/a2a-mode`.
- `/admin/llm/*`.

When a JSON route and an Admin route both exist, prefer the JSON route:

- Use `/gateways` instead of `/admin/gateways` for gateway registration.
- Use `/servers` instead of `/admin/servers` for virtual server changes.
- Use `/tools` instead of `/admin/tools` for manual REST tool changes.
- Use `/resources` and `/prompts` instead of `/admin/resources` and
  `/admin/prompts`.
- Use `/tokens` instead of `/admin/tokens/...` for token lifecycle operations.
- Use `/teams` and `/auth/email/admin/users` instead of UI form handlers.

## Complete Live OpenAPI Method Index

Generated from authenticated `GET /openapi.json` on the local ContextForge gateway. This appendix is intentionally mechanical: when the live schema changes, regenerate this table from the running gateway rather than editing individual rows by hand.

- Paths: 451
- Operations: 532
- Component schemas: 190

### A2A Agent Plugin Bindings

| Method | Path | Purpose | Operation ID |
| --- | --- | --- | --- |
| `GET` | `/v1/a2a-agents/plugin-bindings/` | List A2A Agent Plugin Bindings | `list_a2a_agent_plugin_bindings_v1_a2a_agents_plugin_bindings__get` |
| `POST` | `/v1/a2a-agents/plugin-bindings/` | Upsert A2A Agent Plugin Binding | `upsert_a2a_agent_plugin_binding_v1_a2a_agents_plugin_bindings__post` |
| `DELETE` | `/v1/a2a-agents/plugin-bindings/` | Delete A2A Agent Plugin Bindings By Reference | `delete_a2a_agent_plugin_bindings_by_reference_v1_a2a_agents_plugin_bindings__delete` |
| `DELETE` | `/v1/a2a-agents/plugin-bindings/{binding_id}` | Delete A2A Agent Plugin Binding | `delete_a2a_agent_plugin_binding_v1_a2a_agents_plugin_bindings__binding_id__delete` |
| `GET` | `/v1/a2a-agents/plugin-bindings/{team_id}` | List A2A Agent Plugin Bindings For Team | `list_a2a_agent_plugin_bindings_for_team_v1_a2a_agents_plugin_bindings__team_id__get` |

### A2A Agents

| Method | Path | Purpose | Operation ID |
| --- | --- | --- | --- |
| `GET` | `/a2a` | List A2A Agents | `list_a2a_agents_a2a_get` |
| `POST` | `/a2a` | Create A2A Agent | `create_a2a_agent_a2a_post` |
| `GET` | `/a2a/` | List A2A Agents | `list_a2a_agents_a2a__get` |
| `POST` | `/a2a/` | Create A2A Agent | `create_a2a_agent_a2a__post` |
| `POST` | `/a2a/invoke` | Invoke A2A Agent By Id | `invoke_a2a_agent_by_id_a2a_invoke_post` |
| `GET` | `/a2a/{agent_id}` | Get A2A Agent | `get_a2a_agent_a2a__agent_id__get` |
| `PUT` | `/a2a/{agent_id}` | Update A2A Agent | `update_a2a_agent_a2a__agent_id__put` |
| `DELETE` | `/a2a/{agent_id}` | Delete A2A Agent | `delete_a2a_agent_a2a__agent_id__delete` |
| `POST` | `/a2a/{agent_id}/state` | Set A2A Agent State | `set_a2a_agent_state_a2a__agent_id__state_post` |
| `POST` | `/a2a/{agent_id}/toggle` | Toggle A2A Agent Status | `toggle_a2a_agent_status_a2a__agent_id__toggle_post` |
| `POST` | `/a2a/{agent_name}/invoke` | Invoke A2A Agent | `invoke_a2a_agent_a2a__agent_name__invoke_post` |

### Admin UI

| Method | Path | Purpose | Operation ID |
| --- | --- | --- | --- |
| `GET` | `/admin/` | Admin Home | `admin_home_admin__get` |
| `GET` | `/admin/a2a` | Admin List A2A Agents | `admin_list_a2a_agents_admin_a2a_get` |
| `POST` | `/admin/a2a` | Admin Add A2A Agent | `admin_add_a2a_agent_admin_a2a_post` |
| `GET` | `/admin/a2a/ids` | Admin Get All Agent Ids | `admin_get_all_agent_ids_admin_a2a_ids_get` |
| `GET` | `/admin/a2a/partial` | Admin A2A Partial Html | `admin_a2a_partial_html_admin_a2a_partial_get` |
| `POST` | `/admin/a2a/plugin-bindings` | Admin Create A2A Plugin Binding | `admin_create_a2a_plugin_binding_admin_a2a_plugin_bindings_post` |
| `GET` | `/admin/a2a/plugin-bindings/partial` | Get A2A Plugin Bindings Partial | `get_a2a_plugin_bindings_partial_admin_a2a_plugin_bindings_partial_get` |
| `POST` | `/admin/a2a/plugin-bindings/{binding_id}/delete` | Admin Delete A2A Plugin Binding | `admin_delete_a2a_plugin_binding_admin_a2a_plugin_bindings__binding_id__delete_post` |
| `GET` | `/admin/a2a/search` | Admin Search A2A Agents | `admin_search_a2a_agents_admin_a2a_search_get` |
| `GET` | `/admin/a2a/{agent_id}` | Admin Get Agent | `admin_get_agent_admin_a2a__agent_id__get` |
| `POST` | `/admin/a2a/{agent_id}/delete` | Admin Delete A2A Agent | `admin_delete_a2a_agent_admin_a2a__agent_id__delete_post` |
| `POST` | `/admin/a2a/{agent_id}/edit` | Admin Edit A2A Agent | `admin_edit_a2a_agent_admin_a2a__agent_id__edit_post` |
| `POST` | `/admin/a2a/{agent_id}/state` | Admin Set A2A Agent State | `admin_set_a2a_agent_state_admin_a2a__agent_id__state_post` |
| `POST` | `/admin/a2a/{agent_id}/test` | Admin Test A2A Agent | `admin_test_a2a_agent_admin_a2a__agent_id__test_post` |
| `POST` | `/admin/cache/a2a-stats/invalidate` | Invalidate A2A Stats Cache | `invalidate_a2a_stats_cache_admin_cache_a2a_stats_invalidate_post` |
| `GET` | `/admin/cache/a2a-stats/stats` | Get A2A Stats Cache Stats | `get_a2a_stats_cache_stats_admin_cache_a2a_stats_stats_get` |
| `GET` | `/admin/change-password-required` | Change Password Required Page | `change_password_required_page_admin_change_password_required_get` |
| `POST` | `/admin/change-password-required` | Change Password Required Handler | `change_password_required_handler_admin_change_password_required_post` |
| `GET` | `/admin/config/passthrough-headers` | Get Global Passthrough Headers | `get_global_passthrough_headers_admin_config_passthrough_headers_get` |
| `PUT` | `/admin/config/passthrough-headers` | Update Global Passthrough Headers | `update_global_passthrough_headers_admin_config_passthrough_headers_put` |
| `GET` | `/admin/config/passthrough-headers/cache-stats` | Get Passthrough Headers Cache Stats | `get_passthrough_headers_cache_stats_admin_config_passthrough_headers_cache_stats_get` |
| `POST` | `/admin/config/passthrough-headers/invalidate-cache` | Invalidate Passthrough Headers Cache | `invalidate_passthrough_headers_cache_admin_config_passthrough_headers_invalidate_cache_post` |
| `GET` | `/admin/config/settings` | Get Configuration Settings | `get_configuration_settings_admin_config_settings_get` |
| `GET` | `/admin/events` | Admin Events | `admin_events_admin_events_get` |
| `GET` | `/admin/export/configuration` | Admin Export Configuration | `admin_export_configuration_admin_export_configuration_get` |
| `POST` | `/admin/export/selective` | Admin Export Selective | `admin_export_selective_admin_export_selective_post` |
| `GET` | `/admin/forgot-password` | Admin Forgot Password Page | `admin_forgot_password_page_admin_forgot_password_get` |
| `POST` | `/admin/forgot-password` | Admin Forgot Password Handler | `admin_forgot_password_handler_admin_forgot_password_post` |
| `GET` | `/admin/gateways` | Admin List Gateways | `admin_list_gateways_admin_gateways_get` |
| `POST` | `/admin/gateways` | Admin Add Gateway | `admin_add_gateway_admin_gateways_post` |
| `POST` | `/admin/gateways/discover-oauth` | Admin Discover Oauth | `admin_discover_oauth_admin_gateways_discover_oauth_post` |
| `GET` | `/admin/gateways/ids` | Admin Get All Gateways Ids | `admin_get_all_gateways_ids_admin_gateways_ids_get` |
| `GET` | `/admin/gateways/partial` | Admin Gateways Partial Html | `admin_gateways_partial_html_admin_gateways_partial_get` |
| `GET` | `/admin/gateways/search` | Admin Search Gateways | `admin_search_gateways_admin_gateways_search_get` |
| `POST` | `/admin/gateways/test` | Admin Test Gateway | `admin_test_gateway_admin_gateways_test_post` |
| `GET` | `/admin/gateways/{gateway_id}` | Admin Get Gateway | `admin_get_gateway_admin_gateways__gateway_id__get` |
| `POST` | `/admin/gateways/{gateway_id}/delete` | Admin Delete Gateway | `admin_delete_gateway_admin_gateways__gateway_id__delete_post` |
| `POST` | `/admin/gateways/{gateway_id}/edit` | Admin Edit Gateway | `admin_edit_gateway_admin_gateways__gateway_id__edit_post` |
| `POST` | `/admin/gateways/{gateway_id}/state` | Admin Set Gateway State | `admin_set_gateway_state_admin_gateways__gateway_id__state_post` |
| `GET` | `/admin/grpc` | Admin List Grpc Services | `admin_list_grpc_services_admin_grpc_get` |
| `POST` | `/admin/grpc` | Admin Create Grpc Service | `admin_create_grpc_service_admin_grpc_post` |
| `GET` | `/admin/grpc/{service_id}` | Admin Get Grpc Service | `admin_get_grpc_service_admin_grpc__service_id__get` |
| `PUT` | `/admin/grpc/{service_id}` | Admin Update Grpc Service | `admin_update_grpc_service_admin_grpc__service_id__put` |
| `POST` | `/admin/grpc/{service_id}/delete` | Admin Delete Grpc Service | `admin_delete_grpc_service_admin_grpc__service_id__delete_post` |
| `GET` | `/admin/grpc/{service_id}/methods` | Admin Get Grpc Methods | `admin_get_grpc_methods_admin_grpc__service_id__methods_get` |
| `POST` | `/admin/grpc/{service_id}/reflect` | Admin Reflect Grpc Service | `admin_reflect_grpc_service_admin_grpc__service_id__reflect_post` |
| `POST` | `/admin/grpc/{service_id}/state` | Admin Set Grpc Service State | `admin_set_grpc_service_state_admin_grpc__service_id__state_post` |
| `POST` | `/admin/import/configuration` | Admin Import Configuration | `admin_import_configuration_admin_import_configuration_post` |
| `POST` | `/admin/import/preview` | Admin Import Preview | `admin_import_preview_admin_import_preview_post` |
| `GET` | `/admin/import/status` | Admin List Import Statuses | `admin_list_import_statuses_admin_import_status_get` |
| `GET` | `/admin/import/status/{import_id}` | Admin Get Import Status | `admin_get_import_status_admin_import_status__import_id__get` |
| `GET` | `/admin/login` | Admin Login Page | `admin_login_page_admin_login_get` |
| `POST` | `/admin/login` | Admin Login Handler | `admin_login_handler_admin_login_post` |
| `GET` | `/admin/logout` | Admin Logout Get | `admin_logout_get` |
| `POST` | `/admin/logout` | Admin Logout Post | `admin_logout_post` |
| `GET` | `/admin/logs` | Admin Get Logs | `admin_get_logs_admin_logs_get` |
| `GET` | `/admin/logs/export` | Admin Export Logs | `admin_export_logs_admin_logs_export_get` |
| `GET` | `/admin/logs/file` | Admin Get Log File | `admin_get_log_file_admin_logs_file_get` |
| `GET` | `/admin/logs/stream` | Admin Stream Logs | `admin_stream_logs_admin_logs_stream_get` |
| `GET` | `/admin/maintenance/partial` | Get Maintenance Partial | `get_maintenance_partial_admin_maintenance_partial_get` |
| `POST` | `/admin/mcp-registry/bulk-register` | Bulk Register Catalog Servers | `bulk_register_catalog_servers_admin_mcp_registry_bulk_register_post` |
| `GET` | `/admin/mcp-registry/partial` | Catalog Partial | `catalog_partial_admin_mcp_registry_partial_get` |
| `GET` | `/admin/mcp-registry/servers` | List Catalog Servers | `list_catalog_servers_admin_mcp_registry_servers_get` |
| `POST` | `/admin/mcp-registry/{server_id}/register` | Register Catalog Server | `register_catalog_server_admin_mcp_registry__server_id__register_post` |
| `GET` | `/admin/mcp-registry/{server_id}/status` | Check Catalog Server Status | `check_catalog_server_status_admin_mcp_registry__server_id__status_get` |
| `GET` | `/admin/metrics` | Get Aggregated Metrics | `get_aggregated_metrics_admin_metrics_get` |
| `GET` | `/admin/metrics/partial` | Admin Metrics Partial Html | `admin_metrics_partial_html_admin_metrics_partial_get` |
| `POST` | `/admin/metrics/reset` | Admin Reset Metrics | `admin_reset_metrics_admin_metrics_reset_post` |
| `GET` | `/admin/observability/metrics/heatmap` | Get Latency Heatmap | `get_latency_heatmap_admin_observability_metrics_heatmap_get` |
| `GET` | `/admin/observability/metrics/partial` | Get Observability Metrics Partial | `get_observability_metrics_partial_admin_observability_metrics_partial_get` |
| `GET` | `/admin/observability/metrics/percentiles` | Get Latency Percentiles | `get_latency_percentiles_admin_observability_metrics_percentiles_get` |
| `GET` | `/admin/observability/metrics/timeseries` | Get Timeseries Metrics | `get_timeseries_metrics_admin_observability_metrics_timeseries_get` |
| `GET` | `/admin/observability/metrics/top-errors` | Get Top Error Endpoints | `get_top_error_endpoints_admin_observability_metrics_top_errors_get` |
| `GET` | `/admin/observability/metrics/top-slow` | Get Top Slow Endpoints | `get_top_slow_endpoints_admin_observability_metrics_top_slow_get` |
| `GET` | `/admin/observability/metrics/top-volume` | Get Top Volume Endpoints | `get_top_volume_endpoints_admin_observability_metrics_top_volume_get` |
| `GET` | `/admin/observability/partial` | Get Observability Partial | `get_observability_partial_admin_observability_partial_get` |
| `GET` | `/admin/observability/prompts/errors` | Get Prompts Errors | `get_prompts_errors_admin_observability_prompts_errors_get` |
| `GET` | `/admin/observability/prompts/partial` | Get Prompts Partial | `get_prompts_partial_admin_observability_prompts_partial_get` |
| `GET` | `/admin/observability/prompts/performance` | Get Prompt Performance | `get_prompt_performance_admin_observability_prompts_performance_get` |
| `GET` | `/admin/observability/prompts/usage` | Get Prompt Usage | `get_prompt_usage_admin_observability_prompts_usage_get` |
| `GET` | `/admin/observability/queries` | List Observability Queries | `list_observability_queries_admin_observability_queries_get` |
| `POST` | `/admin/observability/queries` | Save Observability Query | `save_observability_query_admin_observability_queries_post` |
| `GET` | `/admin/observability/queries/{query_id}` | Get Observability Query | `get_observability_query_admin_observability_queries__query_id__get` |
| `PUT` | `/admin/observability/queries/{query_id}` | Update Observability Query | `update_observability_query_admin_observability_queries__query_id__put` |
| `DELETE` | `/admin/observability/queries/{query_id}` | Delete Observability Query | `delete_observability_query_admin_observability_queries__query_id__delete` |
| `POST` | `/admin/observability/queries/{query_id}/use` | Track Query Usage | `track_query_usage_admin_observability_queries__query_id__use_post` |
| `GET` | `/admin/observability/resources/errors` | Get Resources Errors | `get_resources_errors_admin_observability_resources_errors_get` |
| `GET` | `/admin/observability/resources/partial` | Get Resources Partial | `get_resources_partial_admin_observability_resources_partial_get` |
| `GET` | `/admin/observability/resources/performance` | Get Resource Performance | `get_resource_performance_admin_observability_resources_performance_get` |
| `GET` | `/admin/observability/resources/usage` | Get Resource Usage | `get_resource_usage_admin_observability_resources_usage_get` |
| `GET` | `/admin/observability/stats` | Get Observability Stats | `get_observability_stats_admin_observability_stats_get` |
| `GET` | `/admin/observability/tools/chains` | Get Tool Chains | `get_tool_chains_admin_observability_tools_chains_get` |
| `GET` | `/admin/observability/tools/errors` | Get Tool Errors | `get_tool_errors_admin_observability_tools_errors_get` |
| `GET` | `/admin/observability/tools/partial` | Get Tools Partial | `get_tools_partial_admin_observability_tools_partial_get` |
| `GET` | `/admin/observability/tools/performance` | Get Tool Performance | `get_tool_performance_admin_observability_tools_performance_get` |
| `GET` | `/admin/observability/tools/usage` | Get Tool Usage | `get_tool_usage_admin_observability_tools_usage_get` |
| `GET` | `/admin/observability/trace/{trace_id}` | Get Observability Trace Detail | `get_observability_trace_detail_admin_observability_trace__trace_id__get` |
| `GET` | `/admin/observability/traces` | Get Observability Traces | `get_observability_traces_admin_observability_traces_get` |
| `GET` | `/admin/overview/partial` | Get Overview Partial | `get_overview_partial_admin_overview_partial_get` |
| `GET` | `/admin/performance/cache` | Get Performance Cache | `get_performance_cache_admin_performance_cache_get` |
| `GET` | `/admin/performance/history` | Get Performance History | `get_performance_history_admin_performance_history_get` |
| `GET` | `/admin/performance/requests` | Get Performance Requests | `get_performance_requests_admin_performance_requests_get` |
| `GET` | `/admin/performance/stats` | Get Performance Stats | `get_performance_stats_admin_performance_stats_get` |
| `GET` | `/admin/performance/system` | Get Performance System | `get_performance_system_admin_performance_system_get` |
| `GET` | `/admin/performance/workers` | Get Performance Workers | `get_performance_workers_admin_performance_workers_get` |
| `GET` | `/admin/plugins` | List Plugins | `list_plugins_admin_plugins_get` |
| `PUT` | `/admin/plugins` | Toggle Plugins Global | `toggle_plugins_global_admin_plugins_put` |
| `GET` | `/admin/plugins/partial` | Get Plugins Partial | `get_plugins_partial_admin_plugins_partial_get` |
| `GET` | `/admin/plugins/stats` | Get Plugin Stats | `get_plugin_stats_admin_plugins_stats_get` |
| `GET` | `/admin/plugins/{name}` | Get Plugin Details | `get_plugin_details_admin_plugins__name__get` |
| `PUT` | `/admin/plugins/{name}` | Update Plugin Mode | `update_plugin_mode_admin_plugins__name__put` |
| `GET` | `/admin/prompts` | Admin List Prompts | `admin_list_prompts_admin_prompts_get` |
| `POST` | `/admin/prompts` | Admin Add Prompt | `admin_add_prompt_admin_prompts_post` |
| `GET` | `/admin/prompts/ids` | Admin Get All Prompt Ids | `admin_get_all_prompt_ids_admin_prompts_ids_get` |
| `GET` | `/admin/prompts/partial` | Admin Prompts Partial Html | `admin_prompts_partial_html_admin_prompts_partial_get` |
| `GET` | `/admin/prompts/search` | Admin Search Prompts | `admin_search_prompts_admin_prompts_search_get` |
| `GET` | `/admin/prompts/{prompt_id}` | Admin Get Prompt | `admin_get_prompt_admin_prompts__prompt_id__get` |
| `POST` | `/admin/prompts/{prompt_id}/delete` | Admin Delete Prompt | `admin_delete_prompt_admin_prompts__prompt_id__delete_post` |
| `POST` | `/admin/prompts/{prompt_id}/edit` | Admin Edit Prompt | `admin_edit_prompt_admin_prompts__prompt_id__edit_post` |
| `POST` | `/admin/prompts/{prompt_id}/state` | Admin Set Prompt State | `admin_set_prompt_state_admin_prompts__prompt_id__state_post` |
| `GET` | `/admin/reset-password/{token}` | Admin Reset Password Page | `admin_reset_password_page_admin_reset_password__token__get` |
| `POST` | `/admin/reset-password/{token}` | Admin Reset Password Handler | `admin_reset_password_handler_admin_reset_password__token__post` |
| `GET` | `/admin/resources` | Admin List Resources | `admin_list_resources_admin_resources_get` |
| `POST` | `/admin/resources` | Admin Add Resource | `admin_add_resource_admin_resources_post` |
| `GET` | `/admin/resources/ids` | Admin Get All Resource Ids | `admin_get_all_resource_ids_admin_resources_ids_get` |
| `GET` | `/admin/resources/partial` | Admin Resources Partial Html | `admin_resources_partial_html_admin_resources_partial_get` |
| `GET` | `/admin/resources/search` | Admin Search Resources | `admin_search_resources_admin_resources_search_get` |
| `GET` | `/admin/resources/test/{resource_uri}` | Admin Test Resource | `admin_test_resource_admin_resources_test__resource_uri__get` |
| `GET` | `/admin/resources/{resource_id}` | Admin Get Resource | `admin_get_resource_admin_resources__resource_id__get` |
| `POST` | `/admin/resources/{resource_id}/delete` | Admin Delete Resource | `admin_delete_resource_admin_resources__resource_id__delete_post` |
| `POST` | `/admin/resources/{resource_id}/edit` | Admin Edit Resource | `admin_edit_resource_admin_resources__resource_id__edit_post` |
| `POST` | `/admin/resources/{resource_id}/state` | Admin Set Resource State | `admin_set_resource_state_admin_resources__resource_id__state_post` |
| `POST` | `/admin/roots` | Admin Add Root | `admin_add_root_admin_roots_post` |
| `GET` | `/admin/roots/export` | Admin Export Root | `admin_export_root_admin_roots_export_get` |
| `GET` | `/admin/roots/search` | Admin Search Roots | `admin_search_roots_admin_roots_search_get` |
| `GET` | `/admin/roots/{uri}` | Admin Get Root | `admin_get_root_admin_roots__uri__get` |
| `POST` | `/admin/roots/{uri}/delete` | Admin Delete Root | `admin_delete_root_admin_roots__uri__delete_post` |
| `POST` | `/admin/roots/{uri}/update` | Admin Update Root | `admin_update_root_admin_roots__uri__update_post` |
| `GET` | `/admin/search` | Admin Unified Search | `admin_unified_search_admin_search_get` |
| `GET` | `/admin/sections/gateways` | Get Gateways Section | `get_gateways_section_admin_sections_gateways_get` |
| `GET` | `/admin/sections/prompts` | Get Prompts Section | `get_prompts_section_admin_sections_prompts_get` |
| `GET` | `/admin/sections/resources` | Get Resources Section | `get_resources_section_admin_sections_resources_get` |
| `GET` | `/admin/sections/servers` | Get Servers Section | `get_servers_section_admin_sections_servers_get` |
| `GET` | `/admin/servers` | Admin List Servers | `admin_list_servers_admin_servers_get` |
| `POST` | `/admin/servers` | Admin Add Server | `admin_add_server_admin_servers_post` |
| `GET` | `/admin/servers/ids` | Admin Get All Server Ids | `admin_get_all_server_ids_admin_servers_ids_get` |
| `GET` | `/admin/servers/partial` | Admin Servers Partial Html | `admin_servers_partial_html_admin_servers_partial_get` |
| `GET` | `/admin/servers/search` | Admin Search Servers | `admin_search_servers_admin_servers_search_get` |
| `GET` | `/admin/servers/{server_id}` | Admin Get Server | `admin_get_server_admin_servers__server_id__get` |
| `POST` | `/admin/servers/{server_id}/delete` | Admin Delete Server | `admin_delete_server_admin_servers__server_id__delete_post` |
| `POST` | `/admin/servers/{server_id}/edit` | Admin Edit Server | `admin_edit_server_admin_servers__server_id__edit_post` |
| `POST` | `/admin/servers/{server_id}/state` | Admin Set Server State | `admin_set_server_state_admin_servers__server_id__state_post` |
| `GET` | `/admin/support-bundle/generate` | Admin Generate Support Bundle | `admin_generate_support_bundle_admin_support_bundle_generate_get` |
| `GET` | `/admin/system/stats` | Get System Stats | `get_system_stats_admin_system_stats_get` |
| `GET` | `/admin/tags` | Admin List Tags | `admin_list_tags_admin_tags_get` |
| `GET` | `/admin/teams` | Admin List Teams | `admin_list_teams_admin_teams_get` |
| `POST` | `/admin/teams` | Admin Create Team | `admin_create_team_admin_teams_post` |
| `GET` | `/admin/teams/ids` | Admin Get All Team Ids | `admin_get_all_team_ids_admin_teams_ids_get` |
| `GET` | `/admin/teams/partial` | Admin Teams Partial Html | `admin_teams_partial_html_admin_teams_partial_get` |
| `GET` | `/admin/teams/search` | Admin Search Teams | `admin_search_teams_admin_teams_search_get` |
| `DELETE` | `/admin/teams/{team_id}` | Admin Delete Team | `admin_delete_team_admin_teams__team_id__delete` |
| `POST` | `/admin/teams/{team_id}/add-member` | Admin Add Team Members | `admin_add_team_members_admin_teams__team_id__add_member_post` |
| `GET` | `/admin/teams/{team_id}/edit` | Admin Get Team Edit | `admin_get_team_edit_admin_teams__team_id__edit_get` |
| `POST` | `/admin/teams/{team_id}/join-request` | Admin Create Join Request | `admin_create_join_request_admin_teams__team_id__join_request_post` |
| `DELETE` | `/admin/teams/{team_id}/join-request/{request_id}` | Admin Cancel Join Request | `admin_cancel_join_request_admin_teams__team_id__join_request__request_id__delete` |
| `GET` | `/admin/teams/{team_id}/join-requests` | Admin List Join Requests | `admin_list_join_requests_admin_teams__team_id__join_requests_get` |
| `POST` | `/admin/teams/{team_id}/join-requests/{request_id}/approve` | Admin Approve Join Request | `admin_approve_join_request_admin_teams__team_id__join_requests__request_id__approve_post` |
| `POST` | `/admin/teams/{team_id}/join-requests/{request_id}/reject` | Admin Reject Join Request | `admin_reject_join_request_admin_teams__team_id__join_requests__request_id__reject_post` |
| `POST` | `/admin/teams/{team_id}/leave` | Admin Leave Team | `admin_leave_team_admin_teams__team_id__leave_post` |
| `GET` | `/admin/teams/{team_id}/members` | Admin View Team Members | `admin_view_team_members_admin_teams__team_id__members_get` |
| `GET` | `/admin/teams/{team_id}/members/add` | Admin Add Team Members View | `admin_add_team_members_view_admin_teams__team_id__members_add_get` |
| `GET` | `/admin/teams/{team_id}/members/partial` | Admin Team Members Partial Html | `admin_team_members_partial_html_admin_teams__team_id__members_partial_get` |
| `GET` | `/admin/teams/{team_id}/non-members/partial` | Admin Team Non Members Partial Html | `admin_team_non_members_partial_html_admin_teams__team_id__non_members_partial_get` |
| `POST` | `/admin/teams/{team_id}/remove-member` | Admin Remove Team Member | `admin_remove_team_member_admin_teams__team_id__remove_member_post` |
| `POST` | `/admin/teams/{team_id}/update` | Admin Update Team | `admin_update_team_admin_teams__team_id__update_post` |
| `POST` | `/admin/teams/{team_id}/update-member-role` | Admin Update Team Member Role | `admin_update_team_member_role_admin_teams__team_id__update_member_role_post` |
| `GET` | `/admin/tokens/partial` | Admin Tokens Partial Html | `admin_tokens_partial_html_admin_tokens_partial_get` |
| `GET` | `/admin/tokens/search` | Admin Search Tokens | `admin_search_tokens_admin_tokens_search_get` |
| `DELETE` | `/admin/tokens/{token_id}` | Admin Revoke Token | `admin_revoke_token_admin_tokens__token_id__delete` |
| `GET` | `/admin/tool-ops/partial` | Admin Tool Ops Partial | `admin_tool_ops_partial_admin_tool_ops_partial_get` |
| `GET` | `/admin/tools` | Admin List Tools | `admin_list_tools_admin_tools_get` |
| `POST` | `/admin/tools` | Admin Add Tool | `admin_add_tool_admin_tools_post` |
| `POST` | `/admin/tools/` | Admin Add Tool | `admin_add_tool_admin_tools__post` |
| `POST` | `/admin/tools/generate-schemas-from-openapi` | Generate Schemas From Openapi | `generate_schemas_from_openapi_admin_tools_generate_schemas_from_openapi_post` |
| `GET` | `/admin/tools/ids` | Admin Get All Tool Ids | `admin_get_all_tool_ids_admin_tools_ids_get` |
| `POST` | `/admin/tools/import` | Admin Import Tools | `admin_import_tools_admin_tools_import_post` |
| `POST` | `/admin/tools/import/` | Admin Import Tools | `admin_import_tools_admin_tools_import__post` |
| `GET` | `/admin/tools/partial` | Admin Tools Partial Html | `admin_tools_partial_html_admin_tools_partial_get` |
| `GET` | `/admin/tools/search` | Admin Search Tools | `admin_search_tools_admin_tools_search_get` |
| `GET` | `/admin/tools/{tool_id}` | Admin Get Tool | `admin_get_tool_admin_tools__tool_id__get` |
| `POST` | `/admin/tools/{tool_id}/delete` | Admin Delete Tool | `admin_delete_tool_admin_tools__tool_id__delete_post` |
| `POST` | `/admin/tools/{tool_id}/edit` | Admin Edit Tool | `admin_edit_tool_admin_tools__tool_id__edit_post` |
| `POST` | `/admin/tools/{tool_id}/edit/` | Admin Edit Tool | `admin_edit_tool_admin_tools__tool_id__edit__post` |
| `POST` | `/admin/tools/{tool_id}/state` | Admin Set Tool State | `admin_set_tool_state_admin_tools__tool_id__state_post` |
| `GET` | `/admin/users` | Admin List Users | `admin_list_users_admin_users_get` |
| `POST` | `/admin/users` | Admin Create User | `admin_create_user_admin_users_post` |
| `GET` | `/admin/users/partial` | Admin Users Partial Html | `admin_users_partial_html_admin_users_partial_get` |
| `GET` | `/admin/users/search` | Admin Search Users | `admin_search_users_admin_users_search_get` |
| `DELETE` | `/admin/users/{user_email}` | Admin Delete User | `admin_delete_user_admin_users__user_email__delete` |
| `POST` | `/admin/users/{user_email}/activate` | Admin Activate User | `admin_activate_user_admin_users__user_email__activate_post` |
| `POST` | `/admin/users/{user_email}/deactivate` | Admin Deactivate User | `admin_deactivate_user_admin_users__user_email__deactivate_post` |
| `GET` | `/admin/users/{user_email}/edit` | Admin Get User Edit | `admin_get_user_edit_admin_users__user_email__edit_get` |
| `POST` | `/admin/users/{user_email}/force-password-change` | Admin Force Password Change | `admin_force_password_change_admin_users__user_email__force_password_change_post` |
| `POST` | `/admin/users/{user_email}/unlock` | Admin Unlock User | `admin_unlock_user_admin_users__user_email__unlock_post` |
| `POST` | `/admin/users/{user_email}/update` | Admin Update User | `admin_update_user_admin_users__user_email__update_post` |

### Cancellation

| Method | Path | Purpose | Operation ID |
| --- | --- | --- | --- |
| `POST` | `/cancellation/cancel` | Cancel Run | `cancel_run_cancellation_cancel_post` |
| `GET` | `/cancellation/status/{request_id}` | Get Status | `get_status_cancellation_status__request_id__get` |

### Compliance

| Method | Path | Purpose | Operation ID |
| --- | --- | --- | --- |
| `GET` | `/compliance/frameworks` | List Frameworks | `list_frameworks_compliance_frameworks_get` |
| `GET` | `/compliance/reports` | List Reports | `list_reports_compliance_reports_get` |
| `POST` | `/compliance/reports` | Generate Report | `generate_report_compliance_reports_post` |
| `GET` | `/compliance/reports/{report_id}` | Get Report | `get_report_compliance_reports__report_id__get` |
| `GET` | `/compliance/reports/{report_id}/export` | Export Report | `export_report_compliance_reports__report_id__export_get` |

### Email Authentication

| Method | Path | Purpose | Operation ID |
| --- | --- | --- | --- |
| `GET` | `/auth/email/admin/events` | List All Auth Events | `list_all_auth_events_auth_email_admin_events_get` |
| `GET` | `/auth/email/admin/users` | List Users | `list_users_auth_email_admin_users_get` |
| `POST` | `/auth/email/admin/users` | Create User | `create_user_auth_email_admin_users_post` |
| `GET` | `/auth/email/admin/users/{user_email}` | Get User | `get_user_auth_email_admin_users__user_email__get` |
| `PUT` | `/auth/email/admin/users/{user_email}` | Update User Deprecated | `update_user_deprecated_auth_email_admin_users__user_email__put` |
| `PATCH` | `/auth/email/admin/users/{user_email}` | Update User | `update_user_auth_email_admin_users__user_email__patch` |
| `DELETE` | `/auth/email/admin/users/{user_email}` | Delete User | `delete_user_auth_email_admin_users__user_email__delete` |
| `POST` | `/auth/email/admin/users/{user_email}/unlock` | Unlock User | `unlock_user_auth_email_admin_users__user_email__unlock_post` |
| `POST` | `/auth/email/change-password` | Change Password | `change_password_auth_email_change_password_post` |
| `GET` | `/auth/email/events` | Get Auth Events | `get_auth_events_auth_email_events_get` |
| `POST` | `/auth/email/forgot-password` | Forgot Password | `forgot_password_auth_email_forgot_password_post` |
| `POST` | `/auth/email/login` | Login | `login_auth_email_login_post` |
| `GET` | `/auth/email/me` | Get Current User Profile | `get_current_user_profile_auth_email_me_get` |
| `POST` | `/auth/email/register` | Register | `register_auth_email_register_post` |
| `GET` | `/auth/email/reset-password/{token}` | Validate Password Reset Token | `validate_password_reset_token_auth_email_reset_password__token__get` |
| `POST` | `/auth/email/reset-password/{token}` | Complete Password Reset | `complete_password_reset_auth_email_reset_password__token__post` |

### Export/Import

| Method | Path | Purpose | Operation ID |
| --- | --- | --- | --- |
| `GET` | `/export` | Export Configuration | `export_configuration_export_get` |
| `POST` | `/export/selective` | Export Selective Configuration | `export_selective_configuration_export_selective_post` |
| `POST` | `/import` | Import Configuration | `import_configuration_import_post` |
| `POST` | `/import/cleanup` | Cleanup Import Statuses | `cleanup_import_statuses_import_cleanup_post` |
| `GET` | `/import/status` | List Import Statuses | `list_import_statuses_import_status_get` |
| `GET` | `/import/status/{import_id}` | Get Import Status | `get_import_status_import_status__import_id__get` |

### Gateways

| Method | Path | Purpose | Operation ID |
| --- | --- | --- | --- |
| `GET` | `/gateways` | List Gateways | `list_gateways_gateways_get` |
| `POST` | `/gateways` | Register Gateway | `register_gateway_gateways_post` |
| `GET` | `/gateways/` | List Gateways | `list_gateways_gateways__get` |
| `POST` | `/gateways/` | Register Gateway | `register_gateway_gateways__post` |
| `GET` | `/gateways/{gateway_id}` | Get Gateway | `get_gateway_gateways__gateway_id__get` |
| `PUT` | `/gateways/{gateway_id}` | Update Gateway | `update_gateway_gateways__gateway_id__put` |
| `DELETE` | `/gateways/{gateway_id}` | Delete Gateway | `delete_gateway_gateways__gateway_id__delete` |
| `POST` | `/gateways/{gateway_id}/state` | Set Gateway State | `set_gateway_state_gateways__gateway_id__state_post` |
| `POST` | `/gateways/{gateway_id}/toggle` | Toggle Gateway Status | `toggle_gateway_status_gateways__gateway_id__toggle_post` |
| `POST` | `/gateways/{gateway_id}/tools/refresh` | Refresh Gateway Tools | `refresh_gateway_tools_gateways__gateway_id__tools_refresh_post` |

### health

| Method | Path | Purpose | Operation ID |
| --- | --- | --- | --- |
| `GET` | `/health/security` | Security Health | `security_health_health_security_get` |

### JWT Token Catalog, tokens

| Method | Path | Purpose | Operation ID |
| --- | --- | --- | --- |
| `GET` | `/tokens` | List Tokens | `list_tokens_tokens_get` |
| `POST` | `/tokens` | Create Token | `create_token_tokens_post` |
| `GET` | `/tokens/teams/{team_id}` | List Team Tokens | `list_team_tokens_tokens_teams__team_id__get` |
| `POST` | `/tokens/teams/{team_id}` | Create Team Token | `create_team_token_tokens_teams__team_id__post` |
| `GET` | `/tokens/{token_id}` | Get Token | `get_token_tokens__token_id__get` |
| `PUT` | `/tokens/{token_id}` | Update Token | `update_token_tokens__token_id__put` |
| `DELETE` | `/tokens/{token_id}` | Revoke Token | `revoke_token_tokens__token_id__delete` |
| `GET` | `/tokens/{token_id}/usage` | Get Token Usage Stats | `get_token_usage_stats_tokens__token_id__usage_get` |

### JWT Token Catalog, tokens, admin

| Method | Path | Purpose | Operation ID |
| --- | --- | --- | --- |
| `GET` | `/tokens/admin/all` | List All Tokens | `list_all_tokens_tokens_admin_all_get` |
| `DELETE` | `/tokens/admin/{token_id}` | Admin Revoke Token | `admin_revoke_token_tokens_admin__token_id__delete` |

### LLM Admin

| Method | Path | Purpose | Operation ID |
| --- | --- | --- | --- |
| `GET` | `/admin/llm/api-info/html` | Get Api Info Partial | `get_api_info_partial_admin_llm_api_info_html_get` |
| `GET` | `/admin/llm/models/html` | Get Models Partial | `get_models_partial_admin_llm_models_html_get` |
| `DELETE` | `/admin/llm/models/{model_id}` | Delete Model Html | `delete_model_html_admin_llm_models__model_id__delete` |
| `POST` | `/admin/llm/models/{model_id}/state` | Set Model State Html | `set_model_state_html_admin_llm_models__model_id__state_post` |
| `GET` | `/admin/llm/provider-configs` | Get Provider Configs | `get_provider_configs_admin_llm_provider_configs_get` |
| `GET` | `/admin/llm/provider-defaults` | Get Provider Defaults | `get_provider_defaults_admin_llm_provider_defaults_get` |
| `GET` | `/admin/llm/providers/html` | Get Providers Partial | `get_providers_partial_admin_llm_providers_html_get` |
| `DELETE` | `/admin/llm/providers/{provider_id}` | Delete Provider Html | `delete_provider_html_admin_llm_providers__provider_id__delete` |
| `POST` | `/admin/llm/providers/{provider_id}/fetch-models` | Fetch Provider Models | `fetch_provider_models_admin_llm_providers__provider_id__fetch_models_post` |
| `POST` | `/admin/llm/providers/{provider_id}/health` | Check Provider Health | `check_provider_health_admin_llm_providers__provider_id__health_post` |
| `POST` | `/admin/llm/providers/{provider_id}/state` | Set Provider State Html | `set_provider_state_html_admin_llm_providers__provider_id__state_post` |
| `POST` | `/admin/llm/providers/{provider_id}/sync-models` | Sync Provider Models | `sync_provider_models_admin_llm_providers__provider_id__sync_models_post` |
| `POST` | `/admin/llm/test` | Admin Test Api | `admin_test_api_admin_llm_test_post` |

### LLM Configuration

| Method | Path | Purpose | Operation ID |
| --- | --- | --- | --- |
| `GET` | `/llm/gateway/models` | Get Gateway Models | `get_gateway_models_llm_gateway_models_get` |
| `GET` | `/llm/models` | List LLM Models | `list_models_llm_models_get` |
| `POST` | `/llm/models` | Create LLM Model | `create_model_llm_models_post` |
| `GET` | `/llm/models/{model_id}` | Get LLM Model | `get_model_llm_models__model_id__get` |
| `PATCH` | `/llm/models/{model_id}` | Update LLM Model | `update_model_llm_models__model_id__patch` |
| `DELETE` | `/llm/models/{model_id}` | Delete LLM Model | `delete_model_llm_models__model_id__delete` |
| `POST` | `/llm/models/{model_id}/state` | Set LLM Model State | `set_model_state_llm_models__model_id__state_post` |
| `GET` | `/llm/providers` | List LLM Providers | `list_providers_llm_providers_get` |
| `POST` | `/llm/providers` | Create LLM Provider | `create_provider_llm_providers_post` |
| `GET` | `/llm/providers/{provider_id}` | Get LLM Provider | `get_provider_llm_providers__provider_id__get` |
| `PATCH` | `/llm/providers/{provider_id}` | Update LLM Provider | `update_provider_llm_providers__provider_id__patch` |
| `DELETE` | `/llm/providers/{provider_id}` | Delete LLM Provider | `delete_provider_llm_providers__provider_id__delete` |
| `POST` | `/llm/providers/{provider_id}/health` | Check Provider Health | `check_provider_health_llm_providers__provider_id__health_post` |
| `POST` | `/llm/providers/{provider_id}/state` | Set LLM Provider State | `set_provider_state_llm_providers__provider_id__state_post` |

### LLM Proxy

| Method | Path | Purpose | Operation ID |
| --- | --- | --- | --- |
| `POST` | `/v1/chat/completions` | Chat Completions | `chat_completions_v1_chat_completions_post` |
| `GET` | `/v1/models` | List Models | `list_models_v1_models_get` |

### llmchat

| Method | Path | Purpose | Operation ID |
| --- | --- | --- | --- |
| `POST` | `/llmchat/chat` | Chat | `chat_llmchat_chat_post` |
| `GET` | `/llmchat/config/{user_id}` | Get Config | `get_config_llmchat_config__user_id__get` |
| `POST` | `/llmchat/connect` | Connect | `connect_llmchat_connect_post` |
| `POST` | `/llmchat/disconnect` | Disconnect | `disconnect_llmchat_disconnect_post` |
| `GET` | `/llmchat/gateway/models` | Get Gateway Models | `get_gateway_models_llmchat_gateway_models_get` |
| `GET` | `/llmchat/status/{user_id}` | Status | `status_llmchat_status__user_id__get` |

### logs

| Method | Path | Purpose | Operation ID |
| --- | --- | --- | --- |
| `GET` | `/api/logs/audit-trails` | Get Audit Trails | `get_audit_trails_api_logs_audit_trails_get` |
| `GET` | `/api/logs/performance-metrics` | Get Performance Metrics | `get_performance_metrics_api_logs_performance_metrics_get` |
| `POST` | `/api/logs/search` | Search Logs | `search_logs_api_logs_search_post` |
| `GET` | `/api/logs/security-events` | Get Security Events | `get_security_events_api_logs_security_events_get` |
| `GET` | `/api/logs/trace/{correlation_id}` | Trace Correlation Id | `trace_correlation_id_api_logs_trace__correlation_id__get` |

### Main Authentication, Authentication

| Method | Path | Purpose | Operation ID |
| --- | --- | --- | --- |
| `GET` | `/auth/csrf-token` | Get Csrf Token | `get_csrf_token_auth_csrf_token_get` |
| `POST` | `/auth/login` | Login | `login_auth_login_post` |
| `POST` | `/auth/logout` | Logout | `logout_auth_logout_post` |

### meta

| Method | Path | Purpose | Operation ID |
| --- | --- | --- | --- |
| `GET` | `/version` | Diagnostics (admin only) | `version_endpoint_version_get` |

### Metrics

| Method | Path | Purpose | Operation ID |
| --- | --- | --- | --- |
| `GET` | `/metrics` | Get Metrics | `get_metrics_metrics_get` |
| `GET` | `/metrics/prometheus` | Metrics Disabled | `metrics_disabled_metrics_prometheus_get` |
| `POST` | `/metrics/reset` | Reset Metrics | `reset_metrics_metrics_reset_post` |

### Metrics Maintenance

| Method | Path | Purpose | Operation ID |
| --- | --- | --- | --- |
| `POST` | `/api/metrics/cleanup` | Trigger Cleanup | `trigger_cleanup_api_metrics_cleanup_post` |
| `GET` | `/api/metrics/config` | Get Metrics Config | `get_metrics_config_api_metrics_config_get` |
| `POST` | `/api/metrics/rollup` | Trigger Rollup | `trigger_rollup_api_metrics_rollup_post` |
| `GET` | `/api/metrics/stats` | Get Metrics Stats | `get_metrics_stats_api_metrics_stats_get` |

### oauth

| Method | Path | Purpose | Operation ID |
| --- | --- | --- | --- |
| `GET` | `/oauth/authorize/{gateway_id}` | Initiate Oauth Flow | `initiate_oauth_flow_oauth_authorize__gateway_id__get` |
| `GET` | `/oauth/callback` | Oauth Callback | `oauth_callback_oauth_callback_get` |
| `POST` | `/oauth/fetch-tools/{gateway_id}` | Fetch Tools After Oauth | `fetch_tools_after_oauth_oauth_fetch_tools__gateway_id__post` |
| `GET` | `/oauth/registered-clients` | List Registered Oauth Clients | `list_registered_oauth_clients_oauth_registered_clients_get` |
| `DELETE` | `/oauth/registered-clients/{client_id}` | Delete Registered Client | `delete_registered_client_oauth_registered_clients__client_id__delete` |
| `GET` | `/oauth/registered-clients/{gateway_id}` | Get Registered Client For Gateway | `get_registered_client_for_gateway_oauth_registered_clients__gateway_id__get` |
| `GET` | `/oauth/status/{gateway_id}` | Get Oauth Status | `get_oauth_status_oauth_status__gateway_id__get` |

### Prompts

| Method | Path | Purpose | Operation ID |
| --- | --- | --- | --- |
| `GET` | `/prompts` | List Prompts | `list_prompts_prompts_get` |
| `POST` | `/prompts` | Create Prompt | `create_prompt_prompts_post` |
| `GET` | `/prompts/` | List Prompts | `list_prompts_prompts__get` |
| `POST` | `/prompts/` | Create Prompt | `create_prompt_prompts__post` |
| `GET` | `/prompts/{prompt_id}` | Get Prompt No Args | `get_prompt_no_args_prompts__prompt_id__get` |
| `POST` | `/prompts/{prompt_id}` | Get Prompt | `get_prompt_prompts__prompt_id__post` |
| `PUT` | `/prompts/{prompt_id}` | Update Prompt | `update_prompt_prompts__prompt_id__put` |
| `DELETE` | `/prompts/{prompt_id}` | Delete Prompt | `delete_prompt_prompts__prompt_id__delete` |
| `POST` | `/prompts/{prompt_id}/state` | Set Prompt State | `set_prompt_state_prompts__prompt_id__state_post` |
| `POST` | `/prompts/{prompt_id}/toggle` | Toggle Prompt Status | `toggle_prompt_status_prompts__prompt_id__toggle_post` |

### Protocol

| Method | Path | Purpose | Operation ID |
| --- | --- | --- | --- |
| `POST` | `/protocol/completion/complete` | Handle Completion | `handle_completion_protocol_completion_complete_post` |
| `POST` | `/protocol/initialize` | Initialize | `initialize_protocol_initialize_post` |
| `POST` | `/protocol/notifications` | Handle Notification | `handle_notification_protocol_notifications_post` |
| `POST` | `/protocol/ping` | Ping | `ping_protocol_ping_post` |
| `POST` | `/protocol/sampling/createMessage` | Handle Sampling | `handle_sampling_protocol_sampling_createMessage_post` |

### RBAC, RBAC

| Method | Path | Purpose | Operation ID |
| --- | --- | --- | --- |
| `GET` | `/rbac/my/permissions` | Get My Permissions | `get_my_permissions_rbac_my_permissions_get` |
| `GET` | `/rbac/my/roles` | Get My Roles | `get_my_roles_rbac_my_roles_get` |
| `GET` | `/rbac/permissions/available` | Get Available Permissions | `get_available_permissions_rbac_permissions_available_get` |
| `POST` | `/rbac/permissions/check` | Check Permission | `check_permission_rbac_permissions_check_post` |
| `GET` | `/rbac/permissions/user/{user_email}` | Get User Permissions | `get_user_permissions_rbac_permissions_user__user_email__get` |
| `GET` | `/rbac/roles` | List Roles | `list_roles_rbac_roles_get` |
| `POST` | `/rbac/roles` | Create Role | `create_role_rbac_roles_post` |
| `GET` | `/rbac/roles/{role_id}` | Get Role | `get_role_rbac_roles__role_id__get` |
| `PUT` | `/rbac/roles/{role_id}` | Update Role | `update_role_rbac_roles__role_id__put` |
| `DELETE` | `/rbac/roles/{role_id}` | Delete Role | `delete_role_rbac_roles__role_id__delete` |
| `GET` | `/rbac/users/{user_email}/roles` | Get User Roles | `get_user_roles_rbac_users__user_email__roles_get` |
| `POST` | `/rbac/users/{user_email}/roles` | Assign Role To User | `assign_role_to_user_rbac_users__user_email__roles_post` |
| `DELETE` | `/rbac/users/{user_email}/roles/{role_id}` | Revoke User Role | `revoke_user_role_rbac_users__user_email__roles__role_id__delete` |

### Resources

| Method | Path | Purpose | Operation ID |
| --- | --- | --- | --- |
| `GET` | `/resources` | List Resources | `list_resources_resources_get` |
| `POST` | `/resources` | Create Resource | `create_resource_resources_post` |
| `GET` | `/resources/` | List Resources | `list_resources_resources__get` |
| `POST` | `/resources/` | Create Resource | `create_resource_resources__post` |
| `POST` | `/resources/subscribe` | Subscribe Resource | `subscribe_resource_resources_subscribe_post` |
| `GET` | `/resources/templates/list` | List Resource Templates | `list_resource_templates_resources_templates_list_get` |
| `GET` | `/resources/{resource_id}` | Read Resource | `read_resource_resources__resource_id__get` |
| `PUT` | `/resources/{resource_id}` | Update Resource | `update_resource_resources__resource_id__put` |
| `DELETE` | `/resources/{resource_id}` | Delete Resource | `delete_resource_resources__resource_id__delete` |
| `GET` | `/resources/{resource_id}/info` | Get Resource Info | `get_resource_info_resources__resource_id__info_get` |
| `POST` | `/resources/{resource_id}/state` | Set Resource State | `set_resource_state_resources__resource_id__state_post` |
| `POST` | `/resources/{resource_id}/toggle` | Toggle Resource Status | `toggle_resource_status_resources__resource_id__toggle_post` |

### Roots

| Method | Path | Purpose | Operation ID |
| --- | --- | --- | --- |
| `GET` | `/roots` | List Roots | `list_roots_roots_get` |
| `POST` | `/roots` | Add Root | `add_root_roots_post` |
| `GET` | `/roots/` | List Roots | `list_roots_roots__get` |
| `POST` | `/roots/` | Add Root | `add_root_roots__post` |
| `GET` | `/roots/changes` | Subscribe Roots Changes | `subscribe_roots_changes_roots_changes_get` |
| `GET` | `/roots/export` | Export Root | `export_root_roots_export_get` |
| `GET` | `/roots/{root_uri}` | Get Root By Uri | `get_root_by_uri_roots__root_uri__get` |
| `PUT` | `/roots/{root_uri}` | Update Root | `update_root_roots__root_uri__put` |
| `DELETE` | `/roots/{uri}` | Remove Root | `remove_root_roots__uri__delete` |

### Runtime Admin

| Method | Path | Purpose | Operation ID |
| --- | --- | --- | --- |
| `GET` | `/admin/runtime/a2a-mode` | Get A2A Mode | `get_a2a_mode_admin_runtime_a2a_mode_get` |
| `PATCH` | `/admin/runtime/a2a-mode` | Patch A2A Mode | `patch_a2a_mode_admin_runtime_a2a_mode_patch` |
| `GET` | `/admin/runtime/mcp-mode` | Get Mcp Mode | `get_mcp_mode_admin_runtime_mcp_mode_get` |
| `PATCH` | `/admin/runtime/mcp-mode` | Patch Mcp Mode | `patch_mcp_mode_admin_runtime_mcp_mode_patch` |

### Servers

| Method | Path | Purpose | Operation ID |
| --- | --- | --- | --- |
| `GET` | `/servers` | List Servers | `list_servers_servers_get` |
| `POST` | `/servers` | Create Server | `create_server_servers_post` |
| `GET` | `/servers/` | List Servers | `list_servers_servers__get` |
| `POST` | `/servers/` | Create Server | `create_server_servers__post` |
| `GET` | `/servers/{server_id}` | Get Server | `get_server_servers__server_id__get` |
| `PUT` | `/servers/{server_id}` | Update Server | `update_server_servers__server_id__put` |
| `DELETE` | `/servers/{server_id}` | Delete Server | `delete_server_servers__server_id__delete` |
| `GET` | `/servers/{server_id}/.well-known/oauth-protected-resource` | Server Oauth Protected Resource | `server_oauth_protected_resource_servers__server_id___well_known_oauth_protected_resource_get` |
| `POST` | `/servers/{server_id}/message` | Message Endpoint | `message_endpoint_servers__server_id__message_post` |
| `GET` | `/servers/{server_id}/prompts` | Server Get Prompts | `server_get_prompts_servers__server_id__prompts_get` |
| `GET` | `/servers/{server_id}/resources` | Server Get Resources | `server_get_resources_servers__server_id__resources_get` |
| `GET` | `/servers/{server_id}/sse` | Sse Endpoint | `sse_endpoint_servers__server_id__sse_get` |
| `POST` | `/servers/{server_id}/state` | Set Server State | `set_server_state_servers__server_id__state_post` |
| `POST` | `/servers/{server_id}/toggle` | Toggle Server Status | `toggle_server_status_servers__server_id__toggle_post` |
| `GET` | `/servers/{server_id}/tools` | Server Get Tools | `server_get_tools_servers__server_id__tools_get` |

### Tags

| Method | Path | Purpose | Operation ID |
| --- | --- | --- | --- |
| `GET` | `/tags` | List Tags | `list_tags_tags_get` |
| `GET` | `/tags/` | List Tags | `list_tags_tags__get` |
| `GET` | `/tags/{tag_name}/entities` | Get Entities By Tag | `get_entities_by_tag_tags__tag_name__entities_get` |

### Teams

| Method | Path | Purpose | Operation ID |
| --- | --- | --- | --- |
| `GET` | `/teams/` | List Teams | `list_teams_teams__get` |
| `POST` | `/teams/` | Create Team | `create_team_teams__post` |
| `GET` | `/teams/discover` | Discover Public Teams | `discover_public_teams_teams_discover_get` |
| `DELETE` | `/teams/invitations/{invitation_id}` | Cancel Team Invitation | `cancel_team_invitation_teams_invitations__invitation_id__delete` |
| `POST` | `/teams/invitations/{token}/accept` | Accept Team Invitation | `accept_team_invitation_teams_invitations__token__accept_post` |
| `GET` | `/teams/{team_id}` | Get Team | `get_team_teams__team_id__get` |
| `PUT` | `/teams/{team_id}` | Update Team | `update_team_teams__team_id__put` |
| `DELETE` | `/teams/{team_id}` | Delete Team | `delete_team_teams__team_id__delete` |
| `GET` | `/teams/{team_id}/invitations` | List Team Invitations | `list_team_invitations_teams__team_id__invitations_get` |
| `POST` | `/teams/{team_id}/invitations` | Invite Team Member | `invite_team_member_teams__team_id__invitations_post` |
| `POST` | `/teams/{team_id}/join` | Request To Join Team | `request_to_join_team_teams__team_id__join_post` |
| `GET` | `/teams/{team_id}/join-requests` | List Team Join Requests | `list_team_join_requests_teams__team_id__join_requests_get` |
| `DELETE` | `/teams/{team_id}/join-requests/{request_id}` | Reject Join Request | `reject_join_request_teams__team_id__join_requests__request_id__delete` |
| `POST` | `/teams/{team_id}/join-requests/{request_id}/approve` | Approve Join Request | `approve_join_request_teams__team_id__join_requests__request_id__approve_post` |
| `DELETE` | `/teams/{team_id}/leave` | Leave Team | `leave_team_teams__team_id__leave_delete` |
| `GET` | `/teams/{team_id}/members` | List Team Members | `list_team_members_teams__team_id__members_get` |
| `POST` | `/teams/{team_id}/members` | Add Team Member | `add_team_member_teams__team_id__members_post` |
| `PUT` | `/teams/{team_id}/members/{user_email}` | Update Team Member | `update_team_member_teams__team_id__members__user_email__put` |
| `DELETE` | `/teams/{team_id}/members/{user_email}` | Remove Team Member | `remove_team_member_teams__team_id__members__user_email__delete` |

### Tool Plugin Bindings

| Method | Path | Purpose | Operation ID |
| --- | --- | --- | --- |
| `GET` | `/v1/tools/plugin_bindings/` | List Tool Plugin Bindings | `list_tool_plugin_bindings_v1_tools_plugin_bindings__get` |
| `POST` | `/v1/tools/plugin_bindings/` | Upsert Tool Plugin Bindings | `upsert_tool_plugin_bindings_v1_tools_plugin_bindings__post` |
| `DELETE` | `/v1/tools/plugin_bindings/` | Delete Tool Plugin Bindings By Reference | `delete_tool_plugin_bindings_by_reference_v1_tools_plugin_bindings__delete` |
| `DELETE` | `/v1/tools/plugin_bindings/{binding_id}` | Delete Tool Plugin Binding | `delete_tool_plugin_binding_v1_tools_plugin_bindings__binding_id__delete` |
| `GET` | `/v1/tools/plugin_bindings/{team_id}` | List Tool Plugin Bindings For Team | `list_tool_plugin_bindings_for_team_v1_tools_plugin_bindings__team_id__get` |

### Tools

| Method | Path | Purpose | Operation ID |
| --- | --- | --- | --- |
| `GET` | `/tools` | List Tools | `list_tools_tools_get` |
| `POST` | `/tools` | Create Tool | `create_tool_tools_post` |
| `GET` | `/tools/` | List Tools | `list_tools_tools__get` |
| `POST` | `/tools/` | Create Tool | `create_tool_tools__post` |
| `GET` | `/tools/{tool_id}` | Get Tool | `get_tool_tools__tool_id__get` |
| `PUT` | `/tools/{tool_id}` | Update Tool | `update_tool_tools__tool_id__put` |
| `DELETE` | `/tools/{tool_id}` | Delete Tool | `delete_tool_tools__tool_id__delete` |
| `POST` | `/tools/{tool_id}/state` | Set Tool State | `set_tool_state_tools__tool_id__state_post` |
| `POST` | `/tools/{tool_id}/toggle` | Toggle Tool Status | `toggle_tool_status_tools__tool_id__toggle_post` |

### Untagged

| Method | Path | Purpose | Operation ID |
| --- | --- | --- | --- |
| `GET` | `/` | Root Redirect | `root_redirect__get` |
| `GET` | `/health` | Healthcheck | `healthcheck_health_get` |
| `POST` | `/initialize` | Initialize | `initialize_initialize_post` |
| `POST` | `/notifications` | Handle Notification | `handle_notification_notifications_post` |
| `GET` | `/ready` | Readiness Check | `readiness_check_ready_get` |

### Utilities

| Method | Path | Purpose | Operation ID |
| --- | --- | --- | --- |
| `POST` | `/_internal/a2a/agents/{agent_name}/card` | Handle Internal A2A Agent Card | `handle_internal_a2a_agent_card__internal_a2a_agents__agent_name__card_post` |
| `POST` | `/_internal/a2a/agents/{agent_name}/card/` | Handle Internal A2A Agent Card | `handle_internal_a2a_agent_card__internal_a2a_agents__agent_name__card__post` |
| `POST` | `/_internal/a2a/agents/{agent_name}/resolve` | Handle Internal A2A Agent Resolve | `handle_internal_a2a_agent_resolve__internal_a2a_agents__agent_name__resolve_post` |
| `POST` | `/_internal/a2a/agents/{agent_name}/resolve/` | Handle Internal A2A Agent Resolve | `handle_internal_a2a_agent_resolve__internal_a2a_agents__agent_name__resolve__post` |
| `POST` | `/_internal/a2a/authenticate` | Handle Internal A2A Authenticate | `handle_internal_a2a_authenticate__internal_a2a_authenticate_post` |
| `POST` | `/_internal/a2a/authenticate/` | Handle Internal A2A Authenticate | `handle_internal_a2a_authenticate__internal_a2a_authenticate__post` |
| `POST` | `/_internal/a2a/events/flush` | Handle Internal A2A Events Flush | `handle_internal_a2a_events_flush__internal_a2a_events_flush_post` |
| `POST` | `/_internal/a2a/events/flush/` | Handle Internal A2A Events Flush | `handle_internal_a2a_events_flush__internal_a2a_events_flush__post` |
| `POST` | `/_internal/a2a/events/replay` | Handle Internal A2A Events Replay | `handle_internal_a2a_events_replay__internal_a2a_events_replay_post` |
| `POST` | `/_internal/a2a/events/replay/` | Handle Internal A2A Events Replay | `handle_internal_a2a_events_replay__internal_a2a_events_replay__post` |
| `POST` | `/_internal/a2a/get/authz` | Handle Internal A2A Get Authz | `handle_internal_a2a_get_authz__internal_a2a_get_authz_post` |
| `POST` | `/_internal/a2a/get/authz/` | Handle Internal A2A Get Authz | `handle_internal_a2a_get_authz__internal_a2a_get_authz__post` |
| `POST` | `/_internal/a2a/invoke/authz` | Handle Internal A2A Invoke Authz | `handle_internal_a2a_invoke_authz__internal_a2a_invoke_authz_post` |
| `POST` | `/_internal/a2a/invoke/authz/` | Handle Internal A2A Invoke Authz | `handle_internal_a2a_invoke_authz__internal_a2a_invoke_authz__post` |
| `POST` | `/_internal/a2a/list/authz` | Handle Internal A2A List Authz | `handle_internal_a2a_list_authz__internal_a2a_list_authz_post` |
| `POST` | `/_internal/a2a/list/authz/` | Handle Internal A2A List Authz | `handle_internal_a2a_list_authz__internal_a2a_list_authz__post` |
| `POST` | `/_internal/a2a/push/create` | Handle Internal A2A Push Create | `handle_internal_a2a_push_create__internal_a2a_push_create_post` |
| `POST` | `/_internal/a2a/push/create/` | Handle Internal A2A Push Create | `handle_internal_a2a_push_create__internal_a2a_push_create__post` |
| `POST` | `/_internal/a2a/push/delete` | Handle Internal A2A Push Delete | `handle_internal_a2a_push_delete__internal_a2a_push_delete_post` |
| `POST` | `/_internal/a2a/push/delete/` | Handle Internal A2A Push Delete | `handle_internal_a2a_push_delete__internal_a2a_push_delete__post` |
| `POST` | `/_internal/a2a/push/get` | Handle Internal A2A Push Get | `handle_internal_a2a_push_get__internal_a2a_push_get_post` |
| `POST` | `/_internal/a2a/push/get/` | Handle Internal A2A Push Get | `handle_internal_a2a_push_get__internal_a2a_push_get__post` |
| `POST` | `/_internal/a2a/push/list` | Handle Internal A2A Push List | `handle_internal_a2a_push_list__internal_a2a_push_list_post` |
| `POST` | `/_internal/a2a/push/list/` | Handle Internal A2A Push List | `handle_internal_a2a_push_list__internal_a2a_push_list__post` |
| `POST` | `/_internal/a2a/tasks/cancel` | Handle Internal A2A Tasks Cancel | `handle_internal_a2a_tasks_cancel__internal_a2a_tasks_cancel_post` |
| `POST` | `/_internal/a2a/tasks/cancel/` | Handle Internal A2A Tasks Cancel | `handle_internal_a2a_tasks_cancel__internal_a2a_tasks_cancel__post` |
| `POST` | `/_internal/a2a/tasks/get` | Handle Internal A2A Tasks Get | `handle_internal_a2a_tasks_get__internal_a2a_tasks_get_post` |
| `POST` | `/_internal/a2a/tasks/get/` | Handle Internal A2A Tasks Get | `handle_internal_a2a_tasks_get__internal_a2a_tasks_get__post` |
| `POST` | `/_internal/a2a/tasks/list` | Handle Internal A2A Tasks List | `handle_internal_a2a_tasks_list__internal_a2a_tasks_list_post` |
| `POST` | `/_internal/a2a/tasks/list/` | Handle Internal A2A Tasks List | `handle_internal_a2a_tasks_list__internal_a2a_tasks_list__post` |
| `POST` | `/_internal/mcp/authenticate` | Handle Internal Mcp Authenticate | `handle_internal_mcp_authenticate__internal_mcp_authenticate_post` |
| `POST` | `/_internal/mcp/authenticate/` | Handle Internal Mcp Authenticate | `handle_internal_mcp_authenticate__internal_mcp_authenticate__post` |
| `POST` | `/_internal/mcp/completion/complete` | Handle Internal Mcp Completion Complete | `handle_internal_mcp_completion_complete__internal_mcp_completion_complete_post` |
| `POST` | `/_internal/mcp/completion/complete/` | Handle Internal Mcp Completion Complete | `handle_internal_mcp_completion_complete__internal_mcp_completion_complete__post` |
| `POST` | `/_internal/mcp/initialize` | Handle Internal Mcp Initialize | `handle_internal_mcp_initialize__internal_mcp_initialize_post` |
| `POST` | `/_internal/mcp/initialize/` | Handle Internal Mcp Initialize | `handle_internal_mcp_initialize__internal_mcp_initialize__post` |
| `POST` | `/_internal/mcp/logging/setLevel` | Handle Internal Mcp Logging Set Level | `handle_internal_mcp_logging_set_level__internal_mcp_logging_setLevel_post` |
| `POST` | `/_internal/mcp/logging/setLevel/` | Handle Internal Mcp Logging Set Level | `handle_internal_mcp_logging_set_level__internal_mcp_logging_setLevel__post` |
| `POST` | `/_internal/mcp/notifications/cancelled` | Handle Internal Mcp Notifications Cancelled | `handle_internal_mcp_notifications_cancelled__internal_mcp_notifications_cancelled_post` |
| `POST` | `/_internal/mcp/notifications/cancelled/` | Handle Internal Mcp Notifications Cancelled | `handle_internal_mcp_notifications_cancelled__internal_mcp_notifications_cancelled__post` |
| `POST` | `/_internal/mcp/notifications/initialized` | Handle Internal Mcp Notifications Initialized | `handle_internal_mcp_notifications_initialized__internal_mcp_notifications_initialized_post` |
| `POST` | `/_internal/mcp/notifications/initialized/` | Handle Internal Mcp Notifications Initialized | `handle_internal_mcp_notifications_initialized__internal_mcp_notifications_initialized__post` |
| `POST` | `/_internal/mcp/notifications/message` | Handle Internal Mcp Notifications Message | `handle_internal_mcp_notifications_message__internal_mcp_notifications_message_post` |
| `POST` | `/_internal/mcp/notifications/message/` | Handle Internal Mcp Notifications Message | `handle_internal_mcp_notifications_message__internal_mcp_notifications_message__post` |
| `POST` | `/_internal/mcp/prompts/get` | Handle Internal Mcp Prompts Get | `handle_internal_mcp_prompts_get__internal_mcp_prompts_get_post` |
| `POST` | `/_internal/mcp/prompts/get/` | Handle Internal Mcp Prompts Get | `handle_internal_mcp_prompts_get__internal_mcp_prompts_get__post` |
| `POST` | `/_internal/mcp/prompts/get/authz` | Handle Internal Mcp Prompts Get Authz | `handle_internal_mcp_prompts_get_authz__internal_mcp_prompts_get_authz_post` |
| `POST` | `/_internal/mcp/prompts/get/authz/` | Handle Internal Mcp Prompts Get Authz | `handle_internal_mcp_prompts_get_authz__internal_mcp_prompts_get_authz__post` |
| `POST` | `/_internal/mcp/prompts/list` | Handle Internal Mcp Prompts List | `handle_internal_mcp_prompts_list__internal_mcp_prompts_list_post` |
| `POST` | `/_internal/mcp/prompts/list/` | Handle Internal Mcp Prompts List | `handle_internal_mcp_prompts_list__internal_mcp_prompts_list__post` |
| `POST` | `/_internal/mcp/prompts/list/authz` | Handle Internal Mcp Prompts List Authz | `handle_internal_mcp_prompts_list_authz__internal_mcp_prompts_list_authz_post` |
| `POST` | `/_internal/mcp/prompts/list/authz/` | Handle Internal Mcp Prompts List Authz | `handle_internal_mcp_prompts_list_authz__internal_mcp_prompts_list_authz__post` |
| `POST` | `/_internal/mcp/resources/list` | Handle Internal Mcp Resources List | `handle_internal_mcp_resources_list__internal_mcp_resources_list_post` |
| `POST` | `/_internal/mcp/resources/list/` | Handle Internal Mcp Resources List | `handle_internal_mcp_resources_list__internal_mcp_resources_list__post` |
| `POST` | `/_internal/mcp/resources/list/authz` | Handle Internal Mcp Resources List Authz | `handle_internal_mcp_resources_list_authz__internal_mcp_resources_list_authz_post` |
| `POST` | `/_internal/mcp/resources/list/authz/` | Handle Internal Mcp Resources List Authz | `handle_internal_mcp_resources_list_authz__internal_mcp_resources_list_authz__post` |
| `POST` | `/_internal/mcp/resources/read` | Handle Internal Mcp Resources Read | `handle_internal_mcp_resources_read__internal_mcp_resources_read_post` |
| `POST` | `/_internal/mcp/resources/read/` | Handle Internal Mcp Resources Read | `handle_internal_mcp_resources_read__internal_mcp_resources_read__post` |
| `POST` | `/_internal/mcp/resources/read/authz` | Handle Internal Mcp Resources Read Authz | `handle_internal_mcp_resources_read_authz__internal_mcp_resources_read_authz_post` |
| `POST` | `/_internal/mcp/resources/read/authz/` | Handle Internal Mcp Resources Read Authz | `handle_internal_mcp_resources_read_authz__internal_mcp_resources_read_authz__post` |
| `POST` | `/_internal/mcp/resources/subscribe` | Handle Internal Mcp Resources Subscribe | `handle_internal_mcp_resources_subscribe__internal_mcp_resources_subscribe_post` |
| `POST` | `/_internal/mcp/resources/subscribe/` | Handle Internal Mcp Resources Subscribe | `handle_internal_mcp_resources_subscribe__internal_mcp_resources_subscribe__post` |
| `POST` | `/_internal/mcp/resources/templates/list` | Handle Internal Mcp Resource Templates List | `handle_internal_mcp_resource_templates_list__internal_mcp_resources_templates_list_post` |
| `POST` | `/_internal/mcp/resources/templates/list/` | Handle Internal Mcp Resource Templates List | `handle_internal_mcp_resource_templates_list__internal_mcp_resources_templates_list__post` |
| `POST` | `/_internal/mcp/resources/templates/list/authz` | Handle Internal Mcp Resource Templates List Authz | `handle_internal_mcp_resource_templates_list_authz__internal_mcp_resources_templates_list_authz_post` |
| `POST` | `/_internal/mcp/resources/templates/list/authz/` | Handle Internal Mcp Resource Templates List Authz | `handle_internal_mcp_resource_templates_list_authz__internal_mcp_resources_templates_list_authz__post` |
| `POST` | `/_internal/mcp/resources/unsubscribe` | Handle Internal Mcp Resources Unsubscribe | `handle_internal_mcp_resources_unsubscribe__internal_mcp_resources_unsubscribe_post` |
| `POST` | `/_internal/mcp/resources/unsubscribe/` | Handle Internal Mcp Resources Unsubscribe | `handle_internal_mcp_resources_unsubscribe__internal_mcp_resources_unsubscribe__post` |
| `POST` | `/_internal/mcp/roots/list` | Handle Internal Mcp Roots List | `handle_internal_mcp_roots_list__internal_mcp_roots_list_post` |
| `POST` | `/_internal/mcp/roots/list/` | Handle Internal Mcp Roots List | `handle_internal_mcp_roots_list__internal_mcp_roots_list__post` |
| `POST` | `/_internal/mcp/rpc` | Handle Internal Mcp Rpc | `handle_internal_mcp_rpc__internal_mcp_rpc_post` |
| `POST` | `/_internal/mcp/rpc/` | Handle Internal Mcp Rpc | `handle_internal_mcp_rpc__internal_mcp_rpc__post` |
| `POST` | `/_internal/mcp/sampling/createMessage` | Handle Internal Mcp Sampling Create Message | `handle_internal_mcp_sampling_create_message__internal_mcp_sampling_createMessage_post` |
| `POST` | `/_internal/mcp/sampling/createMessage/` | Handle Internal Mcp Sampling Create Message | `handle_internal_mcp_sampling_create_message__internal_mcp_sampling_createMessage__post` |
| `DELETE` | `/_internal/mcp/session` | Handle Internal Mcp Session Delete | `handle_internal_mcp_session_delete__internal_mcp_session_delete` |
| `DELETE` | `/_internal/mcp/session/` | Handle Internal Mcp Session Delete | `handle_internal_mcp_session_delete__internal_mcp_session__delete` |
| `POST` | `/_internal/mcp/tools/call` | Handle Internal Mcp Tools Call | `handle_internal_mcp_tools_call__internal_mcp_tools_call_post` |
| `POST` | `/_internal/mcp/tools/call/` | Handle Internal Mcp Tools Call | `handle_internal_mcp_tools_call__internal_mcp_tools_call__post` |
| `POST` | `/_internal/mcp/tools/call/metric` | Handle Internal Mcp Tools Call Metric | `handle_internal_mcp_tools_call_metric__internal_mcp_tools_call_metric_post` |
| `POST` | `/_internal/mcp/tools/call/metric/` | Handle Internal Mcp Tools Call Metric | `handle_internal_mcp_tools_call_metric__internal_mcp_tools_call_metric__post` |
| `POST` | `/_internal/mcp/tools/call/resolve` | Handle Internal Mcp Tools Call Resolve | `handle_internal_mcp_tools_call_resolve__internal_mcp_tools_call_resolve_post` |
| `POST` | `/_internal/mcp/tools/call/resolve/` | Handle Internal Mcp Tools Call Resolve | `handle_internal_mcp_tools_call_resolve__internal_mcp_tools_call_resolve__post` |
| `POST` | `/_internal/mcp/tools/list` | Handle Internal Mcp Tools List | `handle_internal_mcp_tools_list__internal_mcp_tools_list_post` |
| `POST` | `/_internal/mcp/tools/list/` | Handle Internal Mcp Tools List | `handle_internal_mcp_tools_list__internal_mcp_tools_list__post` |
| `POST` | `/_internal/mcp/tools/list/authz` | Handle Internal Mcp Tools List Authz | `handle_internal_mcp_tools_list_authz__internal_mcp_tools_list_authz_post` |
| `POST` | `/_internal/mcp/tools/list/authz/` | Handle Internal Mcp Tools List Authz | `handle_internal_mcp_tools_list_authz__internal_mcp_tools_list_authz__post` |
| `POST` | `/logging/setLevel` | Set Log Level | `set_log_level_logging_setLevel_post` |
| `POST` | `/message` | Utility Message Endpoint | `utility_message_endpoint_message_post` |
| `POST` | `/rpc` | Handle Rpc | `handle_rpc_rpc_post` |
| `POST` | `/rpc/` | Handle Rpc | `handle_rpc_rpc__post` |
| `GET` | `/sse` | Utility Sse Endpoint | `utility_sse_endpoint_sse_get` |

### well-known

| Method | Path | Purpose | Operation ID |
| --- | --- | --- | --- |
| `GET` | `/.well-known/oauth-protected-resource` | Get Oauth Protected Resource | `get_oauth_protected_resource__well_known_oauth_protected_resource_get` |
| `GET` | `/.well-known/oauth-protected-resource/{path}` | Get Oauth Protected Resource Rfc9728 | `get_oauth_protected_resource_rfc9728__well_known_oauth_protected_resource__path__get` |
| `GET` | `/admin/well-known` | Get Well Known Status | `get_well_known_status_admin_well_known_get` |

## Local ContextForge Operation Recipes

### Register A Local Stdio MCP Service

1. Create `server-instances/<service-slug>/` with the backend command,
   sanitized `.env.example`, ignored `.env`, and a README or manifest.
2. Expose missing transports with `mcpgateway.translate`, for example:
   `python -m mcpgateway.translate --stdio ... --expose-sse --expose-streamable-http`.
3. Probe the direct bridge `/sse` and `/mcp` endpoints.
4. `POST /gateways` with `transport` matching the bridge endpoint being
   registered.
5. Confirm `GET /gateways/{gateway_id}` and `GET /tools?gateway_id=...` show
   discovered tools.
6. `POST /servers` with `associated_tools` set to the discovered tool IDs.
7. Probe `/servers/{server_id}/mcp/` and `/servers/{server_id}/sse`.

### Register A Native Remote MCP Service

1. Document the remote endpoint under `server-instances/<service-slug>/`.
2. Probe the remote endpoint if credentials allow.
3. `POST /gateways` with the native URL and `transport` (`SSE` or
   `STREAMABLEHTTP`).
4. Let ContextForge discover tools.
5. `POST /servers` or `PUT /servers/{server_id}` to expose the resulting tools.
6. Verify virtual MCP transport behavior.

### Replace An Existing Gateway

1. Read current state with `GET /gateways/{gateway_id}`, `GET /tools`, and
   `GET /servers`.
2. Prefer `PUT /gateways/{gateway_id}` for supported metadata/auth/visibility
   changes.
3. Use `POST /gateways/{gateway_id}/tools/refresh` after URL/auth/transport
   changes and verify tool URLs and schemas.
4. If tool ownership, transport class, or discovery state cannot be repaired by
   update plus refresh, delete and recreate the gateway through the API, then
   update virtual server associations.
5. Never repair by direct DB updates unless the user explicitly authorizes an
   emergency repair after API paths fail.

### Change Visibility

Use the entity API that owns the object:

- `PUT /gateways/{gateway_id}` for gateway visibility.
- `PUT /servers/{server_id}` for virtual server visibility.
- `PUT /tools/{tool_id}` for tool visibility only.
- `PUT /resources/{resource_id}` for resource visibility.
- `PUT /prompts/{prompt_id}` for prompt visibility.

For gateway-discovered tools, understand that gateway visibility propagation is
handled by gateway service logic and refresh/update behavior. Verify the child
tool records after changing gateway visibility.

### Token Creation

Use `/tokens`, not a handcrafted JWT command, when the token must be cataloged,
revocable, scoped, or visible in the Admin UI. Handcrafted utility JWTs are only
for explicitly intended diagnostics where catalog membership and revocation are
not required.

## Verification Checklist

Before claiming a ContextForge registration or API mutation is complete:

- The request used JSON API/Admin UI behavior, not direct DB mutation.
- The response status and body were checked.
- `GET` readback confirms the intended gateway/server/tool/resource/prompt/token
  state.
- Gateway-discovered tools exist and point at the intended upstream URL.
- Virtual server associations include the intended tool/resource/prompt IDs.
- Direct upstream `/sse` and `/mcp` probes pass when a local bridge exists.
- Virtual `/servers/{server_id}/sse` and `/servers/{server_id}/mcp/` probes pass.
- Secrets remain only in ignored local env/config files.
