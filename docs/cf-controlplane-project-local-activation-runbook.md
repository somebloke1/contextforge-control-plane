# ContextForge `cf-controlplane` Project-Local Activation Runbook

Date: 2026-06-17

This runbook governs issue #37: preparing
`/home/dgk/workspace/cf-controlplane` to become the project-local Codex
operating context.

The approved first slice is source-prep only. It does not authorize global
Codex config writes, hook trust changes, runtime secret/evidence copies,
service or systemd changes, registry/catalog changes, Pi/global config changes,
process termination, or mutation of the legacy
`/home/dgk/workspace/context-portal` checkout.

## Current Authority

- Issue #37 is open and owns project-local operating-context activation.
- Issue #31 is open and owns Codex runtime/project-context readback after the
  global config migration.
- Issue #15 is closed. Its remaining practical concerns are now represented by
  issue #37, issue #31, and the legacy archive policy.
- PR #35 and PR #36 are merged. The clone is based on `dev-root` at
  `08d72dc898b0ae1c554297009b1145efb95ceda6`.

## Source-Prep Classification

| Surface | Current classification | Handling |
| --- | --- | --- |
| `.codex/skills/contextforge-project-init/**` | Must use `cf-controlplane` root for future helper flows | Track source corrections. |
| `.codex/skills/contextforge-governance/references/ledger-shape.md` | Must use `cf-controlplane` as the repository path template | Track source correction. |
| `.codex/config.toml` | Approval-gated activation surface | Do not retarget in source-prep. Later retarget only after environment and helper plan are coherent. |
| `.project/context_forge_state.json` | Helper-owned project-init state | Do not hand-edit in source-prep. Regenerate or migrate through an approved helper/project-init path. |
| `server-instances/serena-context-portal/**` | Legacy/compatibility Serena evidence | Do not regenerate or rename in source-prep. Classify or replace in a later project-init/Serena slice. |
| `contextforge://context-portal/...` resource ids | Compatibility decision pending | Do not silently rename. Record whether retained as compatibility ids or migrated. |
| Runtime env/evidence/trust/OAuth/hook-state | Local-only runtime state | Do not copy into Git. Recreate or recapture only after explicit approval. |

## Pre-Open Checklist

Before the user opens or approves a Codex project rooted at
`/home/dgk/workspace/cf-controlplane`, a future approved slice should prove:

1. The local Python environment exists, or `.codex/config.toml` does not point
   at a missing interpreter.
2. Project-local MCP command paths and `cwd` values no longer point at
   `/home/dgk/workspace/contextforge-slices/repo-local-skills-and-governance`
   unless that is deliberately classified as a compatibility bridge.
3. `.project/context_forge_state.json` represents `cf-controlplane`, or the
   helper reports a clear recovery/activation plan for reaching that state.
4. The Serena project instance state is either regenerated for
   `cf-controlplane` or explicitly retained as legacy compatibility evidence.
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
5. If Codex reload or new project approval is required, stop and ask the user to
   perform that action.
6. After the user opens/approves the `cf-controlplane` Codex project, verify
   active hooks and MCP paths from that project context.
7. Update issue #37 and issue #31 with readback evidence before claiming the
   operating-context transition complete.

## Non-Actions

Do not mutate the legacy checkout as part of this runbook. The legacy
`context-portal` workspace is archive/insurance and compatibility evidence, not
the source of new operating instructions.

Do not use backend health, process presence, or registry contents alone as proof
that project-local Codex activation succeeded. The acceptance path is
target-client-visible readback from a Codex project rooted at
`/home/dgk/workspace/cf-controlplane`.
