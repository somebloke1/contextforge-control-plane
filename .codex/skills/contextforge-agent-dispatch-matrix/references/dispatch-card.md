# Dispatch Card Reference, Symbolic Form

Use with `contextforge-agent-dispatch-matrix/SKILL.md` and
`../../SHARED_SYMBOL_SCHEME.md`.

## DC Schema

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

## Spark-Eligible Classes

```text
SE := {
  transcript_extraction,
  readiness_claim_lint,
  issue_pr_topology_audit,
  test_fixture_mapping,
  dispatch_card_audit,
  schema_probe_stub*,
  evidence_checklist,
  stale_claim_scan,
  patterned_doc_patch,
  fixture_patch
}

*schema_probe_stub → semantics require SO or M55 review before commit.
```

Constraint:

```text
Sp∈SE only when work = extraction ∨ mechanical_transform.
Sp ✗ {new_acceptance_criteria, validation_semantics, runtime_policy,
      service_localization_semantics, readiness_claims}
```

Structure-not-meaning boundary: matched strings, regexes, keyword checks, and
string parsing are acceptable only for structural evidence; dialogue quality,
readiness, and semantic acceptance require a non-deterministic evaluator.

## Controller-Only Classes

```text
CO := {
  architecture_decision,
  target_client_validation_judgment,
  service_localization_judgment,
  runtime_mutation_plan_or_apply,
  registry_mutation_plan_or_apply,
  project_init_apply_or_recovery,
  global_client_or_trust_change,
  governance_ledger_mutation,
  security_auth_token_remote_exposure_decision,
  final_acceptance_or_readiness_claim,
  pr_push_merge_close_or_issue_closure
}

Sp may extract E for CO; Sp must not decide CO.
```

## Examples

Spark:

```text
DC{
  task_class=transcript_extraction,
  expected_value=extract exact validation failure evidence,
  risk_layer=source/evidence,
  exercised_surface=ignored transcript file,
  write_scope=none,
  verification_available=line ranges and tool names,
  selected_model=gpt-5.3-codex-spark,
  reasoning_effort=low,
  agent_type=explorer,
  fork_context=false,
  selection_reason=fast bounded extraction with no semantic acceptance,
  forbidden_actions={file edits, GitHub mutation, readiness judgment},
  acceptance_owner=controller
}
```

`gpt-5.5`:

```text
DC{
  task_class=target_client_validation_judgment,
  expected_value=decide whether evidence supports target-client readiness,
  risk_layer=readiness acceptance,
  exercised_surface=transcript plus client evidence,
  write_scope=none,
  verification_available=evidence references and guardrail docs,
  selected_model=gpt-5.5,
  reasoning_effort=high,
  agent_type=reviewer,
  fork_context=true only if inheriting same settings,
  selection_reason=semantic readiness judgment is controller-only,
  forbidden_actions={runtime mutation, GitHub closure},
  acceptance_owner=controller
}
```

`gpt-5.4-mini`:

```text
DC{
  task_class=routine_source_worker,
  expected_value=update one script and matching tests,
  risk_layer=source/tests,
  exercised_surface=tracked source files,
  write_scope=one script plus one test file,
  verification_available=focused unittest command,
  selected_model=gpt-5.4-mini,
  reasoning_effort=medium,
  agent_type=worker,
  fork_context=false,
  selection_reason=routine bounded implementation,
  forbidden_actions={runtime mutation, PR push, final acceptance},
  acceptance_owner=controller
}
```

Fidelity: preserves all DC fields, model literals, Spark-eligible classes,
controller-only classes, and examples from v2 reference in symbolic notation.
