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

## Controller SuperLoop

At re-entry:

1. Read the formal goal.
2. Read Project #6 Agent Issue View with `github-project-agent-coordination`.
3. Inspect repo branch/status and active issue/PR state.
4. Reconcile active leases, Agent owner values, worker reports, and open PRs.
5. Choose the next best global move.

During execution:

1. Decompose roadmap intent into bounded work units.
2. Decide which units can proceed in parallel without overlap.
3. Create or refresh leases before workers begin.
4. Monitor worker progress without taking over local execution.
5. Integrate returned evidence with current repo/GitHub/runtime evidence.
6. Make final acceptance, merge, closure, or deferral decisions.

At maintenance:

1. Record durable evidence, non-actions, residual risk, GitHub state, and branch
   state.
2. Update Project #6 only for durable coordination transitions.
3. Retire completed leases and clear or update `Agent owner`.
4. Complete the current formal goal when the subgoal is fully verified.
5. Immediately create the refined successor goal.

## Queue And Lease Model

Workers must not pull arbitrary GitHub issues directly. A worker may begin only
after the controller grants a lease or explicitly authorizes a lease request.

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

Keep implementation branches owned and non-overlapping:

- controller integration branches start from current clean `dev-root`;
- worker branches use `codex/issue-<number>-<short-slug>` unless the lease says
  otherwise;
- workers do not reuse another agent's branch;
- if a worktree contains unrelated dirty changes, create a separate linked
  worktree or stop with exact containment needs;
- the controller verifies merge state, branch containment, and Project state
  before deleting branch refs.

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
