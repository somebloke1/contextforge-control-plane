---
name: contextforge-agent-dispatch-matrix
description: Symbolic advisory model-selection and dispatch-card policy for ContextForge delegation. Use when classifying a work unit, choosing among available agent models including gpt-5.3-codex-spark, setting fork_context/model/reasoning/agent_type fields, or auditing whether a lease is Spark-eligible, controller-only, or local-only.
---

# ContextForge Agent Dispatch Matrix

Read `../SHARED_SYMBOL_SCHEME.md` for shared notation. This skill owns model
policy and dispatch-card shape; it does not replace SuperLoop controller
authority, worker leases, GitHub Project coordination, worktree discipline, or
final acceptance.

## Authority

```text
DM owns {model_choice, dispatch_card_schema, spark_boundary, fork_rule}
DM does not own sequencing, runtime entitlement, acceptance, or roadmap claims
```

Read `references/dispatch-card.md` when a lease needs the full dispatch-card
schema, Spark/controller-only classes, or examples.

## Model Rule

```text
gpt-5.5 ⇐ architecture ∨ semantic_dialogue_judgment ∨ requirement_refinement
          ∨ runtime_adjacent ∨ security/trust ∨ cross_slice_risk
          ∨ final_readiness

gpt-5.4-mini ⇐ routine_implementation ∨ moderate_source_tests
               ∨ config_docs_mapping ∨ repetitive_verification

gpt-5.3-codex-spark ⇐ extraction ∨ source_mapping ∨ checklist_verification
                      ∨ metadata_audit ∨ tiny_mechanical_patch
```

Spark may extract evidence, map files, identify transcript fragments, or make
tiny mechanical patches. Spark must not own multi-turn client dialogue
evaluation, target-client readiness judgment, new acceptance criteria,
requirement refinement decisions, final readiness, security/trust decisions, or
runtime/global/client mutation.

Practical axiom: Spark is optimized for code and textual artifacts, not
social/inferential interaction with other agents. Do not assign Spark to steer,
interview, evaluate, or repair live Pi/OpenCode/Codex/Gemini behavior. Use it
only on the artifacts those sessions produce, under a controller or semantic
evaluator that owns the judgment.

Evaluation axiom: deterministic tools may check structure but not meaning for
model-dependent outputs. A work unit is not Spark-eligible if its pass/fail,
score, readiness, or acceptance depends on matched strings, regexes, keyword
searches, or string parsing over free-form generated prose. The only permitted
deterministic exception is declared structured model output such as JSON:
parseability, schema shape, required fields, and enum/value structure may be
checked by code, but must be paired with non-deterministic evaluator review.

## Fork Rule

```text
fork_context=true ⇔ child inherits same {model, agent_type, reasoning_effort}
change({model, agent_type, reasoning_effort}) → fork_context=false + explicit context
Spark default → fork_context=false unless parent is already Spark with no setting change
```

## Dispatch Rule

```text
SO selects candidate task → classify → dispatch card

If task is semantic-ambiguous, approval-gated, destructive, global, runtime
mutating, or the immediate blocker for the controller's next useful step:
  keep local unless the user explicitly authorizes another workflow.
```

## Controller Integration

Workers and reviewers return evidence. The controller checks model choice,
fork rule, task class, forbidden actions, and report evidence before accepting
or integrating output. A fast response is not a substitute for the correct
model lane.
