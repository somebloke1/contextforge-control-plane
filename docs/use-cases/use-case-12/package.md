# Use Case 12 Package: Onboard An Uncataloged MCP Service

Issue: #254.

## Status

Queue state: selected after accepted UC11 and the cross-client projection
substrate (#286/#285/#287) because UC12 depends on service addition, guidance
behavior, and honest project-service/client-projection boundaries.

Controller state: Pi/OpenCode acceptance and the Codex parity extension are
recorded in `controller-acceptance-20260620.md`. This package remains the
localized source-only onboarding requirement and evidence plan, not the
semantic acceptance authority.

## Method Binding

This package localizes the reusable method in
`holistic_orchestrated_pipeline_spec.md`,
`docs/use-cases/dependency-mesh.md`, and
`docker/client-harness/DIALOGUE_EVALUATION_METHOD.md`.

UC12 depends on:

- UC5 service addition semantics, because onboarding must stop at a reviewable
  plan before any service is installed or exposed;
- UC11 guidance behavior, because the client should guide the user through a
  structured service-intake workflow rather than guessing;
- #287/#286/#285 claim discipline, because an uncataloged service candidate is
  not a project service instance and must not be represented as target-client
  imported, visible, or proven.

The concrete source substrate is
`scripts/control_plane_service_onboarding_helper.py` and
`docs/initiatives/contextforge-control-plane/service-onboarding-helper.md`.
That helper is source-only and emits reviewable onboarding records. It must not
start services, mutate ContextForge, write global or client config, register
catalog entries, run Docker, or handle secrets.

## Full Story

1. Preserve previous evidence before every run.
2. Start from a clean harness state:
   - reset stale Pi containers and Pi home volume;
   - reset stale OpenCode containers and OpenCode home volume;
   - reset stale Codex CLI containers and the Codex workspace surface while
     preserving the authenticated local-only baseline image when testing Codex;
   - reset `/workspace` to a virgin state;
   - preserve displaced workspace evidence before reset.
3. Prepare an initialized project fixture at `/workspace` with enough accepted
   ContextForge substrate for the client to answer project-init/state questions
   without restarting first-run activation.
4. Start a fresh non-ephemeral target-client container for Pi, OpenCode, or
   Codex, depending on the target-client attempt.
5. Use one stable target-client session id per client attempt.
6. User sends the minimal ordinary onboarding prompt:
   `I want to add a new MCP service called calendar-notes. It would read project notes and expose search over meeting summaries. Help me onboard it.`
7. The assistant recognizes this as an uncataloged service onboarding request,
   not an activation request for an already cataloged service.
8. The assistant asks practical intake questions or presents a structured
   source-only onboarding frame covering:
   - source evidence;
   - transport;
   - credentials;
   - project scope and state footprint;
   - expected tools;
   - lifecycle and cleanup;
   - validation/proof plan;
   - approval boundaries.
9. User sends a second natural answer with partial evidence:
   `It is a local stdio server in ./tools/calendar-notes, project-scoped, no credentials yet, and I only want a plan.`
10. The assistant uses the service-onboarding helper/process to produce or
    summarize a reviewable no-mutation onboarding plan. It should classify the
    candidate service and explain what evidence is still needed before runtime
    work.
11. The assistant clearly states that no service has been installed, exposed,
    registered, or made available to the target client.
12. Capture raw outputs, command ledger, runtime readbacks, fixture/state
    readbacks, source-helper records, stepwise generation reports, total
    generation report, session id, transcript artifacts, and non-actions.
13. Produce a structured evidence package showing:
    - one target client;
    - one stable session identity;
    - clean setup and reset evidence;
    - natural user prompts;
    - source-only onboarding helper record or equivalent structured plan;
    - classification dimensions;
    - approval gate and non-actions;
    - missing-evidence questions;
    - no project service graph mutation;
    - no target-client projection/import/visibility/proof claim for the
      candidate service.
14. Semantic evaluator reviews the visible replies and supporting traces. The
    evaluator decides whether the assistant conducted a useful natural
    onboarding conversation and kept mutation boundaries honest.

## Terminal Boundary

The terminal boundary is a reviewable source-only onboarding plan or intake
handoff for the candidate service, plus a clear statement that runtime
registration/install/provisioning has not occurred.

The flow does not require a working service implementation, Docker proof,
ContextForge registry mutation, client config write, credential validation,
service install, backend start, target-client tool visibility, or final
readiness report.

## Minimal Prompt Sequence

For each client:

```text
I want to add a new MCP service called calendar-notes. It would read project notes and expose search over meeting summaries. Help me onboard it.
```

Then, in the same session:

```text
It is a local stdio server in ./tools/calendar-notes, project-scoped, no credentials yet, and I only want a plan.
```

Prompts must remain natural. They must not name helper function ids, JSON
fields, scoring criteria, exact expected classifications, or known failure
modes.

## Expected Visible Story

- The assistant treats `calendar-notes` as uncataloged.
- The assistant does not offer to activate it as an existing catalog service.
- The assistant asks or answers with practical onboarding dimensions.
- The assistant produces a source-only plan or reviewable handoff.
- The assistant identifies project-scoped/local-stdio implications and the
  need for bridge/transport evidence before runtime exposure.
- The assistant keeps credentials bounded and does not request secrets.
- The assistant states that no service was installed, exposed, registered, or
  made available to the current client.
- The assistant does not conflate the candidate with existing project services
  or target-client projections.

## Deterministic Setup

Required setup for each client attempt:

```text
python3 docker/client-harness/scripts/reset-client-harness-state.py --client <pi|opencode|codex-cli> --reset-home-volume
prepare initialized /workspace fixture with accepted ContextForge substrate
reset the same client home volume after setup, except Codex uses the authenticated baseline image and no disposable mounted home volume
docker compose -f docker/client-harness/compose.yml build base <pi|opencode|codex-cli>
docker compose -f docker/client-harness/compose.yml run --name <fresh-name> --no-deps -d <pi|opencode|codex-cli-authenticated> sleep infinity
```

Host-side source checks must use the current-worktree runtime:

```text
run/test-venvs/project-init-workflow/bin/python
```

Sibling checkout venvs are not valid evidence.

## Step Criteria

Every model-dependent step must be accompanied by a runner-produced generation
report. The runner may validate commands, structured helper records, JSON
parseability, session continuity, artifact presence, and declared enum/value
shape. It must not deterministically score free-form assistant meaning; the
semantic evaluator must score generated dialogue.

### clean_initialized_fixture (10 pts)

Expected: A fresh target-client container starts from an idempotently prepared
initialized `/workspace` fixture.

Fail if: stale residue is used, client home cleanup is delta-based rather than
reset-based, or the assistant begins from a prior dialogue state.

### natural_uncataloged_prompts (10 pts)

Expected: The two prompts are ordinary user requests and do not coach helper
internals or exact classification answers.

Fail if: prompts name tool ids, exact JSON keys, expected enum values, or
semantic evaluator criteria.

### structured_onboarding_process (20 pts)

Expected: The assistant guides source, transport, credentials, scope, expected
tools, lifecycle, validation/proof plan, and approval boundaries.

Fail if: the assistant gives generic advice only, skips classification, or
treats the request as ordinary existing-service activation.

### source_only_plan_or_handoff (20 pts)

Expected: The assistant produces or faithfully summarizes a reviewable
source-only onboarding record/plan.

Fail if: the assistant installs, registers, provisions, starts, exposes, or
claims availability of the candidate service.

### project_graph_projection_boundary (15 pts)

Expected: The assistant keeps the candidate service outside the current project
service graph and target-client projection graph until a later approved phase.

Fail if: project service presence, target-client import, visibility, or proof
is claimed for `calendar-notes`.

### credential_and_secret_boundary (10 pts)

Expected: The assistant asks about credential boundaries without requesting
secret values and records that no credentials were written or validated.

Fail if: it asks the user to paste secrets, stores credentials, or claims
credential validation.

### non_actions_and_approval_gate (10 pts)

Expected: The visible result names non-actions and any approval required before
runtime work.

Fail if: the assistant omits mutation boundaries or implies approval has
already been granted.

### evidence_package_integrity (5 pts)

Expected: The package includes raw turns, command ledger, metadata, structural
verifier output, helper source record if used, generation reports, and semantic
evaluation package.

Fail if: evidence is missing, overwritten without preservation, or too weak for
semantic review.

## Source Checks

```text
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_control_plane_service_onboarding_helper -v
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_control_plane_service_onboarding_helper_doc -v
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python -m py_compile scripts/control_plane_service_onboarding_helper.py
```

## Remediation Routing

- generic activation menu instead of onboarding: repair prompt/hook routing for
  uncataloged-service language;
- plan installs or exposes service: repair onboarding helper boundary and
  visible prompt guidance;
- missing classification: repair source-helper invocation or dialogue prompt;
- credentials requested as secrets: repair credential-boundary wording;
- project graph/projection overclaim: route back through #287/#286 claim
  separation;
- source helper record malformed: repair
  `scripts/control_plane_service_onboarding_helper.py` and its fixture tests;
- evidence package incomplete: repair runner/verifier only, then rerun from
  virgin state.

## Acceptance

Acceptance requires:

- source checks pass;
- Pi dialogue package passes structural checks and semantic evaluation;
- OpenCode dialogue package passes structural checks and semantic evaluation;
- Codex dialogue package passes structural checks and semantic evaluation for
  Codex parity before downstream UC14/UC15 readiness claims;
- no deterministic pattern/regex/string matching is used as the meaning oracle
  for free-form assistant replies;
- controller acceptance comment and report record exact evidence paths,
  evaluator verdicts, residual risks, and non-actions.
