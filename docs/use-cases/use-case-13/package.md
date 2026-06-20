# Use Case 13 Package: Controlled Development Validation Containers

Issue: #255.

## Status

Queue state: selected after accepted UC12. UC13 formalizes the development
evidence surface already used throughout the SuperLoop: isolated ContextForge
dev Docker, isolated Pi/OpenCode/Codex client containers, current-worktree test
venv, idempotent reset, evidence capture, and explicit claim boundaries.

Controller state: package materialized. Acceptance requires source checks,
runtime evidence package generation, and controller review. If model-dependent
dialogue evidence is cited as a selected-use-case proof, it must still be
reviewed by a non-Spark semantic evaluator under the ordinary dialogue method.

## Method Binding

This package localizes the reusable method in
`holistic_orchestrated_pipeline_spec.md`,
`docs/use-cases/dependency-mesh.md`, and
`docker/client-harness/DIALOGUE_EVALUATION_METHOD.md`.

UC13 is a development-surface use case rather than an end-user service use
case. Its product value is a repeatable way to run or reuse controlled
validation surfaces without disturbing legacy/live ContextForge, host-global
Pi, host-global OpenCode, host-global Codex, or production-ish local workflows.

## Full Story

1. Use the current checkout as the authority.
2. Use only the current-worktree test venv:
   `run/test-venvs/project-init-workflow/bin/python`.
3. Start or reuse the isolated ContextForge development Docker gateway on
   `http://127.0.0.1:4445`.
4. Keep the host legacy/live ContextForge surface out of scope, including the
   host `127.0.0.1:4444` gateway.
5. Start or reuse development MCP transceiver sidecars on reserved dev ports,
   such as mentality on `127.0.0.1:9201` and Context7 on `127.0.0.1:9203`.
6. Register dev sidecars into the dev Docker gateway through ContextForge APIs,
   not database writes.
7. Probe direct sidecar and dev-gateway virtual MCP surfaces.
8. Reset stale Pi client containers, Pi home volume, and the shared harness
   workspace before the Pi client smoke.
9. Run Pi inside the client harness against `host.docker.internal:4445` using
   the container-local shim/runtime and local Qwen model configuration.
10. Reset stale OpenCode client containers, OpenCode home volume, and the
    shared harness workspace before the OpenCode client smoke.
11. Run OpenCode inside the client harness against
    `host.docker.internal:4445` using container-local config/plugin/runtime and
    local Qwen model configuration.
12. Reset stale Codex client containers, Codex harness home volume, and the
    shared harness workspace before the Codex client smoke.
13. Run Codex inside the authenticated Docker image against
    `host.docker.internal:4445` using OAuth/ChatGPT subscription auth, default
    model `gpt-5.4-mini`, project-local Codex MCP config, no host API-key
    passthrough, and no host-global Codex mutation.
14. Capture command statuses, reset JSON, dev-harness probe output, Pi smoke
    evidence, OpenCode smoke evidence, Codex smoke evidence, token evidence, and
    non-actions.
15. Assemble a single evidence package that states the exact claim boundary.
16. If selected ordinary use-case dialogue evidence is cited, include the
    existing generation reports and semantic evaluator results rather than
    replacing them with deterministic text checks.

## Terminal Boundary

The terminal boundary is a controlled-development validation package showing:

- dev Docker gateway separation;
- client Docker separation for Pi, OpenCode, and Codex;
- current-worktree venv use;
- reset discipline before each client surface;
- dev-gateway registration/probe status;
- Pi, OpenCode, and Codex client-container evidence artifacts;
- token revocation or bounded token handling evidence;
- explicit non-actions and residual risks.

The terminal boundary is not a claim that every ordinary use case has passed,
that OpenCode or Codex has performed an MCP safe call when list-only evidence
exists, or that live/legacy ContextForge has been changed.

## Minimal Commands

```bash
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python \
  docker/client-harness/scripts/run-use-case-13-controlled-dev-validation.py
```

For a source-only dry run:

```bash
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python \
  docker/client-harness/scripts/run-use-case-13-controlled-dev-validation.py \
  --skip-runtime
```

## Expected Visible Story

The package should explain that development validation ran in controlled
containers and did not touch the legacy/live ContextForge surface or host-global
client state. It should present the exact evidence files and the scope of each
client result. It should avoid low-level secret disclosure and should name any
missing safe-call proof plainly.

## Deterministic Boundary

UC13 deterministic scripts may verify command status, JSON parseability,
artifact existence, selected environment paths, declared URLs, token-redaction
boundaries, and structured claim fields.

They must not use string matching, regexes, keyword searches, or text parsing
as a semantic oracle for generated assistant prose. If a selected use-case
dialogue is cited, its free-form meaning remains evaluator-owned.

## Step Criteria

### dev_surface_isolation (20 pts)

Expected: the package uses ContextForge dev Docker on port 4445 and avoids
legacy/live registry mutation.

Fail if: commands target live/legacy ContextForge or mutate host-global client
state.

### current_worktree_venv (10 pts)

Expected: host Python commands use
`run/test-venvs/project-init-workflow/bin/python`.

Fail if: a sibling checkout venv or stale host `.venv` is used as evidence.

### idempotent_client_reset (15 pts)

Expected: each target client starts after stale target containers are removed,
the matching home volume is reset, and the harness workspace is virgin.

Fail if: cleanup relies on manually calculated state deltas.

### dev_registration_and_probe (15 pts)

Expected: dev sidecars are registered and probed through dev ContextForge APIs
and virtual MCP endpoints.

Fail if: sidecar startup alone is treated as registration or direct database
writes are used.

### pi_client_surface (15 pts)

Expected: Pi client Docker produces dev-gateway evidence through the
container-local shim/runtime.

Fail if: host-global Pi state is installed, reloaded, or used as proof.

### opencode_client_surface (15 pts)

Expected: OpenCode client Docker produces dev-gateway evidence through
container-local config/plugin/runtime.

Fail if: host-global OpenCode state is mutated or list-only evidence is
overclaimed as a safe MCP tool call.

### codex_client_surface (15 pts)

Expected: Codex authenticated Docker produces dev-gateway config/list readback
evidence through project-local config, OAuth/ChatGPT subscription auth,
`gpt-5.4-mini`, and stripped API-key environment.

Fail if: host-global Codex state is mutated, API-key auth is used, a model other
than `gpt-5.4-mini` is configured, or list-only evidence is overclaimed as a
safe MCP tool call or dialogue success.

### evidence_package_integrity (10 pts)

Expected: the package includes command ledger, reset JSON, evidence paths,
verifier output, claim boundaries, and non-actions.

Fail if: evidence is missing, overwritten without preservation, or ambiguous
about its claim scope.

## Source Checks

```bash
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python \
  -m unittest tests.test_contextforge_docker_harness -v

PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python \
  -m py_compile \
  docker/client-harness/scripts/run-use-case-13-controlled-dev-validation.py \
  docker/client-harness/scripts/verify-use-case-13-controlled-dev-evidence.py
```

## Remediation Routing

- wrong Python surface: repair smoke/runner defaults to prefer
  `run/test-venvs/project-init-workflow/bin/python`;
- live/legacy surface targeted: repair compose/env defaults and package
  instructions before rerunning;
- stale client state: repair reset script or runner sequencing;
- OpenCode or Codex list-only result overclaimed: repair package/evidence
  wording and require a reviewed safe-call command or reviewed dialogue package
  before making safe-call proof claims;
- missing evidence paths: repair runner package assembly;
- semantic dialogue claim without evaluator review: route back through the
  selected use-case dialogue method and non-Spark evaluator loop.
