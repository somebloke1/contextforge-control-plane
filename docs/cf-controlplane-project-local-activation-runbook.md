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
legacy `/home/dgk/workspace/context-portal` checkout.

## Current Authority

- Issue #37 is open and owns project-local operating-context activation.
- Issue #31 is open and owns Codex runtime/project-context readback after the
  global config migration.
- Issue #15 is closed. Its remaining practical concerns are now represented by
  issue #37, issue #31, and the legacy archive policy.
- PR #35 and PR #36 are merged. PR #38 is merged into `dev-root` at
  `89dc9421d9b7f99a6b03869e88481ee318a308d9`.
- Branch `codex/issue-37-activation-readiness` contains the next
  activation-readiness transition from that merge commit.

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
  `/home/dgk/workspace/cf-controlplane` and revision 12 marks the Codex
  project-local activation state `initialized`, with the current Codex job
  `verified` and validation status `passed`.
- Regression evidence for the activation-readiness branch:
  `tests.test_project_init_scripts -v` ran 72 tests OK,
  `tests.test_project_init_activation_workflow -v` ran 78 tests OK,
  `tests.test_control_plane_project_state -v` ran 31 tests OK,
  `py_compile` passed for the touched scripts, and `git diff --check` passed.
- Delegated stale-reference audit found one active stale old-root readback
  command in `scripts/plan_codex_global_config_migration.py`; this branch
  fixes it and adds a regression. Remaining `context-portal` and
  `contextforge-slices` references are historical evidence, compatibility
  identifiers, or explicit readiness-inspector needles.

## Source-Prep Classification

| Surface | Current classification | Handling |
| --- | --- | --- |
| `.codex/skills/contextforge-project-init/**` | Must use `cf-controlplane` root for future helper flows | Track source corrections. |
| `.codex/skills/contextforge-governance/references/ledger-shape.md` | Must use `cf-controlplane` as the repository path template | Track source correction. |
| `.codex/config.toml` | Project-local activation surface | Retargeted on `codex/issue-37-activation-readiness`; `codex -C ... mcp list --json` reads expected project-local entries. |
| `.project/context_forge_state.json` | Helper-owned project-init state | Rooted at `cf-controlplane`; revision 12 marks Codex project-local activation verified/passed per operator-directed state repair after helper refused a redundant validation record. |
| `server-instances/serena-context-portal/**` | Compatibility Serena evidence with `cf-controlplane` root | Do not silently rename. Classify as compatibility or replace with a generated `serena-cf-controlplane-<hash>` instance in a later approved slice. |
| `contextforge://context-portal/...` resource ids | Compatibility decision pending | Do not silently rename. Record whether retained as compatibility ids or migrated. |
| Runtime env/evidence/trust/OAuth/hook-state | Local-only runtime state | Do not copy into Git. Recreate or recapture only after explicit approval. |

## Pre-Open Checklist

Before claiming issue #37 complete, the operating agent should prove:

1. The local Python environment exists, or `.codex/config.toml` does not point
   at a missing interpreter. Current branch evidence: exists.
2. Project-local MCP command paths and `cwd` values no longer point at
   `/home/dgk/workspace/contextforge-slices/repo-local-skills-and-governance`
   unless that is deliberately classified as a compatibility bridge. Current
   branch evidence: no active config references remain.
3. `.project/context_forge_state.json` represents `cf-controlplane`, or the
   helper reports a clear recovery/activation plan for reaching that state.
   Current branch evidence: root/root hash match `cf-controlplane`; state is
   `initialized` with Codex activation `verified`/`passed`.
4. The Serena project instance state is either regenerated for
   `cf-controlplane` or explicitly retained as legacy compatibility evidence.
   Current branch evidence: retained as compatibility evidence only; no new
   Serena backend or service is provisioned.
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
wrapper process origin, OAuth state, ContextForge registry state, or Pi/OpenCode
client behavior. Those are runtime/client readback gates for issue #31 or later
focused branches.

## Non-Actions

Do not mutate the legacy checkout as part of this runbook. The legacy
`context-portal` workspace is archive/insurance and compatibility evidence, not
the source of new operating instructions.

Do not use backend health, process presence, or registry contents alone as proof
that project-local Codex activation succeeded. The acceptance path is
target-client-visible readback from a Codex project rooted at
`/home/dgk/workspace/cf-controlplane`.
