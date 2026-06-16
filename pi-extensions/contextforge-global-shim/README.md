# ContextForge Global Shim for Pi

Repo-owned source for the user-global Pi extension that imports approved
ContextForge virtual-server MCP tools for the current project.

This directory is source only. Project-init does not install or mutate
`~/.pi/agent/extensions` during normal service activation. Installation or
upgrade of the global Pi extension is a separate explicit approval path.
After any approved install or upgrade, the Pi agent must issue `/reload` before
validation or other reliance on newly installed or changed extension tools.

Runtime model:

- Pi loads this as a global TypeScript extension.
- The extension always registers Pi-native `cf_project_init_*` bootstrap tools
  that proxy to the repo-local ContextForge helper workflow.
- Project-init guidance is injected through Pi's hidden `before_agent_start`
  system-prompt context. The `cf_project_init_prompt` tool is diagnostic only.
- `cf_project_init_*` helper tool calls use empty custom renderers so their
  model-visible JSON results do not fill the user's terminal.
- The shim caches the latest exact project-init proposal, approval receipts, and
  apply result for the current Pi session. Approval can therefore use only the
  user-visible challenge id and plan digest; apply can then use cached receipts.
- On session startup, the extension reads
  `.project/context_forge_state.json` from the current project root.
- Services under `target_clients.pi` are imported through the ContextForge
  virtual-server wrapper.
- Imported MCP tools are registered with deterministic
  `cf_<service>_<identity>__<tool>` Pi tool names, keyed internally by the
  project-state service identity and ContextForge server id when current
  readback provides one. Repeated activation refreshes reuse the same Pi tool
  names and only replace the active route behind each name. The route registry
  is stored on `globalThis` so retained Pi tool closures from a prior `/reload`
  still resolve through the current live route map.
- The shim imports MCP prompt/resource metadata in addition to MCP tools. It
  does not register one Pi tool per prompt/resource.
- The Pi-visible `cf_contextforge_guidance_lookup` tool lazily reads matching
  ContextForge resources and renders matching ContextForge prompts for an
  approved service. This gives Pi the same guidance surface Codex receives from
  MCP prompts/resources without flooding Pi's tool list.
- The Pi-visible `cf_contextforge_pi_readback` tool reports imported services,
  tool names, prompt names, resource URIs, skips, and errors for project-init
  validation and adapter diagnostics.
- Child wrapper stderr is not mirrored into the Pi terminal during normal
  startup; bounded stderr tails are retained only for tool/readback errors.

Environment overrides for installation packaging:

- `CONTEXTFORGE_PI_SHIM_PORTAL_ROOT`
- `CONTEXTFORGE_PI_SHIM_WORKSPACE_ROOT`
- `CONTEXTFORGE_PI_SHIM_PYTHON`
- `CONTEXTFORGE_PI_SHIM_WRAPPER`

An approved install writes `contextforge-root.json` beside the extension source
with the repo root that owns the helper scripts. This keeps the installed
user-global extension bound to the approved ContextForge checkout instead of a
hard-coded local path. `CONTEXTFORGE_PI_SHIM_PORTAL_ROOT` remains the explicit
runtime override.

The included `package.json` marks this extension directory as an ES module and
declares `index.ts` as its Pi extension entrypoint.
