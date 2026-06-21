# Dev Docker And Client Evidence Freshness Protocol

Issue: #58

This protocol defines how to cite, refresh, and promote evidence for the
isolated ContextForge development Docker surface and the Pi/OpenCode client
Docker foils. It does not authorize starting containers, rebuilding images,
creating tokens, registering services, mutating clients, or touching the
legacy/live ContextForge surface.

## Surfaces

Evidence must identify the exercised surface explicitly:

| Surface | Mutable during approved refresh? | Evidence role |
| --- | --- | --- |
| Legacy/live ContextForge | No | Read-only comparison, health, config, process, or log evidence only. |
| ContextForge dev Docker | Yes, with scoped approval | Mutable gateway, registry, backend/transceiver, and endpoint validation surface. |
| Pi client Docker | Yes, with scoped approval | Pi extension/shim validation foil against ContextForge dev Docker. |
| OpenCode client Docker | Yes, with scoped approval | Real OpenCode MCP client validation foil against ContextForge dev Docker. |

Do not cite legacy/live ContextForge evidence as proof that the development
Docker gateway or client Docker flows currently work. Do not cite development
Docker evidence as proof that the legacy/live environment is safe to mutate.

## Refresh Checklist

A full #58 evidence refresh has these phases.

1. Baseline the repository state:
   - record the branch, commit, dirty status, and PR or issue being refreshed;
   - confirm the change is not using `/home/dgk/workspace/legacy-controlplane-archive` as
     the active source root;
   - confirm ignored evidence paths remain ignored.
2. Validate ContextForge dev Docker gateway state:
   - run the approved `docker/contextforge-harness` setup or readback commands;
   - capture gateway `health`, `ready`, version, admin login/readback, gateway
     list, server list, and scoped-token behavior;
   - keep raw secrets and raw bearer tokens out of tracked artifacts.
3. Validate `mentality-transceiver`:
   - prove the direct transceiver endpoint lists the expected tools;
   - register or read back `mentality-dev-docker` only in the dev gateway;
   - prove ContextForge virtual-server readback through
     `mentality_dev_docker_server`;
   - create only short-lived scoped probe tokens and revoke them before the
     refresh is considered complete.
4. Validate client Docker foils:
   - run Pi and OpenCode only, unless a later issue explicitly expands scope;
   - keep local Qwen/llama.cpp as configuration, not an installation task;
   - prove OpenCode through its remote MCP client surface against
     `http://host.docker.internal:4445`;
   - for the `mentality_dev_docker_server` route, distinguish
     `opencode mcp list` connection evidence from target-client readiness by
     also collecting a known-safe governance list/read call from the same OpenCode client Docker run;
   - prove Pi through the extension/shim validation path, not by inventing a
     native Pi MCP config surface;
   - record container-local evidence paths and token revocation.
5. Summarize the result:
   - list the exact commands run, their surface, and their status;
   - identify any stale, skipped, failed, or partial evidence;
   - record non-actions for legacy/live, global config, host Pi, registry,
     Docker, helper/project-init, Serena, and secrets as applicable.

## Local Evidence

Raw refresh outputs stay local and ignored by default:

- `docker/contextforge-harness/evidence/`
- `docker/client-harness/evidence/`
- `docker/contextforge-harness/env/contextforge.env`
- `docker/client-harness/env/semantic-model.env`
- token caches, runtime logs, container volumes, and generated state under
  ignored `run/` or harness-local paths.

Tracked promotion is allowed only for sanitized summaries that contain:

- command names and relative paths;
- surface labels;
- commit, branch, issue, and PR references;
- redacted status output or counts;
- token ids only when useful for token revocation evidence;
- no raw token values, API keys, session cookies, OAuth state, or local secret
  env contents.

Promoted evidence must say whether it is current proof, historical evidence, or
comparison evidence. Historical evidence can justify a design choice; it cannot
prove current readiness.

Ignored evidence files are not proof merely because they exist. Empty files,
partial transcripts, pre-refresh smoke outputs, or files whose generating
commands are unknown must be labeled `unverified` until a current refresh
recreates them with command, surface, timestamp, branch, commit, and token
revocation evidence.

## PR Freshness Rules

Use these labels in PR bodies and issue comments:

- `current`: collected after the PR branch was based on the cited `dev-root`
  commit and after all prerequisite branches were merged or dry-merged.
- `refreshed`: recollected after a branch rebase, merge from `dev-root`, or
  meaningful harness/client change.
- `historical`: useful background that predates the current base or target
  topology.
- `comparison-only`: read-only evidence from legacy/live ContextForge or other
  non-target surfaces.
- `stale`: contradicted by current files, changed dependencies, changed
  container images, changed ports, changed client model config, or changed
  gateway registration state.
- `unverified`: a file, transcript, or claim exists but lacks enough current
  command/readback context to prove the stated behavior.

Refresh evidence before citing it as `current` when any of these change:

- `docker/contextforge-harness/**`
- `docker/client-harness/**`
- `server-instances/**` for the service under test;
- `scripts/contextforge_mcp_wrapper.py`;
- `scripts/pi_*`, `pi-extensions/**`, or `scripts/opencode_*`;
- ContextForge gateway image/version, published ports, env defaults, token
  policy, or registration scripts;
- Pi/OpenCode image, package version, model/provider config, or smoke script.

If a PR cites older evidence, mark it `historical` or `comparison-only` and
state the current refresh boundary that remains.

Backend-only proof is insufficient for client claims. Pi/OpenCode claims need
target-client-visible proof from the matching client Docker surface, while
gateway or transceiver claims need ContextForge dev Docker readback from the
registered virtual server.

## Approved Client Scope

For this protocol, the only client Docker foils are:

- Pi client Docker;
- OpenCode client Docker.

The local Qwen model served by llama.cpp is a configuration target. The refresh
may verify endpoint/model visibility, but it must not install or replace the
model server. Pi/OpenCode model evidence must record the exact advertised model
id returned by the endpoint, compare it with the harness expected model id, and
mark the evidence `stale` when they differ rather than accepting a nearby Qwen
alias. Do not expand #58 evidence claims to Codex CLI, Gemini CLI, Claude Code,
or Claude Desktop without a later scoped issue and approval.

## Non-Actions

This protocol does not authorize:

- mutating the legacy/live ContextForge surface;
- starting, stopping, rebuilding, or deleting containers;
- writing ContextForge registry, gateway, prompt, resource, token, or team
  state;
- installing or reloading host Pi extensions;
- mutating global Codex, Pi, OpenCode, hook, trust, OAuth, or secret state;
- helper/project-init approve, apply, recovery, or validation-state mutation;
- Serena provisioning;
- broad renaming of compatibility identifiers;
- editing `/home/dgk/workspace/legacy-controlplane-archive`.

Those operations require separate explicit approval naming the target surface.
