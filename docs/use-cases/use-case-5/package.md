# Use Case 5 Package: Add Useful Project Services

Issue: #247.

## Scope

Use Case 5 is the umbrella user story for selecting useful ContextForge
services, reviewing a helper-generated plan, approving it, applying
project-local state/config, and reading back the applied result.

This umbrella depends on the decomposed prerequisite slices:

- UC5a/#270 service localization taxonomy;
- UC5b/#259 helper-offered service readiness matrix;
- UC5c-UC5k/#260-#268 per-service source lifecycle/apply proof;
- UC5l/#269 single, curated multi-service, and all-services source-level
  selection-shape proof.

The final #247 umbrella pass requires real target-client dialogue evidence for
Pi, OpenCode, and Codex ordinary sessions across all required selection shapes.

## Target Clients

- Pi.
- OpenCode.
- Codex.

## Required Selection Shapes

Single-service:

- `context7:canonical`
- Prompt sequence: `hello`, `context7`, `approve`

Curated multi-service:

- `context7:canonical`
- `mentality:static_repo_local`
- `ssh-tmux:session_scoped`
- Prompt sequence: `hello`, `context7, mentality, and ssh-tmux`, `approve`

All services:

- `context7:canonical`
- `exa-search:credential_scoped`
- `github:canonical`
- `mentality:static_repo_local`
- `openzeppelin-solidity-contracts:canonical`
- `playwright:session_scoped`
- `ssh-tmux:session_scoped`
- `web-search:credential_scoped`
- `serena:<project-hash>`
- Prompt sequence: `hello`, `all services`, `python`, `approve`

## Full Specified Story

From a virgin project workspace and clean target-client home/session state:

1. The user greets or asks to set up services.
2. The assistant presents the available ContextForge service list.
3. The user selects the required shape using ordinary natural language.
4. If the shape requires Serena language input, the assistant asks for it before
   approval.
5. The assistant presents a clear project-local plan covering exactly the
   selected services, with non-actions and reload/new-session boundary.
6. The user approves in plain language.
7. The helper applies only project-local state/config changes.
8. The assistant reports what changed and what remains pending.
9. The user can ask for readback and see the applied project-local service
   state.
10. The assistant does not claim post-refresh tool visibility or actual tool
    invocation in this use case.

## Deterministic Setup Contract

- Use a current-worktree venv.
- Use `docker/client-harness/scripts/reset-client-harness-state.py` with
  `--reset-home-volume`.
- Reset only the target client being tested.
- Start a fresh non-ephemeral client container.
- Preserve prior evidence before reset.
- Do not borrow sibling `.venv` runtimes.
- Do not rely on manually calculated residue cleanup.

## Evidence Contract

For each client and shape, the runner must capture:

- reset readback;
- container/runtime readback;
- raw turn outputs;
- visible dialogue summary;
- tool audit index;
- stepwise and total generation report;
- deterministic structural verifier JSON;
- evaluator package.

The deterministic verifier checks structure only. It must not judge generated
assistant prose.

## Scorecard

- clean_start: 10
- natural_prompts: 10
- service_menu: 10
- selection_shape: 15
- plan_review: 15
- approval_apply_order: 15
- post_apply_readback: 10
- reload_boundary: 10
- no_overclaim: 5

Pass requires 100/100 with no fatal failure for every required client/shape.

Fatal failures:

- coached prompts naming helper internals, payload keys, challenge mechanics, or
  evaluator criteria;
- missing service list;
- selected service silently omitted;
- approval/apply before user approval;
- missing project-local plan before approval;
- missing post-apply readback;
- missing reload/new-session boundary;
- forbidden global, secret, runtime, systemd, registry, or production
  ContextForge mutation;
- post-refresh target-client visibility or actual tool-use overclaim;
- deterministic semantic scoring of assistant prose.

## Runner

```sh
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python docker/client-harness/scripts/run-use-case-5-dialogue.py --client pi --shape single
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python docker/client-harness/scripts/run-use-case-5-dialogue.py --client opencode --shape single
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python docker/client-harness/scripts/run-use-case-5-dialogue.py --client codex --shape single
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python docker/client-harness/scripts/run-use-case-5-dialogue.py --client pi --shape curated
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python docker/client-harness/scripts/run-use-case-5-dialogue.py --client opencode --shape curated
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python docker/client-harness/scripts/run-use-case-5-dialogue.py --client codex --shape curated
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python docker/client-harness/scripts/run-use-case-5-dialogue.py --client pi --shape all
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python docker/client-harness/scripts/run-use-case-5-dialogue.py --client opencode --shape all
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python docker/client-harness/scripts/run-use-case-5-dialogue.py --client codex --shape all
```

Each resulting package requires non-Spark evaluator scoring and controller
integration before #247 can be accepted.

## Non-Goals

Follow-on issues remain responsible for:

- #252 refreshed tool visibility after project-state changes;
- #250 actual tool use and same-session follow-up.

Use Case 5 may install project-local state/config needed for those later cases,
but it must not pretend those later surfaces have passed.
