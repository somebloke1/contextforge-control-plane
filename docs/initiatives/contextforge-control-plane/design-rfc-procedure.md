# Implementation Procedure: ContextForge Control-Plane Design RFC

Status: Delegation procedure for future implementation planning and execution

## Purpose

This document turns the design in
`docs/initiatives/contextforge-control-plane/design-rfc.md` into a staged
delegation procedure. It is not a replacement for the RFC. The RFC remains the
source of truth for architecture, authority boundaries, schemas, consent,
verification, and acceptance criteria.

Use this procedure when an orchestrating/root agent is ready to delegate
implementation work. The procedure defines dependency order, agent scope,
parallelization opportunities, required QA after each wave, and the root
agent's obligation to assess and fix QA findings before continuing.

## Strategic RFC References

Implementation agents should be pointed to the RFC sections that constrain
their assigned work, not to the whole document by default.

Primary references:

- `design-rfc.md#Normative-Design`: authority model, resource taxonomy,
  service classes, representation matrix, schema/control-service contracts.
- `design-rfc.md#Project-State-Schema`: `.project/context_forge_state.json`
  authority, artifact refs, migration, open-item types, and contract shapes.
- `design-rfc.md#Control-Service-Surface`: v1 workflow-oriented tool surface.
- `design-rfc.md#Catalog-Administration` and
  `design-rfc.md#Service-Management-Skill-Contract`: catalog mutation boundary
  and service-management handoff.
- `design-rfc.md#Consent-And-Audit` and
  `design-rfc.md#Approved-Plan-Journal-And-Idempotency`: consent receipts,
  approval scope, stale plans, idempotency, and audit journals.
- `design-rfc.md#Project-Scoped-Service-Pattern`: Serena, project-inspector,
  and semantic tool-policy compiler.
- `design-rfc.md#Client-Abstraction-And-Verification` and
  `design-rfc.md#Client-Adapter-Contract`: client conformance packs and trust
  broker.
- `design-rfc.md#Testing-Methodology`: deterministic, integration,
  scenario-DSL, inference-inclusive, evaluator, and evidence-ledger testing.
- `design-rfc.md#Control-Plane-Minimal-Viable-Slice`: minimum coherent
  implementation target.
- `design-rfc.md#Implementation-Roadmap` and
  `design-rfc.md#Acceptance-Strategy`: sequencing and acceptance gates.

## Orchestration Rules

The root agent owns coordination and final integration. Dispatched agents own
only their assigned task.

Delegation discipline is mandatory. A dispatched agent has no implicit license
to improve the repository, clean up neighboring files, resolve adjacent design
issues, rename artifacts, reformat unrelated content, or "finish" work outside
its prompt. The root agent must treat the prompt's file list and deliverable
IDs as a hard write boundary. Any agent that needs a change outside that
boundary must stop and return a handoff note; it must not make the change.

Required orchestration behavior:

- Start from current local files, branch state, ContextForge state, and live
  probes. Do not assume the RFC or generated artifacts are current without
  reading them.
- Preserve stock ContextForge as registry/proxy/control-plane anchor. Do not
  create a bespoke gateway fleet.
- Keep ContextForge-owned state mutation behind ContextForge APIs/Admin UI
  behavior. Direct database writes remain prohibited.
- Keep project initialization state in `.project/context_forge_state.json`.
  Legacy `.env` project-init keys are migration input only.
- Treat user-global trust, user-global config, token material, actual secret
  values, catalog promotion, and remote exposure as separate approval classes.
- Dispatch agents with rich task prompts, but include only the RFC sections,
  files, constraints, and expected outputs needed for their assignment.
- Do not ask a dispatched agent to solve neighboring waves, redesign the RFC,
  or perform unassigned implementation.
- Every implementation-agent prompt must include an explicit **allowed write
  set** and **forbidden write set**. The allowed write set is exhaustive:
  omitted files are read-only by default.
- The root agent must tell each implementation agent, in strong terms, that
  editing outside the allowed write set is a blocking scope violation even if
  the edit appears useful, correct, or necessary for a nearby task.
- Agents may read broader context only when the prompt permits it. Reading a
  file does not grant permission to edit it.
- Agents must not reformat, reorder, regenerate, rename, delete, stage, commit,
  or otherwise mutate files outside their allowed write set.
- If an agent discovers an out-of-scope defect, dependency gap, stale doc,
  conflicting edit, or needed refactor, it must report the issue with evidence
  and stop at a handoff. It must not fix the issue unless the root dispatches a
  new scoped assignment.
- Before integrating any dispatched work, the root agent must inspect the
  changed-file list. Any out-of-scope file change must be rejected, reverted in
  the agent's integration patch, or explicitly re-scoped before the wave can
  pass.
- Within a wave, implementation agents may run in parallel only when their
  dependencies are already satisfied and their file ownership is non-conflicting.
- After every implementation wave, dispatch exactly one QA assignment for that
  wave. If blockers require re-checking, reopen the same QA assignment for the
  changed areas or have the root agent verify fixes; do not create an unrelated
  second QA scope.
  The QA agent inspects only the wave's completed work against the assigned
  requirements and relevant RFC sections.
- The root agent must critically assess every QA finding. It must either fix the
  issue, reject it with evidence, or convert it into an explicit blocker before
  starting the next wave.
- No wave is complete until root-level verification and QA adjudication are
  recorded in the implementation run notes.

## Root-Agent Delegation Loop

For each wave:

1. Refresh worktree status, relevant RFC sections, prior wave outputs, and live
   state needed by the wave.
2. Confirm dependencies in the dependency map are complete and verified.
3. Split the wave into non-overlapping agent assignments.
4. Prompt each implementation agent with:
   - task objective;
   - allowed write set, listed as exact files or directories;
   - read-only context files, if any;
   - forbidden files, directories, and domains;
   - exact files/modules it may read or edit;
   - RFC sections it must follow;
   - explicit non-goals and forbidden mutations;
   - expected deliverables;
   - required tests or probes;
   - output format for handoff back to root.
5. Confirm the prompt says omitted files are read-only and that out-of-scope
   edits are blocking scope violations.
6. Run agents in parallel only when assignments are independent.
7. Inspect each agent's changed-file list before reviewing content. Reject or
   quarantine any out-of-scope change before considering whether the edit is
   otherwise good.
8. Merge or apply the wave outputs conservatively. Preserve unrelated worktree
   changes.
9. Run root-level deterministic verification for the wave.
10. Dispatch one QA agent for the just-completed wave.
11. Review every QA problem. Fix real issues before proceeding. If a QA problem
   is rejected, record the evidence and rationale.
12. Update wave status and dependency map before starting the next wave.

Implementation run notes live under
`run/contextforge-control-plane-implementation/<run_id>/`. The root agent keeps
`wave-status.json` current with `run_id`, `branch`, `base_revision`, current
`wave`, completed deliverable IDs, blocked deliverable IDs, dispatched agent
IDs, scoped file ownership, verification command/results refs, QA report refs,
QA adjudications, rejected-finding rationale, and next-wave dependency status.
Each wave may add redacted evidence bundles under the same run directory. Run
notes are local evidence, not governance authority, and must not contain secret
values.

## Dependency Map

| ID | Deliverable | Depends on | Strategic RFC references |
| --- | --- | --- | --- |
| D0 | Current-state baseline and non-mutating governance reconciliation pack | None | Current Repo Baseline; Governance And Service Memory; Control-Plane Minimal Viable Slice |
| D1 | Project-state library, JSON Schema, migration reader, root validation, atomic writes, locks | D0 | Project State Schema; Round 2; Acceptance Strategy |
| D2 | Contract artifact schemas for service binding cards, capsules, tool policies, handoffs, consent receipts, traces, conformance packs, scenarios, verdicts, ledgers | D0 | Resource Taxonomy; ContextForge Representation Matrix; Project State Schema |
| D3 | Control-service read surfaces and redacted catalog/context/gap models | D1, D2 | Control Service Surface; Security And Token Handling Requirements |
| D4 | Test harness foundations: requirement registry, coverage matrix, deterministic fixtures, scenario DSL, evaluator verdict schema, evidence ledger, transcript/world-state capture, remediation handoff | D1, D2 | Testing Methodology; Scenario Simulation Synthesis |
| D5 | Service instantiation classifier and shared-service capability capsule support | D2, D3, D4 | Service Instantiation Classes; Control-Plane Minimal Viable Slice |
| D6 | Non-mutating project-init planner with contract refs, capsules, consent requirements, stale inputs, and handoff objects | D1, D2, D3, D5 | Control Service Surface; Consent And Audit; Catalog Administration |
| D7 | Operation authorization, consent receipts, verification traces, apply journal, and idempotent project-local apply for state and owned config only | D1, D2, D6 | Consent And Audit; Approved Plan Journal And Idempotency |
| D8 | Generic project-scoped service-provision apply layer, including backend homes, systemd, ports, ContextForge registration, virtual servers, client-binding intents, conformance-gated client writes, and recovery paths | D1, D2, D6, D7, D9, D10 | Project-Scoped Service Pattern; Operational Contract |
| D9 | Codex client adapter conformance pack and trust broker | D2, D3, D4, D7 | Client Abstraction And Verification; Client Adapter Contract |
| D10 | Semantic tool-policy compiler and negative checks | D2, D5, D7 | Project-Scoped Service Pattern; Operational Contract |
| D11 | Generic project-scoped adapter foundation and Serena refactor | D6, D8, D9, D10, D13 | Project-Scoped Service Pattern; Round 5 |
| D12 | Read-only project-inspector project-scoped proof, seeded as an RFC-named proof service unless later routed through service-management | D8, D9, D10, D11, D13 | Dedicated Project-Scoped Non-Serena Proof Candidate; Control-Plane Minimal Viable Slice |
| D13 | ContextForge-backed language profiles and explicit install workflow planning | D2, D3, D7 | Language Profiles; Round 6 |
| D14 | Service-memory provider metadata and governance reference/proposal behavior | D2, D3 | Governance And Service Memory; Round 7 |
| D15 | Service-management skill workflow, handoff consumption, catalog promotion/update plans | D2, D5, D6, D7, D10 | Catalog Administration; Service-Management Skill Contract |
| D16 | Auth/security hardening and non-default remote exposure gate | D7, D9, D15 | Auth Profiles; Security And Token Handling Requirements |
| D17 | End-to-end minimal viable slice scenarios and inference-inclusive regression set | D4, D9, D11, D12, D13, D14, D15, D16 | Testing Methodology; Control-Plane Minimal Viable Slice; Acceptance Strategy |
| D18 | Final acceptance pass, docs/runbooks, governance updates after review | D17 | Implementation Roadmap; Acceptance Strategy |

Dependencies are gates, not suggestions. Deliverable IDs are stable references,
not proof of numeric execution order; the wave plan below is the execution
order. If an agent discovers that a dependency is incomplete, it must stop at a
handoff note rather than filling the gap outside its assignment.

## Wave Plan

Each wave below is serial. Agents inside a wave may run in parallel when the
root agent confirms file ownership and dependency boundaries. Fixture, proof,
or evidence-bundle agents whose outputs depend on same-wave implementation work
must run only after the root freezes the interface they consume; otherwise the
root must serialize them inside the wave.

Known intra-wave ordering constraints:

- Wave 1: schema and contract validator interfaces must be frozen before
  fixture agents finalize negative cases.
- Wave 3: shared-service capsule fixtures must include at least one real
  canonical service, preferably `context7` when locally available; if no real
  shared service can be read, the wave must emit a blocking gap instead of a
  synthetic pass.
- Wave 5: authorization and receipt interfaces must be frozen before trace and
  apply-journal fixtures assert receipt replay behavior.
- Wave 6: the tool-policy compiler core may proceed beside adapter/trust work,
  but target-client-visible negative checks are integrated only after the Codex
  conformance and trust broker interfaces are available.
- Wave 7: service provisioning may emit client-binding intents in parallel with
  backend/ContextForge work, but concrete client config writes remain gated by
  Wave 6 conformance and compiled policy evidence.
- Wave 8: language-profile metadata is completed first inside the wave; Serena
  refactor and adapter proof work consume that metadata rather than inventing
  service-local language policy.
- Wave 12: evidence-bundle and runbook work starts after deterministic and
  inference-inclusive scenario refs exist.

### Wave 0: Baseline And Governance Reconciliation

Implementation agents:

- Agent W0-A: Produce the current-state implementation baseline.
- Agent W0-B: Produce the non-mutating governance reconciliation pack.

Dependencies: none.

Expected outputs:

- Baseline note covering branch, worktree, ContextForge health, existing
  server-instances, current project-init state, ignored local state, and known
  blockers.
- Governance reconciliation pack with suggested `DECISIONS.md`,
  `OPEN_QUESTIONS.md`, and `ABEYANT_INTENTIONS.md` operations only. No ledger
  edits.

QA agent W0-QA:

- Check that the baseline uses live evidence.
- Check that governance output is advisory and does not bypass
  `scripts/governance_crud.py` or `mentality`.
- Check that no implementation or catalog mutation happened.

Root gate:

- Fix missing baseline evidence or governance-pack overreach before proceeding.

### Wave 1: Schema And Contract Foundations

Implementation agents:

- Agent W1-A: Implement project-state schema/library, root validation,
  migration input handling, atomic writes, locks, and schema tests.
- Agent W1-B: Implement contract artifact schemas and validators.
- Agent W1-C: Implement deterministic fixture support for schema and root tests.

Dependencies: D0.

Expected outputs:

- `.project/context_forge_state.json` schema and validation path.
- Schema definitions for all RFC contract artifacts.
- Tests for invalid roots, symlinks, denied roots, legacy `.env` migration
  classification, sticky declines, disabled/no-service state, secret exclusion,
  enum validation, stale locks, and schema evolution.

QA agent W1-QA:

- Check project state remains project-init authority only, not a host catalog.
- Check legacy `.env` is migration input, not a parallel authority.
- Check schema tests cover contract artifacts and root-safety cases.

Root gate:

- Resolve any schema ambiguity before allowing planners or apply logic to build
  on it.

### Wave 2: Read Surfaces And Test Harness

Implementation agents:

- Agent W2-A: Implement redacted control-service read models for
  `get_project_context`, `list_catalog`, `list_available_capabilities`, and
  `report_project_gaps`.
- Agent W2-B: Implement requirement registry, coverage matrix, scenario DSL,
  evaluator verdict schema, evidence ledger format, transcript/world-state
  capture, remediation handoff format, and deterministic scenario runner
  skeleton.
- Agent W2-C: Implement redaction helpers and diagnostic bundle fixtures.

Dependencies: D1, D2.

Expected outputs:

- Non-mutating read surfaces with canonical names, contract refs, capsules,
  trust state, open items, and redacted catalog summaries.
- Requirement registry and coverage matrix tied to scenario and evidence
  artifacts suitable for deterministic and future inference-inclusive execution.
- Harness support for later waves to add requirement-linked scenarios and
  inference markers as they implement behavior; Wave 12 executes accumulated
  scenarios rather than creating most of the harness.
- Redaction tests for tokens, secrets, env values, audit payloads, and catalog
  output.

QA agent W2-QA:

- Check read surfaces cannot mutate project, client, ContextForge, systemd, or
  trust state.
- Check catalog output redacts secrets and does not treat client config entries
  as canonical service identity.
- Check scenario fixtures preserve tested-agent view separation from hidden
  evaluator state.

Root gate:

- Fix any read/mutation boundary leak or redaction gap before planning work.

### Wave 3: Classification And Shared-Service Capsules

Implementation agents:

- Agent W3-A: Implement service instantiation classifier and shared-service
  capability capsule handling.
- Agent W3-B: Implement classification and capsule fixture cases for
  `context7`, `ssh-tmux`, `mentality`, Serena, and catalog candidates.

Dependencies: D3, D4.

Expected outputs:

- Tests proving shared canonical services such as `context7` are bound or
  verified without per-project backend creation.
- At least one real shared/canonical capability capsule, preferably `context7`
  when locally available, seeded/read through ContextForge metadata or reported
  as a blocking gap if the local catalog cannot support it.
- Classification output that distinguishes `instance_per_project`,
  `shared_canonical`, credential/resource/caller/session scope,
  `static_repo_local`, and candidates.
- Capsule non-actions and verification requirements for shared services.

QA agent W3-QA:

- Check shared services have capsules and non-actions.
- Check ambiguous classification blocks mutation.
- Check client config entries are not treated as canonical service identities.

Root gate:

- Reject or repair any classifier behavior that duplicates shared services or
  invents client-named identities.

### Wave 4: Project-Init Planning And Service-Management Handoff

Implementation agents:

- Agent W4-A: Implement non-mutating project-init planner with contract-card
  refs, capsule refs, consent requirements, stale-plan inputs, open items, and
  verification requirements.
- Agent W4-B: Implement service-management handoff object emission for catalog
  candidates and catalog repair needs.
- Agent W4-C: Implement planner fixture scenarios and expected handoff outputs,
  including sticky-decline and disabled/no-service cases.

Dependencies: D5.

Expected outputs:

- Planner output that distinguishes accepted services, shared bindings,
  deferred/declined services, missing trust, missing language, stale state, and
  catalog candidates.
- Handoff objects when catalog promotion or repair is needed.
- Tests proving the planner remains non-mutating.

QA agent W4-QA:

- Check the planner never promotes catalog candidates under project-init
  approval.
- Check handoff objects are redacted and typed.
- Check planned consent classes and stale-plan inputs are complete.

Root gate:

- Fix any planner behavior that crosses into mutation or omits required
  contract/capsule/receipt/trace references.

### Wave 5: Operation Authorization, Consent, Apply, And Trace

Implementation agents:

- Agent W5-A: Implement operation authorization, consent receipts, plan
  journals, stale-plan validation, receipt expiry/replay checks, and idempotent
  apply for project-local state and owned config blocks only.
- Agent W5-B: Implement adapter-independent verification trace emission and
  trace-linked lifecycle transitions.
- Agent W5-C: Implement apply/journal fixture cases for stale plans, receipt
  scope changes, interrupted runs, failed trace emission, and owned/unmanaged
  config boundaries.

Dependencies: D6.

Expected outputs:

- Authorization checks for caller/workflow identity, operation class, source
  client, target clients, canonical root, project-state revision, token source,
  receipt scope, receipt expiry, and replay policy.
- Receipts tied to consent class, scope, plan digest, actor, source client, and
  mutation target.
- Apply logic that refuses stale plans and cannot reuse receipts across changed
  scope.
- Verification traces tied to lifecycle transitions.

QA agent W5-QA:

- Check generic project-init approval cannot authorize user-global trust,
  catalog promotion, token material, actual secret values, or remote exposure.
- Check unauthorized callers and stale receipts cannot execute or replay plans.
- Check every verified transition names a verification trace.
- Check owned config applies are idempotent and unmanaged config blocks stop for
  user action.

Root gate:

- Fix any authorization gap, consent bundling, stale receipt reuse, or trace
  omission before service-provision or client-adapter work.

### Wave 6: Codex Trust And Tool Policy

Implementation agents:

- Agent W6-A: Implement Codex client adapter conformance pack.
- Agent W6-B: Implement trust broker inspection/report/approval-record/
  verification flow for Codex.
- Agent W6-C: Implement semantic tool-policy compiler and negative checks.

Dependencies: D7.

Expected outputs:

- Codex conformance proof for project-local config loading, trust gap handling,
  restart behavior, list-tools, call-tool, stale config, and owned-block
  conflicts.
- Trust broker that reports and records trust approval without auto-granting
  trust.
- Compiler from semantic risk classes to ContextForge virtual-server
  associations and target-client negative checks, with fail-closed behavior for
  unknown tools or missing risk metadata.

QA agent W6-QA:

- Check Codex trust is not auto-granted and is verified through actual config
  consumption.
- Check target-client proof requires a passing conformance pack or explicit
  blocking limitation.
- Check scope-changing tools are filtered semantically, not by Serena-only
  string matching, and unknown policy metadata blocks exposure.

Root gate:

- Fix client-proof shortcuts, trust approval bundling, or unsafe tool-policy
  behavior before project-scoped service provisioning.

### Wave 7: Generic Project-Scoped Service Provision

Implementation agents:

- Agent W7-A: Implement generic project-scoped `service_provision` apply for
  backend homes, ignored env placeholders, user-systemd units, ports, and
  manifests.
- Agent W7-B: Implement ContextForge gateway/server registration,
  virtual-server association, client-binding intent generation,
  conformance-gated client write hooks, and trace references for
  project-scoped service provision.
- Agent W7-C: Implement recovery fixtures for interrupted provision, partial
  registration, port conflict, stale unit, readiness failure, and config
  conflict.

Dependencies: D1, D2, D6, D7, D9, D10.

Expected outputs:

- A generic project-scoped provision path that can later host Serena and
  project-inspector without hard-coded service assumptions.
- Clear separation between `service_provision` and `catalog_promotion`.
- Client-visible binding blocked until conformance pack, compiled tool policy,
  negative checks, consent receipts, and stale-input checks pass.
- Recovery paths classified as resume, forward repair, rollback by approved
  workflow, manual recovery, or fresh approval required.

QA agent W7-QA:

- Check the provision layer does not promote host-wide catalog candidates or
  mutate shared canonical service identity.
- Check partial unit, port, ContextForge, and client-binding failures produce
  typed recovery outcomes.
- Check generated service state references consent receipts and verification
  traces.
- Check client-visible exposure is impossible until compiled policy and negative
  readback checks pass.

Root gate:

- Fix provisioning/recovery or policy-gating gaps before proof-service work.

### Wave 8: Language Profiles, Generic Adapter, And Serena Proof

Implementation agents:

- Agent W8-A: Implement ContextForge-backed v1 language-profile metadata needed
  by proof services, including explicit plan-first install workflow metadata.
- Agent W8-B: Implement the generic project-scoped service adapter foundation
  and refactor Serena behind it, consuming language-profile metadata instead of
  service-local language policy.
- Agent W8-C: Implement Serena proof integration fixtures and client-visible
  verification.

Dependencies: D2, D3, D7, D8, D9, D10.

Expected outputs:

- Language profiles for Python, TypeScript/JavaScript, Rust, and Bash with no
  silent install or default global mutation.
- Adapter foundation that separates project identity, backend instance,
  ContextForge registration, virtual server, tool policy, client binding,
  receipts, traces, and recovery behavior.
- Serena proof through that adapter with `activate_project` as one fixture, not
  a hard-coded special case, and with language requirements consumed from
  ContextForge-backed profile metadata.

QA agent W8-QA:

- Check language tooling does not silently install or mutate global tooling.
- Check Serena is not globally exposed and does not become a privileged special
  case.
- Check scope-changing tools are filtered after gateway refresh, server
  association update, restart, and stale-config repair.
- Check the adapter can support a second project-scoped service without
  rewriting Serena-specific logic.

Root gate:

- Fix generic-adapter gaps before project-inspector work.

### Wave 9: Project-Inspector Proof

Implementation agents:

- Agent W9-A: Seed `project-inspector` as the RFC-named proof service through
  the approved project-scoped provision path unless a later approved decision
  routes it through service-management.
- Agent W9-B: Implement read-only `project-inspector` root-bound service
  behavior.
- Agent W9-C: Implement project-inspector proof integration fixtures.

Dependencies: D11.

Expected outputs:

- Project-inspector proof with root-bound read-only tools, no external secrets,
  and the same contract/receipt/trace/client-verification path as Serena.
- Explicit evidence that it is not treated as a random discovered catalog
  candidate and not promoted under generic project-init approval.

QA agent W9-QA:

- Check project-inspector is useful, root-bound, read-only, and not a disguised
  shell or file-exfiltration service.
- Check its catalog/proof status follows the RFC-approved seed path or an
  explicit service-management path.
- Check proof fixtures cover empty, nested, symlinked, ignored-path, and dirty
  worktree roots.

Root gate:

- Fix unsafe project-inspector behavior or catalog-status ambiguity before
  broader service-management flows.

### Wave 10: Memory And Service Management

Implementation agents:

- Agent W10-A: Implement service-memory provider metadata and governance
  reference/proposal behavior.
- Agent W10-B: Implement service-management skill workflow, handoff consumption,
  catalog promotion/update plan shape, and post-approval completion records.
- Agent W10-C: Implement integration fixtures tying language-profile metadata,
  service-memory metadata, service-management handoffs/results, and governance
  reconciliation warnings together.

Dependencies: D0, D1, D2, D3, D4, D5, D6, D7, D8, D9, D10, D11, D12, and D13.

Expected outputs:

- Service memory metadata that remains reference/proposal-only for governance.
- Service-management plans that use ContextForge APIs, dedupe by backend and
  scope, preserve native transports, and require explicit approval.
- Integration evidence that language-profile records remain plan-first and that
  service-management results are the only path from candidate handoff to
  canonical service binding.

QA agent W10-QA:

- Check service memory cannot settle governance decisions.
- Check service-management does not use direct database writes or unnecessary
  bridges.
- Check candidate handoffs cannot become project-state service records without
  a typed service-management result.

Root gate:

- Fix governance authority leaks or transport wrapping mistakes before auth
  hardening.

### Wave 11: Auth Hardening And Remote Gate

Implementation agents:

- Agent W11-A: Implement wrapper token-source and leak checks.
- Agent W11-B: Implement loopback auth checks, token rotation/revocation
  workflow gates, and redaction verification.
- Agent W11-C: Implement non-default remote exposure gate and negative exposure
  checks.

Dependencies: D0, D1, D2, D3, D4, D5, D6, D7, D8, D9, D10, D13, D14, and D15.

Expected outputs:

- Auth/security checks for token source, wrapper leak prevention, loopback
  defaults, token rotation/revocation workflows, and opt-in remote exposure.
- Remote exposure remains non-default and separately approved.

QA agent W11-QA:

- Check remote exposure is non-default, separately approved, and does not reuse
  local shared tokens.
- Check token material does not appear in argv, logs, project state, normal
  audit, diagnostics, or catalog output.
- Check wrapper and direct HTTP paths preserve the active local auth profile.

Root gate:

- Fix auth boundary failures before end-to-end acceptance work.

### Wave 12: Minimal Viable Slice And Acceptance

Implementation agents:

- Agent W12-A: Build deterministic and integration scenarios for the minimal
  viable slice.
- Agent W12-B: Build inference-inclusive headless assistant scenarios and
  evaluator runs for the minimal viable slice.
- Agent W12-C: Build final docs/runbooks and implementation evidence bundle.

Dependencies: all D17 prerequisites: D4, D9, D11, D12, D13, D14, D15, and D16.

Expected outputs:

- End-to-end minimal slice executing the accumulated requirement-linked
  scenarios for project-state, sticky declines, disabled/no-service state,
  planning, consent, apply, Codex trust, semantic tool-policy, Serena,
  project-inspector, shared-service capsule, service-management handoff,
  language-profile behavior, service-memory governance boundary, and governance
  reconciliation cases, plus adversarial malicious-metadata/prompt-injection
  cases.
- Evidence ledgers tying transcripts, deterministic checks, receipts, traces,
  verdicts, and remediation results.
- Final runbook and acceptance checklist mapped to RFC acceptance criteria.

QA agent W12-QA:

- Check deterministic tests, live/fixture integration probes, and
  inference-inclusive tests cover the RFC acceptance strategy.
- Check evaluator verdicts are evidence-cited and requirement gaps remain
  proposals.
- Check the minimal viable slice did not expand into unapproved remote,
  catalog-wide provenance, raw CRUD, or automatic secret-value entry.

Root gate:

- Resolve all blocking QA findings before claiming the RFC implementation is
  ready for broader service/client expansion.

### Wave 13: Governance Closeout And Release Readiness

Implementation agents:

- Agent W13-A: Apply approved governance ledger updates through
  `scripts/governance_crud.py` or `mentality`.
- Agent W13-B: Produce final release-readiness report mapped to RFC acceptance
  criteria.

Dependencies: D17.

Expected outputs:

- Governance ledgers updated only for approved reconciliation items.
- Final evidence index, unresolved non-blockers, and release-readiness summary.

QA agent W13-QA:

- Check governance updates match the approved reconciliation pack.
- Check the final report cites verification evidence rather than assumptions.
- Check no unapproved implementation scope was claimed complete.

Root gate:

- Do not declare completion until final QA findings are fixed, rejected with
  evidence, or recorded as approved non-blockers.

## Scoped Agent Prompt Template

The root agent must richly prompt each implementation agent, but only for the
task assigned. The prompt must be explicit, restrictive, and disciplinary about
file ownership. Use this structure:

```text
You are Agent <wave-id>-<agent-id> for the ContextForge control-plane
implementation.

Objective:
<one precise deliverable>

Relevant RFC sections:
- docs/initiatives/contextforge-control-plane/design-rfc.md#<section>
- <only sections needed for this assignment>

Allowed write set:
- <exact file path or directory path the agent may edit>
- <this list is exhaustive>

Read-only context:
- <files/modules the agent may inspect but must not edit>

Files/modules out of scope:
- <paths or domains agent must not edit>
- All files not listed in Allowed write set are out of scope by default.

Scope discipline:
- You may edit only the files/directories named in Allowed write set.
- Reading a file does not give you permission to edit it.
- Do not modify, reformat, reorder, rename, delete, stage, commit, or regenerate
  any out-of-scope file.
- Do not opportunistically fix nearby issues, adjacent waves, lint churn,
  formatting churn, stale docs, or unrelated tests.
- If you discover a necessary change outside the allowed write set, stop and
  report it as a handoff with file path, evidence, and why it blocks or affects
  your task. Do not make the change.
- If your task cannot be completed without editing an out-of-scope file, stop
  and return a blocker instead of broadening your own scope.

Hard constraints:
- ContextForge remains the stock registry/proxy/control-plane anchor.
- Do not mutate ContextForge catalog/user-global trust/secrets unless this task
  explicitly requires an approved workflow and the root agent has supplied the
  approval evidence.
- Preserve unrelated worktree changes.
- Do not implement adjacent wave work.
- Return the changed-file list in your final response. Any file outside Allowed
  write set is a scope violation.

Expected output:
- <code/docs/tests/artifacts>
- <verification commands/probes>
- <handoff notes including blockers and assumptions>

Stop conditions:
- <dependency missing>
- <schema/RFC ambiguity>
- <unowned file conflict>
- <approval-required mutation not approved>
- <change required outside allowed write set>
```

Do not prompt an agent with a broad instruction such as "implement the control
plane." The agent must receive the minimum complete context needed for its own
deliverable. The root agent must never rely on an agent to infer file scope from
the task title, wave name, or repo layout.

## Per-Agent Prompt Matrix

The root agent should use the template above with these focused assignment
prompts. Add exact file paths and current verification commands at dispatch
time. Each dispatch must also name the deliverable IDs it is allowed to advance,
the dependencies that have already passed, precise RFC section references, the
scoped evidence the agent must return, and stop conditions for missing
dependencies, approval-required mutation, schema ambiguity, or file ownership
conflicts. The matrix is not a write-set grant by itself. Before dispatch, the
root agent must convert each prompt focus into a narrow allowed write set and
must state that all other files are read-only unless listed under read-only
context.

| Agent | Prompt focus |
| --- | --- |
| W0-A | Baseline current branch, worktree, ContextForge health, server-instances, project-init state, ignored local state, and blockers. No mutation. |
| W0-B | Compare RFC/procedure against governance ledgers and produce advisory reconciliation only. No ledger edits. |
| W1-A | Implement project-state schema/library, root validation, migration reader, atomic writes, locks, and schema tests. |
| W1-B | Implement contract artifact schemas and validators for cards, capsules, policies, handoffs, receipts, traces, packs, scenarios, verdicts, ledgers, and reconciliation packs. |
| W1-C | Build deterministic fixtures for schema, root, denied-root, symlink, migration, sticky decline, disabled/no-service, lock, and secret-exclusion tests after W1-A/W1-B interfaces are frozen. |
| W2-A | Implement non-mutating redacted read models for project context, catalog, capabilities, and gaps. |
| W2-B | Implement requirement registry, coverage matrix, scenario DSL, evaluator verdict schema, evidence ledger format, transcript/world-state capture, remediation handoff, and deterministic scenario runner skeleton. |
| W2-C | Implement redaction helpers and diagnostic bundle fixtures for catalog, env, token, audit, and trace output. |
| W3-A | Implement service instantiation classifier and shared-service capsule behavior. |
| W3-B | Build classification/capsule fixtures for `context7`, `ssh-tmux`, `mentality`, Serena, and catalog candidates after classifier output shape is frozen. |
| W4-A | Implement non-mutating project-init planner with contract refs, capsules, consent requirements, stale inputs, open items, and verification requirements. |
| W4-B | Emit redacted service-management handoffs for catalog candidates and catalog repairs. |
| W4-C | Build planner fixtures for accepted, declined, deferred, missing-trust, missing-language, stale-state, and candidate cases. |
| W5-A | Implement operation authorization, consent receipts, plan journals, stale-plan validation, receipt expiry/replay checks, and project-local apply. |
| W5-B | Implement adapter-independent verification trace emission and lifecycle transition references. |
| W5-C | Build apply/journal recovery fixtures for stale plans, receipt-scope changes, interrupted runs, failed traces, and owned/unmanaged config. |
| W6-A | Implement Codex adapter conformance pack for config, trust gap, restart, list-tools, call-tool, stale config, auth strength, and owned-block conflicts. |
| W6-B | Implement Codex trust broker inspect/report/approval-record/verification flow without auto-granting trust. |
| W6-C | Implement semantic tool-policy compiler and fail-closed negative checks. |
| W7-A | Implement project-scoped provision apply for backend homes, env placeholders, user-systemd units, ports, and manifests. |
| W7-B | Implement ContextForge gateway/server registration, virtual-server association, client-binding intents, conformance-gated client write hooks, and trace references for project-scoped provision. |
| W7-C | Build recovery fixtures for interrupted provision, partial registration, port conflict, stale unit, readiness failure, config conflict, and blocked policy exposure. |
| W8-A | Implement ContextForge-backed language-profile metadata and plan-first install workflow metadata for proof-service use. |
| W8-B | Implement generic project-scoped service adapter foundation and refactor Serena behind it while preserving project-specific ContextForge path and `activate_project` filtering. |
| W8-C | Build Serena proof integration fixtures and client-visible verification, including language-profile consumption. |
| W9-A | Seed `project-inspector` as the RFC-named proof service through the approved project-scoped provision path unless explicitly rerouted. |
| W9-B | Implement root-bound read-only project-inspector service behavior. |
| W9-C | Build project-inspector fixtures for empty, nested, symlinked, ignored-path, and dirty worktree roots. |
| W10-A | Implement service-memory provider metadata with governance reference/proposal-only behavior. |
| W10-B | Implement service-management workflow, handoff consumption, catalog promotion/update plans, and completion records. |
| W10-C | Build integration fixtures for language-profile records, service-memory metadata, service-management handoffs/results, and governance reconciliation warnings. |
| W11-A | Implement wrapper token-source and leak checks. |
| W11-B | Implement loopback auth checks, token rotation/revocation workflow gates, and redaction verification. |
| W11-C | Implement non-default remote exposure gate and negative exposure checks. |
| W12-A | Execute and fill gaps in deterministic and integration scenarios for the minimal viable slice. |
| W12-B | Execute and fill gaps in inference-inclusive headless assistant scenarios and evaluator runs. |
| W12-C | Build final docs/runbooks and implementation evidence bundle after W12-A/W12-B evidence is available. |
| W13-A | Apply only approved governance updates through `scripts/governance_crud.py` or `mentality`. |
| W13-B | Produce final release-readiness report mapped to RFC acceptance criteria and evidence. |

## Wave QA Prompt Template

```text
You are the QA agent for Wave <n> of the ContextForge control-plane
implementation.

Scope:
Review only the work completed in Wave <n> against:
- the Wave <n> objectives in design-rfc-procedure.md;
- the specific RFC sections listed for that wave;
- the implementation diff and verification output supplied by the root agent.
- the allowed write set and forbidden write set supplied to each dispatched
  implementation agent.

Do not design or implement future waves. Do not broaden acceptance criteria.

Report:
1. Scope violations: any edited, reformatted, renamed, deleted, staged, or
   generated file outside an agent's allowed write set.
2. Blocking issues with file/line references or concrete evidence.
3. Non-blocking issues or residual risks.
4. Missing verification.
5. Any claim that should be rejected because it relies on assumptions instead
   of local evidence.
6. A concise pass/fail recommendation for this wave.
```

Every wave QA must also run a cumulative invariant regression check for the
surfaces touched by that wave, using evidence supplied by the root agent. The
root owns the full cumulative system verification; the wave QA must not redesign
prior waves but must flag any invariant regression it can evidence.

Any out-of-scope edit by an implementation agent is a blocking QA finding unless
the root agent explicitly re-scoped that file before integration and recorded
the reason in the run notes. Usefulness of the edit is not a defense; scope
discipline protects parallel delegation and unrelated worktree changes.

- ContextForge remains the stock registry/proxy/control-plane anchor.
- Client configs are discovery/consumption surfaces, not service identities.
- `.project/context_forge_state.json` remains the project-init state authority.
- User-global trust, user-global config, token material, actual secret values,
  catalog promotion, and remote exposure remain separately approved.
- Shared canonical services are not duplicated per project.
- Project-scoped services have contract cards, receipts, traces, recovery
  paths, and target-client proof.
- Catalog mutation remains behind service-management handoff and approved
  workflow.
- Redaction prevents secrets/tokens/env values from appearing in catalog,
  project state, normal audit, diagnostics, traces, or logs.
- Service memory remains reference/proposal-only for governance.
- No new implementation path bypasses the dependency map.

## Root QA Adjudication Requirements

For each QA finding, the root agent must classify it as:

- `accepted_blocker`: must be fixed before the next wave.
- `accepted_non_blocker`: can be recorded and scheduled without blocking.
- `rejected`: not valid; root must cite evidence.
- `deferred_design_question`: blocks only if it invalidates current-wave
  acceptance; otherwise record as an open question through governance workflow.

The root agent must run relevant verification after fixes. If additional QA is
needed after blockers, the root should reopen the same wave QA assignment for
the changed areas, or perform root verification when the fix is mechanical and
fully covered by deterministic evidence.

## Final Acceptance Procedure

The implementation is not complete until:

- all dependency nodes D0-D18 are complete or explicitly deferred by approved
  governance decision;
- every `must_pass_mvs` requirement in the coverage matrix is complete; MVS
  requirements may not be deferred unless the RFC itself is amended or a
  governance waiver explicitly changes the acceptance target;
- every wave QA has passed after root adjudication;
- deterministic tests and required integration/probe tests pass;
- inference-inclusive scenarios preserve inferential isolation and have
  structured evaluator verdicts;
- every mutating effect has a consent receipt;
- every verified state references a verification trace;
- project initialization state is in `.project/context_forge_state.json`;
- shared canonical services have capability capsules and are not duplicated per
  project;
- catalog promotion is available only through service-management handoff and
  approved workflow;
- user-global trust, token material, actual secret values, and remote exposure
  are separately approved and evidenced;
- governance reconciliation has been reviewed through the repo's normal
  governance process.

The final root-agent response should summarize completed waves, verification
commands, unresolved non-blockers, governance changes made or still pending,
and the exact RFC acceptance criteria satisfied.
