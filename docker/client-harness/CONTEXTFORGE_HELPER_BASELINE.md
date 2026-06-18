# ContextForge Helper Baseline Contract

Issue #62 identified a real gap: Pi and OpenCode client containers can run
specialized ContextForge smoke flows, but ordinary ad hoc client sessions do
not yet expose the project-init helper/hook surface by default.

This document defines the source contract and harness-owned baseline fixtures
for that baseline without mutating host-global clients, the legacy/live
ContextForge surface, or runtime registry state.

## Scope

In scope:

- Pi client Docker.
- OpenCode client Docker.
- The existing local llama.cpp Qwen model path.
- The ContextForge development Docker surface.
- Project-local helper/hook wiring under this repository.

Out of scope for this baseline:

- Codex CLI, Claude Code, and Gemini CLI client expansion.
- Host Pi install, host Pi reload, or user-global Pi extension mutation.
- User-global OpenCode config or plugin mutation.
- Legacy/live ContextForge registry, token, service, or process mutation.
- Runtime Docker rebuild/run proof. That remains a separately approved
  validation slice.

## Current Evidence

The current harness has useful smoke paths, but they are not baseline session
paths:

- `docker/client-harness/scripts/smoke-pi-contextforge-dev.sh` loads
  `pi-extensions/contextforge-global-shim/index.ts` with an explicit
  `--extension` flag for one validation run.
- `docker/client-harness/scripts/smoke-opencode-contextforge-dev.sh` runs
  `opencode mcp add` against the development gateway for one validation run.
- `docker/client-harness/config/pi/AGENTS.md` only gives Qwen smoke guidance.
- `docker/client-harness/config/opencode/opencode.json` defines the Qwen
  provider/model and the harness-owned `contextforge-helper` local MCP entry.

Therefore a Pi or OpenCode container shell can truthfully lack ContextForge
helper tools even when the specialized smoke scripts pass.

## Desired Baseline

The baseline should make the expected helper surface available whenever a
developer starts a Pi or OpenCode client session from this harness through the
baseline launchers, while keeping the harness isolated and resettable.

Harness-owned baseline entrypoints:

- `docker/client-harness/scripts/start-pi-contextforge-baseline.sh`
- `docker/client-harness/config/pi/start-contextforge-baseline.sh`
- `docker/client-harness/scripts/start-opencode-contextforge-baseline.sh`
- `docker/client-harness/config/opencode/start-contextforge-baseline.sh`
- `docker/client-harness/config/opencode/plugins/contextforge-project-init.js`

### Pi

Pi remains shim-first because Pi does not natively consume MCP the same way an
MCP-aware client does. The sustainable baseline route is:

- load `pi-extensions/contextforge-global-shim/index.ts` from a repository
  mount or copied image path;
- expose the `cf_project_init_*` bootstrap tools and ContextForge startup
  guidance during the client session;
- keep wrapper runtime and token cache inside the container;
- point only at the ContextForge development Docker surface when runtime
  validation is separately approved;
- avoid writing `~/.pi`, requiring `/reload`, or mutating host/global Pi state.

The existing smoke script may keep its explicit `--extension` proof. The
baseline session launcher now carries that extension path by default so the
developer does not have to remember the special flag.
The shim's ordinary-session contract includes two Pi lifecycle hooks:
`before_agent_start` injects hidden project-init guidance and `session_start`
activates ContextForge routes from the project state. A run that disables Pi
session handling, such as a diagnostic `--no-session` probe, is not sufficient
ordinary-session evidence for #62.

For project-state readback, the baseline launcher now mounts the canonical
repository root at `/workspace`, so the session starts in the same project root
where `context_forge_state.json` can be discovered. Project state now records
pending `target_clients.pi` shim bindings for the four existing project-local
services. The active residual gap is no longer missing Pi bindings; it is
wrapper reachability. A baseline Pi session can import the service metadata, but
canonical service tools are not registered until the launcher points wrappers at
a reachable ContextForge surface with matching virtual-server names and
container-local auth material.

The harness now keeps two Pi launch paths distinct:

- `scripts/start-pi-contextforge-baseline.sh` mounts the canonical repository as
  `/workspace` and exercises the real project state. It is the right path for
  checking project-local activation metadata, but it must not claim imported
  service tools are usable until the target ContextForge surface has matching
  virtual servers for that state.
- `scripts/start-pi-contextforge-dev-baseline.sh` writes an isolated
  `mentality:dev_docker` project-state fixture into the resettable harness
  workspace and passes the wrapper environment used by the ContextForge
  development Docker surface. This is the ordinary-session path for proving Pi
  client Docker can see a real shim-imported service without relying on the
  legacy/live ContextForge instance or pretending the canonical four-service
  state has been registered in the dev gateway.

### OpenCode

OpenCode should use a project-local harness fixture rather than a user-global
OpenCode mutation. The sustainable baseline route is:

- provide a harness-owned OpenCode project-init plugin/config fixture under
  `docker/client-harness/config/opencode`;
- expose `contextforge-helper` through a container-local Python environment
  instead of the host `.venv`;
- reuse the project-local hook behavior implemented by
  `scripts/opencode_project_init_hook.py`;
- keep any generated client state inside the OpenCode client container volume;
- point only at the ContextForge development Docker surface when runtime
  validation is separately approved;
- avoid user-global OpenCode config or plugin writes.

The existing smoke script may keep its temporary `opencode mcp add` proof.
Baseline helper availability now uses both a harness-owned `contextforge-helper`
MCP entry in `opencode.json` and a project plugin fixture copied into
`/workspace/.opencode/plugins/contextforge-project-init.js` inside the client
container, so it does not depend on that one-shot command. The plugin invokes
the project-init hook through OpenCode's `experimental.chat.system.transform`
surface, and the Python hook also accepts `session.created`; both are
OpenCode-native session surfaces, not Codex hook banners.

## Runtime Validation Boundary

Source/test changes may define and statically check the baseline contract.
They must not claim runtime completion until a separately approved validation
slice rebuilds/runs the Pi and OpenCode containers and collects evidence from
actual ad hoc client sessions.

Runtime evidence should identify the exercised surface explicitly:

- `ContextForge dev Docker` for the gateway and registry surface;
- `Pi client Docker` for Pi session proof;
- `OpenCode client Docker` for OpenCode session proof.

Minimum future runtime checks:

- Pi ad hoc session imports the expected ContextForge helper/shim bindings from
  either the canonical project state or the dev fixture, through an ordinary Pi
  run that does not disable session lifecycle events, and then lists or can
  invoke service tools through a reachable matching ContextForge surface without
  host-global Pi mutation.
- OpenCode ad hoc session receives project-init helper/hook context from the
  harness-owned fixture through `experimental.chat.system.transform` or
  `session.created` behavior without user-global OpenCode mutation.
- Both clients continue using the local llama.cpp Qwen model path.
- Any scoped development token is created, used, redacted in evidence, and
  revoked before exit.

## Non-Actions

This contract does not approve or perform:

- Docker build/run/rebuild operations.
- ContextForge registry or token mutation.
- host Pi install/reload.
- user-global OpenCode/Pi config mutation.
- unapproved helper approve/apply/recovery state mutation.
- direct `.project/context_forge_state.json` mutation outside the helper path.
- legacy `/home/dgk/workspace/legacy-controlplane-archive` mutation.
