# ContextForge Helper Baseline Contract

Issue #62 identified a real gap: Pi and OpenCode client containers can run
specialized ContextForge smoke flows, but ordinary ad hoc client sessions do
not yet expose the project-init helper/hook surface by default.

This document defines the source contract for adding that baseline without
mutating host-global clients, the legacy/live ContextForge surface, or runtime
registry state.

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
- `docker/client-harness/config/opencode/opencode.json` only defines the Qwen
  provider/model.

Therefore a Pi or OpenCode container shell can truthfully lack ContextForge
helper tools even when the specialized smoke scripts pass.

## Desired Baseline

The baseline should make the expected helper surface available whenever a
developer starts a Pi or OpenCode client session from this harness, while
keeping the harness isolated and resettable.

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

The existing smoke script may keep its explicit `--extension` proof, but the
baseline session launcher should not rely on a human remembering that special
flag.

### OpenCode

OpenCode should use a project-local harness fixture rather than a user-global
OpenCode mutation. The sustainable baseline route is:

- provide a harness-owned OpenCode project-init plugin/config fixture under
  `docker/client-harness/config/opencode`;
- reuse the project-local hook behavior implemented by
  `scripts/opencode_project_init_hook.py`;
- keep any generated client state inside the OpenCode client container volume;
- point only at the ContextForge development Docker surface when runtime
  validation is separately approved;
- avoid user-global OpenCode config or plugin writes.

The existing smoke script may keep its temporary `opencode mcp add` proof, but
baseline helper availability should not depend on that one-shot command.

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

- Pi ad hoc session lists or can invoke the expected ContextForge helper/shim
  tools without host-global Pi mutation.
- OpenCode ad hoc session receives project-init helper/hook context from the
  harness-owned fixture without user-global OpenCode mutation.
- Both clients continue using the local llama.cpp Qwen model path.
- Any scoped development token is created, used, redacted in evidence, and
  revoked before exit.

## Non-Actions

This contract does not approve or perform:

- Docker build/run/rebuild operations.
- ContextForge registry or token mutation.
- host Pi install/reload.
- user-global OpenCode/Pi config mutation.
- helper approve/apply/recovery state mutation.
- `.project/context_forge_state.json` mutation.
- legacy `/home/dgk/workspace/legacy-controlplane-archive` mutation.
