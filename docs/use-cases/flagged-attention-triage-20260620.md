# Flagged-For-Attention Triage - 2026-06-20

Controller: `codex-thread:019ede5e-c2c8-72b0-8665-2effa6288d05`

Scope: open GitHub issues with `flagged-for-attention` after UC15 handoff
acceptance. Project #6 is a coordination index; issue bodies, PR comments,
source files, tests, and controller acceptance artifacts remain authoritative.

## Project Hygiene Applied

Project #6 readback showed three accepted ordinary-use-case items still owned by
an older controller or left at `Ready`. These were corrected to
`Agent state: In Review` and current controller owner:

- #243 UC1: `Agent owner` updated to current controller.
- #246 UC4: `Agent state` updated from `Ready` to `In Review`; owner updated.
- #249 UC7: `Agent state` updated from `Ready` to `In Review`; owner updated.

Readback also confirmed #257 UC15 is `Agent state: In Review` and owned by the
current controller after the UC15 acceptance comment.

## Category A: Use Cases With Local Acceptance Evidence

These flagged issues remain open because the draft PR and broader review/merge
state are still pending, but they have controller-local acceptance artifacts or
reports in the current branch:

- #243 UC1: `run/holistic-orchestrator/reports/uc1-controller-acceptance-20260620T010301Z.md`
  and `run/holistic-orchestrator/reports/uc1-codex-parity-acceptance-20260620T121626Z.md`.
- #244 UC2: `run/holistic-orchestrator/reports/uc2-controller-acceptance-20260620T012346Z.md`
  and `run/holistic-orchestrator/reports/uc2-codex-parity-acceptance-20260620T172259Z.md`.
- #245 UC3: `run/holistic-orchestrator/reports/uc3-controller-acceptance-20260620T012827Z.md`
  and `run/holistic-orchestrator/reports/uc3-codex-parity-acceptance-20260620T172920Z.md`.
- #246 UC4: `run/holistic-orchestrator/reports/uc4-controller-acceptance-20260620T014500Z.md`
  and `run/holistic-orchestrator/reports/uc4-codex-parity-acceptance-20260620T174702Z.md`.
- #247 UC5: `docs/use-cases/use-case-5/controller-acceptance-20260620.md`
  and service-slice reports under `run/holistic-orchestrator/reports/uc5*.md`.
- #248 UC6: `docs/use-cases/use-case-6/controller-acceptance-20260620.md`
  and `run/holistic-orchestrator/reports/uc6-codex-parity-acceptance-20260620T184307Z.md`.
- #249 UC7: `run/holistic-orchestrator/reports/uc7-controller-acceptance-20260620T015423Z.md`
  and `run/holistic-orchestrator/reports/uc7-codex-parity-acceptance-20260620T173428Z.md`.
- #250 UC8: `docs/use-cases/use-case-8/controller-acceptance-20260620.md`
  and `run/holistic-orchestrator/reports/uc8-codex-parity-acceptance-20260620T185331Z.md`.
- #251 UC9: `docs/use-cases/use-case-9/controller-acceptance-20260620.md`
  and `run/holistic-orchestrator/reports/uc9-codex-parity-acceptance-20260620T192900Z.md`.
- #252 UC10: `docs/use-cases/use-case-10/controller-acceptance-20260620.md`
  and `run/holistic-orchestrator/reports/uc10-codex-parity-acceptance-20260620T193900Z.md`.
- #253 UC11: `docs/use-cases/use-case-11/controller-acceptance-20260620.md`
  and `run/holistic-orchestrator/reports/uc11-codex-parity-acceptance-20260620T191056Z.md`.
- #254 UC12: `docs/use-cases/use-case-12/controller-acceptance-20260620.md`
  and `run/holistic-orchestrator/reports/uc12-codex-parity-acceptance-20260620T194900Z.md`.
- #255 UC13: `docs/use-cases/use-case-13/controller-acceptance-20260620.md`
  and `run/holistic-orchestrator/reports/uc13-codex-parity-acceptance-20260620T200100Z.md`.

Coordination disposition: keep these in review until PR #271 review/merge or
explicit closure decisions. Do not close solely from local branch acceptance.

## Category B: Validation-Era Bugs

Flagged issues #272, #273, #274, #275, #276, and #279 came from the earlier
post-install validation flow. The current UC1/project-init direction changed:
project init installs the selected package, reports reload/new-session required,
and stops. Post-install service validation/probing must not be part of ordinary
project init.

Disposition:

- #279 had a local fix under the old strict-validation contract and remains in
  review historically.
- #272, #273, #274, #275, and #276 should not be implemented by reviving
  post-install validation. They should be resolved by the broader removal or
  quarantine of client-visible project-init validation machinery, while keeping
  legitimate test/evidence validation and service-onboarding proof planning.
- Source still contains validation-named state and helper surfaces, so these
  issues are not safe to close as obsolete without a focused removal/quarantine
  pass.

Coordination disposition: promote one bounded cleanup pass if the next queue
focus remains project-init simplification. Do not treat these as independent
target-client validation feature work.

## Category C: Active Follow-Up Or Future Work

- #284 legacy/new ContextForge service, prompt, and resource parity: large
  service-ops/readiness lane. Keep visible, but it is broader than the current
  post-UC cleanup slice.
- #289 visible placeholder regression guard: narrow, ready now. It improves the
  dialogue-evaluation method without deterministic prose matching.
- #138 explicit recovery workflows: high-risk future apply-recovery lane.
- #143 client adapter conformance packs: future client-adapter conformance
  lane.
- #152 service onboarding workflow: ready future service-onboarding lane.
- #154 prompt/resource guidance association: future tool-guidance lane.

## Current Next Target

Select #289 first because it is narrow, flagged, aligned with the current
methodology, and can be handled without changing runtime behavior or reopening
validation semantics. The work is methodology-only:

- refine reusable evaluator guidance;
- preserve the no-pattern-matching rule;
- add source checks that the guidance exists;
- comment and mark #289 in review after verification.
