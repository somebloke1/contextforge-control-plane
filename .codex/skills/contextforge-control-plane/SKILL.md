---
name: contextforge-control-plane
description: Work on the ContextForge assistant control-plane implementation in this repository. Use for RFC-aligned project-state helpers, service binding contracts, consent receipts, authorization/trust gates, redaction, remote exposure, tool policy, client adapter conformance, Pi global shim work, deterministic scenarios, inference harnesses, evidence ledgers, QA gates, and release readiness.
---

# ContextForge Control Plane

Keep implementation tied to the RFC and fixture-backed evidence. This skill is
for control-plane code and tests, not live service registration.

## Core Rules

- ContextForge owns canonical service/resource identity.
- `.project/context_forge_state.json` owns project initialization state.
- Client configs are discovery and consumption surfaces only.
- User-global trust, token/secret entry, remote exposure, and catalog promotion
  require separate explicit approval.
- Project-init helpers may plan/apply project-local config/state only through
  consent receipts.
- Contract artifacts are not optional reporting layers: service binding
  contracts, consent receipts, verification traces, conformance packs,
  requirement scenarios, evaluator verdicts, and evidence ledgers are part of
  the design.

## Work Pattern

1. Read the relevant RFC/runbook/checklist sections before editing.
2. Locate the matching script and test pair under `scripts/control_plane_*.py`
   and `tests/test_control_plane_*.py`.
3. Update fixtures under `tests/fixtures/` when behavior is fixture-driven.
4. Keep helpers pure where the current design expects deterministic planning.
5. Preserve redaction and no-mutation attestations in evidence paths.
6. Run focused tests first, then the broader control-plane suite if the change
   affects shared contracts.

## Useful Commands

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_control_plane_project_state -v
```

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -p 'test_control_plane_*.py'
```

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m py_compile scripts/control_plane_inference_harness.py tests/test_control_plane_inference_harness.py
```

Read [evidence-and-tests.md](references/evidence-and-tests.md) for the current
MVS artifacts, Wave 12/13 gates, and Pi shim files.
