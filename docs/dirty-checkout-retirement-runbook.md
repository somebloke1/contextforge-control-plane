# ContextForge Dirty Checkout Retirement Runbook

This runbook makes issue #15 executable without hiding the retirement boundary.
The user approved Strategy 1 as a first source-only compatibility rebind pass:
project-local/source operating surfaces may be rebound from the legacy checkout
to the clean worktree, while reset, clean, delete, rename, service restart,
registry mutation, hook trust changes, global config writes, Pi install/reload,
and ContextForge runtime mutations still require fresh explicit approval and
readback evidence.

Proper project naming is ContextForge. `context-portal` is a legacy path,
runtime slug, and compatibility identifier where exact paths, service names,
hashes, or historical evidence require it.

## Current State

Clean operating tree:

```text
/home/dgk/workspace/contextforge-slices/repo-local-skills-and-governance
branch: dev-root
head: 9aa732b9f5d89d4663f37be1418d98f8e736f6a8
status: synchronized with origin/dev-root
```

Legacy dirty checkout:

```text
/home/dgk/workspace/context-portal
branch: codex/contextforge-wrapper-lifecycle
head: ae5a4349bdcaa552e2073369df185fa1bdd7f61f
```

Latest preservation snapshot:

```text
run/dirty-state-preservation/20260616T114116Z/
tracked_file_count=35
untracked_path_count=41
checksum verification passed at creation time and was rechecked after PR #21
```

Current GitHub state:

- Issue #15 tracks retirement of the dirty holding checkout.
- Issue #4 has read-only readiness reconciliation on `dev-root` through PR
  #21. Before the Strategy 1 source rebind branch, the clean source state was
  root-mismatched and helper/wrapper processes still sourced from the legacy
  checkout. Merged PR #24 repairs the clean root state, but issue #4 still
  requires target-client validation and any separately approved runtime reload
  or service readback.
- Issue #3 source parity is merged through PR #20, but the user-global Pi
  install/reload/validation is not approved or complete.
- Issue #6 is closed; inventory/service-management triage is no longer hidden
  dirty-checkout work.
- Remaining open roadmap issues are #2, #3, #4, #5, and #15.

Current read-only issue #15 evidence:

- The latest clean preservation bundle `SHA256SUMS` verifies.
- Current legacy status still has 35 tracked modified files and 41 untracked
  paths. `git status --short` may collapse untracked directories such as
  `.codex/skills/`, `.codex/hooks/`, `pi-extensions/`, and `temp/`, but the
  untracked inventory count remains 41.
- Against current `dev-root`, tracked dirty files classify as:
  - already represented unchanged on current `dev-root`: governance shape,
    project-state schema/state helpers, wrapper source, prompt registration,
    several fixtures/tests;
  - still different and not safe to discard blindly: `.codex/config.toml`,
    `.project/context_forge_state.json`, helper/project-init/control-plane
    work, systemd/Serena helpers, server launch scripts, inference harness
    files, and selected tests;
  - path-bound operational state: `.codex/config.toml`,
    `.project/context_forge_state.json`, `server-instances/*/run-*`,
    Serena/mentality manifests, project-local skills, and hook trust.
- Against current `dev-root`, untracked dirty files classify as:
  - now represented on `dev-root`: project-local hooks/skills, Gemini/OpenCode
    hooks, Pi dry-run/CLI helpers, and parts of the Pi extension source;
  - still unique issue-slice candidates: stale cleanup/apply scripts,
    live-inference validation, latency diagnostics, live staged fixtures, and
    contextforge wrapper tests;
  - scratch/runtime candidates: `.tmp/*` and
    `temp/roadmap-conductor-skill-design-20260616/*`.
- Before Strategy 1 source rebind, `scripts/inspect_project_init_readiness.py`
  reported the clean root as `invalid_blocked` due to project-state root
  mismatch and the legacy root as valid with Codex `verified`/`passed` and Pi
  `validation_pending`/`mixed`.
- Merged PR #24 completed the first approved source-only pass and retargets
  project-local active surfaces to
  `/home/dgk/workspace/contextforge-slices/repo-local-skills-and-governance`.
  The corrected readiness report now classifies the primary root as `valid`
  with recommended action `resume_validation` and the comparison legacy root as
  `valid` with recommended action `suppress`.

## Approval Boundary

Without explicit approval, only these actions are allowed:

- inspect both worktrees;
- refresh preservation evidence;
- write planning docs or read-only audit tools on a focused branch;
- open a draft PR for the planning artifact;
- update GitHub issue comments with evidence.

The user explicitly approved the first Strategy 1 source-only compatibility
rebind pass, which merged through PR #24. That approval covered
project-local/source retargeting only:

- `.codex/config.toml` command/argument/cwd references;
- `.project/context_forge_state.json` repair through helper-owned project-init
  state semantics;
- Serena and mentality local manifests, launcher, and LSP paths;
- project-local skill references and project-init registration examples;
- planner/readiness evidence, focused tests, docs, issue comments, and a PR.

These actions still require separate explicit approval outside this scoped
source-only branch:

- changing hook trust, user-global Codex config, Pi global config,
  Claude/OpenCode/Gemini config, systemd units, service registry, local tokens,
  or additional project-local state beyond the approved Strategy 1 source pass;
- stopping/restarting services or killing processes;
- renaming, deleting, cleaning, resetting, or rebasing
  `/home/dgk/workspace/context-portal`;
- installing a new Serena backend or changing the existing Serena service
  registration.

## Path-Bound Operating Surfaces

These tracked clean-tree files currently bind operational behavior to
`/home/dgk/workspace/context-portal` and must be included in any approved
rebind plan:

| Surface | Current role | Rebind concern |
| --- | --- | --- |
| `.codex/config.toml` | Project-local Codex MCP and hook activation surface. | All MCP `command`, `args`, and `cwd` entries point at the legacy checkout. Live dirty config differs from clean tracked config and must be preserved before any replacement. |
| `.project/context_forge_state.json` | Project-init authority. | Contains `project.root` and `root_hash`; a new filesystem root is a different project identity, not a blind path edit. |
| `server-instances/serena-context-portal/instance.json` | Serena backend manifest and ContextForge registration metadata. | Contains project root, root hash, Codex config path, LSP paths, and scope notes for the legacy root. |
| `server-instances/serena-context-portal/run-server.sh` | User-systemd Serena backend launch script. | Starts Serena with `--project /home/dgk/workspace/context-portal` and legacy-local `SERENA_HOME`/`lsp.env` paths. |
| `server-instances/serena-context-portal/lsp.env` | Local LSP environment for Serena. | Contains absolute legacy-root LSP paths; treat as local runtime/config state, not a generic source template. |
| `server-instances/mentality/instance.json` | Governance service manifest. | `backend.working_directory` points at the legacy checkout, even though tools require an explicit `repo` argument. |
| `.serena/project.yml` | Serena project metadata for the clean source tree. | `project_name` is still `context-portal`; decide whether this remains a compatibility name or changes under a new root identity. |
| `.codex/skills/*` references | Agent operating instructions. | Some project-local skills intentionally name `/home/dgk/workspace/context-portal` as the current target. If the active root changes, these instructions must change with it or they will retrain the operating agent back to the legacy path. |
| `scripts/register_serena_context_portal_service.py` | Serena registration helper. | Description/tags still express the legacy scoped backend; registration mutation is approval-gated. |
| `scripts/register_project_init_prompt.py` | Registered project-init guidance examples. | Prompt examples and sample project state paths still use the legacy root and can mislead future helper-mediated activation if not updated after a root decision. |
| `scripts/install_user_systemd.py` | User systemd unit generator. | Uses dynamic repo paths for units, but the Serena unit name/description retain `context-portal` compatibility naming. |
| Codex hook entries in `.codex/config.toml` | PreCompact and compact SessionStart continuity hooks. | Hook command uses `git rev-parse --show-toplevel`, so it follows the active project root, but Codex Desktop must trust the hook in the clean project context before relying on it. |

Historical docs, tests, and fixtures also contain
`/home/dgk/workspace/context-portal`. Do not rewrite those wholesale. Many are
intentional historical evidence, compatibility slugs, or fixed-fixture roots.

## Rebind Strategy Decision

An approved retirement must choose one strategy before mutation.

The current parent-owned approval question is:

> Approve a compatibility rebind of the path-bound local surfaces from
> `/home/dgk/workspace/context-portal` to
> `/home/dgk/workspace/contextforge-slices/repo-local-skills-and-governance`,
> with verification only and no reset, delete, rename, service/process restart,
> global trust change, registry mutation, or Pi install/reload in the first
> pass?

The user selected Strategy 1 for the next subgoal and approved the first
source-only pass. Issue #15 is still open because this does not approve runtime
reload, service restart, registry read/write, hook trust mutation, Pi
install/reload, checkout deletion, checkout rename, or final retirement.

### Strategy 1: Compatibility Rebind

Keep existing compatibility service names such as `serena-context-portal` and
`serena_context_portal_server`, but change their active project root to the
clean worktree.

Use when the user wants the fastest operating-surface cleanup and accepts that
some runtime identifiers retain the legacy slug.

Required approval scope:

- update project-local `.codex/config.toml` to launch from the clean root;
- update project-init state/root hash only through helper-owned repair,
  regeneration, or an explicitly approved compatibility migration plan;
- update Serena run script/manifest/LSP local paths for the clean root;
- update project-local skill references that currently instruct agents to use
  `/home/dgk/workspace/context-portal`;
- update project-init prompt examples so future activation guidance does not
  point back at the legacy root;
- reinstall/reload affected user systemd units and restart Serena only after
  approval;
- refresh ContextForge registration readback if manifest changes imply it.

First-pass source status:

- Merged PR #24 retargets the source/project-local surfaces listed above and
  preserves compatibility identifiers such as `serena-context-portal`,
  `serena_context_portal_server`, and project name `context-portal`.
- Helper-owned repair updated `.project/context_forge_state.json` to the clean
  root and left target-client validation pending. It did not overwrite
  unmanaged `.codex/config.toml`, mutate user-global trust, mutate ContextForge
  registry/catalog state, write secrets, or restart services.
- The remaining issue #15 work is the operator-path validation/reload and
  legacy-checkout disposition, not more blind path rewriting.

Risk:

- The service name remains historically `context-portal` while the active
  project root becomes the clean ContextForge worktree.
- Because `.project/context_forge_state.json` encodes a root hash, direct
  path-string replacement is not a safe implementation strategy.

### Strategy 2: New Root Identity

Treat the clean worktree as a distinct project identity with a new root hash and
new Serena service identity, while preserving the legacy Serena service until
the clean identity is verified.

Use when correctness of root-scoped service identity matters more than speed.

Required approval scope:

- helper-mediated project-init/provisioning for the clean root;
- new or migrated Serena backend identity and ContextForge readback;
- new or updated project-local skills that point at the clean root;
- updated project-init prompt examples for the clean project identity;
- clean-root Codex hook trust approval;
- explicit retirement of the legacy Serena service and dirty checkout only
  after target-client-visible validation.

Risk:

- More moving pieces, more registry/systemd work, and a larger approval surface.
- Slower than compatibility rebind, but cleaner if root-scoped service identity
  must not retain the historical slug.

### Strategy 3: Archival-Only Deferral

Keep `/home/dgk/workspace/context-portal` as the live compatibility root for
now, but declare it archival/compatibility debt and require all new source work
to continue from clean `dev-root`.

Use when the user wants to avoid root-identity mutation in the current loop.

Required approval scope:

- no local mutation beyond issue/roadmap documentation;
- issue #15 remains open with owner, impact, trigger, and retirement condition;
- issue #4 remains blocked on root mismatch until Strategy 1 or Strategy 2 is
  approved and applied.

Risk:

- This avoids immediate operational risk but preserves the agent-operating
  surface debt that issue #15 was created to eliminate.

## Pre-Apply Checklist

Before any approved mutation:

1. Capture a fresh preservation snapshot of the legacy checkout:

   ```sh
   git -C /home/dgk/workspace/context-portal status --short --branch
   git -C /home/dgk/workspace/context-portal diff --binary > /tmp/contextforge-dirty-tracked.diff
   git -C /home/dgk/workspace/context-portal ls-files --others --exclude-standard -z \
     > /tmp/contextforge-dirty-untracked.zlist
   ```

2. Verify the clean root is synchronized:

   ```sh
   git -C /home/dgk/workspace/contextforge-slices/repo-local-skills-and-governance status --short --branch
   git -C /home/dgk/workspace/contextforge-slices/repo-local-skills-and-governance rev-parse HEAD origin/dev-root
   ```

3. Run the read-only rebind preflight planner:

   ```sh
   PYTHONDONTWRITEBYTECODE=1 /home/dgk/workspace/context-portal/.venv/bin/python \
     scripts/plan_dirty_checkout_rebind.py \
     --target-root /home/dgk/workspace/contextforge-slices/repo-local-skills-and-governance \
     --legacy-root /home/dgk/workspace/context-portal \
     --client-type codex --client-type pi
   ```

   The report is evidence only. It must not be treated as approval to mutate
   project state, client config, services, registry entries, hook trust, or the
   legacy checkout.

4. Read back active path-bound state if manual line-level confirmation is
   needed:

   ```sh
   rg -n "/home/dgk/workspace/context-portal|/home/dgk/workspace/contextforge-slices/repo-local-skills-and-governance" \
     /home/dgk/workspace/contextforge-slices/repo-local-skills-and-governance/.codex/config.toml \
     /home/dgk/workspace/contextforge-slices/repo-local-skills-and-governance/.codex/skills \
     /home/dgk/workspace/contextforge-slices/repo-local-skills-and-governance/.project/context_forge_state.json \
     /home/dgk/workspace/contextforge-slices/repo-local-skills-and-governance/server-instances/serena-context-portal \
     /home/dgk/workspace/contextforge-slices/repo-local-skills-and-governance/server-instances/mentality/instance.json \
     /home/dgk/workspace/contextforge-slices/repo-local-skills-and-governance/scripts/register_project_init_prompt.py \
     /home/dgk/workspace/contextforge-slices/repo-local-skills-and-governance/scripts/register_serena_context_portal_service.py \
     /home/dgk/workspace/contextforge-slices/repo-local-skills-and-governance/.serena
   ```

5. Confirm the user selected Strategy 1 or Strategy 2 and approved the exact
   mutation set. Strategy 1 first-pass source retargeting is already approved
   for `codex/issue-15-strategy1-source-rebind`; runtime reload, service
   restart, registry readback/write, hook trust mutation, Pi install/reload, and
   legacy-checkout disposition still need separate approval. If Strategy 3 is
   selected for a future loop, update issue #15 and stop without local mutation.

6. Run the read-only readiness reconciler:

   ```sh
   PYTHONDONTWRITEBYTECODE=1 /home/dgk/workspace/context-portal/.venv/bin/python \
     scripts/inspect_project_init_readiness.py \
     --project-root /home/dgk/workspace/contextforge-slices/repo-local-skills-and-governance \
     --compare-root /home/dgk/workspace/context-portal \
     --client-type codex --client-type pi
   ```

Stop if any of these checks fail or if the dirty checkout changed since the
latest preservation snapshot in a way that is not classified.

## Apply Sequence After Approval

The apply sequence must be idempotent: each step reads current state, changes
only the intended stable surface, and verifies by readback.

1. Preserve the legacy checkout again and verify checksums.
2. Apply the chosen rebind strategy to a focused branch or local approved state,
   not directly inside the legacy dirty branch.
   - For Strategy 1, prefer helper-owned project-state repair/regeneration or a
     purpose-built compatibility migration with root-hash readback; do not
     hand-edit only the root string.
   - For Strategy 2, provision or migrate the clean root as a distinct project
     identity before retiring any legacy service.
3. Validate static config:

   ```sh
   python3 - <<'PY'
   import tomllib
   from pathlib import Path
   tomllib.loads(Path(".codex/config.toml").read_text())
   PY
   ```

4. Verify Codex project-local hooks from the clean root:

   ```sh
   codex -C /home/dgk/workspace/contextforge-slices/repo-local-skills-and-governance
   ```

   In the new session, inspect `/hooks` and approve only the clean-root
   project-local hooks if prompted. Do not edit Codex trust files directly.

5. Verify MCP startup from the clean root:

   ```sh
   codex -C /home/dgk/workspace/contextforge-slices/repo-local-skills-and-governance mcp list
   ```

6. Verify ContextForge and canonical service health before retiring anything:

   ```sh
   curl -fsS http://127.0.0.1:4444/health
   systemctl --user --no-pager --plain status contextforge-gateway.service
   systemctl --user --no-pager --plain status contextforge-serena-context-portal.service
   ```

7. Verify target-client-visible project behavior. For Codex, a clean-root
   session must see the intended MCP entries and the continuity hooks. Serena
   validation must prove the target client sees the clean-root scoped service;
   backend-only probes are not sufficient.

8. Verify the operating-agent surface:

   ```sh
   rg -n "/home/dgk/workspace/context-portal" \
     .codex/config.toml .project/context_forge_state.json .codex/skills \
     server-instances/serena-context-portal server-instances/mentality/instance.json \
     scripts/register_project_init_prompt.py scripts/register_serena_context_portal_service.py \
     .serena || true
   ```

   Remaining matches must be intentional historical compatibility references,
   not active launch paths or agent instructions.

9. Only after readback succeeds, archive or rename the legacy checkout. Do not
   delete it as part of the first successful rebind.

## Rollback

Until the legacy checkout is archived and the clean-root path is proven stable,
rollback is path selection, not destructive restoration:

1. Start Codex from `/home/dgk/workspace/context-portal`.
2. Use the preserved snapshot under
   `run/dirty-state-preservation/20260616T114116Z/` or a fresher snapshot to
   recover unmerged local files if needed.
3. Revert only the approved rebind branch or local config changes; do not reset
   unrelated dirty work.
4. Re-run `/hooks`, `codex mcp list`, ContextForge health, and Serena readback
   from the legacy root before claiming rollback success.

## Retirement Acceptance

Issue #15 can close only when:

- the chosen strategy is approved and applied;
- clean-root hooks, skills, MCP entries, ContextForge health, and Serena/project
  behavior are verified through the operator path;
- legacy dirty state is either archived, renamed, or explicitly declared
  archival-only with no active launch paths pointing at it;
- no generated local reports, secrets, runtime DBs, or token values are
  committed;
- remaining unrelated work is merged, tracked in issues, or preserved with
  owner, impact, trigger, and retirement condition;
- the roadmap and issue #15 contain the final evidence and residual risk.
