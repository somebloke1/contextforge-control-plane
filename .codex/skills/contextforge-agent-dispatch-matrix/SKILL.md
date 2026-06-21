---
name: contextforge-agent-dispatch-matrix
description: Symbolic advisory model-selection and dispatch-card policy for ContextForge delegation. Use when classifying a work unit, choosing among available agent models including gpt-5.3-codex-spark, setting fork_context/model/reasoning/agent_type fields, or auditing whether a lease is Spark-eligible, controller-only, or local-only.
---

# ContextForge Agent Dispatch Matrix

Read `../SHARED_SYMBOL_SCHEME.md` for shared notation. This skill owns `M`
policy and `DC`; it does not replace `SO`, `L`, `GP`, worktree discipline, goal
maintenance, or controller-owned acceptance.

## Inner Scheme

- `PE` = policy entitlement check: user/developer/system instructions + live
  tool availability + spawn constraints + explicit approvals.
- `SE` = Spark-eligible class.
- `CO` = controller-only decision class.
- `FC` = fork constraint.
- `MC` = model choice.

## Authority

```text
DM owns {MC, DC schema, SE, CO, FC}
DM ⊥ SO
DM ∉ runtime entitlement
PE ⊗ DM → safe MC
preferred(M) unavailable → strongest_safe_available(M) ∨ keep_local
```

Read `references/dispatch-card.md` for `DC`, `SE`, `CO`, and examples.

## Model Rule

```text
M55 ⇐ architecture ∨ semantic_acceptance ∨ runtime_adjacent
      ∨ security/trust ∨ cross_slice_risk ∨ final_readiness

M54m ⇐ routine_implementation ∨ moderate_source_tests
       ∨ config_docs_mapping ∨ repetitive_verification

Sp ⇐ extraction ∨ source_mapping ∨ checklist_verification
     ∨ metadata_audit ∨ tiny_mechanical_patch
```

```text
Sp ✗ {
  architecture,
  target_client_validation_judgment,
  final_readiness,
  runtime/service/systemd/Docker/global-client mutation,
  ContextForge registry mutation,
  governance ledger mutation,
  PR merge/closure,
  security/auth/trust/remote-exposure decisions
}
```

## Fork Rule

```text
fork_context=true ⇔ child inherits same {model, agent_type, reasoning_effort}
Δ{model, agent_type, reasoning_effort} → fork_context=false + explicit context
Sp default → fork_context=false unless parent already Sp and Δsettings=none
```

## Dispatch Rule

```text
SO selects candidate T → DM(T) → DC

If semantic_ambiguous(T) ∨ approval_gated(T) ∨ immediate_blocker(T):
  keep_local(SO) unless user explicitly authorizes alternate workflow.
```

## Controller Integration

```text
SO records DC fields in L, including selected_model
WK returns DC fields in report, including selected_model
SO checks {selected_model, MC, FC, SE/CO} coherence before ✓
```

Fidelity: symbolic form preserves model policy, advisory authority, fork
constraints, dispatch-card observability, and Spark boundaries. Losses: prose
examples moved to `references/dispatch-card.md`.
