---
name: sub-agent-delegator
description: Symbolic model-aware subagent delegation gate for ContextForge roadmap work. Use with contextforge-agent-dispatch-matrix when deciding whether to delegate, writing sealed contracts, applying fork_context spawn rules, integrating subagent outputs, or preserving controller ownership across ContextForge roadmap, GitHub, service, project-init, governance, and hook work.
---

# Sub-Agent Delegator

Read `../SHARED_SYMBOL_SCHEME.md`. This skill owns the spawn gate and contract
assembly. `DM` owns model policy.

## Inner Scheme

- `SG` = spawn gate.
- `CT` = contract template.
- `IL` = integration loop.
- `GL` = goal-loop coupling.
- `AP` = approval-gated action.

## Controller Invariants

```text
DG ⟡ SO:
  SO owns {mission, sequencing, integration, E, GH topology, docs, governance, ✓}
  G is active control state, not after-action note
  delegate only sidecar(T) where SO can continue non-overlapping work
```

Prohibitions:

```text
DG ✗ delegate {
  immediate_blocker(T),
  AP,
  global config writes,
  Pi global installs/reloads,
  service deletion/restart,
  process termination,
  registry mutation,
  destructive cleanup,
  architecture commitments,
  branch pushes,
  PR creation,
  ledger mutation
}

WK output = E; WK output ∉ ✓
```

## Spawn Gate

```text
SG(T) ⇔
  local_next_step(SO) stated ∧
  independent(T) ∧ bounded(T) ∧ verifiable(T)
  ∧ disjoint_write_scope(T)
  ∧ T ∉ AP
  ∧ DM(T) → DC matches {M, reasoning, agent_type, fork_context}
```

```text
SG(T)=false → keep_local(SO) ∨ ask_user(real_decision_point)
SG(T)=true → CT(DC) → spawn
```

## Fork Rule

```text
Apply DM.FC:
fork_context=true ⇔ same {model, agent_type, reasoning_effort}
Δsettings → fork_context=false + explicit context
```

## Contract Template

```text
CT := {
  objective + roadmap/issue slice,
  DC,
  W=/home/dgk/workspace/cf-controlplane,
  ContextForge naming boundary,
  allowed files/systems/tools,
  forbidden edits/decisions,
  expected artifact/output,
  required E commands/probes,
  stop conditions,
  integration criteria for SO
}
```

Mode:

```text
read-only explorer ⇐ audit/extraction
worker ⇐ small disjoint write_scope owned by WK
```

## Delegation Lanes

```text
wrapper_lifecycle        → read-only audit/disjoint review; SO owns PR state
project_init_readiness   → file/test mapping; SO owns helper approval/apply
Pi_shim_parity           → status/plan/source audit; SO asks before global reload
registry_Serena_cleanup  → candidate classification; SO asks before mutation
inventory_service_mgmt   → inventory/docs drift; SO preserves *.local.*
governance_roadmap       → stale-ref audit; SO mutates ledgers/docs
hook_continuity          → config-surface research; SO owns hook implementation
```

## Integration Loop

```text
IL(WK report):
  read {outcome, E, assumptions, DC compliance, stop}
  compare(E, current repo/GH/runtime)
  rerun only critical V gating ✓
  resolve branch/PR overlap
  mutate roadmap/PR/issue/governance only if durable_state_changed ∧ SO owns mutation
  record residual_risk{owner, impact, trigger, retirement}
  GL before next T
```

## Goal-Loop Coupling

```text
GL:
  delegation ⊗ ▣SO
  meta-goal = verified idempotent GitHub-legible no-hidden-debt ContextForge
  active_subgoal = one bounded roadmap slice/protocol improvement
  after slice/interruption → refresh E, reconcile stale claims, retire/rewrite goals
  after compaction/resume → re-enter G before new T
  lossless chaining → preserve {value, E, non-actions, risks, approvals,
                                delegated outputs, GH state, candidates, next T}
```

Report only:

```text
Out = integrated outcomes + E + prognosis + remaining risk + next best move
delegated_activity ∉ shipped_value
```

Fidelity: preserves controller invariants, spawn gate, fork rule, contract
template, delegation lanes, integration loop, and goal-loop coupling. Losses:
full prose examples compressed into symbolic clauses.
