# ContextForge Project Init And Per-Project Serena Handoff

Status timestamp: 2026-05-29 13:40 America/Chicago  
Repository: `/home/dgk/workspace/context-portal`  
Branch observed: `agent/contextforge-bootstrap`

This artifact is a restart record for a new Codex agent. It describes the current implementation, live verification evidence, unresolved decisions, risks, and recommended next trajectories for the ContextForge-owned project initialization and per-project Serena integration.

## User Intent

The governing intent is operational, not explanatory:

- Serena must be exposed to Codex through ContextForge, not direct Serena stdio.
- Serena must never treat `/`, `/home/dgk`, or `/home/dgk/workspace` as the project.
- Project selection must be automatic from the actual project context.
- A single unrelated-project-shared Serena instance is not acceptable. Multiple Codex sessions in the same project may share one backend, but unrelated projects need separate project-pinned backends.
- The user values live probes over plausible explanations. Treat current filesystem, service state, ContextForge registry, Codex config, and runtime calls as authority.
- Do not claim completion from config presence alone. The actual exposed Codex MCP path matters.

## Executive State

The plan has been substantially implemented and verified through current live probes.

Implemented:

- ContextForge prompt and resource for project initialization:
  - Prompt: `project_init_prompt`
  - Resource: `contextforge://context-portal/project-init/v1`
- ContextForge Serena-specific guidance:
  - Prompt: `serena_project_instance_guidance`
  - Resource: `contextforge://context-portal/serena-project-instance-guidance/v1`
  - Associated only to Serena-looking ContextForge virtual servers.
- Global Codex hooks in `/home/dgk/.codex/config.toml`:
  - `SessionStart`, matcher `startup`
  - `UserPromptSubmit` fallback
  - Both are currently trusted by Codex app-server hook metadata.
- Hook script:
  - `/home/dgk/workspace/context-portal/scripts/codex_project_init_hook.py`
  - Renders ContextForge `project_init_prompt` and injects it as `hookSpecificOutput.additionalContext`.
  - Stores idempotency state in ignored runtime state under `run/`.
  - Rejects root, home, workspace root, and symlink escapes after canonicalization.
  - Fails open if ContextForge is unavailable.
- Per-project Serena manager:
  - `/home/dgk/workspace/context-portal/scripts/manage_serena_project_instance.py`
  - Creates one ContextForge-owned Serena backend per canonical project root.
  - Creates `server-instances/serena-<slug>-<hash>/`.
  - Installs user systemd unit `contextforge-serena-<slug>-<hash>.service`.
  - Registers ContextForge gateway and project-specific virtual server.
  - Filters Serena `activate_project` at the ContextForge virtual server layer.
  - Writes project-local `.codex/config.toml` last.
  - Marks project `.env` complete only after runtime and registry probes pass.

Current live evidence shows:

- No global Codex `serena` server from `/home/dgk`.
- Project-local `serena` in `/home/dgk/workspace/context-portal`.
- ContextForge gateway and `contextforge-serena-context-portal.service` are active.
- Codex app-server can start a thread rooted at `context-portal`, list the project-local Serena tools, and call Serena through the app-server MCP path.
- App-server Serena tool list has 22 tools and no activate-project exposure.
- App-server `serena-context-portal-get-current-config` reports `Active project: context-portal` and `Language backend: LSP`.
- App-server `serena-context-portal-get-diagnostics-for-file` on `scripts/contextforge_mcp_wrapper.py` returns `{}`.

The largest remaining non-code policy gap is Codex project trust for newly initialized projects. Codex ignores project-local `.codex/config.toml` in untrusted projects until the project root is trusted. This is captured in `OPEN_QUESTIONS.md` as `oq-20260529-0001`.

Repository state is dirty and mostly reflects the broader ContextForge bootstrap effort, not only this handoff. This artifact itself is currently an untracked file:

```text
?? CONTEXTFORGE_SERENA_PROJECT_INIT_HANDOFF.md
```

## Implemented Files

### Shared project-init helpers

Path: `/home/dgk/workspace/context-portal/scripts/project_init_common.py`

Purpose:

- Defines project-init constants, env keys, prompt/resource names, prompt version, denied roots, and project markers.
- Computes deterministic per-project Serena identity.
- Detects canonical project roots.
- Parses and writes only whitelisted project `.env` keys.

Important constants:

```python
PROJECT_INIT_PROMPT_NAME = "project_init_prompt"
PROJECT_INIT_RESOURCE_URI = "contextforge://context-portal/project-init/v1"
SERENA_GUIDANCE_PROMPT_NAME = "serena_project_instance_guidance"
SERENA_GUIDANCE_RESOURCE_URI = "contextforge://context-portal/serena-project-instance-guidance/v1"
PROMPT_VERSION = "v1"
```

Project `.env` keys:

```env
CONTEXTFORGE_PROJECT_INIT_DIALOGUE_STATUS=unasked|asked|complete|disabled
CONTEXTFORGE_SERENA_DECISION=unasked|accepted|declined|disabled
CONTEXTFORGE_SERENA_PROVISION_STATUS=none|pending|created|failed|removed
CONTEXTFORGE_SERENA_INSTANCE_SLUG=serena-<slug>-<hash>
CONTEXTFORGE_SERENA_SERVER_NAME=serena_<slug>_<hash>_server
```

Deterministic identity:

- `<slug>` is normalized project basename.
- `<hash>` is first 12 hex chars of SHA-256 over `{uid}:{canonical_project_root}`.
- Instance slug: `serena-<slug>-<hash>`.
- ContextForge virtual server: `serena_<slug>_<hash>_server`.

Denied roots:

- `/`
- `/home/dgk`
- `/home/dgk/workspace`

Important behavior:

- `validate_project_root(..., require_workspace=True)` refuses anything outside a safe `/home/dgk/workspace` child.
- `detect_project_root()` tries git root, marker root, then first workspace child, but never returns root/home/workspace root.
- `.env` write helper refuses unknown keys.

### Prompt/resource registration

Path: `/home/dgk/workspace/context-portal/scripts/register_project_init_prompt.py`

Purpose:

- Registers and refreshes ContextForge project-init and Serena guidance prompt/resource artifacts through ContextForge APIs only.
- Reuses auth/API helpers from `scripts/contextforge_mcp_wrapper.py`.
- Runs content-security preflight through ContextForge package services.
- Verifies project-init prompt rendering by `POST /prompts/{id}`.
- Associates Serena guidance only to virtual servers that look like Serena servers by name, tag, or description.

Important implementation detail:

- Live ContextForge rendering required Jinja-style `{{ variable }}` placeholders. Single-brace `{variable}` placeholders rendered literally and were rejected as insufficient.

Run:

```bash
/home/dgk/workspace/context-portal/.venv/bin/python \
  /home/dgk/workspace/context-portal/scripts/register_project_init_prompt.py
```

Expected successful output shape:

```text
registered project_init_prompt id=<id>
registered project_init_resource id=<id>
registered serena_project_instance_guidance id=<id>
registered serena guidance resource id=<id>
associated_serena_servers=<comma-separated names or <none>>
verified_render_at=<iso timestamp>
```

### Codex project-init hook

Path: `/home/dgk/workspace/context-portal/scripts/codex_project_init_hook.py`

Purpose:

- Reads Codex hook JSON from stdin.
- Handles only `SessionStart` and `UserPromptSubmit`.
- Detects canonical project root from `cwd`.
- Renders `project_init_prompt` from live ContextForge and emits only JSON with `hookSpecificOutput.additionalContext`.
- Suppresses duplicate injection by session, canonical project root hash, and prompt version.
- Fails open on any error.

State:

- Idempotency state: `/home/dgk/workspace/context-portal/run/project-init-hook-state.local.json`
- Lock: `/home/dgk/workspace/context-portal/run/project-init-hook-state.local.lock`
- Failure log: `/home/dgk/workspace/context-portal/run/project-init-hook.local.log`

Injection policy:

- Safe roots under `/home/dgk/workspace` auto-inject when `.env` state is missing, `unasked`, or `asked`.
- Outside `/home/dgk/workspace`, injection only occurs if `.env` exists and project-init status is `unasked` or `asked`.
- `complete` and `disabled` suppress injection.
- ContextForge outage exits zero with no partial prompt.

Stdout policy:

- No diagnostic text on stdout.
- On injection, stdout is compact JSON:

```json
{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"..."}}
```

### Serena project instance manager

Path: `/home/dgk/workspace/context-portal/scripts/manage_serena_project_instance.py`

Purpose:

- Transactionally create, refresh, inspect, and remove a per-project Serena backend owned by ContextForge.

Commands:

```bash
/home/dgk/workspace/context-portal/.venv/bin/python \
  /home/dgk/workspace/context-portal/scripts/manage_serena_project_instance.py identity \
  --project-root /home/dgk/workspace/<project>

/home/dgk/workspace/context-portal/.venv/bin/python \
  /home/dgk/workspace/context-portal/scripts/manage_serena_project_instance.py status \
  --project-root /home/dgk/workspace/<project>

/home/dgk/workspace/context-portal/.venv/bin/python \
  /home/dgk/workspace/context-portal/scripts/manage_serena_project_instance.py create \
  --project-root /home/dgk/workspace/<project> \
  --require-workspace

/home/dgk/workspace/context-portal/.venv/bin/python \
  /home/dgk/workspace/context-portal/scripts/manage_serena_project_instance.py remove \
  --project-root /home/dgk/workspace/<project> \
  --yes --delete-instance-dir --delete-contextforge-records
```

Creation order:

1. Validate canonical project root.
2. Derive deterministic identity.
3. Take lock: `/home/dgk/workspace/context-portal/run/serena-instance-manager.local.lock`.
4. Reserve port from `9110-9199`, checking existing manifests and live listeners.
5. Create `/home/dgk/workspace/context-portal/server-instances/<instance>/`.
6. Write executable `run-server.sh`.
7. Write initial `instance.json`.
8. Write user systemd unit under `/home/dgk/.config/systemd/user/`.
9. `systemctl --user daemon-reload`.
10. Enable and restart unit.
11. Verify unit active and port open.
12. Register/refresh ContextForge gateway.
13. Refresh gateway tools.
14. Register/refresh ContextForge virtual server.
15. Verify virtual server excludes `activate_project` and includes `get_current_config`.
16. Write final manifest with ContextForge ids.
17. Merge project-local `.codex/config.toml`.
18. Write project `.env` status as created/complete.

Systemd details:

- Unit name: `contextforge-serena-<slug>-<hash>.service`
- `WantedBy=contextforge.target`
- Generated `After=network.target contextforge.service`
- `ExecStart=<instance-dir>/run-server.sh`
- `WorkingDirectory=/home/dgk/workspace/context-portal`
- PATH includes:
  - `/home/dgk/.nvm/versions/node/v24.12.0/bin`
  - `/home/dgk/.local/bin`
  - system paths

The explicit PATH is required. Disposable provisioning initially failed because user systemd could not find `serena`; this was fixed by adding `/home/dgk/.local/bin` and the current Node path.

Potential hardening issue: the live gateway unit is `contextforge-gateway.service`, while the generated per-project Serena units currently specify `After=network.target contextforge.service`. This did not block disposable verification because the units are enabled under `contextforge.target` and the gateway was already running, but the ordering name should probably be corrected or made explicit in a follow-up.

Serena backend launch shape:

```bash
serena start-mcp-server \
  --transport streamable-http \
  --host 127.0.0.1 \
  --port <port> \
  --context codex \
  --project "<canonical project root>" \
  --open-web-dashboard false
```

Tool policy:

- ContextForge virtual server excludes only original Serena tool name `activate_project`.
- `get_current_config` must remain present.
- Serena `single_project` mode is not used in v1 because an equivalent replacement for `get_current_config` was not proven.
- Source-level exclusion is recorded as not applied in manifests:

```json
"source_level_exclusion": "not_applied_v1_contextforge_virtual_filter_is_authoritative"
```

Project-local Codex config behavior:

- Local alias remains `serena`.
- Upstream virtual server is project-specific.
- Managed block includes owner marker:

```toml
# contextforge-project-init-owner = "<server_name>"
[mcp_servers.serena]
command = "/home/dgk/workspace/context-portal/.venv/bin/python"
args = ["/home/dgk/workspace/context-portal/scripts/contextforge_mcp_wrapper.py", "<server_name>"]
cwd = "/home/dgk/workspace/context-portal"
startup_timeout_ms = 60000
tool_timeout_ms = 120000
```

If a project already has unmanaged `[mcp_servers.serena]`, manager refuses unless `--replace-existing-serena-config` is passed.

## Current Global Codex Hook Configuration

File: `/home/dgk/.codex/config.toml`

The global hook entries were added to user config:

```toml
[hooks]

[[hooks.SessionStart]]
matcher = "startup"

[[hooks.SessionStart.hooks]]
type = "command"
command = "/home/dgk/workspace/context-portal/.venv/bin/python /home/dgk/workspace/context-portal/scripts/codex_project_init_hook.py"
timeout = 10
statusMessage = "Checking ContextForge project init"

[[hooks.UserPromptSubmit]]

[[hooks.UserPromptSubmit.hooks]]
type = "command"
command = "/home/dgk/workspace/context-portal/.venv/bin/python /home/dgk/workspace/context-portal/scripts/codex_project_init_hook.py"
timeout = 10
statusMessage = "Checking ContextForge project init"
```

The hooks were initially `untrusted`. Live app-server `hooks/list` returned these hashes:

```text
session_start hash: sha256:9baa8d5c96090e841dcf923d0791064ed50a21c2bb4ccabedb77171cab4ea76e
user_prompt_submit hash: sha256:0bbe16750e78137f70cf0a83ad95420a36dcc29d95501464f9227c2097fa3434
```

Trusted state was added:

```toml
[hooks.state."/home/dgk/.codex/config.toml:session_start:0:0"]
trusted_hash = "sha256:9baa8d5c96090e841dcf923d0791064ed50a21c2bb4ccabedb77171cab4ea76e"

[hooks.state."/home/dgk/.codex/config.toml:user_prompt_submit:0:0"]
trusted_hash = "sha256:0bbe16750e78137f70cf0a83ad95420a36dcc29d95501464f9227c2097fa3434"
```

After this, app-server `hooks/list` reported both hooks as `trustStatus: trusted`.

## Current Context-Portal Serena Runtime

Current project-local Codex MCP lookup from `/home/dgk/workspace/context-portal`:

```text
serena
  enabled: true
  transport: stdio
  command: /home/dgk/workspace/context-portal/.venv/bin/python
  args: /home/dgk/workspace/context-portal/scripts/contextforge_mcp_wrapper.py serena_context_portal_server
  cwd: /home/dgk/workspace/context-portal
  env: -
```

Current global lookup from `/home/dgk`:

```text
Error: No MCP server named 'serena' found.
```

Current user units:

- `contextforge-gateway.service` is active.
- `contextforge-serena-context-portal.service` is active.

Observed `contextforge-serena-context-portal.service` process shape:

```text
/home/dgk/.local/bin/serena start-mcp-server \
  --transport streamable-http \
  --host 127.0.0.1 \
  --port 9108 \
  --context codex \
  --project /home/dgk/workspace/context-portal \
  --open-web-dashboard false
```

This process also has Pyright LSP child processes running through `uvx` and Node.

## Live Verification Completed

### Python syntax

`py_compile` passed for the new scripts:

- `scripts/project_init_common.py`
- `scripts/register_project_init_prompt.py`
- `scripts/codex_project_init_hook.py`
- `scripts/manage_serena_project_instance.py`

### ContextForge registry

Live registry check showed:

```json
{
  "project_prompt_count": 1,
  "project_resource_count": 1,
  "serena_guidance_prompt_count": 1,
  "serena_guidance_resource_count": 1,
  "serena_server_id": "c14f033a68f34b9ba26870bfede42cbf",
  "serena_tool_count": 22,
  "has_activate_project": false,
  "has_get_current_config": true
}
```

Interpretation:

- Project-init prompt/resource are present.
- Serena guidance prompt/resource are present.
- Current `serena_context_portal_server` virtual server has 22 tools.
- `activate_project` is not exposed by the virtual server.
- `get_current_config` remains exposed.

### Hook direct tests

Synthetic hook payloads were tested against `scripts/codex_project_init_hook.py`.

Verified:

- `SessionStart` for `/home/dgk/workspace/context-portal` emitted valid JSON with additional context and substituted project root.
- `UserPromptSubmit` with same session/project/version suppressed after SessionStart, proving idempotency.
- Denied roots emitted nothing:
  - `/`
  - `/home/dgk`
  - `/home/dgk/workspace`
- Symlink escape emitted nothing:
  - `/home/dgk/workspace/contextforge-symlink-escape-test -> /tmp`
- ContextForge outage emitted nothing and exited zero:
  - `CONTEXTFORGE_BASE_URL=http://127.0.0.1:1`
- Outside-workspace explicit opt-in worked when a `.env` file existed with active init state.

### Disposable concurrent Serena provisioning

Two disposable workspace projects were created and provisioned concurrently:

- `/home/dgk/workspace/cf-serena-provision-a-EzzTwu`
- `/home/dgk/workspace/cf-serena-provision-b-Nqw0af`

Successful results:

Project A:

```text
instance_slug = serena-cf-serena-provision-a-ezztwu-11dab4b956fa
server_name   = serena_cf_serena_provision_a_ezztwu_11dab4b956fa_server
port          = 9111
gateway_id    = 73dde95db75b4672b38593cb410ecefa
server_id     = 9677292571414f5690dbf505a4f53ece
tool_count    = 22
blocked_tools = ["activate_project"]
```

Project B:

```text
instance_slug = serena-cf-serena-provision-b-nqw0af-d67373db2d40
server_name   = serena_cf_serena_provision_b_nqw0af_d67373db2d40_server
port          = 9112
gateway_id    = 303a1afa32574d1ea783969d913f5f0a
server_id     = 53f46cdadc7547e49ed9cd8a2bd9e2e0
tool_count    = 22
blocked_tools = ["activate_project"]
```

For both projects, wrapper MCP calls through ContextForge verified:

- Tool count: 22.
- No exposed activate-project tool.
- `get-current-config` reported active project as the disposable project basename.
- Language backend: LSP.
- `get-diagnostics-for-file` on `main.py` returned `{}`.

Rollback completed:

- Test units stopped/disabled/removed.
- ContextForge test gateway/server records deleted.
- Test instance directories deleted.
- Disposable project directories removed.
- Follow-up checks showed no `9111`/`9112` listeners and no stale test records/units.

### Codex project-local association in test projects

Important finding:

- `codex mcp get serena` from disposable projects failed before Codex project trust.
- With a temporary trusted `CODEX_HOME`, `codex mcp get serena` from each disposable project resolved to that project-specific virtual server.

Interpretation:

- The per-project config and deterministic association work.
- New projects need Codex trust before project-local `.codex/config.toml` is loaded.
- This is a Codex security/trust gate, not a ContextForge registry failure.

### App-server actual Codex MCP path

A real `codex app-server --listen stdio://` probe was run from `/home/dgk/workspace/context-portal`.

Protocol shape:

1. `initialize`
2. `initialized`
3. `hooks/list`
4. `thread/start` with:

```json
{
  "cwd": "/home/dgk/workspace/context-portal",
  "ephemeral": true,
  "approvalPolicy": "never",
  "sandbox": "danger-full-access"
}
```

5. `mcpServerStatus/list` with:

```json
{
  "threadId": "<thread id>",
  "detail": "toolsAndAuthOnly"
}
```

6. `mcpServer/tool/call` for Serena.

Evidence:

- `thread/start` returned cwd `/home/dgk/workspace/context-portal`.
- `runtimeWorkspaceRoots` contained `/home/dgk/workspace/context-portal`.
- `instructionSources` contained `/home/dgk/workspace/context-portal/AGENTS.md`.
- `hooks/list` reported the two project-init hooks as trusted.
- `mcpServerStatus/list` returned a `serena` server.
- Serena server exposed 22 tools.
- No tool name contained `activate`.
- Exposed get-config tool:
  - `serena-context-portal-get-current-config`
- Exposed diagnostics tool:
  - `serena-context-portal-get-diagnostics-for-file`

`mcpServer/tool/call` result for `serena-context-portal-get-current-config` contained:

```text
Current configuration:
Serena version: 1.5.3
Active project: context-portal
Language backend: LSP (global default: LSP)
Active context: codex
```

The same output listed `activate_project` as active inside Serena's own upstream configuration. This is expected and not a violation by itself: direct upstream Serena still has the tool internally, but the ContextForge virtual server and Codex-exposed app-server tool list do not expose it. The security boundary here is ContextForge virtual server filtering.

`mcpServer/tool/call` result for `serena-context-portal-get-diagnostics-for-file` with:

```json
{
  "relative_path": "scripts/contextforge_mcp_wrapper.py"
}
```

returned:

```json
{}
```

Interpretation:

- This is the strongest current evidence that Codex can see and call the actual project-local ContextForge-backed Serena tool path after reload/trust.
- The current assistant tool namespace may still not show `mcp__serena` because this running conversation started before reload. The app-server probe is a closer runtime proof than manual wrapper calls.

## Governance Ledger State

Relevant decision:

- `DECISIONS.md` entry `dec-20260529-0047`
  - Accepted project initialization through ContextForge-owned hook and per-project Serena manager.
  - Records disposable concurrent provisioning verification.
  - Records Codex project-local trust caveat.

Relevant open question:

- `OPEN_QUESTIONS.md` entry `oq-20260529-0001`
  - Should project-init explicitly manage Codex project trust?
  - Current fact: Codex ignores project-local `.codex/config.toml` until project root is trusted in `/home/dgk/.codex/config.toml`.
  - Policy fork:
    - Prompt the user to trust project manually.
    - Or allow accepted Serena provisioning to add trust automatically.
  - Risk: automatic trust broadens security surface because project-local hooks and exec policies become loadable, not just MCP entries.

## Design Rationale

### Why one Serena per project

Serena has project state and project activation semantics. Sharing one backend across unrelated projects would depend on mutable session/project activation and would reintroduce exactly the failure mode the user rejected: Serena could treat home, root, or the wrong project as current.

The current design instead pins project root in the backend launch command:

```bash
--project "<canonical project root>"
```

Then ContextForge removes `activate_project` from the Codex-exposed virtual server. This makes project identity an operator/runtime concern rather than an LLM-callable tool.

### Why local alias is still `serena`

Codex users and agents can use a stable per-project alias:

```toml
[mcp_servers.serena]
```

The material identity is not the alias. It is:

- project-local config path,
- wrapper argument pointing at project-specific ContextForge virtual server,
- systemd unit,
- `server-instances/<instance>/instance.json`,
- ContextForge gateway/server records,
- pinned backend command.

### Why ContextForge virtual filtering is authoritative

Direct upstream Serena still reports `activate_project` internally in `get_current_config`. The contract is not that upstream Serena was modified to forget the tool. The contract is that Codex reaches Serena only through the ContextForge virtual server, and that virtual server excludes project switching.

The current evidence supports this:

- ContextForge virtual server has 22 tools and `has_activate_project=false`.
- Codex app-server `mcpServerStatus/list` for `serena` has 22 tools and no activate substring.
- The callable app-server tool names do not include activate.

### Why source-level exclusion was not used in v1

The plan said to attempt project/source-level exclusion if verified without losing `get_current_config`. That was not applied in v1. The manifest explicitly records:

```text
not_applied_v1_contextforge_virtual_filter_is_authoritative
```

Reason:

- `get_current_config` is needed as a verification surface.
- Virtual server filtering already blocks the Codex-exposed attack path.
- Changing Serena internals or modes risks losing the evidence path and introducing opaque behavior.

This is an opportunity for a future hardening pass, not a blocker for the current ContextForge-mediated design.

## Main Risks And Pitfalls

### Codex project trust is the main unresolved rollout question

New project-local `.codex/config.toml` is not sufficient unless Codex trusts the project root.

Pitfall:

- Provisioning can succeed fully from systemd and ContextForge perspectives.
- `codex mcp get serena` may still fail in that project if Codex does not trust the project-local config.

Mitigations:

- Keep `oq-20260529-0001` open until policy is chosen.
- Project-init prompt should explicitly tell the user when trust is required.
- If automatic trust is implemented, it should be explicit, auditable, and probably gated behind accepted Serena setup, not silent hook injection.
- Any trust writer must avoid trusting `/`, `$HOME`, `/home/dgk/workspace`, or symlink escapes.

### Current assistant session may not gain a new `mcp__serena` namespace

The current tool list of an already-running assistant session may not change just because config was fixed. The prior stale session behavior showed timeouts after backend restart.

Mitigations:

- Use app-server thread-level `mcpServerStatus/list` and `mcpServer/tool/call` to verify the actual Codex path without relying on the current model's fixed tool namespace.
- For final user-facing confidence, start a fresh Codex session/Desktop reload inside a trusted project and verify the exposed `mcp__serena` namespace if available to the model.

### App-server reload is not a public CLI feature

Prior investigation found internal app-server protocol methods such as:

- `config/mcpServer/reload`
- `mcpServerStatus/list`

But there is no known public `codex mcp reload`. A standalone `codex app-server daemon start` failed because this environment is npm-managed / desktop-managed, not a standalone daemon path.

Mitigations:

- Prefer fresh session or Desktop reload as the reliable reload boundary.
- Use app-server stdio probes for precise diagnostics.
- Do not kill random MCP child processes unless testing reload behavior deliberately and with clear risk.

### Direct upstream Serena still has `activate_project`

This is expected in current design but can confuse reviewers because `get_current_config` says `activate_project` is active upstream.

Mitigation:

- Always distinguish upstream tool inventory from ContextForge virtual server inventory and Codex app-server exposed inventory.
- Completion evidence should quote the app-server tool list, not just upstream `get_current_config`.

### Systemd PATH is brittle

The first concurrent disposable provisioning attempt failed because the user systemd environment did not find `serena`.

Current mitigation:

- Unit includes explicit PATH with `/home/dgk/.local/bin` and `/home/dgk/.nvm/versions/node/v24.12.0/bin`.

Residual risk:

- If Node moves or Serena install path changes, new units may fail.

Possible future mitigation:

- Resolve `serena`, `uv`, and Node paths dynamically at provisioning time and record them in `instance.json`.
- Add a preflight that checks `serena --help` under the exact systemd PATH before writing the unit.

### Systemd ordering names are inconsistent

Generated per-project Serena units currently say:

```ini
After=network.target contextforge.service
```

The live gateway unit is:

```text
contextforge-gateway.service
```

This did not break the verified disposable runs, but it is an accuracy and startup-ordering issue. A follow-up should decide whether units should order after `contextforge-gateway.service`, `contextforge.target`, or both.

### Port range exhaustion or stale manifests

Ports are drawn from `9110-9199`.

Current mitigation:

- Manager checks existing Serena manifests and live listeners.

Residual risk:

- Stale manifests could reserve ports unnecessarily.
- Non-Serena services in the range can still block ports.

Future mitigation:

- Add `repair` or `gc` command that reconciles manifests, units, ContextForge records, and listeners.

### Partial failure after systemd but before `.env`

The manager writes `.env` created/complete only at the end. This is correct, but partial artifacts can remain if registration fails after the unit starts.

Mitigation:

- `status` command surfaces manifest and unit state.
- `remove --delete-instance-dir --delete-contextforge-records` can clean up.

Future mitigation:

- Add explicit transactional rollback on create failure.
- Add `repair` to resume from partial states.

### Project `.env` is advisory

The hook and manager intentionally treat `.env` as state, not truth.

Mitigation:

- Reconcile against systemd, ContextForge registry, manifests, project-local Codex config, and live MCP calls before claiming success.

### Content security sanitizer is conservative and may mutate prose

`register_project_init_prompt.py` sanitizes patterns that ContextForge content security may flag.

Risk:

- Documentation/prose could be modified unexpectedly.

Mitigation:

- Prompt render verification catches unresolved variables, but not every semantic mutation.
- Review prompt/resource readback after edits.

## Opportunities

### Add an explicit trust workflow

The next high-value feature is a safe, explicit project trust flow.

Recommended behavior:

- Detect when project-local `.codex/config.toml` exists but Codex does not load it.
- Present a precise explanation in project-init prompt.
- Offer an explicit command/action to trust only the canonical project root.
- Log trust changes in the project and/or governance ledger.

Do not silently trust projects merely because they are under `/home/dgk/workspace`.

### Add a `verify` command to the Serena manager

The manager has `identity`, `status`, `create`, and `remove`.

A `verify` command should check:

- canonical root not denied,
- manifest exists and matches deterministic identity,
- unit active,
- port open,
- ContextForge gateway exists and points at port,
- ContextForge virtual server exists,
- virtual server excludes `activate_project`,
- virtual server includes `get_current_config` and diagnostics/symbol tools,
- project `.codex/config.toml` has managed alias,
- `codex mcp get serena` succeeds when project is trusted,
- wrapper/app-server MCP call returns expected active project and LSP result.

### Add `repair` and `gc`

Useful future commands:

- `repair`: resume or correct partial provisioning.
- `gc`: find stale Serena manifests, stale units, stale ContextForge records, and stale ports.

### Parameterize runtime paths

Current unit PATH includes specific local paths. A future hardening pass could:

- Resolve tool paths at create time.
- Store exact resolved paths in `instance.json`.
- Use absolute `ExecStart` dependencies where possible.

### Add tests for script-level behavior

Current testing was live/probe based. Add repo tests for:

- project root detection,
- denied roots,
- symlink escapes,
- `.env` parsing/writing,
- deterministic identity,
- Codex TOML merge behavior,
- unmanaged Serena config refusal.

Do not replace live probes with unit tests; add tests as regression protection.

## Recommended Next Agent Trajectory

1. Re-read current live state before acting.

   Commands:

   ```bash
   git status --short --branch
   codex mcp get serena
   (cd /home/dgk/workspace/context-portal && codex mcp get serena)
   systemctl --user --no-pager --plain status contextforge-gateway.service contextforge-serena-context-portal.service
   ```

2. Verify ContextForge registry again.

   Use the existing ContextForge auth helpers. Confirm:

   - `project_init_prompt` exists once.
   - `contextforge://context-portal/project-init/v1` exists once.
   - `serena_project_instance_guidance` exists once.
   - `contextforge://context-portal/serena-project-instance-guidance/v1` exists once.
   - `serena_context_portal_server` has 22 tools, no `activate_project`, and `get_current_config`.

3. Re-run app-server thread-level probe.

   The important current proof is:

   - thread rooted at `/home/dgk/workspace/context-portal`,
   - `mcpServerStatus/list` contains `serena`,
   - `serena` has 22 tools,
   - no activate tool is exposed,
   - `mcpServer/tool/call` for `serena-context-portal-get-current-config` returns `Active project: context-portal`,
   - diagnostics call returns `{}`.

4. Decide or ask about Codex project trust.

   This is the key policy fork. Do not implement silent broad trust.

5. If implementing more code, prefer:

   - `verify` command for `manage_serena_project_instance.py`,
   - explicit trust workflow,
   - transactional rollback/repair,
   - tests.

6. If preparing final completion, ensure evidence covers all required invariants:

   - Serena is not globally available from `/home/dgk`.
   - Serena is project-local for `context-portal`.
   - ContextForge virtual server excludes `activate_project`.
   - Actual Codex-exposed Serena tools work after reload/restart.
   - Active project is `context-portal`, not home/root.
   - LSP result works through actual exposed tool path.

## Exact App-Server Probe Skeleton

The following Python shape worked for app-server stdio probes:

```python
import json
import select
import subprocess
import time

cwd = "/home/dgk/workspace/context-portal"
proc = subprocess.Popen(
    ["codex", "app-server", "--listen", "stdio://"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    cwd=cwd,
)

next_id = 0

def send(method, params=None, notify=False):
    global next_id
    obj = {"method": method}
    if params is not None:
        obj["params"] = params
    if not notify:
        obj["id"] = next_id
        next_id += 1
    proc.stdin.write(json.dumps(obj, separators=(",", ":")) + "\n")
    proc.stdin.flush()
    return obj.get("id")

def read(expect_id, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        r, _, _ = select.select([proc.stdout], [], [], deadline - time.time())
        if not r:
            break
        msg = json.loads(proc.stdout.readline())
        if msg.get("id") == expect_id:
            return msg
    raise TimeoutError(f"missing response {expect_id}")

def call(method, params=None, timeout=30):
    request_id = send(method, params)
    return read(request_id, timeout)

call(
    "initialize",
    {
        "clientInfo": {"name": "serena-status-probe", "title": None, "version": "0.1.0"},
        "capabilities": {"experimentalApi": True},
    },
    10,
)
send("initialized", notify=True)

thread = call(
    "thread/start",
    {
        "cwd": cwd,
        "ephemeral": True,
        "approvalPolicy": "never",
        "sandbox": "danger-full-access",
    },
    20,
)
thread_id = thread["result"]["thread"]["id"]

status = call(
    "mcpServerStatus/list",
    {"threadId": thread_id, "detail": "toolsAndAuthOnly"},
    45,
)

diag = call(
    "mcpServer/tool/call",
    {
        "threadId": thread_id,
        "server": "serena",
        "tool": "serena-context-portal-get-diagnostics-for-file",
        "arguments": {"relative_path": "scripts/contextforge_mcp_wrapper.py"},
    },
    60,
)
```

Remember to terminate the process after the probe.

## Current Completion Assessment

As of this artifact, the current evidence is strong enough to say the implemented path works for the trusted `context-portal` project through the app-server MCP call path.

The broader project-init rollout is not fully closed because new arbitrary projects still encounter Codex project trust gating. That is an expected Codex behavior and a policy decision, not a failed ContextForge/Serena provisioning result.

For a new agent restarting the goal, do not start by redesigning. Start by verifying current live state, then choose the next trajectory:

- harden and document the trust workflow,
- add manager `verify`/`repair`,
- add regression tests,
- or run a fresh Desktop session test that exposes `mcp__serena` directly in the model tool namespace.
