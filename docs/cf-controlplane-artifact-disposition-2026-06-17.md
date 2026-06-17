# ContextForge `cf-controlplane` Artifact Disposition

Date: 2026-06-17

This report records dirty-checkout cleanup semantics and the successor
activation gates for the migration from the legacy
`/home/dgk/workspace/context-portal` workspace to the canonical
`/home/dgk/workspace/cf-controlplane` workspace.

Cleanup does not mean making `git status` quiet. Cleanup means every
meaningful source or runtime artifact has an intentional relationship to the
new project: tracked, recreated, selectively copied, rewritten, approval-gated,
or archived.

## Current GitHub Gate

- Issue #15 is closed:
  <https://github.com/somebloke1/contextforge-control-plane/issues/15>
- Issue #37 is open for `cf-controlplane` project-local operating-context
  activation:
  <https://github.com/somebloke1/contextforge-control-plane/issues/37>
- Issue #31 is open for Codex `pending_restart` and runtime readback
  after the approved global config migration:
  <https://github.com/somebloke1/contextforge-control-plane/issues/31>
- Current #31 readback: global config/trust migration is verified at disk and
  fresh CLI readback level, but this active Codex Desktop project remains rooted
  in the legacy workspace and has active project-local wrapper processes from
  `/home/dgk/workspace/context-portal`.
- Therefore dirty-checkout retirement is no longer the active tracker, but
  project-local operating-context activation and runtime readback are not
  complete.

## Surface Boundary

This disposition separates legacy/live evidence from mutable validation. The
legacy/live ContextForge surface may be inspected read-only, but must not be
mutated. The ContextForge development Docker surface owns mutable registration,
endpoint, resettable integration, and gateway/app validation. Pi client Docker
and OpenCode client Docker are the only current client foils, and they target
the development Docker surface using the already served local Qwen/llama.cpp
model path as configuration. Evidence must identify the exercised surface.

## Evidence Commands

- `git status --short --branch`
- `git status --short --ignored docker .codex run .project docs/cf-controlplane-migration-stage-roadmap.md .gitignore`
- `find .codex -maxdepth 4 -type f | sort`
- `find docker -maxdepth 4 -type f | sort`
- `find run -maxdepth 3 -type f | sort`
- `rg -n "/home/dgk/workspace/context-portal|context-portal|127\\.0\\.0\\.1:4444|127\\.0\\.0\\.1:4445|172\\.22\\." .codex .project docker docs/cf-controlplane-migration-stage-roadmap.md .gitignore`
- `rg -n "/home/dgk/workspace/context-portal|context-portal" server-instances/serena-context-portal scripts/project_init_common.py scripts/register_serena_context_portal_service.py`
- `gh issue view 15 --json number,title,state,url,labels,assignees,body,comments`
- `gh issue list --state all --limit 30 --json number,title,state,url,labels`

## Disposition Map

| Artifact class | Current paths | Disposition | Reason / migration handling |
| --- | --- | --- | --- |
| Migration roadmap | `docs/cf-controlplane-migration-stage-roadmap.md` | Track/promote | Active stage contract for goal loop, Git cleanup, clone, handoff, and replacement gates. |
| Project status roadmap | `docs/project-status-roadmap-2026-06-16.md` | Track/promote after drift review | Durable roadmap pointer; must stay aligned with the migration stage, issue #37, and issue #31. |
| Codex precompact hook source | `.codex/hooks/contextforge_precompact_continuity.py` | Track/promote | Agent continuity infrastructure; source is project-local and uses repo-root discovery. |
| Hook bytecode | `.codex/hooks/__pycache__/` | Ignore/local only | Generated runtime artifact; must not be copied or tracked. |
| Repo-local skills | `.codex/skills/**` | Track/promote after path cleanup | Agent operating infrastructure; several files still mention the legacy path and need classification/rewrite before `cf-controlplane` handoff. |
| Project-local Codex config | `.codex/config.toml` | Activation-readiness surface / verified state marker | Current branch retargets managed MCP commands and `cwd` values to `/home/dgk/workspace/cf-controlplane`; `codex -C ... mcp list --json` reads the expected project-local entries. |
| Project state | `.project/context_forge_state.json` | Helper-owned activation state / verified | Current branch records `/home/dgk/workspace/cf-controlplane` as root; revision 12 marks status `initialized`, Codex activation `verified`, and validation `passed`. |
| Serena project instance | `server-instances/serena-context-portal/instance.json`, `run-server.sh`, `lsp.env`, `README.md` | Compatibility-classification pending | Current branch retargets the existing compatibility directory to the `cf-controlplane` root but retains the `serena-context-portal` slug and tool names. Generate `serena-cf-controlplane-<hash>` or explicitly retain compatibility naming in a later approved slice. |
| Project-init resource identity | `scripts/project_init_common.py`, `scripts/register_serena_context_portal_service.py` | Needs rewrite or compatibility decision | Uses `contextforge://context-portal/...` resource URIs and `serena-context-portal` registration names/tags. These may be stable compatibility identifiers only if intentionally retained; otherwise they must be renamed/rebound for `cf-controlplane`. |
| Docker ContextForge harness definitions | `docker/contextforge-harness/compose.yml`, `README.md`, `SERVICE_LOCALITY.md`, `scripts/*.sh`, `env/contextforge.env.example` | Track/promote after path/doc cleanup | Defines candidate ContextForge gateway harness. README contains legacy `cd` path and host-specific LAN note that need update or explicit historical/current-host labeling. |
| Docker ContextForge harness runtime state | `docker/contextforge-harness/env/contextforge.env`, `docker/contextforge-harness/evidence/` | Ignore/local only | Contains generated password/env and runtime evidence/DB backup; recreate from examples in `cf-controlplane`. |
| Docker client harness definitions | `docker/client-harness/**` except ignored env/evidence/workspace state | Track/promote | Defines disposable client foils for Pi, OpenCode, Gemini, Codex, and Claude surfaces. |
| Docker client harness runtime state | `docker/client-harness/env/local-llama.env`, `docker/client-harness/evidence/`, `docker/client-harness/workspace/*` | Ignore/local only or recapture after clone | Runtime config/evidence/workspace state; recreate or recapture in new project, never copy blindly. |
| Continuity snapshots and locks | `run/codex-precompact-continuity/**` | Archive/local only | Session-specific continuity evidence; useful for old-session recovery but not source truth for the new workspace. |
| Dirty-state preservation bundles | `run/dirty-state-preservation/**` | Archive/local only | Insurance for missed artifacts; do not track, but preserve until the `cf-controlplane` project context is proven or the user explicitly approves archive disposition. |
| Registration/evidence JSON and local DBs | `run/*registration.json`, `run/*.local.*`, `run/*.db*` | Archive/local only unless summarized | Host/runtime evidence; summarize if needed, do not migrate raw state. |
| Pi global shim source | `pi-extensions/contextforge-global-shim/**` | Needs slice decision | Related to issue #3; likely source artifact, but path defaults and install/reload behavior are approval-gated. |
| ContextForge cleanup scripts | `scripts/apply_contextforge_stale_tool_cleanup.py`, `scripts/inspect_contextforge_cleanup.py` | Needs slice decision | Related to registry cleanup issue #5; must stay non-mutating unless approved. |
| Wrapper diagnostics | `scripts/diagnose_contextforge_wrappers.py`, `scripts/diagnose_mentality_mcp_latency.py`, `tests/test_contextforge_mcp_wrapper.py`, `docs/contextforge-wrapper-lifecycle-runbook.md` | Track/promote if not already represented on `dev-root` | Supports wrapper lifecycle evidence and operations; reconcile against merged issue #1 state before staging. |
| Generated Python bytecode | `scripts/__pycache__/`, `tests/__pycache__/` | Ignore/local only | Generated noise; never migrate. |
| Scratch notes | `.tmp/**`, `temp/**` | Archive-only unless explicitly promoted | Preserved as old workspace evidence, not source of truth. |

## Source-Curation Boundary

This section records the migration-source set for the next subgoal. It is not
an activation-complete claim; issue #37 and issue #31 remain open until their
project-context and runtime-readback gates retire.

Sidecar audit integration:

- Path/secret audit found no real secret material in candidate templates; the
  risk is accidental promotion of generated env/evidence files.
- Dev-root comparison found Docker harnesses and the migration-stage docs absent
  from `origin/dev-root`, making them likely unique migration source.
- Dev-root comparison also found repo-local hooks, skills, and existing roadmap
  docs already present on `origin/dev-root`; integrate those from clean
  `dev-root` plus targeted edits, not by blanket-staging the dirty checkout.

| Source class | Initial curation decision | Condition before clone |
| --- | --- | --- |
| Migration roadmap and artifact disposition docs | Promote through Git | Keep issue #37/#31 state current; do not present these docs as proof that activation/runtime readback is complete. |
| `.gitignore` runtime boundaries | Promote through Git | Preserve ignores for Docker env/evidence, run state, generated caches, and local workspaces while allowing templates and `.gitkeep` files. |
| Codex precompact hook source | Integrate from clean `dev-root` plus targeted edits | Track source only; keep bytecode and generated continuity snapshots ignored/local. Legacy label strings are compatibility metadata, not hardcoded workspace paths. |
| Repo-local skills | Integrate from clean `dev-root` plus path cleanup/classification | Remove accidental legacy absolute paths; retain only deliberate compatibility identifiers with explanation. |
| Docker ContextForge harness definitions | Promote as unique migration source after path/doc cleanup | Keep examples/templates/scripts; keep generated env and evidence ignored. |
| Docker client harness definitions | Promote as unique migration source after portability notes | Keep Dockerfiles, compose, non-secret client config templates, scripts, and workspace `.gitkeep`; keep env/evidence/workspace contents ignored. Document account-local defaults such as Vertex project and authenticated image names as local examples or overridable defaults. |
| Project-local Codex config | Promote after review with evidence | Current branch removes old-root command/cwd references and has CLI readback evidence from `codex -C /home/dgk/workspace/cf-controlplane mcp list --json`. |
| `.project/context_forge_state.json` | Promote helper-owned initialized state | Current branch reflects the `cf-controlplane` root and records the Codex activation state as verified/passed. |
| Serena project instance files | Promote only as compatibility evidence unless separately regenerated | Current branch removes stale root paths but keeps `serena-context-portal` naming as a compatibility decision pending follow-up. |
| Project-init resource identifiers | Needs decision before clone | Decide whether `contextforge://context-portal/...` and `serena-context-portal` names are compatibility identifiers or should be renamed. |

## Cleanup Gate Checklist

This checklist is the enforcement layer for the disposition map. A future
operator must treat any `FAIL` or `PENDING` row as proof that issue #37
activation or issue #31 runtime readback is not complete.

| Gate | Current status | Evidence | Required next action |
| --- | --- | --- | --- |
| GitHub dirty-retirement authority | `PASS / transferred` | Issue #15 is closed; issue #37 and issue #31 own the remaining operating-context and runtime-readback gates. | Do not reopen #15 for ordinary #37 work; update #37/#31 with evidence instead. |
| Runtime restart/readback authority | `FAIL` | Issue #31 is open. Global helper is clean-root by disk/fresh CLI readback, but this Desktop project still launches legacy project-local wrappers. | Validate from the clean-root or future `cf-controlplane` Codex project context, then close/supersede #31 with evidence. |
| Cloneable source artifacts | `PASS` | PR #35 merged the curated migration source into `dev-root` as `75aa437573ac3a8be38f584ab629da2bb0cfa814`; `/home/dgk/workspace/cf-controlplane` is now a clean clone of that branch. | Continue with project-local operating artifact activation; do not copy runtime state as part of this gate. |
| Project-local Codex config | `PASS` | Current branch has no active old-root config references; `codex -C /home/dgk/workspace/cf-controlplane mcp list --json` reads the expected project-local entries. | Keep broader runtime/readback evidence on #31; do not treat it as a blocker for this #37 branch. |
| Project state identity | `PASS` | `.project/context_forge_state.json` root/root hash match `/home/dgk/workspace/cf-controlplane`; revision 12 reports `initialized`, Codex `verified`, and validation `passed`. | Keep deeper client/runtime smoke testing on #31 or future Pi/OpenCode branches. |
| Serena project instance identity | `PENDING compatibility decision` | Existing `server-instances/serena-context-portal/**` points at the `cf-controlplane` root but retains compatibility slug/tool naming; expected `server-instances/serena-cf-controlplane-d46fe58a2a20` is not provisioned. | Generate a `cf-controlplane`-scoped Serena instance or explicitly retain `serena-context-portal` as compatibility naming in a separate approved slice. |
| Project-init resource identity | `PENDING` | `scripts/project_init_common.py` uses `contextforge://context-portal/...`; `scripts/register_serena_context_portal_service.py` uses `serena-context-portal` names/tags. | Decide whether these are durable compatibility identifiers or need a `cf-controlplane` naming migration. |
| Codex hook/skill source | `PASS for tracked source cleanup / PENDING runtime trust` | `.codex/hooks/` and `.codex/skills/` are tracked source surfaces in `cf-controlplane`; active stale old-root readback was fixed, while compatibility identifiers remain documented. | Keep generated hook bytecode ignored; prove hook trust and active runtime origin under #31 or a new `cf-controlplane` Codex project session. |
| Runtime secrets and evidence | `PASS` for ignore posture, `PENDING` for recreation | `.gitignore` ignores Docker env/evidence, run state, local DBs, and generated caches. | Recreate env/evidence in `cf-controlplane`; copy only sanitized summaries if needed. |
| Legacy archive posture | `PASS` as interim, not final | Dirty preservation bundles and legacy workspace remain readable. | Preserve archive until the `cf-controlplane` project context is proven; do not use it as an active source of skills, hooks, MCP commands, or roadmap truth after handoff. |

## Gate Ownership

| Gate | Owner | Next action / retirement condition |
| --- | --- | --- |
| GitHub dirty-retirement authority | Operating agent, with user approval for destructive or global actions | #15 is closed; keep remaining project-context evidence on #37 and #31. |
| Runtime restart/readback authority | Operating agent for evidence; user for Desktop workspace switch/trust actions | Close or supersede #31 after a clean-root or `cf-controlplane` Codex project proves hook/MCP/runtime readback without active legacy project-local wrapper dependence. |
| Cloneable source artifacts | Operating agent | Retired by PR #35 and the clean `cf-controlplane` clone; keep runtime/local state ignored or recreate-only. |
| Project-local Codex config | Operating agent for branch evidence; #31 for broader runtime/readback | Retire the activation-readiness gate when this branch is reviewed; retire broader runtime/readback under #31. |
| Project state identity | ContextForge project-init slice / operating agent | Retire activation-readiness with revision 12 initialized/verified state; keep future client smoke testing under #31 or focused follow-up branches. |
| Serena project instance identity | Serena/project-init slice / operating agent | Generate a new canonical project-scoped Serena instance or classify old `serena-context-portal` as historical compatibility state. |
| Project-init resource identity | Control-plane/project-init slice / operating agent | Decide compatibility naming versus rename; retire when resource URIs and registration names are intentionally documented for `cf-controlplane`. |
| Codex hook/skill source | Operating agent | Track curated source files after path cleanup/classification; retire when new project can read expected hooks and skills from its own root. |
| Runtime secrets and evidence | User plus operating agent | Recreate env/evidence in `cf-controlplane`; retire old runtime state only after new local runtime is validated and no secret-bearing artifact is copied. |
| Legacy archive posture | User plus operating agent | Preserve until the new project is proven; retire only after any destructive archive disposition is explicitly approved. |

## Minimum Next State

Before moving from Subgoal 1 to Git curation, the operator must have:

1. A source-artifact list that can be promoted through Git.
2. A local-only/runtime list that is covered by ignore rules or recreate steps.
3. A path-bound blocker list with a decision for each blocker.
4. GitHub issue #37 updated with the same gate logic.
5. A documented owner and next action for every remaining `FAIL` or `PENDING`
   row, so moving to Git curation cannot be mistaken for cleanup completion.

## Required Before Claiming Activation Complete

1. Issue #37 must prove or explicitly defer project-local operating-context
   activation gates with accepted residual risk. The current branch proves the
   project-local activation-readiness subset, not Codex Desktop approval or
   live runtime readback.
2. Issue #31 must be closed, superseded, or explicitly no longer blocking the
   `cf-controlplane` project-context transition before claiming live runtime
   replacement.
3. The source set intended for cloning into `cf-controlplane` must be staged or
   otherwise made cloneable. This gate is satisfied by PR #35 and merge commit
   `75aa437573ac3a8be38f584ab629da2bb0cfa814`.
4. Runtime/local Codex artifacts must be ignored, recreated, or copied only
   after path and secret review.
5. `.codex/config.toml` and `.project/context_forge_state.json` must be rooted
   at `/home/dgk/workspace/cf-controlplane` and read back cleanly. The current
   branch satisfies this for activation-readiness.
6. `server-instances/serena-context-portal/**`, project-init resource names,
   and Serena registration identifiers must be
   classified as compatibility identifiers or rewritten for `cf-controlplane`.
7. The legacy checkout may remain as archive/insurance, but it must not remain
   the hidden source of active skills, hooks, MCP commands, roadmap truth, or
   Codex project identity.
