# Git/GitHub Coordination Snapshot - 2026-06-20

Controller: `codex-thread:019ede5e-c2c8-72b0-8665-2effa6288d05`

## Branch State

PR #271 is the active ordinary review surface for the SuperLoop harness work:

```text
https://github.com/somebloke1/contextforge-control-plane/pull/271
```

Live PR head must be read from GitHub when acting. The last pre-snapshot
substantive harness readback after flagged-attention and service-parity
integration on 2026-06-21 was:

```text
base: dev-root
head branch: codex/issue-270-259-260-context7
head oid: 11cda693bfcfa575061b67c0a4ea3a7b26eb5ba1
state: open non-draft
merge state: CLEAN
title: Add ContextForge project-init SuperLoop harness
reviews: none
check runs: none
branch delta: 60 commits, 208 changed files
```

This snapshot was then updated by coordination-only documentation commits, so
the PR body and `gh pr view 271 --json headRefOid` are the authoritative live
head readback.

Earlier divergence between the local tested chain and the draft PR branch has
been reconciled into PR #271. Do not rely on the older
`codex/issue-270-259-260-superloop-state` preservation branch as the current
review head.

## Remaining Local Untracked Items

The following diagram-only artifacts remain untracked and were intentionally not
included in the SuperLoop preservation commit:

```text
.codex/skills/schematic-abstract-diagrams/
docs/use-cases/contextforge-use-case-service-projection-diagram.md
```

They should be reviewed separately before inclusion, deletion, or transfer to a
diagram-focused branch.

## Recommended Next GitHub Step

Do not merge or close linked issues from this snapshot alone. Use PR #271 as
the current ordinary review surface. The #293-#296 issue-level review wave has
been integrated, #286 projection vocabulary refinement is in `2b9e5e5`, #285
partial-alignment refinement is in `42e72a9`, the subsequent review-wave
remediation package addresses the #285/#286/#293/#295 follow-up findings, UC14
and UC15 were refreshed in `a332003` and `86ab19a`, flagged-attention triage was
refreshed through `92461a8`, and #284 service-parity investigation integration
is in `11cda69`.

Controller checks after the `11cda69` service-parity integration baseline:

```text
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_use_case1_e2e_gate tests.test_contextforge_docker_harness tests.test_contextforge_development_path_index -v
```

Result: 89 tests OK.

```text
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python -m py_compile docker/client-harness/scripts/run-use-case-14-readiness-report.py docker/client-harness/scripts/verify-use-case-14-readiness-evidence.py docker/client-harness/scripts/run-use-case-15-handoff.py docker/client-harness/scripts/verify-use-case-15-handoff-evidence.py tests/test_use_case1_e2e_gate.py tests/test_contextforge_docker_harness.py tests/test_contextforge_development_path_index.py
```

Result: OK.

`git diff --check` also passed before the `11cda69` commit. GitHub reports no
check runs, so verification remains controller-local and documented in this
branch and PR comments.
