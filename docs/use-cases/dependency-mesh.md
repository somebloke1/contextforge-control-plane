# ContextForge Ordinary Use-Case Dependency Mesh

## Purpose

This document organizes the ordinary ContextForge use cases as a dependency
mesh for SuperLoop scheduling. Issue numbers and natural-order numbers are
evidence, not a substitute for dependency analysis. The controller should
schedule from least-dependent substrate toward higher-order workflows while
preserving accepted-case regressions after shared-surface remediation.

## Source Set

Authoritative issue bodies inspected:

- #243: Use Case 1, initialize ContextForge in a fresh project.
- #244: Use Case 2, resume an initialized project and see available tools.
- #245: Use Case 3, discover available project capabilities.
- #246: Use Case 4, read project governance through a ContextForge tool.
- #247: Use Case 5, add a useful project service with plan and approval.
- #248: Use Case 6, decline or defer a suggested service.
- #249: Use Case 7, ask what ContextForge state the client is using.
- #250: Use Case 8, use a tool and ask a follow-up in the same session.
- #251: Use Case 9, use the same project from Pi and OpenCode.
- #252: Use Case 10, refresh tools after project state changes.
- #253: Use Case 11, see project tool guidance when using a capability.
- #254: Use Case 12, onboard an uncataloged MCP service.
- #255: Use Case 13, run development evidence in controlled containers.
- #256: Use Case 14, produce a readiness report the user can trust.
- #257: Use Case 15, hand off the project with clear next actions.
- #285: Align new clients to the project service set.
- #286: Represent cross-client service disparity without overstating
  availability.
- #287: Project service graph and client projection alignment model.

## Legend

- `E:` explicit dependency stated in the issue body.
- `I:` inferred dependency from technology contract, acceptance gates, or
  ordinary workflow shape.
- `X:` cross-cutting dependency or test-surface dependency, not necessarily a
  product dependency.

## Inventory

| UC | Issue | Purpose | Explicit Dependencies | Inferred Dependencies | Downstream Dependents |
| --- | --- | --- | --- | --- | --- |
| UC1 | #243 | First-run project-local initialization guidance without mutation. | none | project-state classification; Pi/OpenCode startup hooks | UC2, UC3, UC5, all initialized-project cases |
| UC2 | #244 | Resume initialized project and report approved tools. | UC1 | target-client binding readback and initialized fixture | UC3, UC7, UC8, UC9 |
| UC3 | #245 | Answer capability discovery from current project authority. | UC2 | capability catalog/readback DTOs; no stale client-config assumptions | UC4, UC5, UC7, UC11 |
| UC4 | #246 | Read project governance through a ContextForge-served read-only tool. | UC3 | `mentality:static_repo_local` binding, governance tool naming, read-only route policy | UC8, UC11, UC14, route-defect discovery |
| UC5 | #247 | Select, plan, approve, apply, and read back useful services. | UC3, UC7 | UC1 menu substrate; #270 taxonomy; #259 readiness matrix; #260-#268 service readiness; #269 selection-shape validation | UC6, UC8, UC10, UC11, UC12 |
| UC6 | #248 | Decline or defer a suggested service without activating it. | complements UC5 | service-offer state model and readback; import suppression | UC7, UC9, UC10 |
| UC7 | #249 | Read current ContextForge state, tools, skips, errors, and readiness layers. | supports later troubleshooting and validation | UC2 and UC3 initialized-state substrate; target-client-specific state DTOs | UC5, UC8, UC9, UC10, UC14, UC15 |
| UC8 | #250 | Use a ContextForge tool and ask a follow-up in the same session. | available tools and readback | at least one functioning read-only tool route; stable session context; UC4 or UC5/UC10 can supply the tool substrate | UC14 |
| UC9 | #251 | Compare the same project from Pi and OpenCode. | cross-client consistency | UC7 readback from both clients; UC2/UC3 state/tool alignment | UC10, UC14, UC15 |
| UC10 | #252 | Refresh tools after project-state changes. | UC9 | UC5 or UC6 to create state change; revision/hash comparison; route refresh | UC8, UC11, UC14, UC15 |
| UC11 | #253 | Surface project tool guidance while using a capability. | available tools and guidance registration | UC3 capability summary; guidance registration/readback; a selected capability route | UC12, UC14 |
| UC12 | #254 | Start structured onboarding for an uncataloged MCP service. | UC5, UC11 | service classification surfaces; plan-only safety boundary | UC14, UC15 |
| UC13 | #255 | Run repeatable development evidence in controlled containers. | none stated as product dependency | reusable harness surfaces; idempotent client reset; current-worktree venv policy | UC14 evidence aggregation; all client-evidence attempts as test-surface dependency |
| UC14 | #256 | Produce a trustworthy readiness report. | real Pi/OpenCode evidence | accepted/proven UC evidence; UC13 evidence surfaces; claim-ladder aggregation | UC15 |
| UC15 | #257 | Hand off the project with clear next actions. | final ordinary-path set | UC14 and current GitHub/project coordination state | none |

## Dependency Adjacency

```text
UC1 -> UC2 [E], UC3 [I], UC5 [I]
UC2 -> UC3 [E], UC7 [I], UC9 [I]
UC3 -> UC4 [E], UC5 [E via #245], UC7 [I], UC11 [I]
UC4 -> UC8 [I], UC11 [I], UC14 [I]
UC5 -> UC6 [I], UC8 [I/#247 follow-on #250], UC10 [I/#247 follow-on #252], UC11 [I], UC12 [E]
UC6 -> UC7 [I], UC9 [I], UC10 [I]
UC7 -> UC5 [E via #249], UC8 [E], UC9 [I], UC10 [I], UC14 [I]
UC8 -> UC14 [I]
UC9 -> UC10 [E], UC14 [I]
UC10 -> UC8 [I], UC11 [I], UC14 [I]
UC11 -> UC12 [E], UC14 [I]
UC12 -> UC14 [I], UC15 [I]
UC13 -> UC14 [E/test-evidence layer], UC1..UC12 [X harness/evidence layer]
UC14 -> UC15 [E]
```

UC5's internal mesh is:

```text
#270 taxonomy -> #259 readiness matrix -> #260-#268 per-service readiness -> #269 selection-shape validation -> UC5/#247 umbrella
```

Cross-client projection mesh:

```text
#287 model invariant -> #286 disparity/readback vocabulary -> #285 client alignment/import implementation
#287 -> UC9 [claim boundary], UC10 [claim boundary], UC12 [identity/projection gate], UC14 [readiness gate]
```

#287 is not a dialogue use case and does not replace the current queue owner.
It is a container issue for the architecture invariant:

```text
project service graph is global;
project-scoped service instances are project-owned;
client projection/readiness/proof is per target client;
alignment is explicit and approval-gated;
readback must not collapse those layers.
```

#286 should run before or in parallel with #285 because the readback vocabulary
must distinguish project service presence from target-client import,
visibility, reload state, and proof before an alignment helper can be safely
implemented. #285 then owns the user-facing helper operation that aligns a new
client to the project service set. #287 remains the architectural container and
coordination issue for that model.

## Layered Queue

### Layer 0: Product Bootstrap

- `UC1`: fresh-project guidance and no mutation.

### Layer 1: Initialized-Project Substrate

- `UC2`: initialized-project recognition and approved tool listing.
- `UC3`: initialized-project capability discovery.

### Layer 2: State And Route Substrate

- `UC7`: current project-state readback and readiness-layer honesty.
- `UC4`: read-only governance service route through ContextForge.

`UC7` is lower-layer than `UC4` despite its larger natural-order number because
it supplies the project/client state explanation required by UC5, UC8, UC9,
UC10, UC14, and UC15. `UC4` is important for real service-route confidence, but
it is one specific read-only service route rather than the shared state
readback surface.

### Layer 3: Service-Selection State Changes

- `UC5`: add useful project services with plan, approval, apply, and readback.
- `UC6`: decline or defer a suggested service and preserve that state.

`UC5` must be decomposed; PR #271 is scoped to #270, #259, #260, and #279, not
the full #247 umbrella. Do not advance to #269 or later service slices before
the Context7/#260 cumulative slice is accepted.

### Layer 4: Session And Cross-Client Operation

- `UC9`: use the same project from Pi and OpenCode.
- `UC10`: refresh after project-state changes.
- `UC8`: use a tool and follow up in the same session.
- `UC11`: project-specific tool guidance while using a capability.

UC8 can be satisfied through different tool substrates: the governance route
after UC4, or a newly added/refresh-visible service after UC5 and UC10.

UC9 and UC10 evidence before #287/#286/#285 is accepted only within its
documented pre-aligned-fixture boundary. It proves same-project readback and
refresh behavior for prepared Pi/OpenCode projections; it does not prove that a
new client automatically imports another client's services. After #286 or #285
changes land, rerun targeted UC9/UC10 disparity/alignment regressions rather
than blanket historical reruns.

### Layer 5: Expansion, Evidence, Readiness, Handoff

- `UC12`: onboard an uncataloged MCP service.
- `UC13`: controlled development evidence surfaces.
- `UC14`: readiness report with claim-layer honesty.
- `UC15`: final handoff and next actions.

`UC13` is numbered late but cross-cutting. The harness principles are already
part of the reusable method layer; the issue itself can be accepted later as a
user-facing development command/documentation use case.

UC12 and UC14 are gated by the #287 model. UC12 must not onboard services using
client-specific service identities or duplicate project-scoped service
instances. UC14 must not report readiness by collapsing project service
presence into target-client import, visibility, reload state, or proof.

## Current Queue Judgment

The earlier next-target judgment selected `UC7` after UC1-UC3 because state
readback was a lower-layer dependency than a single governance service route.
That sequencing rationale remains useful history, but it is no longer the
current queue state.

Current PR #271 evidence has progressed through the ordinary use-case path
through UC15 as a draft review surface. The #293-#296 issue-level review wave
has been integrated into the PR head, and the projection/alignment follow-ups
have advanced into review state:

- #287: project service graph and target-client projection model;
- #286: readback vocabulary for cross-client service disparity, refined in
  `2b9e5e5`;
- #285: explicit alignment/import helper behavior for new clients, including
  partial/unavailable service representation in `42e72a9`.

The current strategic pressure is PR readiness discipline and Codex parity, not
another numeric use-case step. Before stronger cross-client readiness,
new-client alignment, or release-style claims are made, keep the latest
review-wave remediation tied to PR #271 and rerun targeted UC9/UC10
disparity/alignment regressions only if a later review or remediation shows
that the accepted claim boundaries changed. If any projection/alignment
remediation invalidates UC9, UC10, UC12, UC14, or UC15 claim boundaries, rerun
only the affected localized package and evaluator loop from a clean harness
state.

## Ambiguities To Reconcile

- `UC4` can be strategically early if the current known blocker is governance
  service-route failure. That does not make it generally lower-layer than UC7.
- `UC6` may need to run before the full all-services path of UC5 if decline
  state is required to represent blocked or unsafe service choices without
  pretending activation success.
- `UC11` may be runnable before UC10 if guidance registration is already stable,
  but it still depends on capability and tool visibility.
- `UC11` is not blocked by #287 when it uses explicitly pre-aligned,
  per-target-client fixtures and makes only target-client guidance-surface
  claims. If a UC11 runner or package starts claiming automatic cross-client
  alignment, shared readiness, or project-global service presence as
  target-client proof, pause UC11 and route through #286/#285 instead.
- `UC13` should influence every client-evidence attempt through reset and
  capture discipline, without dragging the user-facing ordinary queue into a
  late-numbered harness-first order.

## Tentative Whole Sequence

This sequence is fully defined so the SuperLoop has a complete route through
all ordinary use cases, but it is not dogma. The controller may reorder the next
dequeued item when fresh evidence changes the dependency graph, when a shared
substrate defect invalidates downstream evidence, or when a narrower regression
must be promoted to protect already accepted cases.

```text
1.  UC1  - fresh-project initialization guidance.
2.  UC2  - initialized-project available-tool readback.
3.  UC3  - initialized-project capability discovery.
4.  UC7  - current ContextForge state/readback and readiness-layer honesty.
5.  UC4  - read governance through a real ContextForge-served tool route.
6.  UC5a - #270 service localization taxonomy.
7.  UC5b - #259 helper-offered service readiness matrix.
8.  UC5c - #260 Context7 single-service lifecycle.
9.  UC5d - #261-#268 remaining per-service readiness slices, ordered by
           least credential/runtime risk before higher-risk services. Current
           `mentality`/#263 was selected after accepted UC5c because it is
           repo-local/static, known-safe, credential-free, and continuous with
           accepted UC4 governance-route evidence. Current next target after
           accepted UC5d is `openzeppelin-solidity-contracts`/#264 because it
           is shared canonical, known-safe, credential-free, and avoids browser,
           session, or project-provisioning prerequisites. Current next target
           after accepted UC5e is `ssh-tmux`/#266 because it is credential-free
           and known-safe, while still requiring strict session-scoped
           read-only boundaries. Current next target after accepted UC5f is
           `playwright`/#265 because it is the lowest-dependency remaining
           service without provider credentials, while still requiring an
           isolated controlled fixture-page boundary. Current next target after
           accepted UC5g is `exa-search`/#261 because it is the narrowest
           remaining credential-scoped service and should be handled before
           broader GitHub mutation-capable and multi-provider web-search
           surfaces. Current next target after accepted UC5h is `github`/#262
           because it is the next narrow credential-scoped surface with a clear
           read-only metadata boundary; it should be handled before broader
           multi-provider `web-search`/#267. Current next target after accepted
           UC5i is `web-search`/#267 because it is the remaining
           credential-scoped provider/request surface; Serena remains later
           because project-scoped provisioning, language selection, and LSP/index
           state are more dependent. Current next target after accepted UC5j is
           `serena`/#268 because it is the remaining per-service readiness slice
           and requires explicit project-scoped provisioning and language-state
           boundaries before #269 selection-shape validation. Current next
           target after accepted UC5k is #269 because all current per-service
           source lifecycle slices are accepted and selection-shape behavior is
           the remaining #247 prerequisite. Current next target after accepted
           UC5l is #247 umbrella acceptance, while preserving that #247 still
           must not overclaim post-refresh target-client visibility or actual
           tool use before those downstream use cases are exercised.
10. UC5l - #269 single, curated multi-service, and all-services selection
           shape validation.
11. UC5  - #247 umbrella acceptance once its decomposed slices are proven.
12. UC6  - decline/defer service state and active-import suppression.
13. UC9  - Pi/OpenCode same-project consistency.
14. UC10 - refresh tools after project-state changes.
15. UC8  - use a tool and ask a follow-up in the same session.
16. UC11 - project tool guidance while using a capability.
17. #286 - cross-client disparity/readback vocabulary, if not already resolved
           before the next cross-client alignment or readiness claim.
18. #285 - explicit client alignment/import helper, after or alongside #286
           when a later use case requires new-client alignment.
19. #287 - remains Candidate/container throughout #286/#285; do not promote it
           to the current queue owner unless the active task is architecture
           reconciliation itself.
20. UC12 - uncataloged MCP service onboarding dialogue.
21. UC13 - controlled development validation as a formal user-facing/dev use
           case; its reset/evidence principles remain active throughout.
22. UC14 - readiness report with claim-layer honesty.
23. UC15 - final handoff with current evidence and next actions.
```

## Flexibility Rules

- A use case may move earlier only if all hard dependencies are already proven
  or the case is explicitly being used as a diagnostic/regression probe.
- A use case may move later when its prerequisite evidence is weak, contradicted
  by a fresh run, or too broad for the current accepted substrate.
- Cross-cutting harness failures promote the smallest use case that exposes the
  shared defect, then trigger targeted regressions after remediation.
- Service-route failures promote `UC4` or the affected UC5 service slice before
  broader service-selection claims.
- State/readback, route-map, or prompt-guidance changes require rerunning the
  minimum affected accepted cases, usually `UC2`, `UC3`, `UC7`, and the nearest
  service-route case.
- Cross-client projection/readback or alignment changes from #286/#285 require
  targeted UC9/UC10 regressions with disparity or alignment fixtures. They do
  not require blanket reruns of earlier accepted cases unless their accepted
  boundary relied on the changed claim.
- UC5 remains decomposed until the service readiness and selection-shape slices
  have their own evidence; do not treat the umbrella as one monolithic pass.
- `UC13` may be worked in parallel as harness/productization work, but it does
  not replace the per-use-case client evidence loops.
