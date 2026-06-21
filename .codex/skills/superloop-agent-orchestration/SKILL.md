---
name: superloop-agent-orchestration
description: Coordinate ContextForge primary SuperLoop controller work across worker agents, child agents, GitHub issues, GitHub Project #6, leases, Agent owner fields, final acceptance, and durable goal maintenance. Use when Codex is acting as the central controller, assigning or integrating parallel work, creating worker contracts, reconciling Project #6 coordination state, or deciding global sequencing across ContextForge roadmap lanes.
---

# SuperLoop Agent Orchestration

Use this skill when you are the primary ContextForge SuperLoop controller. The
controller owns global sequencing, worker assignment, Project #6 coordination,
GitHub mutations, integration, final acceptance claims, and goal maintenance.

For a worker executing an assigned lease, use `superloop-worker-agent` instead.
For low-level subagent spawn mechanics, also use `sub-agent-delegator`. For
Project #6 field semantics and workflow behavior, also use
`github-project-agent-coordination`.

## Controller Identity

Use stable run IDs, not the rotating Codex display names.

- Primary controller: `codex-thread:<thread-id>`.
- Worker agent: `codex-agent:<agent-id>`.
- Child agent: `codex-agent:<parent-agent-id>/<child-agent-id>`.

Get the controller thread ID from the formal goal tool result when available
(`get_goal().goal.threadId`). Get worker and child IDs from the dispatcher or
subagent handle. Human-readable names are aliases only; never use them as lease
identity.

Record structured identity fields in leases and reports:

- `agent_run_id`;
- `parent_agent_run_id`, when applicable;
- `controller_run_id`;
- `role`: `controller`, `worker`, `reviewer`, `researcher`, or `verifier`;
- `assigned_scope`;
- `lease_state`.

## Controller Responsibilities

Own these surfaces:

- global goal state and successor-goal formulation;
- issue and GitHub Project #6 topology;
- work-unit definition, assignment, and lease retirement;
- prioritization across issues, lanes, risk, and dependency clues;
- integration of worker and child-agent outputs;
- final acceptance claims;
- PR creation, pushes, merges, issue closure, and durable GitHub state;
- governance edits and durable roadmap state;
- approval-gated, runtime, destructive, global, or shared-system actions.

Do not let worker-local success become a global readiness claim. Worker and
child output is evidence for the controller to integrate, not authority to ship.

For model-dependent output, deterministic checks may verify structure but not
meaning. No test, gate, score criterion, readiness claim, or acceptance claim
may use matched strings, regexes, keyword searches, or string parsing as the
oracle for free-form generated prose. The only exception is declared structured
model output such as JSON, where scripts may check parseability, schema shape,
required fields, and enum/value structure, and only when paired with
non-deterministic evaluator review.

## Controller SuperLoop

At re-entry:

1. Read the formal goal.
2. Read Project #6 Agent Issue View with `github-project-agent-coordination`.
3. Inspect repo branch/status and active issue/PR state.
4. Reconcile active leases, Agent owner values, worker reports, and open PRs.
5. Choose the next best global move.

Use dependency-aware sequencing, not issue-number dogma. Maintain a complete
tentative queue, but reorder within hard dependency constraints when evidence
shows that a lower-layer substrate, regression, or shared blocker is the better
next target. Record the rationale in the package, dependency mesh, issue/PR
comment, or goal checkpoint.

During execution:

1. Decompose roadmap intent into bounded work units.
2. Decide which units can proceed in parallel without overlap.
3. Create or refresh leases before workers begin.
4. Monitor worker progress without taking over local execution.
5. Integrate returned evidence with current repo/GitHub/runtime evidence.
6. Run reflective learning: classify surfaced improvements as
   `incorporate_now`, `promote_regression`, `defer_with_owner`, or
   `reject_with_rationale`.
7. Make final acceptance, merge, closure, or deferral decisions.

## Worker Pool Cadence

Run the controller as a small worker pool, not as a serial implementer. Start
with three as a maximum concurrency cap, not a quota to keep full. Dispatch a
worker when the controller would otherwise be idle after catching up on
orchestration administration: integrating returned reports, updating issue/PR
comments, reconciling Project #6, refreshing PR state, packaging accepted
worker output, and performing goal maintenance. Keep one slot available for
verification when possible so implementation output does not wait on
controller-local rework.

Use this pool loop:

1. Read Project #6 and open PR state.
2. Select independent work units with disjoint files, branches, or read-only
   evidence surfaces.
3. Dispatch workers with explicit leases and formal worker goal text.
4. Record the lease in issue/PR comments and set `Agent owner` to the active
   worker when the item is represented in Project #6.
5. Continue controller-side queue integration, but do not duplicate worker-local
   implementation or verification just because a worker is still running.
6. When a worker finishes, integrate the report, close or retire that worker,
   update `Agent owner` for handoff or clear it, and dispatch another worker
   only if controller administration is caught up and an independent assignable
   work unit is available.

Prefer `gpt-5.3-codex-spark` for tiny, isolated, low-risk work such as
read-only grep mapping, focused PR metadata checks, test-list confirmation, or
boilerplate verification. Use stronger inherited workers for architecture,
multi-file implementation, risky acceptance, or runtime-adjacent reasoning.

Trust the pipeline when evidence is clean. If a worker and verifier provide
bounded evidence and GitHub/Project automation reflects the expected state, do
not redo the whole task locally. Rerun only the acceptance commands needed for
controller confidence, then package, merge, defer, or lease the next fix.

Do not ignore emergent improvement ideas just because the current package did
not predict them. Study them at loop boundaries and either incorporate the
smallest coherent improvement, promote a regression, defer with an owner, or
reject with rationale. Reflection improves the queue; it must not become
unbounded churn inside a leased work unit.

Worker-local commits are acceptable when the lease permits them and the worker
owns an isolated branch/worktree. Treat the commit as a reviewable artifact, not
as accepted global state. The controller verifies the diff and evidence before
pushing, opening PRs, promoting drafts, merging, or closing issues. Do not allow
workers to commit on controller baselines, shared branches, or branches owned by
another worker unless the controller explicitly reassigns ownership.

GitHub Project automation has latency. After creating a PR or issue, do not
immediately create a duplicate Project item or treat missing board visibility as
failure. First rely on the native PR/issue URL and comment evidence, then run a
targeted Project readback after a short delay or at the next maintenance pass.
Set `Agent owner` only after the auto-added item is visible; if it is still
missing, record the pending reconciliation instead of fighting the workflow.

## Creative Discussion Agents

When the operator asks for creative agents to contribute to a GitHub
discussion, keep the prompt light. Do not wrap idea generation in a full
work-unit lease unless the discussion contribution is tied to an implementation
or roadmap mutation. Send the agent to the discussion, ask it to contribute
creatively, and preserve only the necessary boundaries:

- repo/codebase files remain read-only unless a separate work unit says
  otherwise;
- the named GitHub discussion is writable for the requested contribution;
- no issues, PRs, branches, commits, Project fields, labels, runtime services,
  Docker/client/global config, secrets, hooks, helper apply state, or other
  shared surfaces are mutated unless explicitly authorized;
- the contribution is idea fuel, not accepted roadmap, final evidence, or a
  project completion claim.

Use normal controller integration afterward: read back the discussion URL,
retire the agent, and decide separately whether any idea deserves a real issue,
Project item, work-unit lease, or governance record.

At maintenance:

1. Record durable evidence, non-actions, residual risk, GitHub state, and branch
   state.
2. Update Project #6 only for durable coordination transitions.
3. Retire completed leases and clear or update `Agent owner`.
4. Complete the current formal goal when the subgoal is fully verified.
5. Immediately create the refined successor goal.

## Goal Refinement Cadence

Keep the formal goal current at controller boundaries, not on every tactical
observation. During a live subgoal, maintain fast-changing observations in the
tasklist, issue comments, Project #6 fields, PR notes, or governance ledgers as
appropriate. Fold those observations into the next formal goal when the current
subgoal is verified, handed off, or materially re-scoped.

Use this cadence:

- at every controller re-entry, read the formal goal and Project #6 before
  acting;
- after each completed work unit or small integrated batch, decide whether the
  current subgoal is complete enough to close and refine;
- after any lease assignment, worker report, PR merge, issue closure, or
  Project topology change, update coordination state before choosing the next
  move;
- after surprising evidence, record the correction immediately, then refine the
  successor goal at the next honest boundary;
- early in a new orchestration pattern, prefer smaller subgoals so learning can
  be incorporated into successor goals quickly;
- do not mark a formal goal complete merely to rewrite it; complete it only when
  the bounded subgoal has actual acceptance evidence.

## Queue And Lease Model

Workers must not pull arbitrary GitHub issues directly. The default pattern is
controller-instantiated, controller-assigned work: create or activate a worker
for one bounded work unit, grant a lease, and require the worker to loop only
inside that lease until the stop condition is satisfied.

A standing worker may ask for another work unit after reporting completion or a
handoff, but it still must not self-select from the queue. The controller either
retires the worker, grants a successor lease, or leaves it idle. Treat
worker-requested work as a request for controller assignment, not as queue
ownership by the worker.

A worker may begin only after the controller grants a lease or explicitly
authorizes a lease request.

Use the Project #6 `Agent owner` text field for current ownership:

- controller-held item: `codex-thread:<thread-id>`;
- worker-held item: `codex-agent:<worker-agent-id>`;
- child-held evidence task, only if represented directly:
  `codex-agent:<parent-agent-id>/<child-agent-id>`.

Use `Agent state` for coordination status:

- `Ready`: prepared enough to lease;
- `Active`: leased and in progress;
- `Blocked`: concrete boundary or external prerequisite;
- `In Review`: packaged for controller review, PR review, or merge decision;
- `Done`: accepted, closed, merged, or retired with evidence;
- `Deferred`: intentionally later-phase;
- `Candidate`: plausible future work.

Do not use `Assignees` as the agent lease owner. GitHub assignees are
repository-owned human/account metadata. `Agent owner` is the agent lease field.

## Issue Comment Lease

When a work unit is more than a trivial local check, write an issue comment
lease before or immediately after assignment:

```text
Work unit lease:
- controller_run_id: codex-thread:<controller-id>
- worker_agent_id: codex-agent:<worker-id>
- parent_agent_id: optional codex-agent:<parent-id>
- role: worker | reviewer | researcher | verifier
- scope: issue number and bounded task statement
- allowed delegation: none | research-only | verification-only | bounded worker children
- allowed files/systems/tools: explicit list
- forbidden actions: explicit list
- lease_started_at: YYYY-MM-DDTHH:MM:SSZ
- expected artifact: patch | report | validation evidence | issue comment | PR
- stop_condition: concrete completion or handoff condition
```

Close the loop with a completion or handoff comment that names returned
evidence, residual risk, and whether the controller accepted, rejected, or
re-scoped the work.

## Worker Contracts

Every worker contract must include:

- initial worker formal goal text, including the lease-scoped objective,
  evidence plan, forbidden actions, stop condition, and reporting contract;
- objective and issue/roadmap slice;
- active repo root `/home/dgk/workspace/cf-controlplane`;
- branch/worktree instructions;
- allowed files, systems, tools, and mutations;
- forbidden actions;
- whether child delegation is allowed;
- required evidence commands or probes;
- expected report format;
- stop conditions;
- integration criteria.

Workers may request clarification, narrowed or expanded scope, or permission to
spawn child research/verification agents. They may not self-promote scope, close
issues, merge PRs, mutate global/runtime surfaces, or make final project claims
unless the controller explicitly leases that authority.

The controller remains responsible for making sure worker formal goals remain
subordinate to the controller SuperLoop. A worker may complete its own goal when
its lease stop condition is satisfied, but it may create a worker successor goal
only inside the same lease or after a controller response authorizes the next
bounded worker cycle.

## Child Agent Rule

Child agents are evidence producers. They own one narrow research,
verification, audit, or log-parsing task. They return findings, file
references, commands, risks, and uncertainties. They do not own the work unit,
GitHub state, or final claims.

A worker may spawn child agents only when its lease permits it. The worker must
integrate child output before reporting to the controller. The controller treats
both worker and child output as evidence, not authority.

## Branch Discipline

Keep implementation branches and worktrees owned and non-overlapping. The
controller should normally maintain one clean controller baseline on current
`dev-root` for integration, readback, and final acceptance. Use separate linked
worktrees for worker branches, feature branches, or any slice that would
otherwise mix with dirty or concurrent work.

Do not casually move the controller through many dirty worktrees. Treat linked
worktrees as leased execution surfaces:

- controller integration branches start from current clean `dev-root`;
- worker branches use `codex/issue-<number>-<short-slug>` unless the lease says
  otherwise;
- workers do not reuse another agent's branch;
- if a worktree contains unrelated dirty changes, create a separate linked
  worktree or stop with exact containment needs;
- the controller records which worktree owns each active branch or lease;
- the controller returns to the clean baseline before final integration when
  feasible;
- the controller verifies merge state, branch containment, and Project state
  before deleting branch refs.

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

The controller accepts a worker output only after checking:

- the lease scope matches the returned work;
- changed files match the allowed set;
- evidence commands prove the local acceptance criteria;
- residual risk is named with owner and retirement condition;
- GitHub issue/PR/Project state is consistent;
- no forbidden action occurred;
- final claims do not exceed exercised surfaces.

If evidence is missing or overbroad, re-scope or reject the output rather than
closing the global goal.
