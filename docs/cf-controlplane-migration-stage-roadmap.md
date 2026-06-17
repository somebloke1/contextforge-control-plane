# ContextForge `cf-controlplane` Migration Stage Roadmap

Date: 2026-06-17

This roadmap stage governs the transition from the legacy working path
`/home/dgk/workspace/context-portal` to the canonical control-plane workspace
`/home/dgk/workspace/cf-controlplane`.

The project name is ContextForge / Context Forge. `context-portal` is a
deprecated path and compatibility identifier until the migration is complete.

## Supergoal: Cyclic Goal Refinement

The operating agent belongs in a persistent goal loop. The loop itself is the
supergoal: finish one bounded subgoal, settle evidence and residual risk, then
refine and activate the next formal goal without losing unchosen context.

Every major subgoal in this migration must end with a goal-maintenance step:

1. prove or reject completion against current evidence;
2. preserve value delivered, non-actions, approvals, delegated outputs, and
   residual risks;
3. update this roadmap or the governance ledgers when durable truth changes;
4. retire, split, defer, or promote candidate subgoals;
5. activate the next formal Codex goal with the cyclic-refinement directive
   included in the goal text.

This protocol is user-authorized and persistent. When the user changes the
operating goal, the operator's instruction is the authority for refining the
goal chain. The previous formal goal must not lock the agent into stale work
when goal refinement is itself the instructed work.

The user has expressly and unambiguously authorized the operating agent to pass
through goals iteratively in this migration stage. This means a formal goal may
be retired as complete when its purpose has been satisfied by preserving its
state, evidence, residual risk, and next-action intent into a refined successor
goal, even though that would not be "normal" closure for a singular,
non-iterative goal. The measure of completion for this iterative method is not
whether the entire migration is finished inside one goal object; it is whether
the completed subgoal has been settled without loss and the next formal goal
has been activated with the cyclic-refinement directive intact.

This authorization is not optional process commentary. It is part of the
operating contract for the agent: after each major subgoal, complete the
current goal when the refinement act has preserved the prior state, then create
the next goal rather than remaining trapped in a stale goal object.

## Live-System Boundary

Until an explicit replacement checkpoint, normal Codex Desktop and normal local
Codex sessions continue using the existing live ContextForge installation. The
new `cf-controlplane` workspace and container harness are a development and
validation layer.

Exception: disposable client agents inside the container/VM harness may point at
the candidate ContextForge stack for validation.

Do not silently repoint global Codex config, Codex Desktop, project hooks, or
the root operating agent to the candidate gateway.

## GitHub Operating Protocol

The GitHub issue/branch/PR pattern used in the legacy workspace must resume
immediately in `cf-controlplane`. The new workspace does not reset the
coordination standard.

Required habit:

- every meaningful migration or implementation slice maps to a GitHub issue or
  an explicitly documented existing issue;
- branches are cut from the agreed migration/root branch and named by slice;
- PRs stay focused, preferably draft while still proving evidence;
- PR descriptions include outcome, non-goals, acceptance evidence, tests/probes,
  residual risk, and rollback or pause conditions;
- issue comments or roadmap entries record evidence and closeout state;
- no giant mixed PR is opened from a dirty holding branch;
- after each merge or handoff, the active goal is refined and the next issue/PR
  target is selected before implementation resumes.

When control moves to `cf-controlplane`, the first operating-agent pass must
refresh GitHub state from that workspace before claiming current issue, PR,
branch, or CI truth.

## Migration Objects

### Track Through Git

- curated `.codex/hooks/` and `.codex/skills/`;
- governance ledgers and roadmap files after path cleanup;
- Docker harness definitions, scripts, examples, and locality policy;
- service manifests, templates, and validation scripts;
- documentation that describes desired state and operator procedure.

### Keep Ignored Or Recreate

- `env/contextforge.env`, API tokens, passwords, generated JWTs, OAuth state;
- Docker volumes, SQLite DBs, runtime logs, and evidence DB backups;
- authenticated image layers and baked auth captures unless explicitly
  recaptured as local runtime state;
- Codex Desktop trust/approval state, which must be re-approved per workspace;
- generated diagnostics unless intentionally promoted after sanitization.

### Copy Selectively After Clone

- project-local Codex operating artifacts that are intentional but not yet
  tracked;
- sanitized prompt/governance artifacts that should become durable;
- local env examples, never live secret files;
- selected non-secret evidence summaries, not raw runtime state.

Any copied runtime Codex artifact must be checked against the cloned tree
before copying. If the clone already supplies the same logical file, either
merge intentionally, skip the copy, or record an explicit replacement decision.
Do not overwrite cloned hooks, skills, prompts, config, or governance files with
stale runtime copies by default.

Runtime Codex artifacts copied for local operation must be ignored unless they
are intentionally promoted to source-of-truth project files. This includes
local trust markers, hook approval state, generated continuity snapshots,
session-local diagnostics, prompt caches, and other Codex runtime products.

### Legacy Workspace Archive

The legacy `context-portal` checkout may remain as an accessible archive after
the migration source is finalized. The archive is insurance for missed
artifacts, not a blocker that forces every dirty file to be resolved before the
clone.

The migration source is sufficient when essential tracked/promoted artifacts
for `cf-controlplane` are present, runtime/local artifacts are ignored or
explicitly copy-later, and the old workspace is preserved readably for later
retrieval. Do not delete, reset, or discard the dirty legacy workspace merely to
make it look clean.

### GitHub Dirty-Retirement Gate

GitHub issue #15 was the authoritative completion indicator for retiring the
dirty `context-portal` checkout as an agent operating surface:

- <https://github.com/somebloke1/contextforge-control-plane/issues/15>

Current issue #15 state: closed. Its remaining practical concerns have been
transferred to the specific successor gates that own them:

- issue #37 owns `cf-controlplane` project-local Codex operating-context
  activation;
- issue #31 owns Codex runtime/project-context readback after the global config
  migration;
- issue #2, issue #3, issue #4, issue #5, and issue #33 continue to own their
  original service/project-init/Pi/registry/Serena work where still open.

Current refreshed evidence on 2026-06-17:

- issue #15 is closed;
- issue #37 is open for `cf-controlplane` project-local activation;
- issue #31 is open for Codex `pending_restart` and runtime readback after the
  approved global config migration;
- issue #31 now distinguishes the state precisely: the global config/trust
  migration is verified at disk and fresh CLI readback level, but active
  Codex Desktop project-local wrapper processes still come from the legacy
  `context-portal` project because this Desktop thread remains rooted there.

The archive-insurance posture remains valid only as an interim operating
strategy. It does not complete issue #37 or issue #31 until the new
`cf-controlplane` project context proves hooks, skills, MCP paths, and runtime
readback from the new root.

### Cleanup Semantics

For this migration, cleanup is not equivalent to making `git status` quiet.
Cleanup means the old and new operating surfaces have a deliberate, verified
relationship:

- source artifacts needed by future agents are tracked or intentionally staged
  for tracking before the clone;
- local Codex runtime artifacts are either recreated in `cf-controlplane`,
  copied only after path and secret review, or preserved only as archive
  evidence;
- project-local hooks, skills, prompt files, governance ledgers, and continuity
  scripts are treated as agent operating infrastructure, not incidental files;
- hook approval state, trust state, generated continuity snapshots, OAuth
  state, Docker volumes, service DBs, live env files, and token caches remain
  local/runtime state unless an explicit promotion decision says otherwise;
- absolute references to `/home/dgk/workspace/context-portal` are classified
  before migration as historical, compatibility, archive-only, or operational
  blockers;
- the legacy checkout may remain readable as insurance, but it must not remain
  a hidden source of skills, hooks, MCP commands, roadmap truth, or active
  Codex project identity after the `cf-controlplane` handoff.

Therefore a dirty-checkout cleanup claim must answer two questions together:

1. What happened to each meaningful source or runtime artifact in the old
   workspace?
2. How will the corresponding agent capability, if still needed, exist in the
   new `cf-controlplane` workspace without stale path dependence?

If either answer is missing, cleanup is incomplete even if the local Git tree
looks clean.

The current artifact-level disposition report is:

- `docs/cf-controlplane-artifact-disposition-2026-06-17.md`

## Subgoal Chain

### Subgoal 1: Validate Essential Migration Source

Outcome: validate that the essential artifacts already refined for migration
are present and intentionally categorized, while leaving the remaining dirty
legacy checkout available as an archive/insurance source.

Acceptance evidence:

- `git status --short --branch` captured;
- essential migration artifacts are enumerated: roadmap, governance, hooks,
  skills, Docker harness definitions, ignore rules, and validation scripts;
- each essential artifact is assigned to track, ignore, copy later, or needs
  decision;
- remaining dirty artifacts are explicitly classified as archive-only unless
  evidence shows they are essential;
- issue #15 and any successor blocker issues are read and reconciled into this
  roadmap before the subgoal is claimed complete;
- no unrelated dirty work is reset, deleted, or discarded.

Goal-maintenance output:

- update this file with the accepted essential-artifact disposition map or link
  to a generated sanitized report;
- refine the next formal goal to Git curation and clone preparation.

Current disposition report:

- `docs/cf-controlplane-artifact-disposition-2026-06-17.md`

Current blockers:

- issue #15 is closed; remaining operating-context work is owned by issue #37;
- issue #31 remains open;
- `.codex/config.toml` and `.project/context_forge_state.json` still encode
  legacy `context-portal` operational identity and must not migrate as-is.
- `server-instances/serena-context-portal/**`, `scripts/project_init_common.py`,
  and `scripts/register_serena_context_portal_service.py` still require
  compatibility classification or rewrite before `cf-controlplane` can rely on
  them.

Current gate status:

- Issue #37 activation is not complete while any activation gate in
  `docs/cf-controlplane-artifact-disposition-2026-06-17.md` is `FAIL`.
- Subgoal 1 may close only after each `FAIL` or `PENDING` gate has an owner and
  next action, so moving to Git curation cannot be mistaken for cleanup
  completion.

### Subgoal 2: Curate Git-Tracked Migration Source

Outcome: the current repository contains the source-of-truth artifacts needed
to clone `cf-controlplane`, while runtime state remains ignored.

Current integration rule:

- assemble the migration source from clean `dev-root` plus selected unique
  additions, not by blanket-staging the dirty legacy checkout;
- Docker harnesses and migration-stage docs are unique migration source
  candidates absent from `origin/dev-root`;
- repo-local hooks, skills, and existing roadmap/runbook files already exist on
  `origin/dev-root` and require selective integration from the clean source
  plus targeted path cleanup;
- live `.codex/config.toml`, `.project/context_forge_state.json`, and
  `server-instances/serena-context-portal/**` remain blocked from as-is
  promotion.

Acceptance evidence:

- `.gitignore` explicitly covers runtime state and permits tracked templates;
- tracked files include intentional hooks, skills, harness definitions,
  locality policy, governance, and migration roadmap;
- copied-runtime destinations are either ignored or explicitly promoted, and do
  not conflict with clone-supplied files;
- tests or syntax checks for touched scripts pass;
- no secrets are present in staged/tracked content.

Goal-maintenance output:

- record remaining copy-later artifacts and approvals;
- refine the next formal goal to clone validation.

### Subgoal 3: Wrap Up Legacy Git Operations

Outcome: the legacy `context-portal` checkout has a Git-sound migration source
state, and further development in that checkout is paused except for emergency
or explicitly approved fixes.

Required operations:

1. preserve local state before branch or commit surgery;
2. commit or intentionally leave unstaged only those artifacts whose
   disposition map says they should not move through Git;
3. ensure the migration source branch contains the curated hooks, skills,
   governance files, roadmap files, harness definitions, and ignore rules;
4. run the agreed focused checks for touched scripts/docs;
5. push or otherwise make the migration source branch cloneable only after the
   user approves any ambiguous GitHub operation;
6. record the exact source branch and commit intended for the clone.

Acceptance evidence:

- `git status --short --branch` shows no unclassified migration-relevant
  changes;
- runtime and operational Codex artifacts that should exist only locally are
  covered by `.gitignore` or an equivalent project-local ignore rule before
  the checkout is treated as clean;
- `git log -1 --oneline` identifies the migration source commit;
- if pushed, `git status --branch` or `git rev-parse @{u}` confirms upstream
  alignment;
- remaining local-only artifacts are all either ignored, copy-later, or
  approval-gated;
- the roadmap records that the next step is to switch workspace, not continue
  ordinary development in `context-portal`.

Goal-maintenance output:

- refine the next formal goal to clone and immediate workspace handoff;
- pause if user action is required to approve GitHub operations, create the new
  Codex project, or approve project-local hooks.

### Subgoal 4: Clone `cf-controlplane`

Outcome: `/home/dgk/workspace/cf-controlplane` exists as a clean clone of the
curated branch and is not yet treated as the live substrate.

Acceptance evidence:

- clone command and source branch recorded;
- `git status --short --branch` clean in the clone;
- path scan reports old-path references classified as historical,
  compatibility, or operational;
- no secret/runtime files copied by Git.

Goal-maintenance output:

- refine the next formal goal to Codex operating-artifact activation.

Status as of 2026-06-17:

- Complete for Git clone creation. PR #35 was marked ready and merged into
  `dev-root` as `75aa437573ac3a8be38f584ab629da2bb0cfa814`.
- `/home/dgk/workspace/cf-controlplane` is a clean `dev-root` clone at that
  merge commit.
- Path scans found no `cf-control-plane-target`, `cf-controlplane-target`, or
  stale `cf-control-plane` target naming.
- The clone is not yet the live Codex operating substrate because
  `.codex/config.toml`, `.project/context_forge_state.json`,
  `server-instances/serena-context-portal/**`, and project-init resource
  identifiers still require retarget, regeneration, or explicit compatibility
  classification.
- GitHub evidence is recorded on issue #15, issue #31, and issue #37.

Immediate switch rule:

- after the clone validates, stop normal implementation in `context-portal`;
- switch control to a Codex project rooted at
  `/home/dgk/workspace/cf-controlplane` as soon as the user can create/open and
  approve that project;
- use the legacy checkout only as a reference or rollback source until the new
  workspace fails validation or the user explicitly redirects.

### Subgoal 5: Activate Project-Local Codex Operating Artifacts

Outcome: `cf-controlplane` has curated project-local hooks, skills, and
governance artifacts, with operational path references corrected and hooks
approved at the project level.

Runbook:

- `docs/cf-controlplane-project-local-activation-runbook.md`

Status as of this source-prep branch:

- branch `codex/issue-37-cf-controlplane-operating-context` prepares the
  project-local activation instructions and runbook from
  `/home/dgk/workspace/cf-controlplane`;
- it does not retarget `.codex/config.toml`, regenerate
  `.project/context_forge_state.json`, mutate hook trust, copy runtime state,
  touch services/systemd/registry/Pi/global config/processes, or edit the
  legacy checkout;
- draft PR #38 publishes the branch for review:
  <https://github.com/somebloke1/contextforge-control-plane/pull/38>;
- PR #38 is source-prep only and leaves environment setup, `.codex/config.toml`
  retarget, `.project/context_forge_state.json` regeneration/migration, Serena
  compatibility or regeneration, Codex project approval, and #31 runtime
  readback as later approval-gated transitions.

Acceptance evidence:

- `.codex/hooks/` and `.codex/skills/` present as intended;
- project-local hook list shows required hooks active after user approval;
- any copied Codex runtime artifacts are non-secret, ignored when local-only,
  and non-redundant with clone-supplied project files;
- path scan has no unintended `/home/dgk/workspace/context-portal`
  operational dependencies;
- a new Codex session can read the expected skills/governance from
  `cf-controlplane`.

Goal-maintenance output:

- retire `context-portal` as controller only after the clone proves this layer;
- refine the next formal goal to runtime recreation.

Pause gate:

- the current operating goal must pause when control needs to move from the
  legacy `context-portal` Codex project to a Codex project rooted at
  `/home/dgk/workspace/cf-controlplane`;
- the user must create/open the new Codex workspace, approve project-local
  hooks/trust, and confirm the new session is ready;
- the resumed or peer agent in `cf-controlplane` must read this roadmap,
  re-enter the cyclic goal loop, refresh evidence from the clone, and only then
  continue runtime recreation;
- do not treat the old workspace as retired until the new workspace proves
  project-local hooks, skills, governance, and harness definitions are active.

### Subgoal 6: Recreate Candidate Runtime State

Outcome: the candidate ContextForge harness runs from `cf-controlplane`
definitions with fresh ignored local env, not copied live secrets.

Acceptance evidence:

- env generated from templates;
- Docker gateway harness healthy;
- admin/API auth works;
- `gateways` and `servers` are empty until deliberate service registration;
- existing live ContextForge for normal Codex remains untouched.

Goal-maintenance output:

- refine the next formal goal to first MCP service integration or to migration
  hardening, depending on evidence.

## Replacement Checkpoint

The candidate stack can replace the current live ContextForge only after:

- container harness and selected MCP services validate both `/sse` and `/mcp`
  where supported;
- single-user service instance boundaries are explicit;
- client foils validate expected behavior;
- auth/token strategy is acceptable for the current phase;
- rollback path is documented;
- governance, hooks, skills, and goal-loop continuity work from
  `cf-controlplane`;
- the user explicitly approves replacement.

## Current Next Move

Continue Subgoal 5 by activating project-local Codex operating artifacts for
`/home/dgk/workspace/cf-controlplane`.

The next transition is not runtime recreation. First, retarget or regenerate the
project-local Codex config and project-state artifacts for the new root, keep
runtime secrets/evidence local-only, then have the user open/approve the
`cf-controlplane` Codex project and verify hooks, skills, governance, and
project-local MCP paths from that project context.

Do not treat issue #37 activation or issue #31 runtime verification as complete
until the new project context proves it is no longer using hidden
`context-portal` or `contextforge-slices` operating paths.

Source-edit boundary: after this clone, any new migration documentation,
configuration source, hook, skill, harness, or governance change belongs in
`/home/dgk/workspace/cf-controlplane` unless the user explicitly directs a
legacy compatibility edit. Do not create new source truth in the legacy
`/home/dgk/workspace/context-portal` directory that would not be reflected in
the cloned workspace.
