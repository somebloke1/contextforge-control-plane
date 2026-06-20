# Use Case 13 Controller Acceptance: Controlled Development Validation Containers

Issue: #255.

Status: accepted by controller on 2026-06-20 after runtime evidence package
generation, structural verifier pass, focused source checks, and Codex parity
extension.

## Accepted Scope

UC13 is accepted for the controlled development validation surface. The
accepted terminal state is a repeatable package showing dev ContextForge Docker
separation, Pi/OpenCode/Codex client Docker separation, current-worktree
test-venv usage, idempotent client reset, runtime smoke evidence, token
revocation or bounded token handling, and honest claim boundaries.

This is not an acceptance claim for UC14 readiness reporting, UC15 handoff, all
ordinary use cases, live/legacy ContextForge mutation, or OpenCode/Codex MCP
safe-call proof beyond the list-only boundary recorded below.

## Evidence

- Package: `docs/use-cases/use-case-13/package.md`
- Runner:
  `docker/client-harness/scripts/run-use-case-13-controlled-dev-validation.py`
- Structural verifier:
  `docker/client-harness/scripts/verify-use-case-13-controlled-dev-evidence.py`
- Runtime metadata:
  `docker/client-harness/evidence/use-case-13/use-case-13-metadata-20260620T092521Z.json`
- Runtime verifier:
  `docker/client-harness/evidence/use-case-13/use-case-13-verifier-20260620T092521Z.json`
- Runtime package:
  `docker/client-harness/evidence/use-case-13/use-case-13-evaluation-package-20260620T092521Z.md`
- Pi smoke evidence:
  `docker/client-harness/evidence/pi-contextforge-dev-smoke.txt`
- OpenCode smoke evidence:
  `docker/client-harness/evidence/opencode-contextforge-dev-smoke.txt`

## Codex Parity Evidence

Accepted Codex parity extension evidence:

- Runtime metadata:
  `docker/client-harness/evidence/use-case-13/use-case-13-metadata-20260620T195710Z.json`
- Runtime verifier:
  `docker/client-harness/evidence/use-case-13/use-case-13-verifier-20260620T195710Z.json`
- Runtime package:
  `docker/client-harness/evidence/use-case-13/use-case-13-evaluation-package-20260620T195710Z.md`
- Codex smoke evidence:
  `docker/client-harness/evidence/codex-contextforge-dev-smoke.txt`

The Codex smoke is accepted as Docker OAuth/config/list-readback evidence only:
it uses the authenticated Codex image, verifies `gpt-5.4-mini`, strips API-key
auth, lists the project-local `contextforge-mentality-dev` MCP server, and does
not claim a safe MCP tool call or dialogue success.

Non-Spark evaluator: Einstein
`019ee69c-aeac-77b0-81a5-b6f5c4d93e6f`.

Evaluator verdict: PASS, 92/100, no primary failure class. Recommendation:
controller acceptance of UC13 as a controlled-development validation surface for
Pi, OpenCode, and Codex only. The evaluator explicitly did not recommend
treating this as semantic dialogue success or OpenCode/Codex safe-call
readiness.

## Runtime Result

The runtime runner completed successfully with `runtime_skipped=false`.

Accepted runtime claims:

- ContextForge dev Docker is addressed through `http://127.0.0.1:4445` from
  the host and `http://host.docker.internal:4445` from client containers.
- Host Python work uses
  `run/test-venvs/project-init-workflow/bin/python`.
- Pi and OpenCode client harness state are reset before each client smoke.
- Pi produces dev-gateway readback evidence through the container-local shim.
- OpenCode adds/lists the dev MCP endpoint through container-local config and
  records `list_only_without_safe_call`.
- Scoped probe tokens are revoked and raw token values are not printed.
- Host-global Pi, host-global OpenCode, live/legacy ContextForge, and direct
  ContextForge database writes remain out of scope and unmutated.

## Verification Commands

```bash
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python \
  docker/client-harness/scripts/run-use-case-13-controlled-dev-validation.py \
  --timeout 300
```

Result: package assembled successfully.

```bash
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python \
  docker/client-harness/scripts/verify-use-case-13-controlled-dev-evidence.py \
  --metadata \
  docker/client-harness/evidence/use-case-13/use-case-13-metadata-20260620T092521Z.json
```

Result: `ok=true`.

```bash
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python \
  docker/client-harness/scripts/run-use-case-13-controlled-dev-validation.py \
  --timeout 300
```

Codex parity result: package assembled successfully with Pi, OpenCode, and
Codex client smokes required and passing.

```bash
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python \
  docker/client-harness/scripts/verify-use-case-13-controlled-dev-evidence.py \
  --metadata \
  docker/client-harness/evidence/use-case-13/use-case-13-metadata-20260620T195710Z.json
```

Codex parity result: `ok=true`.

```bash
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python \
  -m unittest tests.test_contextforge_docker_harness -v
```

Result: 34 tests passed.

```bash
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python \
  -m unittest tests.test_contextforge_docker_harness -v
```

Codex parity result: 36 tests passed.

```bash
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python \
  -m py_compile \
  docker/client-harness/scripts/run-use-case-13-controlled-dev-validation.py \
  docker/client-harness/scripts/verify-use-case-13-controlled-dev-evidence.py \
  tests/test_contextforge_docker_harness.py
```

Codex parity result: pass.

## Controller Judgment

Accepted.

The decisive remediation in this loop was:

- smoke scripts now prefer the dedicated current-worktree test venv before
  falling back to `.venv` or `python3`;
- the UC13 runner invokes dev registration/probe scripts through that venv
  explicitly;
- the runner waits for dev-gateway health before registration and retries the
  virtual probe across bounded timing races;
- the OpenCode dev smoke keeps its temporary `HOME`, config target, plugin
  target, rules target, runtime dir, and project-init run root internally
  consistent so the entrypoint safety checks pass.

Residual risk: OpenCode and Codex safe-call invocation remain deliberately
unclaimed until reviewed safe-call commands or reviewed dialogue packages are
supplied. UC13 accepts the controlled dev validation surface, not target-client
safe-call proof or semantic dialogue readiness.

## Next Queue Decision

Per operator instruction, do not proceed directly to UC14 or UC15. The next
workstream is Codex client bring-up from the same foundation to parity with the
current Pi/OpenCode harness behavior and evidence level.
