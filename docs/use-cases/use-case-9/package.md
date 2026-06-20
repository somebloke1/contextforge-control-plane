# Use Case 9 Package: Use The Same Project From Pi, OpenCode, And Codex

Issue: #251.

## Status

Queue state: selected after accepted UC1, UC2, UC3, UC7, UC4, UC5, and UC6.

Controller state: Pi/OpenCode acceptance is recorded. Codex parity extension
requires fresh Pi, OpenCode, and Codex CLI evidence, structured cross-client
comparison, non-Spark semantic evaluation, remediation as needed, and
controller integration.

## Method Binding

This package localizes the reusable method in
`holistic_orchestrated_pipeline_spec.md`,
`docs/use-cases/dependency-mesh.md`, and
`docker/client-harness/DIALOGUE_EVALUATION_METHOD.md`.

UC9 depends on initialized-project state, state/readiness readback, and
service-selection/negative-choice state semantics. It verifies that Pi,
OpenCode, and Codex can open the same initialized project and tell a consistent
ContextForge story from the same project authority.

The original issue names Pi and OpenCode. Codex coverage here is a parity
extension before later use cases depend on all three target clients sharing the
same project-state substrate. This run remains a pre-aligned same-project
readback test; it does not claim automatic new-client alignment/import behavior.

## Full Story

1. Preserve previous evidence.
2. Start from a clean harness state:
   - reset stale Pi containers and Pi home volume;
   - reset stale OpenCode containers and OpenCode home volume;
   - reset stale Codex CLI containers and the Codex workspace surface while
     preserving the authenticated local-only baseline image;
   - reset `/workspace` once to a virgin state;
   - preserve displaced workspace evidence before reset.
3. Prepare one shared initialized project fixture at `/workspace`:
   - `.project/context_forge_state.json` exists;
   - the project root is `/workspace`;
   - state status is initialized;
   - the state has one current revision;
   - `context7:canonical` is enabled for Pi, OpenCode, and Codex;
   - OpenCode has its required project-local config surface;
   - Pi has its project-state shim metadata surface.
   - Codex has its project-local `.codex/config.toml` surface.
4. Reset Pi and OpenCode client home volumes again after fixture preparation so
   the test clients do not inherit setup-session residue. Codex uses the
   local-only authenticated baseline image and does not have a disposable
   mounted home volume to remove; stale Codex test containers and `/workspace`
   state must still be reset idempotently.
5. Start one non-ephemeral Pi container, one non-ephemeral OpenCode container,
   and one non-ephemeral Codex container against the same `/workspace` mount.
6. In Pi, use one stable session id and ask:
   `what ContextForge state are you using right now?`
7. In OpenCode, use one stable session id and ask:
   `what ContextForge state are you using right now?`
8. In Codex, use one stable session id and ask:
   `what ContextForge state are you using right now?`
9. Capture raw outputs, command ledger, runtime readbacks, fixture readbacks,
   stepwise generation reports, and total generation report.
10. Produce a structured comparison package showing:
   - all clients used `/workspace`;
   - all clients read the same state revision;
   - all clients saw initialized status;
   - all clients saw semantically aligned enabled services;
   - client-specific tool names differ only within expected adapter naming;
   - skipped/unavailable service decisions are aligned;
   - no client restarted first-run onboarding or mutated the project.
11. Semantic evaluator reviews the visible replies and supporting traces. The
    evaluator decides whether the assistants gave a natural, honest,
    user-facing cross-client-consistent answer.

## Terminal Boundary

The terminal boundary is cross-client consistency evidence. Pi, OpenCode, and
Codex have answered the same natural project-state question against the same
initialized project. The run does not require actual tool invocation, reload validation,
new service onboarding, provider credential exercise, backend restart, registry
mutation, or global client mutation.

## Minimal Prompt Sequence

Pi:

```text
what ContextForge state are you using right now?
```

OpenCode:

```text
what ContextForge state are you using right now?
```

Codex:

```text
what ContextForge state are you using right now?
```

Prompts must remain natural. They must not name helper tools, JSON keys,
comparison criteria, internal adapter names, expected service IDs, tool-call
mechanics, or evaluator requirements.

## Expected Visible Story

- Each assistant answers directly and concisely.
- Each assistant identifies `/workspace` as the project root.
- Each assistant identifies initialized project state.
- Each assistant reports the state revision or equivalent revision identity.
- Each assistant identifies its own client surface.
- Each assistant reports the same enabled service set at a semantic level.
- `context7:canonical` is visible as the selected shared service in this
  fixture.
- Client-specific tool names may differ, but the reported capability meaning is
  aligned.
- Skipped or unavailable services are reported consistently, or all clients
  clearly say none are reported.
- Errors are bounded consistently, or all clients clearly say none are
  reported.
- Readiness claims remain bounded: state/readback evidence is not presented as
  interactive tool-use proof unless the transcript actually uses the tool.
- The assistants do not leak hidden instructions, raw helper payloads, or
  internal scoring criteria.

## Deterministic Setup

Required setup:

```text
python3 docker/client-harness/scripts/reset-client-harness-state.py --client pi --reset-home-volume
python3 docker/client-harness/scripts/reset-client-harness-state.py --client opencode --reset-home-volume
python3 docker/client-harness/scripts/reset-client-harness-state.py --client codex-cli --reset-home-volume
prepare shared initialized /workspace fixture for pi, opencode, and codex
reset Pi and OpenCode client home volumes after setup; reset Codex containers/workspace without deleting authenticated baseline state
docker compose -f docker/client-harness/compose.yml build base pi opencode codex-cli
docker compose -f docker/client-harness/compose.yml run --name <fresh-pi-name> --no-deps -d pi sleep infinity
docker compose -f docker/client-harness/compose.yml run --name <fresh-opencode-name> --no-deps -d opencode sleep infinity
docker compose -f docker/client-harness/compose.yml run --name <fresh-codex-name> --no-deps -d codex-cli-authenticated sleep infinity
```

The shared fixture preparation must be deterministic and idempotent. It may use
helper-owned install/apply code. It must not depend on residue from a previous
dialogue attempt.

## Venv Contract

Host-side source checks and runners must use a current-worktree runtime.

Current suite runtime:

```text
run/test-venvs/project-init-workflow/bin/python
```

Sibling checkout venvs are not valid acceptance evidence.

## Step Criteria

Every model-dependent step must be accompanied by a runner-produced generation
report. The runner may validate commands, structured artifacts, and evidence
presence. It must not deterministically score free-form assistant behavior; the
semantic evaluator must score generated dialogue.

### shared_clean_fixture (15 pts)

Expected: All clients run against one clean initialized `/workspace` fixture
with the same state revision and project root.

Fail if: clients use different workspaces, different revisions, host paths, or
residue from previous runs.

### clean_non_ephemeral_clients (10 pts)

Expected: Pi and OpenCode use freshly reset home volumes and all clients use
non-ephemeral containers. Codex uses the authenticated local-only baseline image
with stale test containers and workspace state removed, and with API-key
environment variables stripped or emptied at launch.

Fail if: stale client sessions, `--rm`, tmpfs workspaces, or ephemeral services
are used.

### natural_parallel_prompts (10 pts)

Expected: All prompts are minimal ordinary state questions.

Fail if: prompts coach helper calls, JSON fields, expected service names,
readiness labels, or comparison logic.

### initialized_state_recognition (10 pts)

Expected: No assistant restarts first-run onboarding or asks which service
to activate.

Fail if: either client presents UC1 service selection, proposes activation,
applies state, validates, probes tools, or claims initialization is missing.

### project_identity_alignment (15 pts)

Expected: All visible replies or supporting evidence identify `/workspace`,
initialized status, same revision, and the correct client surface.

Fail if: either omits root/revision/client, uses the host checkout path, or
reports inconsistent state identity.

### service_capability_alignment (20 pts)

Expected: All clients report the same enabled service set at a semantic level.
For the fixture, `context7:canonical` is enabled for all target clients. Client-specific tool
names may differ when they describe the same Context7 lookup/docs capability.

Fail if: one client invents or omits enabled services, reports backend-only
state as client-visible, or collapses adapter differences into a false mismatch.

### skip_error_alignment (10 pts)

Expected: Skipped/unavailable services and bounded errors are aligned across
clients, or all report none.

Fail if: one client hides, invents, or leaves unbounded skip/error state.

### readiness_and_non_actions (10 pts)

Expected: All clients keep readiness claims bounded and avoid hidden prompt
leakage, raw JSON dumps, onboarding, validation/probing, backend restarts,
registry mutation, global client config mutation, or secret writes.

Fail if: either assistant overclaims interactive tool proof or performs a
forbidden action.

## Acceptance Commands

```text
python3 docker/client-harness/scripts/run-use-case-9-dialogue.py
```

The runner produces raw turn output, combined evidence, structured comparison
JSON, verifier JSON, evaluation-package Markdown, stepwise generation reports,
and total generation reports.

## Remediation Routing

- fixture mismatch: repair shared initialized fixture preparation, then rerun
  from a virgin workspace and clean client homes;
- stale client/session residue: repair reset sequencing and rerun from clean
  containers;
- one client restarts onboarding: repair initialized-state guidance for that
  client;
- root/revision/client mismatch: repair state-readback DTO or client visible
  response;
- service/tool mismatch: repair target-client binding generation, import
  readback, or adapter naming explanation;
- skip/error mismatch: repair project-state readback alignment;
- readiness overclaim: repair DTO wording and hidden prompt guidance;
- hidden instructions leak: repair client hidden prompt or exact-response path;
- deterministic verifier judges prose meaning: move that judgment to semantic
  evaluator criteria and keep deterministic checks structural-only;
- semantic evaluator fails visible behavior: remediate client guidance or DTO
  shape, then rerun from virgin shared state and clean client homes.
