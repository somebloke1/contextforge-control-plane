# ContextForge `cf-controlplane` Project-Local Activation Runbook

Date: 2026-06-17

This runbook governs issue #37: preparing
`/home/dgk/workspace/cf-controlplane` to become the project-local Codex
operating context.

The merged first slice was source-prep only. The current activation-readiness
slice may update project-local tracked activation artifacts in this checkout,
but it still does not authorize global Codex config writes, hook trust changes,
runtime secret/evidence copies, service or systemd changes, registry/catalog
changes, Pi/global config changes, process termination, or mutation of the
legacy `/home/dgk/workspace/legacy-controlplane-archive` checkout.

The legacy/live ContextForge surface is read-only for this runbook and for
successor Docker/client work. Mutable ContextForge registration, endpoint, reset,
and client-smoke experiments must target the isolated ContextForge development
Docker surface plus Pi/OpenCode client Docker surfaces, not the legacy/live
operator environment. Pi and OpenCode are the client Docker surfaces for the
indefinite development path; use the existing local llama.cpp-hosted Qwen 3.6
A3B model as configuration/default state, not installation. Avoid Codex and
Gemini client containers unless explicitly reopened. Evidence must state which
surface was exercised.

Pi integration architecture is recorded in
`docs/pi-contextforge-integration-architecture.md`. In short: Pi remains a
global TypeScript extension-shim client, direct ContextForge API use is valid
for helper/control readback where public APIs support it, and stdio MCP
backends need stock ContextForge gateway/transceiver endpoints for IP-to-IP
development Docker validation.

## Current Authority

- Issue #37 is open and owns project-local operating-context activation.
- Issue #31 is open and owns Codex runtime/project-context readback after the
  global config migration.
- Issue #15 is closed. Its remaining practical concerns are now represented by
  issue #37, issue #31, and the legacy archive policy.
- PR #35, PR #36, PR #38, and PR #39 are merged. PR #39 merged the
  activation-readiness source-prep branch into `dev-root` at
  `5e336c66953ece50043d78a4ac70530980304531`.
- The primary activation-readiness queue has landed on `dev-root`: #47 Serena
  port guardrails, #48 stale Serena user-unit inspector, #49 ContextForge
  cleanup inspector, and #51 project MCP container/locality matrix merged in
  that order. The merge-tip evidence is issue #37 comment `4734271745`.
- PR #59 remains the focused draft follow-up for #56. It refreshes the
  project-local precompact/helper path contract after the primary queue merge
  and still requires an explicit operator decision before promotion or merge.
- The remaining refreshed activation-readiness queue is #59, #65, #61, #64,
  #63, #53, and #55, followed by this PR #54 as the final docs-only runbook
  refresh. Issue #37 comment `4735200531` records the queue-order dry merge
  through #55 and the current evidence boundary.
- PR #53 records the guided MCP service-onboarding helper taxonomy for #52. It
  remains important but lower priority because #52 is high impact and
  low-to-medium priority. It has been refreshed against current `dev-root` and
  the active queue; do not treat it as runtime activation evidence.
- PR #54 is this runbook/status refresh. It is docs-only, should stay last in
  the refresh order, and should not be treated as runtime activation evidence.
- PR #55 remains a draft project-init activation-job reconciliation slice unless
  explicitly promoted. It has current #4/#37 evidence, but does not retire the
  Serena provisioning or compatibility-identifier readiness warnings.
- Issue #31 remains the owner for non-mutating Codex runtime/project-context
  readback after the global config migration. Do not treat #37 source/readiness
  packaging as proof of #31 runtime closure.

## Current Calibration Evidence

- `.venv/bin/python` exists in `/home/dgk/workspace/cf-controlplane`.
- `codex -C /home/dgk/workspace/cf-controlplane mcp list --json` sees
  project-local entries for `contextforge-helper`, `context7`, `github`,
  `mentality`, and `web_search` from this checkout.
- `scripts/inspect_project_init_readiness.py --project-root
  /home/dgk/workspace/cf-controlplane --client-type codex --no-processes`
  reports no blockers for activation-readiness, with remaining warnings for
  Serena provisioning and compatibility identifiers.
- `.project/context_forge_state.json` is rooted at
  `/home/dgk/workspace/cf-controlplane` and revision 13 marks the Codex
  project-local activation state `initialized`, with the current Codex job
  `verified` and validation status `passed`; `project.name` is
  `cf-controlplane`.
- Regression evidence for the activation-readiness branch:
  `tests.test_project_init_scripts -v` ran 74 tests OK,
  `tests.test_project_init_activation_workflow -v` ran 78 tests OK,
  `tests.test_control_plane_project_state -v` ran 31 tests OK,
  `py_compile` passed for the touched scripts, and `git diff --check` passed.
- Delegated stale-reference audit found one active stale old-root readback
  command in `scripts/plan_codex_global_config_migration.py`; this branch
  fixes it and adds a regression. Remaining `cf-controlplane` and
  `legacy-controlplane-slices` references are historical evidence, compatibility
  identifiers, or explicit readiness-inspector needles.
- The approved primary queue was merged in order #47, #48, #49, #51. Final
  `dev-root` readback was `274871322c2455cfab8e716d831043171eea1291`; the
  post-merge touched-suite validation passed 98 tests, `py_compile`, and
  `git diff --check`. Durable merge evidence is issue #37 comment
  `4734271745`.
- PR #59 was refreshed after the primary queue merge. Its current head is
  `d56782bfa2491c6827739a00a175a8a722a1d379`, base is `dev-root`
  `274871322c2455cfab8e716d831043171eea1291`, and canonical workspace
  validation passed the focused precompact config test, full unittest discovery
  with 505 tests, `py_compile`, and `git diff --check`. Durable evidence is PR
  #59 comment `4734298590` and issue #56 comment `4734298713`.
- PR #65, #61, #64, #63, #53, and #55 were refreshed after the primary queue
  merge. The current recommended order is `#59 -> #65 -> #61 -> #64 -> #63 ->
  #53 -> #55`, then this PR #54 last.
- The queue-order dry merge through #55 applied cleanly and passed 150
  queue-owned tests, `py_compile`, and `git diff --check`. The #59 precompact
  config assertion is location-sensitive in arbitrary temp worktrees, so it was
  verified separately in the canonical checkout with
  `tests.test_codex_precompact_continuity_hook -v` running 17 tests OK.
  Durable evidence is issue #37 comment `4735200531`.
- PR #55 read-only inspector evidence still reports `status: attention_required`
  with warnings `serena_project_instance_not_provisioned` and
  `project_init_compatibility_identifiers_present`. Its activation-job
  reconciliation summary has `current_verified_jobs=1`,
  `current_validation_pending_jobs=0`, `superseded_pending_jobs=2`, and
  `attention_required_jobs=0`. Durable #4 evidence is comment `4735196608`.
- Earlier five- and six-PR dry-run evidence for #53/#54 remains useful history
  but is no longer current merge evidence after #47, #48, #49, and #51 landed.

## Source-Prep Classification

| Surface | Current classification | Handling |
| --- | --- | --- |
| `.codex/skills/contextforge-project-init/**` | Must use `cf-controlplane` root for future helper flows | Track source corrections. |
| `.codex/skills/contextforge-governance/references/ledger-shape.md` | Must use `cf-controlplane` as the repository path template | Track source correction. |
| `.codex/config.toml` | Project-local activation surface | Retargeted on `codex/issue-37-activation-readiness`; `codex -C ... mcp list --json` reads expected project-local entries. |
| `.project/context_forge_state.json` | Helper-owned project-init state | Rooted at `cf-controlplane`; revision 13 marks Codex project-local activation verified/passed and repairs stale project naming after delegated review. |
| `server-instances/serena-cf-controlplane-d46fe58a2a20/**` | Compatibility Serena evidence with `cf-controlplane` root | Do not silently rename. Serena backend provisioning and the means to provision it are an abeyant hard requirement, not optional. Classify as compatibility only until a later Serena/project-init slice generates `serena-cf-controlplane-<hash>` or records an explicit validated compatibility decision. |
| `contextforge://cf-controlplane/...` resource ids | Compatibility decision pending | Do not silently rename. Record whether retained as compatibility ids or migrated. |
| Runtime env/evidence/trust/OAuth/hook-state | Local-only runtime state | Do not copy into Git. Recreate or recapture only after explicit approval. |

## Pre-Open Checklist

Before claiming issue #37 complete, the operating agent should prove:

1. The local Python environment exists, or `.codex/config.toml` does not point
   at a missing interpreter. Current branch evidence: exists.
2. Project-local MCP command paths and `cwd` values no longer point at
   `/home/dgk/workspace/legacy-controlplane-slices/repo-local-skills-and-governance`
   unless that is deliberately classified as a compatibility bridge. Current
   branch evidence: no active config references remain.
3. `.project/context_forge_state.json` represents `cf-controlplane`, or the
   helper reports a clear recovery/activation plan for reaching that state.
   Current branch evidence: root/root hash/name match `cf-controlplane`; state
   is `initialized` with Codex activation `verified`/`passed`.
4. The Serena project instance state is rooted in `cf-controlplane` source and
   later receives target-client-visible runtime validation under a
   GitHub-tracked Serena/project-init slice. Current branch evidence: source
   naming is canonical, but live runtime/service/registry validation remains
   separately approval-gated. This defers a hard requirement; it does not retire
   it.
5. Hook trust and project-local hook activation remain user-approved actions,
   not source-prep side effects.

## Activation Sequence

1. Refresh `git status`, open issues, and PR state from
   `/home/dgk/workspace/cf-controlplane`.
2. If environment setup is approved, create ignored `.venv` locally and verify
   helper scripts with the new root. Do not commit `.venv`.
3. Use `contextforge-helper` project-init tools for activation planning. Do not
   reconstruct project-init plans by hand.
4. Present helper digests, challenge ids, effects, and recovery plans exactly
   before applying any approved change.
5. If later runtime/client smoke tests require UI approval, OAuth login, hook
   trust toggle, service mutation, or process/systemd changes, route that
   concrete boundary to #31 or a new focused issue instead of reopening this
   activation-readiness state marker.
6. After the user opens/approves the `cf-controlplane` Codex project, verify
   active hooks and MCP paths from that project context.
7. Update issue #37 and issue #31 with readback evidence before claiming the
   operating-context transition complete.

## Residual Risk

This branch does not prove Codex Desktop project approval, hook trust, live
wrapper process origin, OAuth state, ContextForge registry state, Serena backend
provisioning, or Pi/OpenCode client behavior. Those are runtime/client readback
or Serena/project-init provisioning gates for issue #31 or later focused
branches. Serena provisioning may remain parked only until the appropriate
approved provisioning juncture surfaces.

## Issue #31 Readback

Use the read-only runtime inspector for current Codex runtime/project-context
evidence:

```bash
scripts/inspect_codex_runtime_readback.py \
  --project-root /home/dgk/workspace/cf-controlplane \
  --config-path /home/dgk/.codex/config.toml
```

The 2026-06-17 readback on `codex/issue-31-runtime-readback-plan` reported
`status: blocked`. Both `codex mcp list --json` from the project cwd and
`codex -C /home/dgk/workspace/cf-controlplane mcp list --json` had zero
predecessor workspace or `legacy-controlplane-slices` transport references, but process
inspection still found one live helper sourced from
`/home/dgk/workspace/legacy-controlplane-slices/repo-local-skills-and-governance`.
Global `~/.codex/config.toml` also still references that older clean-root helper
path. Do not kill the process or rewrite global config as part of readback;
route any required Codex Desktop project reload/new-session, hook trust, global
config, or cleanup action through a concrete approval boundary.

## Docker MCP Backend Boundary

Issue #41 owns the dev Docker MCP backend/transceiver layer. Stdio MCP backends
cannot be registered with the ContextForge dev Docker gateway through direct
process-local stdio; they need a backend-local transceiver/gateway process that
fronts stdio with packetized `/mcp` and `/sse` endpoints for IP-to-IP
communication. Keep those services on the ContextForge development Docker
surface, use the reserved `9200-9299` range, and continue to keep the
legacy/live ContextForge surface read-only.

Pi is not a native MCP client. Pi validation must go through a Pi extension or
API adapter surface, not direct `/mcp` or `/sse` consumption. The existing
TypeScript global shim under `pi-extensions/contextforge-global-shim` is one
candidate: it imports ContextForge virtual-server tools/prompts/resources and
registers Pi-native `registerTool()` tools. A direct ContextForge API path is
also acceptable if the stock API makes that simpler and stable enough. Issue
#41 should evaluate those options before selecting the Pi validation adapter.

## Non-Actions

Do not mutate the legacy checkout as part of this runbook. The legacy
`cf-controlplane` workspace is archive/insurance and compatibility evidence, not
the source of new operating instructions.

Do not use backend health, process presence, or registry contents alone as proof
that project-local Codex activation succeeded. The acceptance path is
target-client-visible readback from a Codex project rooted at
`/home/dgk/workspace/cf-controlplane`.
