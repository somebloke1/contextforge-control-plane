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
- Host user-global OpenCode config or plugin mutation.
- Legacy/live ContextForge registry, token, service, or process mutation.
- Runtime Docker rebuild/run proof. That remains a separately approved runtime
  evidence pass.

## Current Evidence

The current harness has useful smoke paths, but they are not baseline session
paths:

- `docker/client-harness/scripts/smoke-pi-contextforge-dev.sh` loads
  `pi-extensions/contextforge-global-shim/index.ts` with an explicit
  `--extension` flag for one readback run.
- `docker/client-harness/scripts/smoke-opencode-contextforge-dev.sh` runs
  `opencode mcp add` against the development gateway for one runtime check.
- `docker/client-harness/config/pi/AGENTS.md` only gives Qwen smoke guidance.
- `docker/client-harness/config/opencode/opencode.json` defines the Qwen
  provider/model and the harness-owned `contextforge-helper` local MCP entry,
  but ordinary shell runs need that fixture materialized into the container
  user's normal OpenCode config directory.

Therefore a Pi or OpenCode container shell can truthfully lack ContextForge
helper tools even when the specialized smoke scripts pass.

## Desired Baseline

The baseline should make the expected helper surface available whenever a
developer starts a Pi or OpenCode client session from this harness through the
baseline launchers, while keeping the harness isolated and resettable.

Harness-owned baseline entrypoints:

- `docker/client-harness/scripts/start-pi-contextforge-baseline.sh`
- `docker/client-harness/config/pi/start-contextforge-baseline.sh`
- `docker/client-harness/pi/pi-wrapper.sh`
- `docker/client-harness/pi/contextforge-pi-bootstrap.sh`
- `docker/client-harness/scripts/start-opencode-contextforge-baseline.sh`
- `docker/client-harness/config/opencode/start-contextforge-baseline.sh`
- `docker/client-harness/config/opencode/plugins/contextforge-project-init.js`

### Pi

Pi remains shim-first because Pi does not natively consume MCP the same way an
MCP-aware client does. The sustainable baseline route is:

- load `pi-extensions/contextforge-global-shim/index.ts` from a repository
  mount into the container-local Pi extension directory;
- expose the `cf_project_init_*` bootstrap tools and ContextForge startup
  guidance during the client session;
- keep wrapper runtime and token cache inside the container;
- point only at the ContextForge development Docker surface when runtime checks
  are separately approved;
- avoid host Pi installs, host `/reload`, or host/global Pi state mutation.

The persistent Pi Compose service must also support the common interactive
debugging path `docker compose -f docker/client-harness/compose.yml run pi bash`
followed by a bare `pi` command. The image-level wrapper at `/usr/local/bin/pi`
seeds the same container-local `models.json`, AGENTS guidance, and shim files
before delegating to the real npm Pi binary at `/usr/bin/pi`, and defaults that
bare session to `local-llama-qwen/qwen3.6-a3b` unless the command explicitly
selects another provider or model.
  Container-local writes under `/home/agent/.pi/agent/extensions` are harness
  setup, not project-init approval/apply writes.

The existing smoke script may keep its explicit `--extension` proof. The
baseline session launcher now materializes the shim into Pi's normal
auto-discovered extension directory so a developer does not have to remember the
quick-test `--extension` flag.

For project-state readback, the baseline launcher now mounts the canonical
repository root at `/workspace`, so the session starts in the same project root
where `context_forge_state.json` can be discovered. When that state file is
present but has no `target_clients.pi` service bindings, the shim readback still
reports `project state has no approved target_clients.pi service bindings` and
`services: []` as the active residual gap.

### OpenCode

OpenCode should use the normal container-user global OpenCode plugin surface
for the first-prompt trigger, while keeping selected MCP service bindings
project-local after helper approval/apply. The sustainable baseline route is:

- provide harness-owned OpenCode bootstrap fixtures under
  `docker/client-harness/config/opencode`;
- seed the helper bootstrap config into
  `/home/agent/.config/opencode/opencode.json`;
- seed the first-prompt trigger into
  `/home/agent/.config/opencode/plugins/contextforge-project-init.js`;
- expose `contextforge-helper` through a container-local Python environment
  instead of the host `.venv`;
- reuse the project-local hook behavior implemented by
  `scripts/opencode_project_init_hook.py`;
- use the OpenCode messages transform plugin hook as the first-prompt trigger,
  not `experimental.chat.system.transform` as the primary init path;
- keep hook runtime state under writable container-local runtime paths, not
  under the read-only `/repo` mount;
- keep any generated client state inside the OpenCode client container volume;
- point only at the ContextForge development Docker surface when runtime checks
  are separately approved;
- avoid host user-global OpenCode config or plugin writes.

The existing smoke script may keep its temporary `opencode mcp add` proof.
Baseline helper availability now uses both a harness-owned `contextforge-helper`
MCP entry in the container user's OpenCode config and a global plugin copied
into `/home/agent/.config/opencode/plugins/contextforge-project-init.js`, so it
does not depend on that one-shot command and does not create project-local
`.opencode/plugins` in a fresh workspace. Approved selected MCP services remain
project-local in `opencode.json` plus `.project/context_forge_state.json`.

## Runtime Evidence Boundary

Source/test changes may define and statically check the baseline contract.
They must not claim runtime completion until a separately approved evidence pass
rebuilds/runs the Pi and OpenCode containers and collects evidence from actual
ad hoc client sessions.

Runtime evidence should identify the exercised surface explicitly:

- `ContextForge dev Docker` for the gateway and registry surface;
- `Pi client Docker` for Pi session proof;
- `OpenCode client Docker` for OpenCode session proof.

Minimum future runtime checks:

- Pi ad hoc session lists or can invoke the expected ContextForge helper/shim
  tools without host-global Pi mutation.
- OpenCode ad hoc session receives project-init helper/hook context from the
  container user-home fixture without host user-global OpenCode mutation.
- Both clients continue using the local llama.cpp Qwen model path.
- Any scoped development token is created, used, redacted in evidence, and
  revoked before exit.

## Non-Actions

This contract does not approve or perform:

- Docker build/run/rebuild operations.
- ContextForge registry or token mutation.
- host Pi install/reload.
- host user-global OpenCode/Pi config mutation.
- helper approve/apply/recovery state mutation.
- `.project/context_forge_state.json` mutation.
- legacy `/home/dgk/workspace/legacy-controlplane-archive` mutation.
