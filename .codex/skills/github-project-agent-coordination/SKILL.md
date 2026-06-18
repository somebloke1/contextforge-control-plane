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

## Project Enum Value Semantics

If a single-select enum value is not defined here, do not use it as an agent
coordination signal until the operator or a follow-up source/docs branch gives
it a ContextForge-specific meaning.

`Status` values are workflow-owned:

- `Todo`: open item added to the project but not workflow-linked to active
  work.
- `In progress`: workflow evidence says the issue or PR is active, linked,
  reopened, or under review.
- `Done`: issue or PR is closed or merged.

`Agent state` values are agent-owned:

- `Candidate`: plausible future work, not selected now.
- `Ready`: validated or prepared enough to pick up without broad rediscovery.
- `Active`: current SuperLoop/subgoal work.
- `Blocked`: cannot advance without an approval, external state, or concrete
  prerequisite.
- `In Review`: source or plan is packaged for review, merge, or acceptance.
- `Done`: merged, closed, or otherwise completed with durable evidence.
- `Deferred`: intentionally later-phase work that should not attract ordinary
  cleanup pressure.

`Lane` values identify the dominant roadmap surface:

- `Service identity`: canonical naming, deduplication, and backend identity.
- `Project state`: project-local state files, contracts, and helper readback.
- `Contract artifacts`: schemas, fixtures, and machine-readable agreements.
- `Project init`: activation, repair, approval, and apply/readback flows.
- `Authorization`: operator approvals and action boundaries.
- `Apply recovery`: recovery from partial or failed apply operations.
- `Service management`: service lifecycle scripts, manifests, and health.
- `Registry validation`: ContextForge registry checks and registration proof.
- `Transport`: stdio, SSE, streamable HTTP, and bridge behavior.
- `Tool policy`: client/tool allowlists, guidance, and safety controls.
- `Client adapters`: Pi, OpenCode, or other client-specific integration code.
- `Evidence`: probes, ledgers, proof artifacts, and claim discipline.
- `Trust`: hook trust, consent, provenance, and trust-state boundaries.
- `Auth`: tokens, credentials, login, and authentication boundaries.
- `Remote exposure`: network exposure, ports, hosts, and remote access.
- `Service provisioning`: installing or materializing backend services.
- `Proof service`: reusable validation/proof-producing service behavior.
- `Language catalog`: prompt, resource, and tool-language inventory.
- `Service onboarding`: facilitated addition of new MCP/service offerings.
- `Inventory`: read-only discovery of configured services and clients.
- `Tool guidance`: registered prompt/resource guidance for tools.
- `Governance`: decisions, abeyant intentions, and open questions.
- `Memory`: continuity, compaction, and persistent agent knowledge.
- `Wrapper validation`: wrapper lifecycle and wrapper/client behavior checks.
- `Operator UX`: human-facing command flow, prompts, and ergonomics.
- `Coordination`: issue, PR, Project, merge queue, and SuperLoop orchestration.
- `Readiness`: acceptance gates and activation-readiness packaging.

`Priority` values describe importance:

- `low`: useful cleanup or later polish.
- `medium`: worthwhile roadmap work without urgent sequencing pressure.
- `high`: important for near-term roadmap progress or repeated friction.
- `critical`: blocks safe operation, major roadmap progress, or trust.

`Risk` values describe expected blast radius if mishandled:

- `Low`: local, easy to verify, and easy to revert.
- `Low-Med`: mostly local with a small coordination or behavior risk.
- `Med`: meaningful cross-file, workflow, or user-visible risk.
- `Med-High`: broad workflow/runtime impact or difficult recovery.
- `High`: could disrupt active operation, trust, secrets, or critical state.

`Effort` values describe likely implementation size:

- `Low`: one focused edit, probe, issue update, or narrow test slice.
- `Medium`: several coordinated edits or a moderate validation pass.
- `High`: multi-surface implementation, migration, or extended validation.

`Complexity` values describe reasoning and integration uncertainty:

- `Low`: clear pattern and isolated behavior.
- `Medium`: multiple dependencies or nontrivial sequencing.
- `High`: architecture, runtime integration, or uncertain external behavior.

`Team` is inherited from a generic GitHub Project template. Do not set
`Squad 1`, `Squad 2`, or `Squad 3` for ContextForge work until a real team
model is defined.

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

## Update Cadence

At goal re-entry:

1. Inspect the formal goal.
2. Inspect repo branch/status and relevant issue/PR state.
3. Inspect Project #6 `Agent Issue View`, including roadmap draft items, with
   a filtered or cached read rather than repeated broad board scans.
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

## GraphQL Budget Discipline

GitHub Project v2 reads and writes are GraphQL-backed. Repeated broad
`gh project field-list`, `gh project item-list --limit 100`, per-item
`item-edit`, and full-board readback loops can exhaust the hourly GraphQL
budget before the roadmap work itself is done.

Use this rate-aware pattern:

- Cache the Project ID, item IDs, field IDs, and single-select option IDs for
  the current session or goal turn. Refresh field IDs only when they are
  missing, stale, or the operator changed the Project schema.
- At SuperLoop re-entry, take at most one Project #6 snapshot unless the board
  itself is the current subgoal. Prefer server-side filtering with
  `gh project item-list --query`, such as `-status:Done`, instead of fetching
  the full board and filtering only with `jq`.
- Use REST-backed issue/PR reads for substantive GitHub state when Project
  fields are not needed, for example `gh api repos/OWNER/REPO/issues`.
  Use native REST issue/PR mutations for assignees, labels, milestones, and
  repository-owned fields; Project item field mutations do not own those
  values.
- Compute updates locally and skip no-op mutations.
- For one or two field updates, `gh project item-edit` is acceptable. For
  larger multi-item or multi-field updates, consider a small direct
  `gh api graphql` mutation batch with aliased
  `updateProjectV2ItemFieldValue` calls after computing a no-op-free local
  plan. Treat each mutation result independently; aliased mutation batches are
  an efficiency tactic, not a transaction boundary.
- Avoid concurrent Project mutation runs. Keep batches bounded, pause between
  larger mutative runs, and watch both primary GraphQL budget and secondary
  limits such as endpoint points, CPU time, and content generation.
- Avoid per-item readback. Do one targeted readback for changed item IDs, or
  defer board readback into the goal evidence if GraphQL budget is low.
- When reading Project pages directly through GraphQL, follow `pageInfo`
  cursors until `hasNextPage` is false. Do not assume one `first:100` page is
  complete, and request smaller pages when a query touches many connections.
- Project item content can be `REDACTED` if the current GitHub identity cannot
  view the underlying issue, PR, or draft. Treat that as a permission/readback
  limitation rather than as an absent item.
- GitHub Project v2 items cannot be added and field-updated in the same API
  call. For draft-item automation, add the item first, then update fields.
- Prefer rate-limit response headers where available; use `gh api rate_limit`
  or a GraphQL `rateLimit` query as explicit evidence when headers are not
  visible in the current tool flow.
- If GraphQL remaining budget is low, preserve the pending Project action in
  the formal goal and continue source/test work that does not require Project
  mutation.

Do not let rate-limit avoidance weaken evidence discipline. The goal is fewer
better-shaped reads and writes, not skipping the Project #6 coordination
contract.

Issue #166 owns the future helper implementation for this pattern. Until that
helper exists, agents should apply the discipline manually and keep Project
mutations small, explicit, and evidence-backed.

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
gh project view 6 --owner "$CONTEXTFORGE_GITHUB_PROJECT_OWNER" --format json
gh project field-list 6 --owner "$CONTEXTFORGE_GITHUB_PROJECT_OWNER" --format json
gh project item-list 6 --owner "$CONTEXTFORGE_GITHUB_PROJECT_OWNER" --format json --limit 100
gh project item-list 6 --owner "$CONTEXTFORGE_GITHUB_PROJECT_OWNER" --format json --query '-status:Done' --limit 80
gh api "repos/$CONTEXTFORGE_GITHUB_REPO/issues?state=open&per_page=60"
gh api rate_limit --jq '{core:.resources.core, graphql:.resources.graphql}'
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

When several Project fields or items need updates, create a local plan first
and consider a direct GraphQL batch instead of issuing many independent
`gh project item-edit` calls with full-board readbacks between them.
