# Dispatch Card Reference

## Schema

```text
dispatch_card := {
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
transcript_extraction
readiness_claim_lint
issue_pr_topology_audit
review_disposition_evidence_map
test_fixture_mapping
dispatch_card_audit
evidence_checklist
acceptance_report_index
project_update_plan_lint
comment_body_draft_from_controller_report
agent_pool_hygiene_snapshot
link_and_path_check
temporary_residue_scan
schema_option_readback_summary
stale_claim_scan
patterned_doc_patch
fixture_patch
```

Spark eligibility requires extraction or mechanical transformation. Spark is
not eligible for new acceptance criteria, validation semantics, runtime policy,
service-localization judgment, requirement-refinement decisions, or readiness
claims.

For review-disposition work, Spark may extract facts and apply a
controller-supplied mechanical checklist, but the controller owns the state
recommendation and all GitHub/Project mutations. Spark may prepare evidence
maps, stale-reference scans, mutation-plan lint, link/path checks, issue/PR
metadata tables, and comment drafts from already accepted controller reports;
it must not decide final Agent state, issue closure, PR readiness, or review
acceptance.

Spark eligibility also excludes any semantic oracle over free-form generated
prose. A dispatch card must not treat matched strings, regexes, keyword
searches, or string parsing as the pass/fail, score, readiness, or acceptance
mechanism for model output. Those tools may only organize or structurally
validate evidence. The only deterministic exception is declared structured
model output such as JSON, where code may check parseability, schema shape,
required fields, and enum/value structure, and only when paired with
non-deterministic evaluator review.

## Controller-Only Classes

```text
architecture_decision
target_client_dialogue_judgment
service_localization_judgment
runtime_mutation_plan_or_apply
registry_mutation_plan_or_apply
project_init_apply_or_recovery
global_client_or_trust_change
governance_ledger_mutation
security_auth_token_remote_exposure_decision
final_acceptance_or_readiness_claim
pr_push_merge_close_or_issue_closure
```

Spark may extract evidence for these classes. It must not decide them.
