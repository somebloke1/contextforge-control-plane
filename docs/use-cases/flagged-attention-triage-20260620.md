# Flagged-For-Attention Triage - 2026-06-20

Controller: `codex-thread:019ede5e-c2c8-72b0-8665-2effa6288d05`

Scope: open GitHub issues with `flagged-for-attention` after UC15 handoff
acceptance and the PR #271 ready-for-review transition. Project #6 is a
coordination index; issue bodies, PR comments, source files, tests, and
controller acceptance artifacts remain authoritative.

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

These flagged issues remain open because broader review/merge state is still
pending, but they have controller-local acceptance artifacts or reports in the
current branch:

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

- #275 and #279 already had install-only quarantine comments.
- #272, #273, #274, and #276 now have disposition comments tying them to the
  install-only cleanup rather than stricter post-install validation.
- `record_project_init_validation` now returns
  `project_init_validation_retired` and records no project-init validation.
- `record_project_init_client_reload` rejects `validation_mode` instead of
  resuming a validation/probe continuation.
- UC1 dialogue gates prohibit validation payloads, safe-probe fields, and
  post-apply Context7 service calls in passing ordinary install evidence.

Residual: deeper validation/proof data structures still exist for historical
evidence, controlled-development, and future readiness/proof work. They should
not be exposed as ordinary project-init. #274 also preserves a future
service-output-quality concern if a separate proof workflow evaluates Context7
documentation relevance.

Coordination disposition: keep #272-#276 and #279 In Review pending PR #271
review/merge. Do not treat them as independent target-client validation feature
work, and do not revive post-install validation to close them.

## Category C: Remediated Or Packaged Follow-Ups Still Awaiting Review/Merge

- #290 Pi Serena defer continuation/direct-apply bug: helper-level remediation,
  focused tests, and live Pi verifier evidence are recorded in issue comments.
  It remains open/In Review until the containing PR/review surface is resolved.
- #292 Pi post-reload stale-state/raw-status bug: investigation, remediation,
  source verification, and live Pi verifier evidence are recorded in issue
  comments. It remains open/In Review until the containing PR/review surface is
  resolved.
- #293 agent-invokable reset helper: initial implementation plus follow-up
  remediation for reset ownership, root derivation, receipt shape, evidence
  collision safety, and unsafe-root refusal are recorded in issue comments and
  PR #271. It remains open/In Review pending review/merge.
- #289 visible placeholder regression guard: methodology-only acceptance is
  recorded in `docs/use-cases/visible-placeholder-regression-guard-acceptance-20260620.md`
  and the issue comment. It remains open/In Review pending review/merge; do not
  reimplement it as a deterministic placeholder detector.

## Category D: Active Follow-Up Or Future Work

- #284 legacy/new ContextForge service, prompt, and resource parity: read-only
  investigation integrated. The host-local gateway on `127.0.0.1:4444` is a
  user `contextforge-gateway.service`; authenticated readback with the local
  bearer token shows nine servers, including the eight shared canonical
  services plus the project-scoped Serena server. Port `4445` is a separate
  Docker-published `ghcr.io/ibm/mcp-context-forge:v1.0.3` container and rejects
  the 4444 bearer token. Authenticated 4445 readback using the ignored Docker
  harness admin env now succeeds and shows a dev-Docker subset: 2 servers, 7
  tools, 0 prompts, and 0 resources. Refreshed full-list 4444 readback is
  recorded in `docs/use-cases/contextforge-service-parity-readback-20260621.md`:
  the host gateway has 9 servers, 104 tools, 83 prompts, 84 resources, and
  complete 81/81 `tool-guidance` prompt/resource pairing by canonical tool tag.
  The operator has since clarified that 4444 is scheduled for decommissioning,
  so this readback is a legacy migration baseline rather than a durable
  operating authority. The remaining required boundary is Docker-specific 4445
  migration implementation plus parity reconciliation before 4444 is retired.
- #138 explicit recovery workflows: high-risk future apply-recovery lane.
- #143 client adapter conformance packs: future client-adapter conformance
  lane.
- #152 service onboarding workflow: ideal-form acceptance boundary for #52, not
  a separate duplicate implementation lane. It is now In Review because #52 and
  draft PR #197 already carry the service-onboarding helper review path.
- #154 prompt/resource guidance association: future tool-guidance lane.

## Current Next Target

Do not select #289 again unless review finds a concrete gap; it is already
packaged. After the #284 report integration, the next controller-maintenance
target is PR/Project hygiene:

- keep PR #271 as the active ordinary review surface and keep its body,
  comments, and coordination snapshots aligned with the latest pushed head;
- keep #243-#255 in review rather than closing them solely from local
  controller acceptance; issue closure should follow PR review/merge or an
  explicit closure decision;
- keep #290/#292/#293/#289 in review rather than active development unless
  reviewers return actionable defects;
- keep the validation-era cleanup group (#272-#276/#279) In Review under the
  install-only quarantine boundary;
- keep #138, #143, and #154 deferred as future ideal-form lanes until
  issue-specific implementation or acceptance evidence exists;
- treat #284's next safe slice as a Docker-specific successor-surface migration
  plan and implementation path: do not apply live-surface `127.0.0.1:910x`
  registry recreation defaults directly to 4445, and require explicit parity
  reconciliation against the 4444 legacy baseline before replacement-readiness
  is claimed.
