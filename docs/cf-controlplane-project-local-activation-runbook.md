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
- Issue #31 is closed. It owns the completed global Codex config/helper cleanup
  and runtime/project-context readback closure for this host. Final evidence is
  issue #31 comment `4735909113`.
- Issue #15 is closed. Its remaining practical concerns are now represented by
  issue #37, issue #50, and the legacy archive policy.
- Issue #33 is closed. PR #47 merged the Serena operator-port guardrail, and
  corrected closeout evidence is issue #33 comment `4736060615`.
- Issue #41 is closed for the initial dev Docker MCP backend/transceiver layer.
  The first stock transceiver path, OpenCode client Docker smoke, Pi client
  Docker shim validation, and service-locality matrix are now merged. Corrected
  closeout evidence is issue #41 comment `4736060708`.
- PR #35, PR #36, PR #38, and PR #39 are merged. PR #39 merged the
  activation-readiness source-prep branch into `dev-root` at
  `5e336c66953ece50043d78a4ac70530980304531`.
- The primary activation-readiness queue has landed on `dev-root`: #47 Serena
  port guardrails, #48 stale Serena user-unit inspector, #49 ContextForge
  cleanup inspector, and #51 project MCP container/locality matrix merged in
  that order. The merge-tip evidence is issue #37 comment `4734271745`.
- Issue #62 remains open and is packaged in draft PR #68 for source-only
  Pi/OpenCode baseline helper launchers. Runtime Docker/client proof remains
  separately approval-gated.
- Issue #52 remains open and is packaged in draft PR #69 for the first
  executable no-mutation service-onboarding record helper. It is source/docs/
  tests/fixtures only and is not a long-running helper daemon.
- PR #70 is this runbook/status refresh. It is docs-only and should not be
  treated as runtime activation evidence.
- Issue #2 remains open and is packaged in draft PR #71. The stale Serena unit
  inspector now classifies retired runtime-surface units and paths as migration
  blockers, not cleanup candidates.
- Issue #5 remains open and is packaged in draft PR #72. The read-only
  ContextForge cleanup inspector now separates retired project-surface registry
  records from ordinary orphan DELETE candidates.
- Issue #50 remains open and is packaged in draft PR #73 for source-only
  Serena verifier diagnostics. The verifier now distinguishes an open canonical
  port from a port owned by the canonical manifest process.
- The current activation-readiness review queue is #68, #69, #70, #71, #72,
  and #73. Issue #37 comment `4736205570` records the six-PR dry merge and
  current evidence boundary. No PR in this queue is approved for merge or draft
  promotion by this runbook.
- Issue #50 remains open for canonical Serena runtime/service/client-visible
  closure or an explicit validated compatibility decision.

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
- PR #68 adds source-only Pi/OpenCode baseline launchers and project-init
  fixture coverage for #62. It does not prove Docker/client runtime behavior.
  Durable issue evidence is #62 comment `4735996680`.
- PR #69 adds the first no-mutation service-onboarding record helper for #52.
  It records classifications, lifecycle planning, and evidence boundaries but is
  not a daemon or service installer. Durable issue evidence is #52 comment
  `4736046051`.
- PR #71 hardens the stale Serena unit inspector for #2. Its read-only audit
  reports `status: attention_required`, eleven retired runtime-surface blockers,
  and zero cleanup candidates. Durable issue evidence is #2 comment
  `4736111304`; #50 was also updated because this affects Serena closure.
- PR #72 hardens the read-only ContextForge cleanup inspector for #5. Its live
  API readback leaves one ordinary orphan prompt DELETE candidate and separates
  two retired project-surface registry records into a blocker list. Durable
  issue evidence is #5 comment `4736136201`.
- PR #73 hardens the Serena project-instance verifier for #50. Its read-only
  host probe classifies the current port listener as `foreign_or_stale_owner`,
  with no matching canonical PID. Durable issue evidence is #50 comment
  `4736200559`; #2 was also updated because the listener evidence affects stale
  Serena cleanup.
- The current six-PR queue-order dry merge #68 -> #69 -> #70 -> #71 -> #72
  -> #73
  applied cleanly from `origin/dev-root@4cc252f1cd1770f2e574b443e0471b94960a611f`
  and passed 135 queue-owned tests plus `git diff --check`. Durable evidence is
  issue #37 comment `4736205570`.
- Earlier queue dry-run evidence remains useful history but is no longer the
  current merge recommendation after #31/#33/#41 closure and the #68-#73
  packaging work.

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

Issue #31 is closed. The final read-only runtime inspector evidence reported a
clean target-root runtime after the approved global config/helper cleanup and
exact-match stale helper process termination:

```bash
scripts/inspect_codex_runtime_readback.py \
  --project-root /home/dgk/workspace/cf-controlplane \
  --pretty
```

Final #31 evidence is issue #31 comment `4735909113`: `status: readback_clean`,
no blockers, `foreign_count: 0`, and `legacy_count: 0`.

Use the same inspector for future regression readback:

```bash
scripts/inspect_codex_runtime_readback.py \
  --project-root /home/dgk/workspace/cf-controlplane \
  --config-path /home/dgk/.codex/config.toml
```

Future regressions should stop at the concrete boundary involved: Codex Desktop
reload/new-session, hook trust/state, global config mutation, process cleanup,
or client/runtime mutation. Do not convert this closed #31 state into broad
authorization for unrelated runtime changes.

## Docker MCP Backend Boundary

Issue #41 is closed for the initial dev Docker MCP backend/transceiver layer.
The merged layer proves the stock ContextForge bridge/transceiver path with the
repo-local `mentality` stdio backend, ContextForge dev Docker registration,
OpenCode client Docker smoke, and Pi client Docker shim validation. Future
stdio MCP backends still cannot be registered with the ContextForge dev Docker
gateway through direct process-local stdio; they need a backend-local
transceiver/gateway process that fronts stdio with packetized `/mcp` and `/sse`
endpoints for IP-to-IP communication. Keep those services on the ContextForge
development Docker surface, use the reserved `9200-9299` range, and continue to
keep the legacy/live ContextForge surface read-only.

Pi is not a native MCP client. Pi validation must go through a Pi extension or
API adapter surface, not direct `/mcp` or `/sse` consumption. The existing
TypeScript global shim under `pi-extensions/contextforge-global-shim` is one
candidate: it imports ContextForge virtual-server tools/prompts/resources and
registers Pi-native `registerTool()` tools. A direct ContextForge API path is
also acceptable if the stock API makes that simpler and stable enough. #41 used
the shim-first route; #62 now owns the remaining ordinary Pi/OpenCode baseline
session availability gap.

## Non-Actions

Do not mutate the legacy checkout as part of this runbook. The legacy
`cf-controlplane` workspace is archive/insurance and compatibility evidence, not
the source of new operating instructions.

Do not use backend health, process presence, or registry contents alone as proof
that project-local Codex activation succeeded. The acceptance path is
target-client-visible readback from a Codex project rooted at
`/home/dgk/workspace/cf-controlplane`.
