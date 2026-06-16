---
name: sub-agent-delegator
description: Model-aware subagent delegation discipline for ContextForge roadmap work. Use when Codex needs to decide whether to delegate, choose a subagent model/reasoning/fork shape, write a sealed subagent contract, run bounded parallel audits or implementation slices, integrate subagent outputs, or maintain a controller-owned goal loop across ContextForge roadmap, GitHub, service, project-init, governance, and hook work.
---

# Sub-Agent Delegator

You are the operating agent. Use subagents only when delegation materially
improves ContextForge roadmap execution without weakening your controller
ownership. Keep commits, pushes, PRs, global config changes, service mutations,
destructive cleanup, and final acceptance claims in the parent/root agent unless
the user explicitly narrows and approves otherwise.

## Controller Invariants

- Keep the parent agent responsible for mission, sequencing, integration,
  evidence, GitHub topology, docs, governance, and final claims.
- Treat the live goal object as the operating agent's control state, not as a
  passive checklist or after-action note.
- Delegate bounded sidecar work that can proceed while the parent does
  non-overlapping critical-path work.
- Do not delegate the immediate blocking step when the parent needs that result
  before any useful local progress can continue.
- Do not delegate approval-gated work: global config writes, Pi global installs
  or reloads, service deletion/restart, process termination, registry mutation,
  destructive cleanup, architecture commitments, branch pushes, PR creation, or
  ledger mutation.
- Treat subagent output as evidence to integrate, not as authority to ship.
- Close or retire subagents once their output is integrated.

## Model Matrix

Use this project-specific default mapping unless the user gives a stronger
instruction or live tool availability differs.

| Model | Use | Reasoning | Fork Guidance |
| --- | --- | --- | --- |
| `gpt-5.5` | Deep audits, architecture choices, cross-slice risk, high-criticality implementation review | high or adaptive | Good for full-context forks when inheriting parent model/settings is desired |
| `gpt-5.4-mini` | Routine audits, log parsing, config/docs mapping, repetitive verification, shallow fan-out | low or medium | Use explicit context; fork only when same model/settings and rich inherited context are necessary |
| `gpt-5.3-codex-spark` | Tiny local micro-edits or boilerplate where speed matters and risk is low | low or default | Prefer direct parent work; do not use for independent reasoning-heavy forks |

When using `fork_context=true`, do not set a different `model`,
`agent_type`, or `reasoning_effort`. Full-context forks inherit the parent
agent type, model, and reasoning settings. If a different model is useful,
spawn without a full context fork and pass the needed context explicitly.

## Delegation Gate

Before spawning, state the local next step and classify the candidate task:

1. Is the task independent enough to run without blocking the parent?
2. Does it have a clear objective and stop condition?
3. Can it be verified from concrete artifacts, commands, or file paths?
4. Is the write set disjoint from other active work?
5. Is the task free of approval-gated or destructive operations?

Delegate only when the answer is yes. Otherwise, keep the work local or ask the
user for the real decision point.

## Contract Template

Every subagent prompt must include:

- objective and roadmap/issue slice;
- project root and naming boundary: ContextForge is the proper name;
  `context-portal` is a legacy path/runtime identifier only;
- allowed files/systems/tools;
- forbidden edits and forbidden decisions;
- expected artifact or output format;
- required evidence commands or probes;
- stop conditions;
- integration criteria for the parent.

Use read-only explorer contracts for audits. Use worker contracts only when the
write set is small, disjoint, and owned by that worker.

## ContextForge Delegation Lanes

- Wrapper lifecycle: use read-only audits or disjoint code review around PR #7;
  parent owns integration, branch, and PR state.
- Project-init readiness: delegate file classification and focused test
  mapping; parent owns helper-mediated approval/apply semantics.
- Pi shim parity: delegate status/plan/source audit only; parent asks before
  user-global install or reload.
- Registry and Serena cleanup: delegate candidate classification only; parent
  asks before deletion, service stop, or registry mutation.
- Inventory/service-management: delegate inventory classification and docs
  drift checks; parent preserves generated `.local.*` boundaries.
- Governance/roadmap: delegate audits only; parent performs durable ledger and
  roadmap edits.
- Hook/continuity work: delegate documentation or config-surface research;
  parent owns implementation because hooks affect agent behavior.

## Integration Loop

After a subagent completes:

1. Read the result once for outcome, evidence, assumptions, and stop
   conditions.
2. Compare it against current local evidence; rerun only critical verification
   that gates acceptance.
3. Resolve overlap with active branches and PRs.
4. Update the roadmap, PR body, issue comment, or governance ledger only when
   durable state changed.
5. Record residual risk with owner, impact, trigger, and retirement condition.
6. Run goal maintenance/refinement before selecting the next subgoal.

## Goal Loop Coupling

Delegation is subordinate to the dynamic goal loop:

- Meta-goal: move ContextForge toward verified, idempotent, documented,
  GitHub-legible roadmap completion with no hidden debt.
- Active subgoal: one bounded roadmap slice or protocol improvement at a time.
- Goal maintenance: after each slice or interruption, refresh evidence,
  reconcile stale claims, retire or rewrite subgoals, and choose the next best
  move.
- Operating-agent residency: after compaction or resume, first re-enter the
  live goal state, then continue or retire the current subgoal before starting
  another.
- Lossless chaining: after a major subgoal is met, preserve value, evidence,
  non-actions, residual risk, approvals, delegated outputs, GitHub state,
  candidate subgoals, and the chosen next subgoal before re-initializing the
  loop. Do not let unchosen information disappear just because attention moved.

Never report delegated activity as shipped value. Report only integrated
outcomes, evidence, prognosis, remaining risk, and the next best move.
