---
name: contextforge-project-init
description: Project-local ContextForge activation and validation workflow for this repository. Use when Codex needs to initialize, repair, approve, apply, validate, or explain project activation for ContextForge services, including Codex/Pi client bindings, Serena project instances, helper-mediated service selection, reload requirements, config conflicts, and .project/context_forge_state.json state.
---

# ContextForge Project Init

Use the visible `contextforge-helper` tools as the authority for project init.
Do not bypass them with direct file writes or shell-invoked helper scripts when
the task is project activation, approval, apply, reload acknowledgement, or
validation.

## Required Sequence

1. Call `get_project_context` or `cf_project_init_get_context` with:
   - `project_root=/home/dgk/workspace/context-portal`
   - `client_type=codex` unless the user explicitly targets Pi or another client.
2. Call `list_available_capabilities` or `cf_project_init_list_capabilities`.
3. If services are not selected, ask exactly one service-selection question using
   the helper-returned choices.
4. Pass selected service ids back to `cf_project_init_propose`. Do not rebuild
   descriptors by hand.
5. If the helper asks for one input, ask exactly that input. Serena language is
   currently a single-select helper input.
6. If the helper returns a plan, present the exact digest/challenge/effects and
   ask for scoped approval only.
7. After approval, use `cf_project_init_approve` with the exact challenge id and
   plan digest, then `cf_project_init_apply`.
8. If `cf_project_init_propose` returns `status=config_conflict` with an embedded
   `recovery_plan`, treat that embedded plan as the current helper-owned plan.
   Present its exact digest/challenge/effects, ask for scoped recovery approval,
   then call `cf_project_init_recovery_approve` followed by
   `cf_project_init_recovery_apply`.
9. If the helper reports reload is required, ask for explicit reload and stop.
10. After reload, record it with `cf_project_init_record_client_reload`, then
   validate or record skip only from the user's validation choice.

## Hard Boundaries

- `.project/context_forge_state.json` is the project-init authority.
- Client configs and extension files are discovery or activation surfaces, not
  service identity.
- Mutate only helper-approved project-local activation state.
- Do not mutate user-global trust, global client configs, secrets, live
  ContextForge registry/catalog state, backend installs, or backend restarts in
  ordinary project init.
- Do not use backend health or tool availability alone as validation proof.
  Validation must be target-client-visible and non-destructive.
- If helper tools are missing, stale, unsupported, or cannot complete the
  approval/apply path, stop at that readiness boundary.

## Conflict Handling

If `.codex/config.toml` already has unmanaged blocks with the selected aliases,
do not overwrite them. Use the helper's conflict prompt and embedded recovery
plan. After approval, prefer the cached recovery continuation:
`cf_project_init_recovery_approve` -> `cf_project_init_recovery_apply`.

Do not call `apply_project_init_recovery` with only `plan_id`, `plan_digest`, or
receipt ids. That lower-level endpoint requires the complete helper-returned
recovery plan object and will reject abbreviated objects because it revalidates
the plan digest from full contents. If you approved recovery through
`cf_project_init_recovery_approve`, use `cf_project_init_recovery_apply` unless
you intentionally have the full plan object and full receipt objects in hand.

If the helper cannot consume the user's conflict resolution through visible
tools, report that project activation remains blocked and avoid hidden writes.

## Reference

Read [helper-flow.md](references/helper-flow.md) when you need exact local files,
approved service classes, or validation expectations.
