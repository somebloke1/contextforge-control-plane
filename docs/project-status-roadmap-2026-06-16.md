# ContextForge Project Status And Roadmap

Date: 2026-06-16

This document summarizes the current project fronts, their completion status,
dependencies, risks, and GitHub cleanup plan after reviewing the eight most
recent ContextForge-related sessions and re-checking the current local repo,
runtime, and GitHub state.

## Evidence Snapshot

Current local checks used for this snapshot:

- `git status --short --branch`
- `git log --oneline origin/dev-root..dev-root`
- `git log --oneline dev-root..HEAD`
- `gh pr list --state all --limit 30`
- `gh issue list --state all --limit 30`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -p 'test_control_plane_*.py'`
- `systemctl --user --no-pager --plain status contextforge-gateway.service contextforge-mentality.service`
- `systemctl --user --no-pager --plain list-units 'contextforge*.service'`
- `curl -fsS -m 5 http://127.0.0.1:4444/health`
- `curl -fsS -m 5 http://127.0.0.1:4444/ready`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/diagnose_contextforge_wrappers.py process-report`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/diagnose_contextforge_wrappers.py time-mentality-path --repo /home/dgk/workspace/context-portal --timeout 20`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/inspect_contextforge_cleanup.py --output /tmp/contextforge-cleanup-current.json`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/inventory_mcp.py`
- `opencode mcp list`
- `codex mcp list`
- `tsc --noEmit --target ES2022 --module NodeNext --moduleResolution NodeNext --skipLibCheck pi-extensions/contextforge-global-shim/index.ts`

Session-derived context came from these rollout summaries:

- `2026-06-14T23-27-11-t9Fk-contextforge_multiclient_opencode_helper_cleanup.md`
- `2026-06-14T22-03-04-8xtk-pi_mcp_mediator_equivalent_interface.md`
- `2026-06-14T20-18-03-pOR8-contextforge_guidance_gap_remediation_and_inspector_fix.md`
- `2026-06-14T15-40-51-va9w-codex_mcp_tooling_comparison_research_with_private_repo_veri.md`
- `2026-06-14T15-33-05-1oSX-contextforge_web_search_public_repo_mapping.md`
- `2026-06-14T08-45-35-2lV4-contextforge_wrapper_proliferation_lifecycle_fix.md`
- `2026-06-14T08-34-22-06gs-contextforge_mentality_timeout_wrapper_proliferation.md`
- `2026-06-14T07-15-16-bjVL-contextforge_tool_validation_in_mathfoundationsml.md`

## Conductor Operating Contract

Use the global `$project-roadmap-conductor` skill as the operating wrapper for
this roadmap. The roadmap is the project-specific execution target; the skill
defines the project-independent discipline for turning roadmap intent into
verified state transitions with no hidden technical, operational,
coordination, documentation, or GitHub debt.

The conductor must start every substantial continuation by refreshing current
evidence, then parsing the roadmap into outcomes, invariants, dependencies,
hidden work, acceptance criteria, evidence requirements, GitHub topology, and
debt policy. It should not treat this document as current truth when live
files, services, tests, issues, PRs, or runtime probes contradict it. If the
roadmap is stale, update this document or the appropriate governance ledger
before proceeding as though the stale claim were true.

This roadmap uses project-specific ContextForge skills as specialized lanes:

- Use `contextforge-service-ops` for gateway, service inventory, bridge/native
  transport, systemd, endpoint, registry, guidance, and runtime health work.
- Use `contextforge-control-plane` for project-init, state, helper, policy,
  inference harness, evidence-ledger, and control-plane code/test work.
- Use `contextforge-project-init` for helper-mediated activation, validation,
  consent, local client binding, and reload guidance.
- Use `contextforge-governance` for `DECISIONS.md`, `ABEYANT_INTENTIONS.md`,
  `OPEN_QUESTIONS.md`, and `mentality` ledger continuity.
- Use `sub-agent-delegator` for model-aware subagent selection, fork-scope
  decisions, sealed delegation contracts, integration criteria, and keeping
  delegated work subordinate to the dynamic goal loop.

The conductor owns sequencing, integration, GitHub topology, issue/PR hygiene,
delegation contracts, acceptance claims, idempotency enforcement, prognosis,
and no-debt closeout. Specialized skills own domain execution inside those
boundaries.

## Dynamic Goal Loop

The durable meta-goal is to move ContextForge from mixed local/roadmap state to
a verified, GitHub-legible, idempotent operating state with no hidden
technical, operational, documentation, or coordination debt.

The root Codex instance is the operating agent and must operate from inside
this persistent goal state. The goal is not only a checklist; it is the control
object that binds the agent's attention, delegation, evidence, and next-action
selection across compaction, interruption, branch switching, and subagent
fan-out. A resumed operating agent should first re-enter the current goal
state, then refresh evidence, then continue the current subgoal or retire it
explicitly.

Formal Codex goal state is part of that operating surface, and the user is the
ultimate authority over goal intent and completion. The user has persistently
authorized and instructed a self-referential goal-maintenance method across
goal iterations: when the current formal goal carries this directive, the
operating agent must preserve it, recognize future user refinements as
authoritative, retire stale dynamic-loop formal goals as complete when
replacement is the goal-maintenance act, and immediately instantiate the
refined formal goal without stale-goal lock-in. This protocol is recorded in
decision `dec-20260616-0002`.

Every roadmap slice must run as a chained sub-goal loop:

1. Refresh current evidence for the slice.
2. Reconcile stale roadmap, GitHub, runtime, and governance claims.
3. Define or confirm the slice contract and acceptance evidence.
4. Extract or update the isolated branch/PR.
5. Verify the real operator path and focused tests/probes.
6. Document evidence, non-actions, residual risk, and approvals.
7. Perform goal maintenance/refinement before selecting the next slice.

The final step is mandatory. At the end of each loop, update the active
meta-goal and sub-goal map: mark completed value, retire or reclassify stale
goals, add newly discovered sub-goals, reprioritize by dependency/risk/value,
and record the next best move in the roadmap, governance ledger, or GitHub
issue/PR where future operators will look. This keeps the roadmap as a dynamic
goal system rather than a static task list.

### Operating-Agent Goal Residency Protocol

The active root agent should maintain four goal layers:

- Meta-goal: verified, idempotent, GitHub-legible ContextForge roadmap
  completion with no hidden debt.
- Formal goal state: the active Codex goal object, including the persistent
  user-authorized interrupt protocol for goal refinement/replacement.
- Current subgoal: the one bounded state transition now being executed.
- Candidate subgoals: queued slices discovered through evidence, roadmap drift,
  subagent audits, and GitHub/runtime state.
- Retired subgoals: completed, superseded, blocked, or deliberately deferred
  goals with evidence and retirement condition.

Each loop must preserve this state explicitly inside the operating agent:

1. Re-enter: after compaction, interruption, or resume, restate the meta-goal,
   current formal goal, current subgoal, evidence authority, and current
   branch/PR topology.
2. Execute: make only the state transition owned by the current subgoal.
3. Integrate: fold subagent outputs, tests, runtime probes, docs, GitHub, and
   governance into one current truth.
4. Refine: update the goal chain by completing, splitting, blocking, deferring,
   or promoting subgoals.
5. Rebind: choose the next current subgoal and record why it is next by
   dependency, risk, user value, and verification readiness.

### Lossless Goal Chaining

When a major subgoal is met, the operating agent must refine and re-initialize
the goal chain without unchosen loss. "Done" for a subgoal means its value,
evidence, non-actions, residual risks, approvals, branch/PR/GitHub state,
documentation state, delegated outputs, and follow-up triggers have been
settled somewhere durable or explicitly rejected.

The transition to the next subgoal must preserve:

- completed value and verification evidence;
- decisions made and options intentionally not taken;
- residual risk with owner, impact, trigger, and retirement condition;
- queued candidate subgoals and dependencies;
- active branch/worktree/PR/issue topology;
- user approvals still required or explicitly absent;
- compaction continuity state needed for the next operating agent turn.

After that settlement, initialize the next subgoal as a fresh bounded state
transition with its own outcome, beneficiary, current state, desired state,
invariants, dependencies, acceptance criteria, evidence plan, and debt policy.
If any information would be dropped merely because attention moved on, the
subgoal is not closed; it is split, deferred, or recorded as tracked residual
work.

### Current Goal Chain

- Active meta-goal: operate as ContextForge roadmap conductor inside a
  persistent dynamic goal loop until the roadmap reaches verified no-debt
  state.
- Retired protocol subgoal: goal-loop and model-aware delegation discipline are
  merged to `dev-root` through PR #8.
- Retired continuity subgoal: project-local Codex compaction continuity hooks are
  merged to `dev-root` through PR #9:
  `PreCompact` preserves local state before compaction and `SessionStart`
  after `compact` restores additive continuity evidence without replacing
  Codex's default compaction prompt.
- Retired continuity hardening subgoal: issue #12 is closed by merged PR #13:
  the hook no longer maintains repo-global latest pointers, restores only
  session-scoped continuity evidence, falls back to event-only evidence when no
  session id is available, removes stale root latest files, and bounds ignored
  snapshot retention.
- Retired hook activation coordination subgoal: issue #11 is closed after
  post-Codex Desktop-restart user-visible readback showed `PreCompact` and
  `SessionStart` enabled at the project level for
  `/home/dgk/workspace/context-portal`. This is the intended non-global scope;
  separate worktrees remain independently trusted by their `.codex/config.toml`
  path if they are actively used.
- Retired wrapper lifecycle subgoal: issue #1 is closed by merged PR #7 at
  merge commit `9d6b539`; post-merge wrapper tests, process report, and
  `mentality_server` timing evidence passed without process termination,
  service restart, or registry/database mutation.
- Landed project-init readiness slice: PR #10 merged to `dev-root` as merge
  commit `f530dda`. It advanced issue #4 with helper-mediated multi-client
  project-init support and recovery-resume idempotency fixes, backed by focused
  compile checks, 165 focused unit tests, changed-diff review, and diff hygiene.
  PR #16 then merged as `f1a6404`, closing the narrow follow-on where
  helper-mediated Serena provisioning requested `write_codex_config=False` but
  the Serena manager still wrote `.codex/config.toml` directly.
  Issue #4 remains open because live project-state reconciliation and readiness
  acceptance are still unproven.
- Active test-portability slice: issue #14 is on
  `codex/clean-worktree-test-hermeticity`. The branch removes unit-test
  dependence on ignored local `.env` and `run/*registration.json` files; focused
  adapter/classification tests, broad control-plane discovery, and full
  `unittest discover` now pass from a clean slice worktree when run with the
  project `.venv` interpreter. A default system `python` without `mcp` /
  `mcpgateway` remains outside that claim.
- Current execution subgoal: issue #15 tracks retiring the dirty
  `/home/dgk/workspace/context-portal` holding checkout as a hidden source of
  truth. This is now part of the current execution priority because stale
  worktree state directly degrades skill discovery, hook trust, formal goal
  continuity, and delegation discipline. A read-only sidecar audit classified
  the remaining dirty checkout state into already-extracted PR #10 files,
  already-merged baseline files, unextracted future slices, and local
  runtime/scratch state; cleanup remains open until those classes are reconciled
  without losing preserved local work.

## Executive Summary

The project is not directionally confused; it is overloaded with several
partially integrated fronts. The core stock ContextForge runtime is alive, the
test suite is green, and the recent work generally reinforces the same
architecture: ContextForge owns canonical service identity, client configs are
consumers/discovery inputs, bridges exist only for missing transports, and
project activation should flow through helper-mediated consent and state.

The immediate problem is integration hygiene:

- GitHub now reflects the accepted integration baseline and the fast-tracked
  foundation merges: `dev-root` and `origin/dev-root` include PR #8 at
  `f8a1aab`, PR #9 at `eb97c66`, and PR #13 at `c6fb551`.
- The current branch has one extra committed feature and a very large dirty
  worktree.
- GitHub has tracking issues #2-#6 for the remaining original active fronts,
  issue #14 for clean-worktree test hermeticity, and issue #15 for dirty
  checkout retirement. Issue #1, issue #11, and issue #12 are closed after
  wrapper lifecycle cleanup, post-restart hook activation, and precompact
  hardening were verified. PR #10 is open for issue #4 project-init readiness;
  PR #7, PR #8, PR #9, and PR #13 are merged foundational/runtime slices.
- Runtime reliability cleanup is retired through PR #7 and post-merge evidence.
  Dirty holding checkout retirement is now the current execution subgoal.
- Several stale-looking Serena test units, one phronesis-devstack Serena unit,
  and matching project/instance directories remain live and should be reviewed
  separately before cleanup.

## Naming Boundary

The project name is ContextForge / Context Forge / `contextforge`.
`context-portal` is deprecated as a human-facing project name. It still appears
as the current repository path, historical/runtime slug, Serena service slug,
project hash input, ContextForge resource URI fragment, and GitHub repository
name. Treat those occurrences as compatibility identifiers until a separate
approved migration defines the exact renames, rollback path, and runtime
readback evidence. See decision `dec-20260616-0001`.

## Idempotency Requirements

Idempotency is a hard requirement for this project phase, not a polish item.
Every lifecycle operation must be safe to inspect, plan, resume, retry, and
reconcile without duplicating services, sessions, client config blocks, gateway
records, project-state jobs, prompts, resources, systemd units, ports, or
cleanup actions.

Required forms:

- Service lifecycle operations must derive stable service identities from
  canonical backend identity, project root, runtime scope, credential scope, and
  exposed resource scope. Re-running create/apply must converge on the same
  service, not mint a sibling.
- Service sessions and wrappers must have ownership, liveness, and parent/session
  attribution. Reconnecting or reloading a client must not leave unbounded
  orphan sessions.
- Service-management handoffs must be plan-first and repeatable. A handoff can
  propose create/update/delete, but it must not mutate until approval is bound
  to stable ids, current readback, and stale-input digests.
- Service CRUD must use read-before-write, idempotency keys or stable external
  ids, post-write readback, and explicit conflict handling. Direct ContextForge
  database writes remain prohibited.
- Cleanup operations must be exact-match, dry-run first, and resumable. Running
  cleanup twice should produce an empty second diff, not errors or broader
  deletion.
- Project-state writes must remain revision-aware, schema-validated, atomic,
  and secret-free. Historical jobs must be terminal, reconciled, or explicitly
  non-blocking; they must not be silently duplicated.
- GitHub housekeeping must be idempotent too: branch slicing should be based on
  explicit file ownership and issue links so rerunning the plan does not create
  duplicate PRs or lose untracked work.

## Front Status

### 1. Stock ContextForge Gateway And Canonical Services

Status: mostly operational; needs cleanup and fresh endpoint proof before any
final declaration.

Current evidence:

- `contextforge-gateway.service` is active.
- `http://127.0.0.1:4444/health` returns `status: healthy`.
- `http://127.0.0.1:4444/ready` returns `status: ready`.
- Active local units include gateway, mentality, ssh-tmux, context7,
  playwright, exa-search, github, web-search, Serena for this repo, Serena
  for phronesis-devstack, and stale-looking Serena test projects.
- `scripts/inspect_contextforge_cleanup.py` reports `guidance_gaps: {}`.
- Current cleanup candidates are no longer only small prompt/resource orphans:
  one orphan prompt, two old project-init resources, and 23 stale
  project-scoped Serena tools are reported by the dry-run inspector.

Dependencies:

- ContextForge API/Admin behavior remains the only approved mutation path.
- Runtime env, local DBs, generated tokens, and local inventory reports remain
  ignored local state.
- Service claims require endpoint and registration readback, not only manifests.
- Service registration, user systemd installation, bridge startup, and
  prompt/resource association must be idempotent: re-running the operator path
  should update or verify the existing canonical record, not create duplicate
  gateway servers, virtual servers, units, ports, prompts, or resources.

Risks:

- The gateway currently runs on `0.0.0.0:4444` according to the systemd status
  command, while repo docs describe local loopback HTTP. Decide whether this is
  intentional local exposure or a config drift to close.
- `/sse` curl probes behave as open event streams and time out after receiving
  headers; that is not itself failure, but final verification should use
  protocol-aware MCP probes.
- The current Serena service for this repo is native streamable HTTP; `/sse`
  returning 404 on its native port is expected unless a separate SSE bridge is
  explicitly required.

Prognosis: good. This front looks close to operationally complete after cleanup
and a fresh service/readback verification run.

### 2. Control-Plane RFC / Project-Init MVS

Status: test-green and coherent, but not yet a polished operator-grade product.

Current evidence:

- Full tests pass from the issue #14 clean slice with the project `.venv`
  interpreter: 437 tests OK.
- Focused control-plane discovery passes from the issue #14 clean slice with
  the project `.venv` interpreter: 301 tests OK.
- `.project/context_forge_state.json` currently has `status: initialized`.
- The current `.project/context_forge_state.json` shape has service records
  and no top-level activation job list. Recorded Codex target-client validation
  is `passed`, but ContextForge gateway readback fields are still
  `not_checked`.
- The project state still carries deprecated project label `context-portal`;
  per `dec-20260616-0001`, that is naming debt unless a compatibility-safe
  migration is planned and approved.

Dependencies:

- `.project/context_forge_state.json` is the project-local state authority.
- Mutating project-init work depends on consent receipts and helper-mediated
  apply jobs.
- User-global trust, global config writes, token material, secrets, catalog
  promotion, and remote exposure remain separately approved workflows.
- Project-init plan/apply/validate/reconcile must be idempotent across retries:
  the same approved plan digest and selected stable service ids must converge on
  the same project state, client config blocks, activation job, and validation
  records.

Risks:

- State no longer exposes the historical activation-job shape described by
  older issue text, but it does expose `not_checked` gateway readback and the
  deprecated project label. The project should reconcile those fields before
  declaring state hygiene complete.
- Some implementation remains helper/script-oriented rather than a cohesive
  production operator CLI.
- Live inference validation exists as a script path but should be re-run only
  intentionally because it invokes real model/client behavior.

Prognosis: good for the RFC/MVS; moderate for production readiness until
operator UX and state reconciliation are tightened.

### 3. Client Bootstrap And Wrapper Lifecycle

Status: retired through merged PR #7 and post-merge verification.

Current evidence:

- `opencode mcp list` shows one global MCP server, `contextforge-helper`, and
  it is connected.
- `codex mcp list` shows project-local ContextForge-backed wrappers for
  canonical services plus `contextforge-helper`.
- The mentality path is fast across all layers:
  local registry, stdio backend, direct bridge, ContextForge virtual server,
  and wrapper route all returned successfully in under a second.
- Current wrapper diagnostics after Codex Desktop restart and the wrapper idle
  window report:
  - `codex_contextforge_wrapper`: 0
  - `contextforge_helper`: 12
  - `node_repl`: 12
  - total wrapper `CLOSE-WAIT` count is 0
  - filtered port-4444 socket readback shows no `CLOSE-WAIT` or `TIME-WAIT`
    sockets and one established Chrome network-service connection to
    `mcpgateway`, not a stale Codex Desktop wrapper connection
- Subagent and parent evidence showed transient wrapper bursts drain without
  process termination: 45 wrappers / 45 wrapper `CLOSE-WAIT`, then 18 / 18,
  then 0 / 0 after the idle window. The runbook now treats immediate counts as
  snapshots and bounded idle-window drain as the acceptance signal.

Dependencies:

- The hardened wrapper launcher and `.codex/config.toml` managed blocks must be
  integrated cleanly before stale processes can be considered fixed for future
  launches.
- Existing stale processes require Codex Desktop relaunch or exact-match cleanup
  following `docs/contextforge-wrapper-lifecycle-runbook.md`.
- Claude Desktop still depends on stdio wrapper behavior because its installed
  config schema does not expose direct URL/header MCP entries.
- Wrapper lifecycle management must be idempotent at the session level: repeated
  client reloads, reconnects, or helper calls must reuse or retire existing
  wrappers predictably and must not accumulate orphan processes or `CLOSE-WAIT`
  sockets.

Risks:

- Future tool timeouts may still be caused by stale Codex-facing wrappers even
  when ContextForge backend services are healthy; current evidence shows this
  condition is not present now.
- Broad process killing or service restarts are unsafe; cleanup must target
  exact wrapper process shapes after evidence capture.
- The current wrapper fix affects new launches, not already-running stale
  wrappers.

Prognosis: retired. Continue monitoring through normal runtime probes, but
wrapper lifecycle is no longer the current execution front.

### 4. Pi Global Shim And Prompt/Resource Parity

Status: source-ready; a different user-global Pi shim is installed.

Current evidence:

- `pi-extensions/contextforge-global-shim/index.ts` typechecks with `tsc`.
- `scripts/manage_pi_global_shim.py status` reports `installed_different`:
  the repo source digest differs from
  `/home/dgk/.pi/agent/extensions/contextforge-global-shim`.
- Focused regression
  `test_pi_extension_source_registers_bootstrap_helper_tools_without_bridge_reuse`
  passes.
- `scripts/manage_pi_global_shim.py plan` proposes an approval-gated
  user-global install/upgrade and then a Pi `/reload`.
- The reviewed session established the intended Pi behavior: expose equivalent
  prompt/resource guidance semantics through the mediator, not just imported
  MCP tools.

Dependencies:

- Canonical ContextForge prompts/resources must remain useful and current.
- `scripts/manage_pi_global_shim.py` owns global shim status/plan/install.
- Installing/reloading the Pi global extension is user-global mutation and
  requires explicit approval.
- Pi global shim status/plan/install must be idempotent. Re-running install
  after approval should converge on the same target extension files and
  activation metadata, and reloading Pi should not duplicate imported tools,
  prompt/resource caches, or guidance lookup registrations.

Risks:

- Passing source tests does not prove the user-global Pi extension matches this
  repo source; current status proves it does not.
- Pi reload behavior and `globalThis` persistence need live verification.
- Fuzzy prompt/resource matching may need edge-case hardening after real use.

Prognosis: good for source readiness, incomplete for live Pi use until the
approval-gated install/upgrade and `/reload` are performed.

### 5. Guidance Library And Registry Cleanup

Status: guidance gaps resolved; orphan cleanup remains.

Current evidence:

- The cleanup inspector reports no guidance gaps.
- Current registry summary reports 126 tools, 82 prompts, 92 resources, and 18
  servers.
- Current cleanup candidates:
  - delete prompt `project-init-prompt`
  - delete resource `contextforge://context-portal/project-init/v15`
  - delete resource `contextforge://context-portal/project-init/v14`
  - review 23 stale project-scoped Serena tools for the
    `serena-phronesis-devstack-cdb531b045e5` service before deletion

Dependencies:

- Cleanup must use ContextForge APIs/Admin behavior only.
- The orphaned `ssh-tmux-cleanup-dead-sessions` tool was intentionally
  preserved in earlier work and should not be deleted without separate
  approval.
- Prompt/resource/tool cleanup must be idempotent and exact-match. The dry-run
  report is the deletion contract; applying it must delete only approved ids,
  record rollback/readback evidence, and leave a second dry run empty for the
  approved candidate set.

Risks:

- Cleanup candidates can drift as prompt/resource registration changes.
- Deletion needs rollback/readback evidence, not only a dry-run candidate list.

Prognosis: close. Treat as a small approved cleanup PR/run.

### 6. Inventory And Service Identity

Status: broad inventory coverage exists; classification remains an ongoing
catalog-management task.

Current evidence:

- `scripts/inventory_mcp.py` wrote the ignored local report
  `inventory/contextforge-services.local.json`.
- Current inventory summary: 197 entries, 193 enabled.
- Coverage includes AnythingLLM, Claude Desktop, Claude Code, Codex
  Terminal/project configs, Gemini CLI, OpenCode, Pi Coding Assistant, and
  workspace-local configs.
- `web-search` maps to sibling backend repo `/home/dgk/workspace/web_search`
  with upstream `https://github.com/somebloke1/web_search`; package name
  `pi-web-access` is not the service identity.

Dependencies:

- Deduplicate by backend package/server, runtime scope, credential scope, and
  exposed resource scope.
- Client config names do not define ContextForge service identity.
- Noncanonical direct entries such as desktop-commander, gemini-mcp,
  filesystem, zai-mcp-server, invoiceapi, and workspace governance services
  require explicit scope decisions before promotion.
- Service-management triage must be idempotent: the same inventory evidence
  should classify the same backend into the same exclude/project-local/candidate
  handoff bucket, and approved promotions must use stable ids instead of
  client-specific names.

Risks:

- Inventory is local and drift-prone.
- Pi package entries are numerous and should not be treated as one service per
  project/worktree.
- Service promotion too early will recreate the old client-config-driven
  duplication problem.

Prognosis: good as an inventory/discovery substrate. Catalog expansion should
remain gated by service-management handoff and explicit approval.

### 7. Serena Project-Scoped Services

Status: canonical Serena for this repo is active; stale test units remain.

Current evidence:

- `contextforge-serena-context-portal.service` is active.
- `contextforge-serena-phronesis-devstack-cdb531b045e5.service` is active.
- Eight `contextforge-serena-test-new-proj-*` units are active and enabled.
- Matching test project directories still exist under `/home/dgk/workspace/`.
- Matching stale test service-instance directories still exist under
  `server-instances/`.

Dependencies:

- Serena remains project-scoped and should not become a global Codex service.
- Cleanup must distinguish canonical project services from disposable test
  artifacts.
- Serena create/status/verify/remove flows must be idempotent. The same project
  root must resolve to the same Serena instance slug, port, unit, virtual
  server, and project-local config block; stale test cleanup must leave a second
  status pass with no extra units to remove.

Risks:

- Active stale test units consume ports and confuse inventory/readback.
- Removing units before confirming their directories and manifests are stale
  risks deleting a legitimate project service.

Prognosis: straightforward cleanup after review and explicit approval.

## GitHub Housekeeping

Current GitHub state:

- Remote: `https://github.com/somebloke1/contextforge-control-plane.git`
- Default branch: `dev-root`
- `gh auth status` is authenticated as `somebloke1`.
- Merged PR [#7: ContextForge: wrapper lifecycle cleanup](https://github.com/somebloke1/contextforge-control-plane/pull/7)
  landed as merge commit `9d6b539`.
- Merged PR [#10: ContextForge: helper-mediated project init readiness](https://github.com/somebloke1/contextforge-control-plane/pull/10)
  landed as merge commit `f530dda`. The branch was merged forward to current
  `origin/dev-root` at `f285f89`, then advanced to `e38c5df` for
  recovery-resume idempotency before merge.
  Evidence was recorded in PR comments
  `https://github.com/somebloke1/contextforge-control-plane/pull/10#issuecomment-4717222163`,
  `https://github.com/somebloke1/contextforge-control-plane/pull/10#issuecomment-4717512657`,
  and
  `https://github.com/somebloke1/contextforge-control-plane/pull/10#issuecomment-4717661173`.
  No GitHub status checks were configured for the PR branch.
- Merged PR [#16: ContextForge: honor Serena config write suppression](https://github.com/somebloke1/contextforge-control-plane/pull/16)
  landed as merge commit `f1a6404`. It is the narrow issue #4 follow-on that
  makes `manage_serena_project_instance.py create()` honor
  `write_codex_config=False` while preserving the normal CLI default.
- Merged PR [#8: ContextForge: roadmap and governance operating discipline](https://github.com/somebloke1/contextforge-control-plane/pull/8)
  landed as merge commit `f8a1aab`.
- Merged PR [#9: ContextForge: project-local precompact continuity hook](https://github.com/somebloke1/contextforge-control-plane/pull/9)
  landed as merge commit `eb97c66`.
- Merged PR [#13: ContextForge: harden precompact continuity retention](https://github.com/somebloke1/contextforge-control-plane/pull/13)
  landed as merge commit `c6fb551`.
- GitHub tracking issues now hold the active cleanup fronts and operating
  protocol debt:
  - [#2: Review and clean stale Serena test project units](https://github.com/somebloke1/contextforge-control-plane/issues/2)
  - [#3: Deploy and verify Pi global ContextForge shim prompt/resource parity](https://github.com/somebloke1/contextforge-control-plane/issues/3)
  - [#4: Polish project-init operator state reconciliation and readiness](https://github.com/somebloke1/contextforge-control-plane/issues/4)
  - [#5: Perform approved ContextForge registry orphan prompt/resource cleanup](https://github.com/somebloke1/contextforge-control-plane/issues/5)
  - [#6: Triage noncanonical inventory entries and service-management handoffs](https://github.com/somebloke1/contextforge-control-plane/issues/6)
  - [#14: Make clean-worktree test suite independent of ignored local evidence](https://github.com/somebloke1/contextforge-control-plane/issues/14)
  - [#15: Retire dirty holding checkout as agent operating surface debt](https://github.com/somebloke1/contextforge-control-plane/issues/15)
- Closed coordination issues:
  - [#1: Control Codex ContextForge wrapper lifecycle and stale process cleanup](https://github.com/somebloke1/contextforge-control-plane/issues/1)
  - [#11: Reconcile project-local precompact hook visibility across active worktrees](https://github.com/somebloke1/contextforge-control-plane/issues/11)
  - [#12: Prevent ad-hoc compactions from replacing conductor continuity pointer](https://github.com/somebloke1/contextforge-control-plane/issues/12)
- Local `dev-root` and `origin/dev-root` are synchronized after the
  fast-tracked foundation merges and follow-up status-only roadmap updates.
- Holding worktree `/home/dgk/workspace/context-portal` is on
  `codex/contextforge-wrapper-lifecycle`, one commit beyond `dev-root`, and
  remains the intentionally dirty source for not-yet-extracted slices.
- Branch `codex/wrapper-lifecycle-cleanup` was merged through PR #7; the remote
  branch was deleted after merge. The local slice worktree remains only as a
  temporary readback artifact until local worktree cleanup is performed
  deliberately.
- PR #8 is merged; its former slice worktree now checks out clean `dev-root`.
- PR #9 is merged; its remote branch is deleted, while the local merged worktree
  remains until local worktree cleanup is approved or performed deliberately.
- Issue #11 is closed. The dirty `codex/contextforge-wrapper-lifecycle`
  worktree has received the hardened hook and config, passed TOML/direct hook
  smoke checks, and has been user-approved in Codex. After a Codex Desktop
  restart, the user-visible project-level hook view for
  `/home/dgk/workspace/context-portal` showed `PreCompact` and `SessionStart`
  enabled. That is the intended non-global scope; separate worktrees remain
  independently keyed by their own `.codex/config.toml` path and may require
  separate approval when actively used.
- Issue #12 captured the ad-hoc compaction continuity risk and is closed by PR
  #13. The hook contract is now session-scoped latest pointers, event-only
  fallback without a shared unknown pointer, stale global latest cleanup, and
  bounded retention of ignored local snapshots.

### Desired GitHub State

GitHub should make the project state legible without requiring access to this
dirty local checkout. The target state is:

- `origin/main`: protected bootstrap baseline only.
- `origin/dev-root`: current integration baseline for accepted local work.
- One draft PR per active front, all targeting `dev-root`.
- One open tracking issue per active front, linked from the matching PR.
- No long-lived feature branch that mixes runtime cleanup, helper architecture,
  Pi extension work, governance ledgers, and generated/local diagnostic state.
- No PR should include ignored runtime state, secret material, local databases,
  generated inventory files, or broad unrelated formatting churn.

### Current Branch Topology

Current local topology:

```text
main / origin/main
  7572018 Bootstrap repository branch policy

origin/dev-root and dev-root
  include f8a1aab Merge pull request #8
  include eb97c66 Merge pull request #9
  include c6fb551 Merge pull request #13
  include 9d6b539 Merge pull request #7

merged runtime worktrees
  /home/dgk/workspace/contextforge-slices/wrapper-lifecycle-cleanup
    codex/wrapper-lifecycle-cleanup -> PR #7 merged, remote branch deleted

open draft PR worktrees
  /home/dgk/workspace/contextforge-slices/helper-multiclient-project-init
    codex/helper-multiclient-project-init -> PR #10

merged foundation worktrees
  /home/dgk/workspace/contextforge-slices/repo-local-skills-and-governance
    dev-root -> PR #8, PR #9, and PR #13 merged
  /home/dgk/workspace/contextforge-slices/precompact-continuity-hook
    codex/precompact-continuity-hook -> PR #9 merged, remote branch deleted
  /home/dgk/workspace/contextforge-slices/precompact-conductor-pointer
    codex/precompact-conductor-pointer -> PR #13 merged, remote branch deleted

historical baseline shown before synchronization
  9d41c6b Add ContextForge control plane initiative plan

holding worktree
  /home/dgk/workspace/context-portal
  codex/contextforge-wrapper-lifecycle
    ae5a434 Implement ContextForge helper project init workflow
    one commit beyond dev-root with many tracked modifications and untracked files

duplicate local branch with no separate worktree
codex/contextforge-helper-project-init
  ae5a434 Implement ContextForge helper project init workflow
```

The two holding feature branches currently point at the same commit. The dirty
holding worktree is on `codex/contextforge-wrapper-lifecycle` and contains a
large uncommitted mix of newer fronts.

### GitHub Migration Plan

Phase 0: preserve local state.

- Do not reset, rebase, or force-push from the dirty worktree.
- Treat this phase as idempotent preservation work. If interrupted, re-running
  the capture commands must refresh the same named evidence files without
  deleting local changes.
- Capture a current patch bundle before branch surgery:
  `git diff > /tmp/context-portal-current-worktree.patch`
- Capture untracked file inventory:
  `git ls-files --others --exclude-standard > /tmp/context-portal-untracked-files.txt`
- Capture untracked file contents before branch surgery:
  `git ls-files -z --others --exclude-standard | tar --null -T - -cf /tmp/context-portal-untracked-files.tar`
- Keep `codex/contextforge-wrapper-lifecycle` as the temporary holding branch
  until all slices are extracted.

Phase 1: publish the accepted integration baseline and fast-track foundation.
Status: completed.

- Evidence: local `dev-root` and `origin/dev-root` are synchronized and include
  merge commit `c6fb551`.
- The former 11-commit local lead has been synchronized to GitHub without a
  baseline PR because `dev-root` is the integration branch.
- PR #8, PR #9, and PR #13 were marked ready and merged to `dev-root`.
- Re-run focused tests before merging dependent slices, but do not repeat
  baseline push work unless evidence shows the refs diverged again.

Phase 2: create branch/PR slices from `dev-root`.

Recommended PR slices. Rows with PR links are already extracted; rows without
PR links are planned slices whose branch names can still be adjusted during
extraction if current evidence proves a better review boundary.

| Branch | Issue | Intended contents | First checks |
| --- | --- | --- | --- |
| `codex/wrapper-lifecycle-cleanup` | [#1](https://github.com/somebloke1/contextforge-control-plane/issues/1) / [PR #7](https://github.com/somebloke1/contextforge-control-plane/pull/7) | `scripts/contextforge_mcp_wrapper.py`, `scripts/diagnose_contextforge_wrappers.py`, `tests/test_contextforge_mcp_wrapper.py`, and `docs/contextforge-wrapper-lifecycle-runbook.md`. Project-local `.codex/config.toml` managed-block rewrites stay with project-init unless a later wrapper-only config delta is needed. | wrapper unit tests; wrapper process report; mentality timing path |
| `codex/helper-multiclient-project-init` | [#4](https://github.com/somebloke1/contextforge-control-plane/issues/4) / [PR #10](https://github.com/somebloke1/contextforge-control-plane/pull/10) | `scripts/contextforge_helper_mcp.py`, `scripts/control_plane_project_init_helper.py`, project-state/schema updates, Codex/OpenCode/Gemini project-init hooks, project-init docs, and activation workflow tests. | `test_project_init_activation_workflow.py`; `test_project_init_scripts.py`; control-plane discovery |
| `codex/pi-global-shim-parity` | [#3](https://github.com/somebloke1/contextforge-control-plane/issues/3) | `pi-extensions/contextforge-global-shim/`, `scripts/manage_pi_global_shim.py`, Pi dry-run/CLI helpers, Pi prompt/resource parity docs/tests. | TypeScript `tsc`; focused Pi regression; `manage_pi_global_shim.py status/plan` |
| `codex/live-validation-and-registry-cleanup-tools` | [#5](https://github.com/somebloke1/contextforge-control-plane/issues/5) | `scripts/inspect_contextforge_cleanup.py`, `scripts/apply_contextforge_stale_tool_cleanup.py`, `scripts/run_live_inference_validation.py`, live staged fixtures if they are sanitized and intended to be tracked. | cleanup inspector dry-run; inference harness tests; secret scan by review |
| `codex/service-inventory-triage` | [#6](https://github.com/somebloke1/contextforge-control-plane/issues/6) | inventory classification docs or scripts only; no generated `*.local.json`; any service-management handoff documentation. | inventory script; no generated/local files tracked |
| `codex/serena-stale-unit-cleanup` | [#2](https://github.com/somebloke1/contextforge-control-plane/issues/2) | documentation and cleanup plan for stale Serena test units, plus narrow manager fixes if needed. Runtime stop/disable actions should be recorded but not hidden in code commits. | systemd list/readback; manager tests if code changes |
| `codex/clean-worktree-test-hermeticity` | [#14](https://github.com/somebloke1/contextforge-control-plane/issues/14) | Unit-test and fixture cleanup so clean slice worktrees do not depend on ignored `.env` or `run/*registration.json` files. | focused adapter/classification tests; broad control-plane discovery; full `unittest discover` |
| `codex/repo-local-skills-and-governance` | merged cross-links #1-#6 as needed / [PR #8](https://github.com/somebloke1/contextforge-control-plane/pull/8) | `.codex/skills/`, `DECISIONS.md`, `ABEYANT_INTENTIONS.md`, `OPEN_QUESTIONS.md`, and this roadmap if intentionally tracked. | governance CRUD shape checks; ledger-focused tests |
| `codex/precompact-continuity-hook` | merged cross-cutting continuity slice / [PR #9](https://github.com/somebloke1/contextforge-control-plane/pull/9) | Project-local Codex `PreCompact` and `SessionStart`/`compact` hooks, ignored continuity snapshots, hook tests, and operator documentation. Does not override Codex's default compaction prompt. | precompact/session-start hook unit tests; hook smoke invocation; config guardrail check |
| `codex/precompact-conductor-pointer` | closed [#12](https://github.com/somebloke1/contextforge-control-plane/issues/12) / merged [PR #13](https://github.com/somebloke1/contextforge-control-plane/pull/13) | Session-scoped continuity latest pointers, event-only fallback without a shared unknown pointer, stale root latest cleanup, bounded snapshot/session retention, hook tests, and hook documentation. | precompact/session-start hook unit tests; `py_compile`; TOML config parse; `git diff --check` |

### Executable Slice Contracts

#### Precompact continuity hardening -> issue #12

- Outcome: project-local Codex compaction continuity remains useful without any
  ad-hoc session becoming a repo-wide mission pointer or growing ignored event
  state indefinitely.
- Beneficiary: operators and future agents resuming ContextForge work after
  compaction, especially when multiple Codex sessions are active.
- Current state: closed. PR #13 is merged to `dev-root`; issue #12 is closed;
  issue #11 is also closed after post-restart project-level hook readback.
- Desired state: achieved in tracked source. PR #13 stores session latest
  snapshots under `sessions/<session-key>/`, stores event-only evidence when no
  session id is available, removes stale root-level latest files, and enforces
  bounded event and session retention.
- Invariants: do not set `compact_prompt`, `experimental_compact_prompt_file`,
  or `model_auto_compact_token_limit`; do not make hook output authoritative
  over Codex's default compaction summary or the active user-selected goal; do
  not write tracked runtime snapshots.
- Dependencies: PR #9 baseline, current Codex hook payload identity fields or
  `CODEX_THREAD_ID`, and ignored `run/` state.
- Hidden work: the hardened hook was propagated into the dirty
  `codex/contextforge-wrapper-lifecycle` holding worktree and direct smoke/TOML
  checks passed; the user subsequently approved those hooks. Post-restart
  Codex Desktop readback now confirms project-level `PreCompact` and
  `SessionStart` activation for `/home/dgk/workspace/context-portal`.
- Acceptance: completed. Hook tests prove session isolation, no-session event-only
  fallback, bounded event retention, bounded session retention, stale root
  latest cleanup, idempotent event ids, and sensitive value redaction; docs
  explain non-commandeering semantics and retention.
- Evidence: `tests.test_codex_precompact_continuity_hook` passed with 14 tests
  on both the PR branch and merged `dev-root`; `py_compile` for the hook and
  tests passed; TOML parse of `.codex/config.toml` passed; `git diff --check`
  passed; direct dirty-checkout hook smoke passed.
- Debt policy: issue #12 and issue #11 are retired. Future worktree-specific
  hook trust prompts are expected Codex behavior unless a new active worktree
  needs approval and fails to show installed project-local hooks.

#### Wrapper lifecycle cleanup -> issue #1

- Outcome: Codex-facing ContextForge wrappers stop accumulating duplicate
  long-lived sessions and stale `CLOSE-WAIT` sockets.
- Beneficiary: operators using Codex Desktop MCP tools through ContextForge.
- Current state: closed. PR #7 is merged to `dev-root` at `9d6b539`; issue #1
  is closed; the remote wrapper branch is deleted. The compact wrapper process
  report at `2026-06-16T09:41:00Z` showed no `codex_contextforge_wrapper`
  processes and `close_wait_total: 0`, with nine `contextforge_helper` and
  nine `node_repl` processes. The `mentality_server` path still succeeds in
  under a second, including the stdio wrapper route at about 357 ms. Live audit
  also observed transient wrappers drain 45 -> 18 -> 0 without process
  termination.
- Desired state: new wrapper launches carry attribution, idle/parent shutdown,
  session handling, and diagnostics; existing stale wrappers are cleared only by
  Codex relaunch or approved exact-match PID cleanup.
- Invariants: do not kill broad Python/mcpgateway processes, restart backend
  services, delete registry records, or assume wrapper cleanup proves backend
  health.
- Dependencies: Phase 0 preservation, pushed `dev-root`, wrapper code/tests,
  current diagnostic report, and explicit approval before process termination.
- Hidden work: none accepted for this slice. Issue #1 body still has historical
  165-count context, but current comments record zero-wrapper/zero-`CLOSE-WAIT`
  evidence, transient 45 -> 18 -> 0 drain evidence, the diagnostic attribution
  fallback, and post-merge verification. Socket ownership remains part of the
  evidence model for future regressions.
- Acceptance: wrapper unit tests pass; process report after cleanup or idle
  retirement shows no unbounded duplicate growth; mentality path remains fast;
  cleanup is dry-run and exact-PID scoped if process termination is used. The
  current evidence satisfies the no-stale-wrapper runtime check without process
  termination. PR #7 is merged and issue #1 is closed.
- Evidence: `tests/test_contextforge_mcp_wrapper.py`,
  `scripts/diagnose_contextforge_wrappers.py process-report`,
  `scripts/diagnose_contextforge_wrappers.py time-mentality-path --repo
  /home/dgk/workspace/context-portal --timeout 20`, `codex mcp list`.
- Debt policy: retired. Future wrapper regressions should open a new issue with
  fresh runtime evidence rather than reopening stale pre-merge counts.

#### Stale Serena test units -> issue #2

- Outcome: disposable Serena test instances are classified and safely removed
  or explicitly retained.
- Beneficiary: operators reading systemd, inventory, registry, and port state.
- Current state: this repo's Serena unit is active; phronesis-devstack Serena is
  active; eight `contextforge-serena-test-new-proj-*` units and matching
  workspace plus `server-instances/` directories exist. A read-only
  classification pass was recorded on issue #2 at
  `https://github.com/somebloke1/contextforge-control-plane/issues/2#issuecomment-4718131243`:
  the context-portal unit is canonical, phronesis-devstack is intentionally
  retained, and the eight `test-new-proj*` units are disposable candidates only
  after explicit approval. The same pass found three empty `serena-tmp*`
  server-instance directories with no installed or loaded user units.
- Desired state: legitimate project-scoped Serena services remain active;
  disposable test units/directories/registry records are removed only after
  approval and exact-match readback.
- Invariants: do not stop `contextforge-serena-context-portal.service`; do not
  delete another workspace's legitimate Serena service; do not treat a path
  name alone as proof of disposability.
- Dependencies: fresh systemd list, `server-instances/*/instance.json`
  readback, target workspace directory checks, and approval before stop/disable
  or deletion.
- Hidden work: reconcile stale project-scoped registry tools reported by
  `scripts/inspect_contextforge_cleanup.py`; issue #2 and issue #5 overlap and
  must not double-delete the same logical service assets.
- Additional risk: current live Serena listeners on ports `9108` and
  `9110`-`9117` are bound to `0.0.0.0`; exposure changes remain approval-gated
  and must not be bundled into stale test-unit cleanup.
- Acceptance: retained services have a rationale; removed services have dry-run
  evidence, stop/disable/delete readback, and a second status/cleanup pass with
  no unexpected candidates.
- Evidence: `systemctl --user --no-pager --plain list-units
  'contextforge-serena-test*' 'contextforge*serena*'`, `find
  server-instances -maxdepth 2 -name instance.json -path '*serena-test*'
  -print`, workspace test-directory inventory, cleanup inspector readback.
- Debt policy: any retained stale-looking unit must record owner, target
  project root, impact, review trigger, and removal condition.

#### Pi global shim parity -> issue #3

- Outcome: Pi's user-global ContextForge shim exposes the same helper and
  prompt/resource guidance semantics as the repo source intends.
- Beneficiary: Pi users activating ContextForge services or reading guidance
  through Pi extension tools.
- Current state: TypeScript source typechecks; focused regression passes; the
  user-global target exists but has a different digest from repo source.
- Desired state: repo source merged; user-global install/upgrade is performed
  only after explicit approval; Pi `/reload` happens before validation; live Pi
  readback proves the changed tools are active.
- Invariants: do not mutate `/home/dgk/.pi/agent/extensions/` or require a Pi
  reload without explicit approval; do not write secrets; do not duplicate
  imported tools or guidance caches.
- Dependencies: pushed baseline, Pi source branch/PR, `manage_pi_global_shim.py
  status/plan`, user approval token
  `I_APPROVE_USER_GLOBAL_PI_EXTENSION_WRITE`, and Pi reload.
- Hidden work: update issue #3 from "deployment pending" to
  `installed_different`; plan live validation steps that use Pi-visible routes,
  not backend-only substitutes.
- Acceptance: `tsc` and focused tests pass; install plan is approved and
  applied; Pi reload is confirmed; live Pi validation proves parity or records
  an explicit skipped/presumed-working status with rationale.
- Evidence: `tsc --noEmit --target ES2022 --module NodeNext
  --moduleResolution NodeNext --skipLibCheck
  pi-extensions/contextforge-global-shim/index.ts`, focused Pi regression,
  `scripts/manage_pi_global_shim.py status`, `scripts/manage_pi_global_shim.py
  plan`, post-install digest readback, Pi-visible validation transcript.
- Debt policy: source-ready is not live-ready; if install/reload is deferred,
  issue #3 stays open with the approval blocker and target/source digests.

#### Project-init readiness polish -> issue #4

- Outcome: project-init state and helper UX are operator-grade, current, and
  consistent with helper-mediated consent.
- Beneficiary: maintainers activating ContextForge services in this repo and
  future project worktrees.
- Current state: PR #10 merged the helper-mediated multi-client project-init
  slice to `dev-root` at `f530dda`, including recovery-resume idempotency fixes;
  PR #16 merged the follow-on Serena config-write suppression guard at
  `f1a6404`. Focused compile checks, 166 focused unit tests before PR #16 merge,
  post-merge compile checks, and 3 post-merge regression tests passed. Issue #14
  now has a green clean-worktree branch for the broad test-suite evidence gap
  under the project `.venv` interpreter.
  The live project state still requires final reconciliation/readiness acceptance
  before issue #4 can close.
- Desired state: project-state labels, readback fields, helper prompts, reload
  guidance, and state reconciliation tell the current truth without stale job
  assumptions.
- Invariants: `.project/context_forge_state.json` remains the state authority;
  project-init mutations require helper consent receipts; no direct global
  trust, secret, registry, or catalog writes happen in this slice.
- Dependencies: helper context/list evidence, schema/test updates, naming
  decision `dec-20260616-0001`, and explicit approval before any compatibility
  migration of live names or service identities.
- Hidden work: issue #4 body still refers to historical
  `validation_pending` jobs that are no longer present in the current state
  shape.
- Acceptance: schema-valid state, no stale activation-job claims, clear
  `not_checked`/verified/presumed-working semantics, numbered choices, explicit
  reload text, and full tests pass.
- Evidence: helper `cf_project_init_get_context`,
  `cf_project_init_list_capabilities`, `.project/context_forge_state.json`
  readback, project-init focused tests, control-plane discovery, full suite.
  Current PR #10 slice evidence: `py_compile` for project-init/helper hooks,
  `unittest tests.test_project_init_activation_workflow
  tests.test_project_init_scripts tests.test_control_plane_contextforge_binding
  tests.test_control_plane_project_state
  tests.test_control_plane_service_provision_fixtures -v` with 165 tests OK,
  broad `test_control_plane_*.py` discover with 301 tests run and only issue
  #14 local evidence gaps remaining at that time, and
  `git diff --check origin/dev-root...HEAD`. Current PR #16 evidence:
  `py_compile scripts/manage_serena_project_instance.py
  tests/test_project_init_scripts.py`, focused flag regression, full
  `tests.test_project_init_scripts -v`, targeted helper-mediated Serena
  provisioning regressions, expanded 166-test focused suite before merge, and
  post-merge compile plus 3-regression check on `dev-root`.
- Debt policy: any remaining deprecated label or unchecked readback must be
  tracked with owner, impact, migration trigger, and retirement condition.

#### Registry orphan cleanup -> issue #5

- Outcome: stale ContextForge prompt/resource/tool records are removed only
  when exact-match, approved, and reversible enough for local operation.
- Beneficiary: operators relying on registry counts, guidance coverage, and
  service-management readback.
- Current state: cleanup inspector reports no guidance gaps; candidates are one
  orphan prompt, two project-init resources, and 23 stale project-scoped Serena
  tools; counts are 126 tools, 82 prompts, 92 resources, 18 servers.
- Desired state: approved orphan records are gone, guidance gaps remain empty,
  and a second dry run shows no approved candidate remains.
- Invariants: ContextForge API/Admin behavior only; no direct DB writes; do not
  delete `ssh-tmux-cleanup-dead-sessions` or stale-looking Serena assets
  without approval and cross-check against issue #2.
- Dependencies: fresh dry-run output, issue #2 classification for
  project-scoped Serena records, API token/admin availability, and explicit
  approval before deletion.
- Hidden work: issue #5 body is stale because it mentions only prompt/resource
  candidates; update/comment before PR closeout.
- Acceptance: dry-run reviewed; approved ids deleted by API; readback confirms
  deletion; second dry run is empty for approved ids; rollback source is
  documented for each class.
- Evidence: `scripts/inspect_contextforge_cleanup.py --output
  /tmp/contextforge-cleanup-current.json`, `jq '.summary, .cleanup_candidates'
  /tmp/contextforge-cleanup-current.json`, cleanup apply logs/readback.
- Debt policy: unapproved candidates remain visible with owner, impact, review
  trigger, and retirement condition.

#### Inventory and service-management triage -> issue #6

- Outcome: noncanonical discovered services are classified without recreating
  client-config-driven service duplication.
- Beneficiary: maintainers deciding which backends should become ContextForge
  services.
- Current state: inventory finds 197 entries, 193 enabled; local report is
  ignored; `by_client.context-portal` is a deprecated label signal.
- Desired state: each noncanonical direct entry is classified as exclude,
  already covered, project-local only, or service-management candidate with a
  stable identity rationale.
- Invariants: client config names are discovery metadata only; no service
  promotion, registry mutation, backend install, or secret write without
  explicit service-management approval.
- Dependencies: fresh inventory, service map, open questions on noncanonical
  backends, and naming decision `dec-20260616-0001`.
- Hidden work: issue #6 body has stale 191/187 counts and should be refreshed.
- Acceptance: classification artifact or script is tracked; generated
  `*.local.json` remains ignored; repeated inventory yields the same bucket
  decisions for unchanged inputs.
- Evidence: `scripts/inventory_mcp.py`, ignored
  `inventory/contextforge-services.local.json`, classification tests or review
  output, no generated/local files tracked.
- Debt policy: every unresolved candidate keeps owner, impact, next evidence
  step, trigger, and retirement condition.

#### Repo-local skills and governance -> cross-cutting

- Outcome: project-specific skills, ledgers, and roadmap reflect the current
  ContextForge operating model without becoming a hidden mixed feature PR.
- Beneficiary: future agents and maintainers resuming roadmap work.
- Current state: `.codex/skills/`, this roadmap, the wrapper runbook, and
  naming decision `dec-20260616-0001` are local/uncommitted; governance ledgers
  already contain earlier accepted additions.
- Desired state: skills, runbooks, roadmap, and ledger entries are reviewed as
  a scoped documentation/governance change or intentionally assigned to the
  matching feature slice.
- Invariants: preserve governance anchors; use `scripts/governance_crud.py` for
  ledger mutations; do not commit local diagnostics, secrets, ignored reports,
  or temporary brainstorming files unless intentionally promoted.
- Dependencies: pushed baseline, branch slicing, and explicit ownership of
  `.codex/skills/` plus roadmap docs.
- Hidden work: `temp/roadmap-conductor-skill-design-20260616/` and `.tmp/`
  need promote/ignore/delete decisions before any PR.
- Acceptance: ledger shape checks pass; docs no longer present deprecated
  `context-portal` as project name outside compatibility/path contexts; PR
  clearly lists included and excluded documentation artifacts.
- Evidence: governance CRUD read/list, full tests or ledger-focused tests,
  `rg` naming audit, `git status --short`.
- Debt policy: any remaining naming compatibility identifier must be
  intentional, exact, and tied to a future migration trigger if it should ever
  change.

Phase 3: PR discipline.

- Open each PR as draft first.
- Before opening a PR, search existing open PRs/issues for the intended branch
  and issue link. Do not create duplicate PRs for the same slice.
- PR title format: `ContextForge: <front>`
- PR body must include:
  - linked issue;
  - files intentionally included;
  - files intentionally excluded;
  - exact tests/probes run;
  - runtime actions not performed;
  - remaining manual approvals.
- Merge order should be:
  1. roadmap/governance skills if they are needed to guide review;
  2. wrapper lifecycle cleanup (complete through PR #7);
  3. helper multi-client/project-init;
  4. Pi shim parity;
  5. cleanup/live validation tools;
  6. inventory/service-management triage;
  7. Serena stale-unit cleanup docs or manager fixes.

Phase 4: post-merge hygiene.

- Delete or archive duplicate local branch
  `codex/contextforge-helper-project-init` if it remains identical to
  `codex/contextforge-wrapper-lifecycle`.
- Close each tracking issue only after the matching PR is merged and any
  required live/manual operation is verified or explicitly deferred.
- Branch deletion, issue closure, and cleanup comments must be idempotent:
  re-running the closeout should find the branch already gone or the issue
  already linked/closed, not create new branches or duplicate issue noise.
- Re-run final state checks from this document and update this roadmap or the
  governance ledgers if the accepted state changes.

Do not open one giant PR from the current dirty branch. Recommended sequence:

1. Keep `dev-root` synchronized with `origin/dev-root`; the original 11-commit
   baseline push is complete as of `b4db351`.
2. Use the tracking issues above as the GitHub coordination layer for active
   work.
3. Split current dirty work into reviewable branches:
   - `codex/wrapper-lifecycle-cleanup` (complete through PR #7)
   - `codex/helper-multiclient-project-init`
   - `codex/pi-global-shim-parity`
   - `codex/live-validation-and-registry-cleanup-tools`
   - `codex/service-inventory-triage`
   - `codex/serena-stale-unit-cleanup`
   - `codex/repo-local-skills-and-governance`
   - `codex/precompact-continuity-hook`
   - `codex/precompact-conductor-pointer` (complete through PR #13)
4. For each branch, include only one front, run focused tests, then open a draft
   PR against `dev-root`.
5. Only after PRs exist, decide whether each issue closes through a PR,
   documented manual operation, or explicit deferral.

## Recommended Execution Order

1. Keep new feature work frozen until the remaining dirty-branch slices are
   represented as reviewable branches or explicitly deferred.
2. Treat the `dev-root` baseline push as complete while continuing to verify
   the ref before dependent PR work.
3. Preserve the current dirty branch as-is, then continue splitting it into
   small branches rather than piling new changes onto it.
4. Treat issue #11 as retired. If a different worktree is actively used and
   prompts for project-local hook trust, approve or diagnose that worktree
   explicitly rather than converting the hooks to global user scope.
5. Treat PR #7 / issue #1 as retired unless new runtime evidence proves a fresh
   wrapper regression.
6. Continue issue #15 dirty-checkout retirement before starting new
   inward-facing work, because stale active-tree state degrades the operating
   agent itself.
7. Review and clean stale Serena test units.
8. Treat PR #10 as landed and continue issue #4 only for final live
   project-state reconciliation and readiness acceptance.
9. Merge issue #14 clean-worktree evidence-gap fix after review; its branch is
   green under the project `.venv` interpreter and removes ignored local `.env`
   / `run/*registration.json` dependencies.
10. Land Pi shim source and perform approved global install/reload verification.
11. Perform approved registry orphan cleanup using exact ids from a fresh
   dry-run report and verify a second dry run is empty for those candidates.
12. Re-run full tests, inventory, gateway health, service unit status,
    protocol-aware MCP probes, and selected client-visible validation.
13. Run goal maintenance/refinement: update the meta-goal/sub-goal map,
    reprioritize the next slice from current evidence, and record the next best
    move in this roadmap or the relevant issue/PR.

## Definition Of Done For The Current Project Phase

This phase should not be called complete until all of the following are true:

- GitHub `dev-root` contains the accepted local baseline.
- Active fronts are represented by issues and draft PRs or explicitly closed as
  no-op/duplicate.
- The current dirty branch has been split or intentionally archived.
- Full tests pass from a clean branch for each PR.
- Gateway health and ready checks pass.
- Canonical service units are active and stale test units are either justified
  or removed.
- Wrapper diagnostics no longer show unbounded stale Codex wrapper growth.
- ContextForge registry guidance gaps are empty and approved orphan cleanup is
  complete or deferred.
- Pi shim deployment status is explicitly recorded as installed/verified or
  source-ready but not deployed.
- Project state has a clear explanation for old activation jobs and current
  verified status.
- Re-running service lifecycle, project-init, wrapper cleanup, Serena cleanup,
  registry cleanup, and GitHub branch/PR housekeeping commands converges on the
  same state without duplicate records, duplicate units, duplicate wrappers,
  duplicate PRs, or additional cleanup candidates.
