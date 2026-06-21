# Shared Symbol Scheme: ContextForge Delegation V2

This scheme applies to every symbolic skill in this directory. Each skill also
defines a small inner scheme for role-local aliases.

## Shared Legend

Entities:

- `RC` = `project-roadmap-conductor`
- `SO` = `superloop-agent-orchestration`
- `DM` = `contextforge-agent-dispatch-matrix`
- `DG` = `sub-agent-delegator`
- `WK` = `superloop-worker-agent`
- `GP` = `github-project-agent-coordination`
- `CF` = ContextForge control-plane work domain
- `GH` = GitHub issues/PRs/Project #6
- `W` = workspace/repo root `/home/dgk/workspace/cf-controlplane`
- `G` = formal goal state
- `T` = task/work unit
- `L` = lease
- `DC` = dispatch card
- `E` = evidence
- `V` = verification/validation
- `M` = selected model
- `Sp` = `gpt-5.3-codex-spark`
- `M55` = `gpt-5.5`
- `M54m` = `gpt-5.4-mini`

Operators:

- `→` = sequence, handoff, or transition
- `⋈` = contract/interface binding
- `⟡` = authority/scope boundary
- `⊗` = conditional dependency
- `⊥` = must remain distinct / non-substitutable
- `∈` = belongs to
- `∉` = excluded from
- `✓` = accepted only after controller verification
- `⚠` = risk/caveat
- `✗` = prohibited
- `▣` = recurrent/self-maintaining loop
- `∇` = reflective review or judgment
- `⊕` = synthesis/integration

## Shared Topology

```text
RC → SO → DM → DG → WK → SO
          ↘ GP ↗
```

Meaning:

- `RC` frames roadmap/no-debt intent.
- `SO` runs SuperLoop and owns acceptance.
- `DM` produces model/dispatch policy.
- `DG` converts `DC` into spawn/worker contracts.
- `WK` executes one `L`, returns `E`, and stops.
- `GP` indexes coordination; it does not decide substance.

## Shared Invariants

```text
DM ⊥ SO            # model policy does not replace orchestration
DC ⊥ L             # dispatch card augments lease, not replaces it
E ⊥ ✓             # evidence is not acceptance until SO integrates
GP ⊥ issue/PR/doc  # Project #6 is coordination index, not substance
Sp ⊥ judgment      # Spark extraction is not semantic judgment
```

```text
SO owns {G, GH topology, L assignment, integration, final claims}
DM owns {M policy, DC schema, Sp/M54m/M55 lanes}
DG owns {spawn gate, contract assembly, integration handoff}
WK owns {one L, local E, bounded report}
GP owns {Agent state, Agent owner semantics}
```

## Shared Dispatch Card

```text
DC := {
  task_class,
  expected_value,
  risk_layer,
  exercised_surface,
  write_scope,
  verification_available,
  selected_model,
  reasoning_effort,
  agent_type,
  fork_context,
  selection_reason,
  forbidden_actions,
  acceptance_owner=controller
}
```

## Shared Flow

```text
▣SO:
  read(G, GP, GH, repo) →
  decompose(CF task) →
  choose local-next-step →
  if delegateable(T): DM(T) → DC →
  DG(DC) → L ⋈ WK →
  WK(L) → E →
  SO(∇E ⊕ repo/GH/runtime readback) →
  {accept | reject | rescope | defer} →
  refine(G)
```

## Shared Boundary Rules

```text
delegate(T) ⇔ independent(T) ∧ bounded(T) ∧ verifiable(T)
              ∧ disjoint_write_scope(T)
              ∧ T ∉ approval_gated
              ∧ T ∉ immediate_blocker

approval/global/destructive/runtime/shared-system ⇒ SO-only
```

```text
fork_context=true ⇔ child inherits same {model, agent_type, reasoning_effort}
change({model, agent_type, reasoning_effort}) → fork_context=false + explicit context
Sp default → fork_context=false unless parent already Sp with no setting change
```

```text
WK report + E + DC compliance + repo/GH/runtime readback ⊗ SO judgment → ✓
WK ∉ ✓
Sp ∉ controller-only decisions
```

## Shared Model Surface

```text
M55 ⇐ architecture ∨ semantic_acceptance ∨ runtime_adjacent
      ∨ security/trust ∨ cross_slice_risk ∨ final_readiness

M54m ⇐ routine_implementation ∨ moderate_source_tests
       ∨ config_docs_mapping ∨ repetitive_verification

Sp ⇐ extraction ∨ source_mapping ∨ checklist_verification
     ∨ metadata_audit ∨ tiny_mechanical_patch
```

## Fidelity

This shared scheme preserves functional topology, authority boundaries,
model-selection constraints, dispatch-card observability, and SuperLoop
primacy. Inner skill schemes must not redefine shared symbols with conflicting
meanings.
