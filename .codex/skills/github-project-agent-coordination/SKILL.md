---
name: github-project-agent-coordination
description: Use when working on ContextForge roadmap, SuperLoop, issue, PR, or merge-queue coordination that should consult or update GitHub Project #6 Agent Issue View. Covers when to read the board, when to update Agent state, how to relate board fields to issues/PRs, and how to avoid duplicating roadmap or evidence ledgers.
---

# GitHub Project Agent Coordination

Use GitHub Project #6, `cf-controlplane-project`, as a lightweight coordination
index for agent work selection and near-roadmap anticipation. The board helps
agents answer what is active, blocked, ready, deferred, or done across issues,
PRs, and deliberately scoped roadmap draft items. It is not a second issue
body, PR body, evidence ledger, or goal store.

## Core Rules

- Read Project #6 `Agent Issue View` during SuperLoop re-entry before choosing
  or confirming the current subgoal.
- Include both live issue/PR items and roadmap draft items in that readback.
- Treat issues, PRs, repo files, tests, runtime probes, and governance ledgers
  as authoritative for substance.
- Use the project board only for cross-object coordination and roadmap-lane
  visibility.
- Update `Agent state` only after durable state changes, not for transient
  progress within a turn.
- Create or update draft roadmap items only for durable future paths named by
  roadmap artifacts, user intent, or repeated project evidence. Do not create
  draft items for every thought, command, or transient follow-up.
- Promote a draft roadmap item to an issue or PR only when it becomes selected
  bounded work with acceptance criteria and an evidence plan.
- Respect configured GitHub Project workflows: if GitHub auto-adds issue or PR
  items, or auto-marks merged PR items done, do not create duplicate native
  project items or fight the workflow-managed status.
- Preserve the board-use directive in successor formal goals.
- Keep mutations idempotent: read the item and field IDs first, then update
  only the intended project item field.

## Field Semantics

- `Title`: native issue/PR title, or a concise `Roadmap: ...` title for draft
  roadmap items.
- `Status`: GitHub Projects default workflow state. Leave it coarse unless the
  operator asks to make it authoritative. Prefer configured GitHub workflow
  automation for native issue/PR status transitions.
- `Labels`: native issue labels. Maintain on issues, not by project-field hacks.
- `Linked pull requests`: native GitHub relationship. Prefer PR body/reference
  hygiene over manual board bookkeeping.
- `Parent issue`: use only when GitHub issue hierarchy is intentionally set.
- `Created` and `Updated`: native timestamps. Do not manually maintain.
- `Agent state`: agent-facing coordination state. This is the main field agents
  may update.

## Roadmap Draft Items

Roadmap draft items are allowed when the project needs an intelligible,
intentful future visible to agents before every lane is ready to become a
GitHub issue. Keep them at lane or bounded-initiative resolution:

- title format: `Roadmap: <lane or initiative>`;
- body: outcome, current evidence source, promotion trigger, and non-goals;
- `Agent state`: usually `Candidate`, `Ready`, or `Deferred`;
- no detailed evidence duplication; link or name the authoritative doc, issue,
  PR, or decision instead.

Use draft items to prevent future paths from being lost during compaction or
goal refresh. Do not let draft items replace issues once implementation begins.
When a draft roadmap item is promoted to an issue or PR, allow the configured
Project workflow to create the native issue/PR project item. Then retire,
defer, or cross-reference the draft item so the board does not contain two
active items for the same work.

## Configured Project Workflows

The following GitHub Project #6 workflows were verified read-only in the GitHub
UI on 2026-06-17. Treat this as the current automation contract until a fresh
browser or API readback proves it changed.

- `Auto-add to project`: for repository `contextforge-control-plane`, filter
  `is:issue,pr is:open`; matching open issues and PRs are added to the
  project.
- `Item added to project`: when an issue or pull request is added, set
  `Status: Todo`.
- `Pull request linked to issue`: when a pull request is linked to an issue,
  set `Status: In progress`.
- `Code changes requested`: when a pull request has a review requesting
  changes, set `Status: In progress`.
- `Code review approved`: when a pull request is approved, set
  `Status: In progress`.
- `Pull request merged`: when a pull request is merged, set `Status: Done`.
- `Item closed`: when an issue or pull request is closed, set `Status: Done`.
- `Item reopened`: when an issue or pull request is reopened, set
  `Status: In progress`.
- `Auto-close issue`: when `Status` is updated to `Done`, close the issue.
- `Auto-add sub-issues to project`: when an item in the project has
  sub-issues, add the sub-issues to the project.
- `Auto-archive items`: filter `is:issue is:closed updated:<@today-2w`; archive
  matching items on GitHub's periodic workflow cadence, shown in the UI as
  every 12 hours.

Operational consequences:

- Do not manually create native issue or PR project items for open
  `contextforge-control-plane` issues/PRs; the auto-add workflow should do it.
- Do not manually manage native issue/PR `Status` unless repairing a proven
  workflow miss; `Status` is workflow-owned for normal issue/PR lifecycle
  transitions.
- Do manually manage `Agent state` as the agent coordination field.
- Do manually manage roadmap draft items because they are not native
  repository issues or PRs.
- When a roadmap draft item is promoted to a real issue, let the workflow add
  the issue item, then mark the draft item `Done`, `Deferred`, or
  cross-referenced so the board has one active owner for the work.

## Workflow Knowledge Persistence

Persist the workflow automation map in this skill. Goal text, issue comments,
PR bodies, and roadmap docs may point here or quote a short reminder, but they
must not become the canonical store for GitHub Project workflow behavior.

When a browser or API readback discovers a workflow change, update this section
and `Configured Project Workflows` in the same source/docs/tests branch that
depends on the change. Record the readback date and whether the evidence came
from the GitHub UI, `gh project` commands, or both. If the workflow cannot be
read, do not infer changes from project item state alone; report the limitation
and treat the last verified workflow map as stale-but-operative until refreshed.

Successor formal goals should carry only the compact directive: read Project #6
`Agent Issue View` at goal re-entry and maintenance, and use this skill for the
workflow contract. This keeps the goal persistent without turning it into a
copy of the skill.

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
3. Inspect Project #6 `Agent Issue View`, including roadmap draft items.
4. Reconcile `Agent state` against live issue/PR evidence before selecting or
   confirming the next subgoal.
5. Notice missing or stale roadmap draft items only as coordination findings;
   create or update them during goal maintenance unless the current bounded
   subgoal is board hygiene.

At goal maintenance:

1. Record durable evidence in the issue, PR, doc, or governance ledger.
2. Update `Agent state` only if the coordination state changed.
3. Add, update, retire, or promote roadmap draft items when roadmap artifacts
   expose durable future paths not represented by issues or PRs.
4. Let configured Project workflows auto-add linked issues/PRs and auto-close
   or mark merged PR items done; manually reconcile only gaps that workflows do
   not cover.
5. Include the board-use directive in the successor formal goal.

## Suggested State Patterns

- A validated PR awaiting merge approval: PR `Blocked`; owning issue `In Review`.
- A merged PR whose owning issue remains open for broader work: PR `Done`;
  owning issue remains `In Review`, `Ready`, or `Active` depending on the next
  slice.
- A late-phase runtime blocker that should not be selected now: `Deferred`.
- A newly surfaced follow-up without a selected slice: `Candidate`.
- A current implementation or readiness slice: `Active`.
- A durable roadmap lane that is visible but not yet sliced: draft item
  `Candidate`.
- A roadmap lane with a clear next slice but no current approval: draft item
  `Ready`.
- A roadmap lane intentionally reserved for a later stability phase: draft item
  `Deferred`.

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
