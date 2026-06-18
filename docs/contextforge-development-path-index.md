# ContextForge Development Path Index

Date: 2026-06-18

This index is the current roadmap-facing path map for `cf-controlplane`.
It complements the historical migration roadmap by naming the active
development lanes that should guide SuperLoop subgoals after the source and
runtime migration queue has largely closed.

The project direction remains: use stock IBM ContextForge as the assistant
control plane, keep ContextForge-owned service identity canonical, treat client
configs as discovery or consumption surfaces, keep project initialization state
in `.project/context_forge_state.json`, and prove behavior through current
evidence rather than inherited claims.

## Agent Coordination Index

GitHub Project #6, `cf-controlplane-project`, is the lightweight agent
coordination index for current work selection and near-roadmap anticipation.
Its single required view is `Agent Issue View`; the board is not a duplicate
issue body, PR body, formal goal, or evidence ledger.

Agents should read `Agent Issue View` during SuperLoop re-entry before choosing
or confirming the next subgoal, including roadmap draft items alongside live
issue/PR items. They should reconcile `Agent state` values against current
GitHub issue/PR evidence where applicable. Agents should update `Agent state`
only when a durable coordination transition occurs, such as a PR becoming ready
for review, merging, blocking on approval, an issue becoming deferred, or a
roadmap lane becoming ready to promote into a bounded issue.

Roadmap draft items are allowed when a durable future path is visible but not
yet ready to become an implementation issue. Keep them at lane or
bounded-initiative resolution, with `Roadmap: ...` titles and bodies that name
the outcome, current evidence source, promotion trigger, and non-goals. Promote
them to issues or PRs when the work becomes selected, scoped, and evidence
planned. When configured GitHub Project workflows auto-add issue or PR items,
agents should let that automation create native project items and mark merged
PRs done rather than duplicating those transitions manually.

The repo-local skill
`.codex/skills/github-project-agent-coordination/SKILL.md` owns the detailed
practice for this board. Preserve the board-use directive in successor formal
goals so the practice survives goal refreshes and compaction.

## Surface Boundaries

All path work must name the exercised surface:

- `legacy/live ContextForge read-only`: the active operator substrate. Use for
  non-mutating health, readiness, config, process, socket, log, diagnostic, and
  comparison evidence only.
- `ContextForge dev Docker`: the isolated mutable gateway/app surface for
  development registration, endpoint, bridge, resettable integration, and
  generated evidence work.
- `Pi client Docker`: the Pi client foil against the development Docker
  surface. Pi is a TypeScript extension/shim client, not a native MCP config
  client.
- `OpenCode client Docker`: the OpenCode client foil against the development
  Docker surface.

Do not use legacy/live readback as proof that dev Docker or client Docker
flows currently work. Do not use Docker evidence as approval to mutate
legacy/live runtime, host Pi, global client config, hook trust/state, secrets,
or project-init apply/recovery state.

## Current GitHub Topology

Open issues:

- #95: post-merge refresh for this development path index after #93/#94
  landed.
- #52: guided MCP service-onboarding helper.
- #3: host Pi global ContextForge shim prompt/resource parity and live
  Pi-visible readback.
- #2: deferred Serena runtime blockers for the later migration/cutoff phase.

Recent PR topology:

- #87 merged the #52 source/docs/tests fixture increment for bridged stdio,
  credential-scoped, and client/session-local onboarding examples.
- #88 merged the source/docs/tests path-index refresh, including Project #6
  coordination practice and workflow knowledge persistence.
- #90 merged the client-visible activation matrix source/docs/tests slice and
  closed #89.
- #92 merged the #91 path-index topology refresh after #88/#90 landed and
  closed #91.
- #93 merged the #52 source-only resume envelope for deterministic
  `dialogue_session` metadata without file persistence.
- #94 merged the #52 opt-in local ignored session store under
  `run/service-onboarding-sessions/`.

Recently closed path-setting issues include #91, #89, #79, #83, #85, #62,
#58, #50, #41, #37, #31, #25, and #66. They are evidence and history, not
substitutes for current path ownership.

## Named Development Paths

### Runtime/Service Ops

Outcome: keep the stock ContextForge gateway, canonical service registry,
systemd units, prompt/resource guidance, bridge/transceiver behavior, and
`/mcp` plus `/sse` endpoint proof coherent and repeatable.

Current state:

- #79 closed the canonical live user-systemd migration and API registry
  reconstruction path.
- #83 closed all-services tool-guidance coverage after canonical registry
  reconstruction.
- README and AGENTS.md remain the primary source for stock gateway, native
  registration, service homes, bridge-only-when-needed, and endpoint
  verification rules.

Near-term gap:

- No open issue currently owns continuing operator-grade runtime readiness
  checks after future service additions. Create a focused issue when a new
  service or registry change needs runtime evidence beyond source planning.

### Project-State And Helper Control Plane

Outcome: make project activation explicit, reversible where practical,
idempotent, and mediated through helper/state contracts rather than silent
global config or runtime mutation.

Current state:

- #37 and #31 are closed for project-local operating-context activation and
  runtime/helper readback.
- #85 closed residual comparison-state cleanup for the retired archive state.
- `.project/context_forge_state.json` remains the project-init state authority
  by design decision, but this path does not authorize rewriting it during
  ordinary source-only work.

Near-term gap:

- The helper surface is still script-oriented. Operator productization should
  eventually make helper flows easier to inspect, resume, and retry without
  hiding consent or approval boundaries.

### Client Adapter And Visible UX

Outcome: define what activation/readiness looks like to real clients instead
of treating all clients as Codex hook clones.

Current state:

- #3 remains open for host Pi global shim install/reload/readback.
- #62 closed the container baseline helper/shim visibility path for Pi and
  OpenCode client Docker.
- #89/#90 now package the client-visible activation matrix as a focused
  source/docs/tests slice, including the distinction between #62 client Docker
  proof and still-separate host Pi, host OpenCode, and Codex hook claims.
- Pi-visible behavior is shim/tool/guidance availability, not a Codex-style
  project hook banner.
- OpenCode-visible behavior is project-local plugin/helper behavior.
- Codex-visible behavior is project-local hook/helper/readback behavior.

Near-term gap:

- After #90, keep client-visible validation claims tied to the matrix:
  do not generalize #62 Pi/OpenCode client Docker proof to host Pi global
  install/reload, host OpenCode global config, or Codex hook activation.

### Dev Docker Integration Lab

Outcome: keep mutable integration experiments inside the isolated
ContextForge dev Docker surface and Pi/OpenCode client Docker foils.

Current state:

- #41 closed the initial dev Docker MCP backend/transceiver layer.
- #58 closed the evidence freshness protocol for ContextForge dev Docker and
  Pi/OpenCode client Docker.
- #62 closed baseline helper/shim visibility for client containers.

Near-term gap:

- The lab should add services through explicit onboarding records and bounded
  runtime approvals, not by broad container expansion. #52, including the
  merged #87/#93/#94 helper increments, is the current source-side feeder for
  that work.

### MCP Service Onboarding Lifecycle

Outcome: guide new service ideas through source discovery, feasibility,
classification, strategy, footprint, approval boundaries, and issue/PR
topology before runtime work starts.

Current state:

- #52 is open and owns the guided MCP service-onboarding helper.
- #69 merged the first deterministic no-mutation onboarding-record helper.
- #87 merged a source/docs/tests increment adding bridged stdio,
  credential-scoped, and client/session-local examples.
- #93 merged a source-only resume envelope with deterministic
  `dialogue_session` metadata, previous-record resumption, and no file
  persistence.
- #94 merged opt-in project-local ignored session persistence under
  `run/service-onboarding-sessions/`, including `--save-session`,
  `--resume-session`, path-safety checks, and no runtime/service mutation.

Near-term gap:

- The current helper is still deterministic CLI tooling rather than a
  long-running helper process. A later #52 slice should either add richer
  dialogue/session management on top of the local ignored store or use the
  helper to produce a first real onboarding record for a selected service.

### Serena/Project-Scoped Service Lifecycle

Outcome: treat Serena as the reference project-scoped service lifecycle,
including backend locality, project root, tool policy, LSP evidence, client
visibility, and eventual retired-surface migration.

Current state:

- #50 closed canonical `cf-controlplane` Serena registration/readback.
- #33 closed static-port guardrails.
- #2 remains open for deferred Serena runtime blockers in a later
  migration/cutoff phase.

Near-term gap:

- Do not treat #2 as ordinary cleanup pressure. The remaining blockers belong
  to a later phase after the new stack is stable and the operator no longer
  depends on the legacy/live substrate for continuity.

### Safe Client-Visible Validation Probes

Outcome: replace skipped or presumed validation with safe target-client-visible
probes where services can support them.

Current state:

- `OPEN_QUESTIONS.md` keeps this as an open question for services that still
  lack safe default probe payloads.
- Project-init validation rules require target-client-visible ContextForge
  routes, not backend-only checks or local shell substitutes.

Near-term gap:

- Create a focused issue to inventory services without safe probes and add
  harmless read-only probes one service at a time.

### Operator Productization

Outcome: move from many correct scripts and fixtures toward a coherent
operator workflow that remains auditable, idempotent, and approval-aware.

Current state:

- The release-readiness report explicitly treats the RFC MVS as an evidence
  index and readiness statement, not as a polished production operator CLI.
- Current workflows are powerful but distributed across helpers, runbooks,
  issue comments, fixtures, and tests.

Near-term gap:

- Create a productization issue when the next operator-facing pain point is
  concrete enough to slice: command grouping, status dashboard, guided
  retries, evidence summaries, or approval packet generation.

### Governance/Evidence/SuperLoop

Outcome: preserve continuity through decisions, abeyant intentions, open
questions, evidence comments, draft PRs, and formal goal maintenance.

Current state:

- #25 closed standardized continuity and goal-loop artifacts.
- The SuperLoop remains the operating protocol: refresh evidence, execute one
  bounded transition, document evidence and non-actions, complete the current
  formal goal, and activate the refined successor goal.
- Project #6 `Agent Issue View` now supplies the lightweight cross-object
  coordination index for agents. It should be read at goal re-entry and updated
  during goal maintenance only when durable coordination state changes.

Near-term gap:

- Keep this index current when a path changes phase. Do not let closed
  migration issues remain the only roadmap map for future agents.

### Legacy Retirement

Outcome: retire predecessor naming, paths, and runtime surfaces only through
focused, evidence-backed phases that do not destabilize the active operator.

Current state:

- #66 closed retired-name cleanup in tracked source.
- #79 and #85 closed major migration/runtime/archive-state cleanup fronts.
- #2 is the remaining open late-phase Serena runtime blocker.

Policy:

- Legacy retirement is a named path, but it is late and deliberately not the
  current primary feature-development driver.
- Do not shut down or cut off legacy/live ContextForge merely because a
  retired surface still exists. Cutoff belongs only after the new stack is
  rigorously proven and changes can be made one bounded refinement at a time.

## Project #6 Roadmap Draft Items

The following roadmap paths should be represented in Project #6 as draft
items until they are promoted into concrete issues or PRs:

- `Roadmap: Client-visible activation UX matrix` was promoted to #89/#90 and
  should be marked done or cross-referenced rather than kept as a second active
  owner for the same work.
- `Roadmap: Safe client-visible validation probes` for harmless
  target-client-visible checks.
- `Roadmap: Operator productization` for helper, registration, readback,
  retry, and approval packet workflows.
- `Roadmap: Dev Docker service expansion` driven by #52 onboarding records and
  bounded runtime approvals.
- `Roadmap: Project inspector and language-profile proof path` for expanding
  project-specific service evidence beyond Serena.
- `Roadmap: Requirement/scenario QA and evidence ledger` for durable
  acceptance evidence across services and clients.
- `Roadmap: Upstream ContextForge dependency and packaging watch` for tracking
  ContextForge capabilities, bridge behavior, and packaging assumptions.
- `Roadmap: Security/auth/remote exposure gate` for later remote or
  credential-sensitive exposure decisions.

Keep #2 as the explicit deferred late-phase legacy/Serena blocker instead of
creating a duplicate roadmap draft item for legacy cutoff.

When one of these draft items is promoted to a concrete issue or PR, let the
configured Project workflows create the native issue/PR item. Then retire,
defer, or cross-reference the roadmap draft item so the board does not show two
active items for the same work.

## Gap Issue Candidates

These are candidates for future GitHub issues when the operator chooses to
promote them:

- safe client-visible validation probes for services that still lack harmless
  target-client-visible checks;
- operator productization of helper/registration/readback workflows;
- next dev Docker service expansion driven by #52 onboarding records;
- project inspector and language-profile proof path;
- requirement/scenario QA and evidence ledger;
- upstream ContextForge dependency and packaging watch;
- security/auth/remote exposure gate;
- late legacy-retirement phase for the remaining #2 Serena blockers.

Do not implement these gaps from this index alone. Each needs its own bounded
issue, approval boundary, evidence plan, and PR topology.
