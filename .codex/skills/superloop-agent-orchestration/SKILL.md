---
name: superloop-agent-orchestration
description: Symbolic ContextForge SuperLoop controller workflow across worker agents, child agents, GitHub issues, GitHub Project #6, leases, Agent owner fields, final acceptance, durable goal maintenance, and dispatch-card use with contextforge-agent-dispatch-matrix.
---

# SuperLoop Agent Orchestration

Read `../SHARED_SYMBOL_SCHEME.md`. This skill is the controller runtime. `SO`
owns SuperLoop; `DM` owns model policy; `DG` owns spawn contracts; `WK` executes
leases; `GP` owns Project #6 field semantics.

## Inner Scheme

- `CID` = controller identity.
- `CR` = controller responsibilities.
- `SL` = SuperLoop.
- `WP` = worker pool.
- `CD` = creative discussion mode.
- `GR` = goal refinement.
- `QL` = queue/lease model.
- `BD` = branch discipline.
- `AD` = acceptance discipline.

## Controller Identity

```text
CID:
  controller = codex-thread:<thread-id>
  worker = codex-agent:<agent-id>
  child = codex-agent:<parent-agent-id>/<child-agent-id>
  controller_id source = get_goal().goal.threadId when available
  worker/child_id source = dispatcher/subagent handle
  human-readable names = aliases only
```

Lease/report identity fields:

```text
{agent_run_id, parent_agent_run_id?, controller_run_id,
 role, assigned_scope, lease_state}
```

## Controller Responsibilities

```text
CR:
  SO owns {
    G + successor G,
    GH topology + GP coordination,
    T definition + DC review + L assignment/retirement,
    priority across issues/lanes/risk/dependencies,
    integration(WK/child E),
    final claims,
    PR push/merge/closure + issue closure,
    governance/docs,
    approval-gated/runtime/destructive/global/shared-system actions
  }

WK/child output = E, not ✓.
SEM claims require evaluator judgment; regex/string/keyword matching over
free-form prose is never a semantic or readiness oracle.
```

## Controller SuperLoop

```text
SL re-entry:
  read(G) →
  read(GP Agent Issue View) →
  inspect(repo branch/status + active issue/PR) →
  reconcile({L, Agent owner, WK reports, DC, open PRs}) →
  choose next global move
```

```text
SL execution:
  decompose(roadmap intent) →
  parallelizable? →
  DM(T) → DC for delegated T →
  create/refresh L before WK begins →
  monitor(WK) without taking over →
  integrate(E + repo/GH/runtime readback) →
  decide {✓ accept | reject | rescope | defer | merge | close}
```

## Worker Pool

```text
WP:
  max_concurrency=3 as cap, not quota
  keep verification slot when possible
  dispatch only after controller admin is caught up enough to integrate outputs
```

Pool loop:

```text
read(GP, open PRs) →
select independent T with disjoint files/branches/read-only surfaces →
DM(T) → DC →
DG(DC) → L with formal WK goal →
record L in issue/PR comment →
set Agent owner only when GP item visible →
continue SO-side integration →
on WK done: integrate, retire/close WK, clear/update Agent owner,
            dispatch next only if admin caught up and T exists
```

Pipeline rule:

```text
clean WK+verifier E + expected GH/GP state → rerun only acceptance-gating checks
```

Worker commits:

```text
WK commit allowed ⇔ L permits ∧ isolated branch/worktree
commit = reviewable artifact, not global state
SO verifies before push/PR/promote/merge/close
```

Project latency:

```text
new issue/PR → wait for workflow auto-add; no duplicate GP item
set Agent owner only after item visible; else record pending reconciliation
```

## Creative Discussion Agents

```text
CD:
  if user asks for creative GitHub discussion contribution:
    light prompt; no full L unless implementation/roadmap mutation
    allowed write = named discussion only
    repo read-only
    ✗ {issues, PRs, branches, commits, GP fields, labels, runtime, Docker,
       client/global config, secrets, hooks, helper apply state}
    output = idea fuel ∉ roadmap acceptance
  SO reads discussion URL → retire agent → decide if issue/GP/L/governance needed
```

## Goal Refinement

```text
GR:
  keep G current at controller boundaries, not every observation
  live observations → tasklist/issue/GP/PR/governance as appropriate
  after completed work batch → decide close/refine
  after L assignment/WK report/PR merge/issue closure/GP topology change →
    update coordination before next move
  surprising E → record correction now; refine successor G at honest boundary
  early pattern → smaller subgoals
  ✗ complete(G) merely to rewrite
  complete(G) ⇔ bounded subgoal has actual acceptance E
```

## Queue And Lease

```text
QL:
  WK ✗ pull arbitrary GH issues
  default = SO-instantiated, SO-assigned, one bounded T per L
  WK loops only inside L until stop
  standing WK may request T; SO {retires | grants successor L | leaves idle}
  WK-requested work = request, not queue ownership
  WK begins only after SO grants/authorizes L
```

Project ownership:

```text
GP.Agent owner:
  controller-held = codex-thread:<thread-id>
  worker-held = codex-agent:<worker-agent-id>
  child-held = codex-agent:<parent-agent-id>/<child-agent-id>

GP.Agent state ∈ {Ready, Active, Blocked, In Review, Done, Deferred, Candidate}
Assignees ∉ agent lease owner
```

## Lease Contract

```text
L := {
  controller_run_id,
  worker_agent_id,
  parent_agent_id?,
  role,
  scope,
  DC,
  allowed_delegation,
  allowed files/systems/tools,
  forbidden actions,
  lease_started_at,
  initial_worker_formal_goal,
  expected_artifact,
  stop_condition
}
```

Worker contract adds:

```text
{formal WK goal, roadmap slice, W, branch/worktree instructions,
 allowed mutations, child delegation stance, required E commands/probes,
 report format, integration criteria}
```

## Child Agent Rule

```text
child A = E producer only
child owns one narrow research/verification/audit/log-parse T
child ∉ work unit ownership, GH state, final claims
WK may spawn child only if L permits; WK integrates child E before reporting
SO treats WK+child outputs as E, not authority
```

## Branch Discipline

```text
BD:
  maintain clean SO baseline on current dev-root where feasible
  linked worktrees = leased execution surfaces
  controller branches start from clean dev-root
  worker branch = codex/issue-<number>-<short-slug> unless L says otherwise
  WK ✗ reuse another agent branch
  unrelated dirty worktree → separate worktree or stop with containment needs
  SO records worktree owner for each active branch/L
  SO returns to clean baseline before final integration when feasible
  SO verifies merge state + branch containment + GP state before deleting refs
```

Run branch work as a tight branch -> develop -> merge cycle:

1. Start each implementation or reconciliation branch from freshly fetched
   current `origin/dev-root`; do not stack unrelated work on stale or already
   merged branches.
2. Keep the branch small enough that the controller can review the diff,
   evidence, PR body, and issue/Project impact in one bounded pass.
3. Push and open or update the PR as soon as the slice has local evidence,
   even if the PR is draft; do not let unpushed local work become hidden queue
   state.
4. Promote, merge, defer, or close each PR promptly after controller review.
   A draft PR is not a storage shelf; it needs an explicit next action,
   blocker, or retirement rationale.
5. After merge, refresh `dev-root`, reconcile dependent branches/PRs, retarget
   or rebase only branches still worth preserving, and close or delete
   superseded refs when authorized.
6. Treat closed-unmerged and conflict-bearing branches as debt. Reopen/rework
   them only when their value still exceeds the rebase/review cost; otherwise
   record the retirement path and keep them out of the active queue.

## Acceptance Discipline

```text
AD:
  SO accepts WK output only if:
    L scope + DC match returned work
    M/reasoning/agent_type/fork_context coherent and auditable
    changed files ⊆ allowed set
    E commands prove local acceptance criteria
    residual risk has owner + retirement condition
    GH/PR/GP state consistent
    no forbidden action occurred
    final claims ≤ exercised surfaces

  missing/overbroad E → reject ∨ rescope; ✗ silent claim upgrade
```

Fidelity: preserves controller identity, SuperLoop, worker pool, creative
discussion mode, goal refinement, queue/lease model, child-agent rule,
branch/worktree discipline, Project #6 semantics, dispatch-card additions, and
acceptance discipline.
