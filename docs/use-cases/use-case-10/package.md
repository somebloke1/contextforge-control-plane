# Use Case 10 Package: Refresh Tools After Project-State Changes

Issue: #252.

## Status

Queue state: selected after accepted UC9 cross-client consistency.

Controller state: package materialized; acceptance requires fresh Pi and
OpenCode CLI evidence already exists. Codex parity extension requires fresh Pi,
OpenCode, and Codex CLI evidence, structured pre/post state comparison,
non-Spark semantic evaluation, remediation as needed, and controller
integration.

## Method Binding

This package localizes the reusable method in
`holistic_orchestrated_pipeline_spec.md`,
`docs/use-cases/dependency-mesh.md`, and
`docker/client-harness/DIALOGUE_EVALUATION_METHOD.md`.

UC10 depends on UC9 because refresh behavior is meaningful only after target
clients have proven they can read the same project authority. It also depends
on UC5/UC6 state-change semantics because project-state revision and service
binding changes must be treated as authoritative.

## Full Story

1. Preserve previous evidence.
2. Start from a clean harness state:
   - reset stale Pi containers and Pi home volume;
   - reset stale OpenCode containers and OpenCode home volume;
   - reset stale Codex CLI containers and the Codex workspace surface while
     preserving the authenticated local-only baseline image;
   - reset `/workspace` to a virgin state;
   - preserve displaced workspace evidence before reset.
3. Prepare one shared initialized project fixture at `/workspace`:
   - state revision is known;
   - `context7:canonical` is enabled for Pi, OpenCode, and Codex;
   - target-client surfaces exist for all target clients.
4. Reset Pi and OpenCode client home volumes after setup so test clients do not
   inherit setup-session residue. Codex uses the local-only authenticated
   baseline image and does not have a disposable mounted home volume to remove;
   stale Codex test containers and `/workspace` state must still be reset
   idempotently.
5. Start one non-ephemeral Pi container, one non-ephemeral OpenCode container,
   and one non-ephemeral Codex container against the same `/workspace` mount.
6. In each client, ask a natural baseline question:
   `what ContextForge state are you using right now?`
7. Apply a project-local state change through helper-owned mechanisms:
   - add `mentality:static_repo_local` for Pi, OpenCode, and Codex, or another
     credential-free already-ready service if mentality is unavailable;
   - increment project-state revision;
   - do not mutate global client config, live registry, secrets, or unrelated
     services;
   - record the exact before/after revision and enabled-service set.
8. In each existing client session, ask a natural refresh question:
   `refresh ContextForge state`
9. Pi expected refresh shape:
   - recognizes current project state changed;
   - reads the new revision;
   - reflects the updated enabled-service set;
   - uses its approved refresh mechanism rather than restarting unrelated
     services.
10. OpenCode expected refresh shape:
    - recognizes current project state changed;
    - reads the new revision;
    - reflects the updated project capability set;
    - remains honest that OpenCode discovers project-local MCP servers at
      session start, so newly configured MCP tool registration may require a
      new OpenCode session;
    - does not present stale pre-change tools as the complete current project
      state.
11. Codex expected refresh shape:
    - recognizes current project state changed;
    - reads the new revision;
    - reflects the updated project capability set;
    - remains honest about the Codex session/new-session boundary for newly
      configured MCP tool registration;
    - does not present stale pre-change tools as the complete current project
      state.
12. Capture raw outputs, command ledger, runtime readbacks, fixture/state
    readbacks, stepwise generation reports, and total generation report.
13. Produce a structured comparison package showing:
    - before revision;
    - after revision;
    - before enabled services;
    - after enabled services;
    - per-client baseline response artifacts;
    - per-client refresh response artifacts;
    - per-client refresh boundary: hot route refresh, readback refresh, or
      new-session-required boundary.
14. Semantic evaluator reviews the visible replies and supporting traces. The
    evaluator decides whether the assistants gave a natural, honest,
    user-facing refresh response without stale-tool overclaim.

## Terminal Boundary

The terminal boundary is current-state refresh/readback after a project-local
state change. The flow does not require actual tool invocation, same-session
tool follow-up, provider credential exercise, backend restart, live
ContextForge registry mutation, global client mutation, or user-managed global
reload/install.

## Minimal Prompt Sequence

For each client:

```text
what ContextForge state are you using right now?
```

After the runner applies the project-local state change:

```text
refresh ContextForge state
```

Prompts must remain natural. They must not name helper tools, JSON keys,
comparison criteria, exact state revisions, service IDs, tool-call mechanics,
or evaluator requirements.

## Expected Visible Story

- Baseline replies identify `/workspace`, initialized state, current revision,
  target client, and baseline enabled services.
- After the state change, refresh replies identify the newer revision or
  otherwise clearly indicate changed current project state.
- Refresh replies report the updated service/capability set or configured
  imported-tool policy at a semantic level from the refreshed project state.
- Stale pre-change tools are not presented as the full current state.
- If a client cannot hot-register newly configured MCP tools in the current
  session, it says so plainly and names the required safe boundary.
- No client restarts first-run onboarding.
- No client performs validation/probing, backend restart, registry mutation,
  global client mutation, or secret write.
- No client leaks hidden instructions, raw helper payloads, or internal scoring
  criteria.

## Deterministic Setup

Required setup:

```text
python3 docker/client-harness/scripts/reset-client-harness-state.py --client pi --reset-home-volume
python3 docker/client-harness/scripts/reset-client-harness-state.py --client opencode --reset-home-volume
python3 docker/client-harness/scripts/reset-client-harness-state.py --client codex-cli --reset-home-volume
prepare shared initialized /workspace fixture with context7 for pi, opencode, and codex
reset Pi and OpenCode client home volumes after setup; reset Codex containers/workspace without deleting authenticated baseline state
docker compose -f docker/client-harness/compose.yml build base pi opencode codex-cli
docker compose -f docker/client-harness/compose.yml run --name <fresh-pi-name> --no-deps -d pi sleep infinity
docker compose -f docker/client-harness/compose.yml run --name <fresh-opencode-name> --no-deps -d opencode sleep infinity
docker compose -f docker/client-harness/compose.yml run --name <fresh-codex-name> --no-deps -d codex-cli-authenticated sleep infinity
```

The runner owns the project-state change between baseline and refresh prompts.
That state change must use helper-owned project-local activation/apply paths and
must be idempotent from a virgin workspace.

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

### clean_baseline_fixture (10 pts)

Expected: All target clients start against one clean initialized `/workspace` fixture
with the same baseline revision and baseline enabled service set.

Fail if: clients use different workspaces, stale state, host paths, or residue
from previous runs.

### clean_non_ephemeral_clients (10 pts)

Expected: Pi and OpenCode use freshly reset home volumes and all clients use
non-ephemeral containers. Codex uses the authenticated local-only baseline image
with stale test containers and workspace state removed, and with API-key
environment variables stripped or emptied at launch.

Fail if: stale client sessions, `--rm`, tmpfs workspaces, or ephemeral services
are used.

### natural_baseline_and_refresh_prompts (10 pts)

Expected: Baseline and refresh prompts are ordinary user requests without
helper/tool coaching.

Fail if: prompts name helper calls, JSON fields, exact service IDs, revision
numbers, tool-order criteria, or evaluator logic.

### structured_state_change (15 pts)

Expected: The runner records before and after project-state revision/hash and
enabled-service set, and the after state contains an added service.

Fail if: revision does not change, the service set does not change, or the
state change bypasses helper-owned project-local mechanisms.

### client_detects_refresh (15 pts)

Expected: Each client's refresh reply uses current project-state authority and
does not answer only from stale baseline memory.

Fail if: either refresh reply repeats only the baseline service set or misses
the newer revision/state change.

### updated_capabilities_visible_or_bounded (20 pts)

Expected: Each client reports updated capabilities honestly. Pi may report
hot-refreshed routes if present. OpenCode may report project-state capability
updates while clearly stating any new-session boundary for actual MCP tool
registration.

Fail if: either client claims stale tools are complete, claims hot reload when
the client cannot support it, or hides a required new-session boundary.

### stale_tools_suppressed (10 pts)

Expected: Stale pre-change tools are not presented as the full current
capability set after refresh.

Fail if: either client presents only baseline tools as current after the state
change.

### non_actions_and_hidden_boundary (10 pts)

Expected: No hidden prompt leakage, raw helper payload, first-run onboarding,
validation/probing, backend restart, live registry mutation, global client
mutation, unrelated service restart, or secret write.

Fail if: any forbidden action or leakage appears.

## Acceptance Commands

```text
python3 docker/client-harness/scripts/run-use-case-10-dialogue.py
```

The runner produces raw turn output, combined evidence, structured before/after
comparison JSON, verifier JSON, evaluation-package Markdown, stepwise
generation reports, and total generation reports.

## Remediation Routing

- fixture mismatch: repair shared initialized fixture preparation, then rerun
  from a virgin workspace and clean client homes;
- state change missing: repair helper-owned project-local apply path or
  selected added-service fixture;
- stale client/session residue: repair reset sequencing and rerun from clean
  containers;
- one client restarts onboarding: repair initialized-state guidance for that
  client;
- refresh reply misses new revision/service: repair readback/availability DTO
  or prompt-routing guidance;
- client overclaims hot reload: repair wording to distinguish project-state
  refresh from actual MCP tool registration;
- stale tools presented as current: repair availability/readback policy to
  include revision and stale-boundary information;
- hidden instructions leak: repair client hidden prompt or exact-response path;
- deterministic verifier judges prose meaning: move that judgment to semantic
  evaluator criteria and keep deterministic checks structural-only;
- semantic evaluator fails visible behavior: remediate client guidance or DTO
  shape, then rerun from virgin shared state and clean client homes.
