---
name: github-project-agent-coordination
description: Use when working on ContextForge roadmap, SuperLoop, issue, PR, or merge-queue coordination that should consult or update GitHub Project #6 Agent Issue View. Covers when to read the board, when to update Agent state, how to relate board fields to issues/PRs, and how to avoid duplicating roadmap or evidence ledgers.
---

# GitHub Project Agent Coordination

Use GitHub Project #6, `cf-controlplane-project`, as a lightweight coordination
index for agent work selection. The board helps agents answer what is active,
blocked, ready, deferred, or done across issues and PRs. It is not a second
roadmap, issue body, PR body, evidence ledger, or goal store.

## Core Rules

- Read Project #6 `Agent Issue View` during SuperLoop re-entry before choosing
  or confirming the current subgoal.
- Treat issues, PRs, repo files, tests, runtime probes, and governance ledgers
  as authoritative for substance.
- Use the project board only for cross-object coordination state.
- Update `Agent state` only after durable state changes, not for transient
  progress within a turn.
- Preserve the board-use directive in successor formal goals.
- Keep mutations idempotent: read the item and field IDs first, then update
  only the intended project item field.

## Field Semantics

- `Title`: native issue/PR title. Do not manually maintain.
- `Status`: GitHub Projects default workflow state. Leave it coarse unless the
  operator asks to make it authoritative.
- `Labels`: native issue labels. Maintain on issues, not by project-field hacks.
- `Linked pull requests`: native GitHub relationship. Prefer PR body/reference
  hygiene over manual board bookkeeping.
- `Parent issue`: use only when GitHub issue hierarchy is intentionally set.
- `Created` and `Updated`: native timestamps. Do not manually maintain.
- `Agent state`: agent-facing coordination state. This is the main field agents
  may update.

## Agent State Values

- `Candidate`: plausible future work, not selected now.
- `Ready`: validated or prepared enough to pick up without broad rediscovery.
- `Active`: current SuperLoop/subgoal work.
- `Blocked`: cannot advance without an approval, external state, or concrete
  prerequisite.
- `In Review`: source or plan is packaged for review, merge, or acceptance.
- `Done`: merged, closed, or otherwise completed with durable evidence.
- `Deferred`: intentionally later-phase work that should not attract ordinary
  cleanup pressure.

## Update Cadence

At goal re-entry:

1. Inspect the formal goal.
2. Inspect repo branch/status and relevant issue/PR state.
3. Inspect Project #6 `Agent Issue View`.
4. Reconcile `Agent state` against live issue/PR evidence before selecting or
   confirming the next subgoal.

At goal maintenance:

1. Record durable evidence in the issue, PR, doc, or governance ledger.
2. Update `Agent state` only if the coordination state changed.
3. Include the board-use directive in the successor formal goal.

## Suggested State Patterns

- A validated PR awaiting merge approval: PR `Blocked`; owning issue `In Review`.
- A merged PR whose owning issue remains open for broader work: PR `Done`;
  owning issue remains `In Review`, `Ready`, or `Active` depending on the next
  slice.
- A late-phase runtime blocker that should not be selected now: `Deferred`.
- A newly surfaced follow-up without a selected slice: `Candidate`.
- A current implementation or readiness slice: `Active`.

## Useful Commands

```sh
gh project view 6 --owner somebloke1 --format json
gh project field-list 6 --owner somebloke1 --format json
gh project item-list 6 --owner somebloke1 --format json --limit 100
```

To update a single-select value, first resolve the project ID, item ID, field
ID, and option ID from the readback above, then run:

```sh
gh project item-edit \
  --project-id PROJECT_ID \
  --id ITEM_ID \
  --field-id FIELD_ID \
  --single-select-option-id OPTION_ID
```
