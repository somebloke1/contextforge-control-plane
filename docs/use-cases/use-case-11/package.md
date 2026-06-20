# Use Case 11 Package: See Project Tool Guidance When Using A Capability

Issue: #253.

## Status

Queue state: selected after accepted UC8 same-session Context7 tool-use
evidence because UC11 depends on a functioning selected capability route and
registered guidance metadata for that route.

Controller state: package materialized and accepted for Pi, OpenCode, and
Codex with fresh target-client CLI evidence, guidance-readback evidence,
ordinary user-facing guidance behavior, non-Spark semantic evaluation,
remediation records, and controller integration. Future target clients must
repeat the localized package from a clean target-client state.

## Method Binding

This package localizes the reusable method in
`holistic_orchestrated_pipeline_spec.md`,
`docs/use-cases/dependency-mesh.md`, and
`docker/client-harness/DIALOGUE_EVALUATION_METHOD.md`.

UC11 depends on:

- UC3 initialized-project capability summary, because the user asks about or
  invokes a capability in an already initialized project;
- UC8 Context7 same-session tool-use, because the selected capability must be
  usable rather than merely listed;
- registered ContextForge prompt/resource/tool guidance, because the client
  must surface project guidance through natural capability mechanisms.

The selected concrete substrate is `context7:canonical`, specifically the
OpenCode documentation lookup workflow. It is credential-free, read-only,
already accepted for ordinary tool use in UC8, and has source-defined guidance
for `context7-local-resolve-library-id` and `context7-local-query-docs` in
`scripts/register_tool_guidance.py`.

This package uses explicitly pre-aligned per-target-client fixtures. It does
not test automatic client alignment, project-wide service propagation, or a new
client importing another client's services. #287's project service
graph/client projection model constrains UC11 claims: the package may show
that one target client surfaced guidance for one selected project capability;
it must not claim that project service presence alone proves target-client
import, visibility, reload state, or tool proof for any other client.

Pi's concrete guidance surface is the project shim's
`cf_contextforge_guidance_lookup` tool, which lazily reads matching
ContextForge prompt/resource guidance for an approved service without exposing
every prompt/resource as a separate Pi tool. OpenCode must surface equivalent
guidance through its natural MCP prompt/resource/tool guidance mechanism for
the selected ContextForge capability. Codex must surface equivalent guidance
through the project-local Codex hook/MCP surface in the authenticated Docker
client without using host Codex state or API-key authentication.

## Full Story

1. Preserve previous evidence.
2. Start from a clean harness state:
   - reset stale target-client containers and target-client home volume where
     that client uses a disposable home volume;
   - reset `/workspace` to a virgin state;
   - preserve displaced workspace evidence before reset.
3. Prepare one initialized project fixture at `/workspace` for the target
   client:
   - project root is `/workspace`;
   - project status is initialized;
   - `context7:canonical` is enabled for the target client;
   - the evidence separates the global project service graph from this target
     client's projection;
   - target-client project-local config or shim surfaces exist;
   - the guidance/tool surface is visible to this target client;
   - ContextForge guidance metadata for Context7 resolve/query tools is
     present or readback-verifiable;
   - no unrelated service, registry, credential, global client, or host config
     mutation is required.
4. Reset the target client's home volume again after setup so the test client
   does not inherit setup-session residue.
5. Start one fresh non-ephemeral target-client container against `/workspace`.
6. Use one stable target-client session id for the guidance question and any
   follow-up capability use.
7. User sends the minimal ordinary guidance prompt:
   `how should I use the project docs lookup capability for opencode configuration questions?`
8. The assistant recognizes the initialized project and selected docs
   capability without restarting first-run activation.
9. The assistant surfaces practical project-specific guidance for using the
   docs lookup capability:
   - identify that ContextForge provides the docs lookup route;
   - explain that the workflow should resolve the relevant OpenCode docs or
     library entry when needed;
   - explain that the docs query should ask a concrete configuration question
     and prefer current documentation-backed guidance;
   - keep wording concise and user-facing.
10. If the client uses a guidance lookup or prompt/resource read internally,
    that supporting tool evidence is captured. The visible answer must not
    expose raw prompt/resource JSON, hidden instructions, helper payloads,
    internal scoring criteria, or implementation trace noise.
11. User sends the optional ordinary follow-up prompt in the same session:
    `use that approach to check what I should read about opencode config files`
12. The assistant uses the selected docs capability naturally, or clearly
    applies the surfaced guidance to the concrete docs lookup task. The answer
    remains bounded to the selected capability and project context.
13. Capture raw outputs, command ledger, runtime readbacks, fixture/state
    readbacks, stepwise generation reports, total generation report, guidance
    readback/tool evidence, session id, and transcript artifacts.
14. Produce a structured evidence package showing:
    - one target client;
    - one stable session identity;
    - clean setup and reset evidence;
    - `project_service_graph`: the selected Context7 service exists or is
      accepted for the project fixture;
    - `target_client_projection`: the selected service is imported/configured
      for the target client under test;
    - `target_client_visibility`: the guidance/tool surface is visible in that
      target client;
    - `target_client_proof`: the target client surfaced guidance, and optional
      follow-up tool use if that path is run;
    - natural user prompts;
    - guidance metadata presence or readback evidence;
    - visible practical guidance for the selected capability;
    - optional same-session capability use after guidance;
    - no first-run onboarding, reinitialization, validation/probing, backend
      restart, registry mutation, global client mutation, or secret write.
15. Semantic evaluator reviews the visible replies and supporting traces. The
    evaluator decides whether the assistant gave useful natural guidance for
    using the project capability, not whether any exact phrase appeared.

## Terminal Boundary

The terminal boundary is a natural answer that helps the user use the selected
project capability correctly and practically. A stronger run may also include a
same-session follow-up docs lookup using that guidance, but the acceptance
claim is guidance surfacing for the capability.

The flow does not require service onboarding, post-install validation, provider
credential exercise, backend restart, live registry mutation, global client
mutation, broad prompt-library productization, or a final readiness report.

The flow also does not require or prove #285-style client alignment. If setup
finds that a target-client projection is missing, stale, blocked, or reload-
required, the runner must report that structured state and stop or route to the
appropriate remediation. It must not silently align/import the service or use
one client's projection as another client's proof.

## Minimal Prompt Sequence

For each client:

```text
how should I use the project docs lookup capability for opencode configuration questions?
```

Optional follow-up in the same session:

```text
use that approach to check what I should read about opencode config files
```

Prompts must remain natural. They must not name helper tools, exact MCP tool
ids, prompt/resource object names, JSON keys, expected tool order, scoring
criteria, evaluator requirements, or known failure modes.

## Expected Visible Story

- The assistant recognizes this is an initialized project with a docs lookup
  capability available.
- The assistant explains the capability in practical terms: resolve a relevant
  docs/library entry when needed, then ask a concrete docs query for the
  configuration task.
- The guidance helps the user choose a correct prompt or workflow.
- The guidance is current for the project and tied to the selected capability,
  not a generic model-memory answer about documentation.
- The answer is bounded to the current project/client session, or an equivalent
  target-client-specific phrase, rather than implying every client has imported
  or proven the capability.
- The assistant does not restart first-run onboarding or ask which service to
  activate.
- The assistant does not expose raw prompt/resource JSON, helper payloads,
  internal route names as required user knowledge, hidden instructions, or
  internal scoring criteria.
- The assistant does not overclaim that all future docs answers are guaranteed
  current, complete, or validated beyond the observed guidance/tool surfaces.
- If the follow-up is run, the assistant uses the same session and either uses
  the docs capability or clearly applies the surfaced guidance to the concrete
  docs lookup task.

## Deterministic Setup

Required setup for each client attempt:

```text
python3 docker/client-harness/scripts/reset-client-harness-state.py --client <pi|opencode|codex-cli> --reset-home-volume
prepare initialized /workspace fixture for <client> with context7:canonical installed
verify or record Context7 tool guidance metadata/readback for the selected capability
reset the same client home volume after setup when that client uses a disposable home volume
docker compose -f docker/client-harness/compose.yml build base <client>
docker compose -f docker/client-harness/compose.yml run --name <fresh-name> --no-deps -d <client> sleep infinity
```

The initialized fixture preparation must be deterministic and idempotent. It
may use helper-owned install/apply code and readback-only guidance checks. It
must not depend on residue from a previous dialogue attempt.

Codex uses the local-only authenticated baseline image rather than a disposable
home volume so OAuth/ChatGPT subscription state is preserved without host API
keys. Codex attempts must still reset `/workspace`, remove stale target
containers, launch fresh non-ephemeral containers, and pass empty known API-key
environment variables. A second post-setup home-volume reset is not applicable
for Codex when the authenticated compose service has no mounted client-home
volume.

Runner metadata must include separate structured fields for:

- `project_service_graph`;
- `target_client_projection`;
- `target_client_visibility`;
- `target_client_proof`.

The structural verifier may check those fields exist and have declared enum or
boolean shape. It must not infer free-form assistant meaning from matched
phrases.

## Venv Contract

Host-side source checks and runners must use a current-worktree runtime.

Current suite runtime:

```text
run/test-venvs/project-init-workflow/bin/python
```

Sibling checkout venvs are not valid acceptance evidence.

## Step Criteria

Every model-dependent step must be accompanied by a runner-produced generation
report. The runner may validate commands, structured artifacts, guidance
metadata presence, tool-call presence, session id continuity, and evidence
presence. It must not deterministically score free-form assistant behavior; the
semantic evaluator must score generated dialogue.

### clean_initialized_guidance_fixture (10 pts)

Expected: A fresh target-client container starts from an idempotently prepared
initialized `/workspace` fixture with `context7:canonical` installed for the
target client and guidance metadata available or readback-verifiable.

Fail if: stale residue from a previous test is used, the Context7 capability is
missing, guidance metadata is absent without a recorded blocker, unrelated
client state is reset, or setup relies on manual residue cleanup.

### project_graph_projection_separation (10 pts)

Expected: Evidence distinguishes project service presence from target-client
projection, target-client visibility, and target-client proof for exactly the
client under test.

Fail if: project service presence is treated as target-client proof, Pi
evidence is used as OpenCode proof, OpenCode evidence is used as Pi proof, or
the runner silently aligns/imports a missing target-client projection.

### non_ephemeral_same_session (10 pts)

Expected: The target assistant runs in a non-ephemeral Docker client container
and all prompts in the attempt use one stable session identity.

Fail if: `--rm`, tmpfs workspace, ephemeral services, different session ids, or
one-shot unrelated sessions are used.

### natural_guidance_prompt (10 pts)

Expected: The prompt is an ordinary user question asking how to use a project
docs lookup capability for an OpenCode configuration task.

Fail if: the prompt names helper calls, exact MCP tool ids, prompt/resource
object names, JSON fields, expected tool order, exact library ids, or evaluator
criteria.

### guidance_surface_used_or_honestly_available (15 pts)

Expected: Supporting evidence shows the client had access to guidance metadata
or a natural guidance surface for the selected ContextForge capability. Pi may
use `cf_contextforge_guidance_lookup`; OpenCode may use its natural MCP
prompt/resource/tool guidance path.

Fail if: the assistant answers only from model memory while the guidance
surface is absent, reads local source files as a workaround, or treats a
generic capability/readback list as the guidance answer.

### practical_project_specific_guidance (25 pts)

Expected: The visible answer gives practical guidance for the selected project
capability: resolve the relevant OpenCode docs/library entry when needed, ask a
specific configuration docs question, prefer documentation-backed current
guidance, and keep claims bounded to the current project/client session or
equivalent target-client scope.

Fail if: the answer is generic advice about reading docs, merely describes
what the assistant could do, invents unsupported rules, or omits the selected
project docs lookup workflow. Also fail if the answer claims project-global
availability, all-client readiness, or cross-client alignment without target-
client evidence.

### implementation_noise_suppressed (10 pts)

Expected: The visible answer is user-facing and does not expose raw
prompt/resource JSON, hidden instructions, helper payloads, exact internal
route names as required user knowledge, command transcripts, or scoring
criteria.

Fail if: internal implementation details become the user-facing answer rather
than supporting evidence.

### optional_followup_applies_guidance (10 pts)

Expected: If the optional follow-up is run, it stays in the same session and
uses the prior guidance to perform or frame the concrete OpenCode config docs
lookup.

Fail if: the assistant ignores the prior guidance, restarts onboarding, asks
the user to repeat context, or loses project/tool context.

### readiness_and_non_actions (5 pts)

Expected: The assistant keeps claims bounded and avoids onboarding,
validation/probing, backend restart, live registry mutation, global client
mutation, service onboarding, secret writes, and hidden prompt leakage.

Fail if: any forbidden action or overclaim appears.

### evidence_package_integrity (5 pts)

Expected: The package includes raw turns, command ledger, metadata, verifier
JSON, guidance metadata/readback evidence, stepwise generation reports, total
generation report, and semantic evaluation package.

Fail if: evidence is missing, overwritten without preservation, or too weak for
semantic review.

## Acceptance Commands

Planned runner shape:

```text
python3 docker/client-harness/scripts/run-use-case-11-dialogue.py --client pi
python3 docker/client-harness/scripts/run-use-case-11-dialogue.py --client opencode
```

The runner must produce raw turn output, combined evidence, structured
metadata, verifier JSON, evaluation-package Markdown, stepwise generation
reports, total generation reports, and guidance-readback or guidance-tool
evidence.

Until the runner exists, acceptance is blocked at package materialization. Do
not substitute manual transcript inspection for the full SuperLoop acceptance
cycle.

## Remediation Routing

- fixture mismatch: repair initialized fixture preparation, then rerun from a
  virgin workspace and clean client home;
- missing, stale, blocked, or reload-required target-client projection: report
  the structured state and route to #286/#285 as appropriate; do not silently
  align/import inside UC11;
- guidance metadata absent: repair `scripts/register_tool_guidance.py`,
  ContextForge prompt/resource registration, client prompt/resource import, or
  readback plumbing;
- stale client/session residue: repair reset sequencing and rerun from a fresh
  non-ephemeral container;
- guidance surface unavailable in Pi: repair `cf_contextforge_guidance_lookup`,
  prompt/resource import, or shim route selection;
- guidance surface unavailable in OpenCode: repair OpenCode MCP
  prompt/resource/tool guidance exposure or plugin wiring;
- assistant restarts onboarding: repair initialized-state guidance for that
  client;
- assistant answers from generic memory: repair normal-use guidance so ordinary
  capability questions route to project guidance before generic explanation;
- assistant leaks raw guidance objects: repair client hidden prompt, exact
  response rendering, or summarization boundary;
- assistant overclaims readiness or freshness: repair DTO wording and
  user-facing guidance language;
- deterministic verifier judges prose meaning: move that judgment to semantic
  evaluator criteria and keep deterministic checks structural-only;
- semantic evaluator fails visible behavior: remediate client guidance,
  guidance metadata, runner prompts, or capability routing, then rerun from
  virgin state and clean client home.
