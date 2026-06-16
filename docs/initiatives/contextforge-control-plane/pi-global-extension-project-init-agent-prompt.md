# Pi Global Extension Project-Init Agent Prompt

Use the following prompt for an independent ContextForge/control-plane implementation agent.

```text
Work in the current ContextForge repository checkout. On this host, the
historical checkout path may still contain `context-portal`, but that is a
legacy path/runtime identifier and not the product name.

You are an independent ContextForge/control-plane implementation agent. Research, plan, and implement Pi support for ContextForge-hosted MCP service activation.

Prime intention:
Make the user-global Pi coding agent, likely Pi 0.78.x, a first-class ContextForge project-init target client through a global Pi extension shim. Do NOT build this for the Pi instance localized to the noetic-pi project. The noetic-pi project may be useful only as read-only reference material if relevant; the target is the user-global Pi coding agent installation and its global extension system.

Important correction:
Pi does not have native MCP client config support equivalent to Codex's [mcp_servers.*] TOML workflow. Do not model Pi as if it supports project-local MCP server declarations. Pi's extension model is the integration surface. The deliverable should be a Pi extension-based integration and project-init equivalent, not a new Pi MCP server.

Current reality:
- Codex supports project/global MCP server config directly via ~/.codex/config.toml and project .codex/config.toml.
- Pi does not natively read MCP server config.
- Pi supports TypeScript extensions that can register tools dynamically with pi.registerTool().
- Therefore ContextForge MCP service activation for Pi should be implemented through a global Pi extension shim, not by assuming .pi/settings.json can contain MCP server declarations.
- Existing ~/.pi/agent/extensions/mcp-bridge/index.ts proves the pattern: it starts ContextForge MCP wrappers, maps MCP tools into Pi tools, and registers them through Pi's extension API.
- The current bridge is hand-wired for Context7 and Playwright only; it needs to become a generic ContextForge virtual-server importer.

Read first:
- AGENTS.md
- docs/initiatives/contextforge-control-plane/design-rfc.md
- docs/initiatives/contextforge-control-plane/design-rfc-procedure.md
- docs/initiatives/contextforge-control-plane/contextforge-helper-project-init-plan.md
- scripts/codex_project_init_hook.py
- scripts/contextforge_helper_mcp.py
- scripts/control_plane_project_init_helper.py
- scripts/project_init_common.py
- scripts/register_project_init_prompt.py
- scripts/control_plane_project_state.py
- scripts/control_plane_contextforge_binding.py
- tests/test_project_init_scripts.py
- tests/test_project_init_activation_workflow.py
- server-instances/*/instance.json
- ~/.pi/agent/extensions/mcp-bridge/index.ts, read-only first

Goal:
Add client_type="pi" as a first-class supported client type in the ContextForge project-init/helper workflow, using a global Pi extension shim for runtime tool activation.

Do not reuse the Codex config writer for Pi. Codex writes .codex/config.toml MCP blocks. Pi should produce a Pi activation plan targeting project state and the global Pi shim extension, not a fake Pi MCP config file.

User experience requirement:
Pi project-init should require the same level of user labor as Codex:
- same service discovery menu
- same approval/consent flow
- same non-actions
- same validate-now vs presume-working choice
- no manual editing of Pi extension code by the user
- no per-service hand configuration by the user

Architecture:
1. One-time global Pi shim extension:
   - lives under ~/.pi/agent/extensions/
   - implemented in TypeScript
   - uses Pi extension API, especially pi.registerTool()
   - loads approved project service bindings from .project/context_forge_state.json
   - connects to corresponding ContextForge virtual servers
   - calls MCP tools/list
   - dynamically registers each approved MCP tool as a Pi-visible tool
   - prefixes tool names safely to avoid collisions
   - enforces allowlists/policies for dangerous services
   - exposes target-client-visible validation signals back to the workflow
   - after any approved install or upgrade, the Pi agent must issue `/reload` before validation or other reliance on newly installed or changed extension tools

2. Pi project-init/hook equivalent:
   - research Pi's startup, workspace, extension activation, and user-facing prompt surfaces
   - identify the closest Pi-native equivalent to Codex's project-init hook
   - use Pi's `before_agent_start` event to supply project-init guidance as hidden model-visible system-prompt context
   - avoid dumping model-visible control text into the user transcript when Pi provides a hidden or structured extension path
   - suppress helper-tool transcript noise with Pi custom rendering where possible; user-visible output should be limited to information that requires user understanding or response
   - treat `cf_project_init_prompt` as diagnostic/manual render only, not as the normal project-init guidance path
   - cache the latest exact helper proposal and consent receipts in the Pi shim so approve/apply can proceed from the user-visible challenge id and plan digest without reconstructing hidden JSON
   - conduct the same step-by-step call-and-response dialogue as Codex project init
   - ask one question at a time and stop after each user-facing question
   - route all activation operations through the global Pi extension/helper pathway, not direct local file edits by the agent

3. Per-project activation:
   - writes .project/context_forge_state.json
   - does not write Codex-style MCP server config
   - does not mutate user-global Pi config during ordinary project activation
   - records target_clients.pi activation status and virtual-server bindings
   - uses the global shim to load approved services at runtime

4. ContextForge helper workflow:
   - distinguishes service identity from client activation:
     - service identity = ContextForge virtual server / service binding
     - client activation = Pi shim loading approved services for the current project
     - target-client validation = Pi-visible tool list and safe tool call proof
   - supports repair/resume for Pi:
     - pending validation resumes at validation choice
     - state/shim activation mismatch returns repair required
     - repair updates only approved project state/shim activation metadata
     - validation recording is helper-owned

Project state shape:
Record Pi separately from Codex. Use a structure equivalent to:

```json
"target_clients": {
  "pi": {
    "status": "shim_activation_planned",
    "surface": "global Pi extension + .project/context_forge_state.json",
    "alias": "context7",
    "virtual_server": "context7_local_server",
    "validation_status": "pending"
  }
}
```

Exact schema can differ if the current state schema already has a better shape, but the semantics must be explicit: Pi activation is shim-driven and project-state-driven, not client-config-driven.

Research tasks:
1. Inspect existing Pi extension structure:
   - extension manifest/package format
   - runtime API
   - pi.registerTool() usage
   - project-root/current-workspace detection
   - local process spawning
   - tool call lifecycle
   - logging/debug surface
2. Inspect ~/.pi/agent/extensions/mcp-bridge/index.ts:
   - how it starts ContextForge wrappers
   - how it talks MCP
   - how it maps MCP tools into Pi tools
   - how it handles errors/restarts
   - where it is hard-coded for Context7 and Playwright
3. Inspect ContextForge wrapper options:
   - existing scripts/contextforge_mcp_wrapper.py
   - whether wrapper stdio works cleanly from Pi extension child processes
   - whether direct SSE/streamable HTTP would be better
   - whether a Pi-specific wrapper/adapter is needed
4. Determine the safest one-time global shim installation path:
   - do not install or mutate user-global Pi files without explicit approval
   - if existing shim can be upgraded in-place, plan it separately
   - if repo-owned source should generate/install the shim, implement only the repo-owned source and an explicit install command
   - include a structured post-install instruction requiring the Pi agent to issue `/reload` before validation; apply the same explicit reload-before-validation step for any future target client whose extension/plugin runtime requires reload after install or upgrade

Implementation requirements:
1. Add pi to supported client types without weakening Codex behavior.
2. Add Pi-specific project-init planning/apply semantics:
   - no .codex/config.toml
   - no fake .pi/settings.json MCP config
   - project-state activation records for Pi
   - explicit consent classes for project state and Pi shim activation metadata
3. Extend helper/project-init tools so Pi can:
   - discover available services
   - propose selected services
   - approve scoped plan
   - apply project-local state activation
   - repair state/shim activation mismatch
   - record validation results
4. Add or scaffold the generic Pi MCP shim extension:
   - reads current project state
   - discovers approved target_clients.pi service bindings
   - imports all approved ContextForge virtual-server tools
   - prefixes names deterministically
   - blocks or gates dangerous tools based on policy
   - provides validation/readback tool(s) visible to Pi
5. Update project-init prompt/resource text:
   - mention Pi as a supported client type
   - for Pi, helper visibility may be through Pi-native tools registered by the shim, not native MCP
   - project init may activate ContextForge services through the Pi shim
   - validation must prove Pi-visible tools and safe calls, not backend health only
6. Preserve non-actions:
   - no user-global Pi config mutation during ordinary project activation
   - no user-global trust mutation
   - no secrets/token material writes
   - no ContextForge registry/catalog mutation
   - no backend install/restart for shared canonical services

Validation policy:
Target-client validation for Pi must prove Pi-visible behavior:
- list Pi-registered imported tools for selected services
- perform safe non-destructive tool calls where available
- record skipped with reason where credentials or semantics prevent safe probing
- do not count backend-only probes as Pi validation

Service-specific safe defaults:
- context7: safe docs lookup
- mentality: read/list only
- ssh-tmux: list/session visibility only unless explicitly approved
- github/web-search/exa/playwright/openzeppelin: safe read/search/list probes only where credentials and semantics allow; otherwise skipped with reason

Tests:
- Deterministic tests for Pi project-state activation planning.
- Tests that Pi activation never calls Codex config writer.
- Tests that no fake Pi MCP config surface is generated.
- Tests for project state entries under target_clients.pi.
- Tests for repair/resume:
  - pending validation resumes
  - state/shim mismatch returns repair required
  - repair is project-state/shim-metadata scoped
  - validation recording works
- Tests for generic Pi shim importer:
  - reads approved bindings from project state
  - starts/connects ContextForge wrappers
  - imports MCP tools/list
  - registers Pi tools with safe prefixes
  - handles name collisions
  - enforces deny/allow policy
- Regression tests that Codex behavior remains unchanged.
- Inference-inclusive/semantic tests where applicable:
  - Pi user gets service menu
  - selected services require scoped approval before activation
  - no manual Pi extension editing is requested from user
  - validation is Pi-visible

Verification:
- Run focused deterministic tests.
- Run broader project-init/control-plane tests.
- Run relevant inference-inclusive harness cases if available.
- Run a fixture-backed Pi extension dry-run showing:
  - current project root detection
  - approved service bindings read from state
  - MCP tools/list import
  - Pi tool registration names
  - safe validation/readback signal
- If real Pi is installed, perform read-only discovery only unless explicit approval is given for user-global extension installation or mutation.

Forbidden writes:
- Do not mutate live ~/.pi extension files without explicit approval.
- Do not install or upgrade the Pi extension globally without explicit approval.
- Do not write secrets, token material, or real credentials.
- Do not mutate live ContextForge registry/catalog except through existing safe prompt/helper registration paths when explicitly required and justified.
- Do not stage or commit.
- Do not edit unrelated service manifests or systemd units.
- Do not build this for the Pi instance localized to the noetic-pi project.

Deliverable:
Start with a researched plan. Clearly state what is confirmed versus inferred about the user-global Pi 0.78.x extension model and MCP wrapper options. Then implement only safe, supported pieces. If Pi cannot support a clean global shim + project-state workflow, stop and report the exact blocker and safest alternative.
```
