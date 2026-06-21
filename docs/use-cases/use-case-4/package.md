# Use Case 4 Package: Read Project Governance Through ContextForge

## Status

Queue state: controller-accepted after accepted Use Case 3.

Controller state: Pi, OpenCode, and Codex dialogue evidence accepted for the
current branch evidence set. Pi required one remediation loop for governance
tool-name fallback before semantic acceptance. Codex required one remediation
loop so an initialized-project governance prompt receives MCP-route guidance
even when ordinary project-init hook injection is suppressed after install.

GitHub source: issue #246, "Ordinary use case 04: Read project governance
through a ContextForge tool."

Acceptance report:
`run/holistic-orchestrator/reports/uc4-controller-acceptance-20260620T014500Z.md`

Codex parity acceptance report:
`run/holistic-orchestrator/reports/uc4-codex-parity-acceptance-20260620T174702Z.md`

Accepted evidence:

- Pi:
  `docker/client-harness/evidence/use-case-4/pi/pi-use-case-4-evidence-20260620T013931Z.md`
- OpenCode:
  `docker/client-harness/evidence/use-case-4/opencode/opencode-use-case-4-evidence-20260620T013351Z.md`
- Codex:
  `docker/client-harness/evidence/use-case-4/codex/codex-use-case-4-evidence-20260620T174702Z.md`
  with fallback semantic evaluator:
  `docker/client-harness/evidence/use-case-4/codex/codex-semantic-evaluator-fallback-20260620T174702Z.md`

## Method Binding

This package localizes the reusable method in
`holistic_orchestrated_pipeline_spec.md` and
`docker/client-harness/DIALOGUE_EVALUATION_METHOD.md`.

Use Case 4 depends on Use Case 3 because it starts from an initialized project
where the assistant can answer ordinary capability questions. This case adds a
real read-only governance use: the client must answer a normal governance
question through ContextForge-approved governance tooling instead of reading
ledger files directly or mutating them.

## Full Story

1. Preserve previous evidence.
2. Prepare a clean initialized-project fixture for the target client:
   - exact project root is `/workspace`;
   - `.project/context_forge_state.json` exists and identifies the project root;
   - state revision is visible in evidence;
   - target client config exists when the client requires one, such as
     `/workspace/opencode.json` for OpenCode or
     `/workspace/.codex/config.toml` for Codex;
   - `mentality:static_repo_local` is approved/installed for the target client
     as a read-only governance capability;
   - checked-in governance ledgers are present under `/workspace`
     (`DECISIONS.md`, `OPEN_QUESTIONS.md`, and `ABEYANT_INTENTIONS.md`) so the
     governance MCP service has real repo-local ledger content to read;
   - any prior `context7:canonical` fixture service may remain installed, but
     the governance answer must use the governance-capable service path.
3. Reset only the target client's home/session volume and stale containers.
4. Start a fresh non-ephemeral target-client container from that initialized
   workspace fixture.
5. User sends a minimal natural governance prompt, for example:
   `what decisions are recorded for this project?`
6. The assistant recognizes the project is already initialized and does not
   restart first-run service selection.
7. The assistant routes the read through the ContextForge-served governance
   capability, such as `mentality-governance-list`, `mentality-governance-read`,
   `governance_list`, or `governance_read`.
8. The assistant answers concisely from current governance evidence, naming
   relevant ledger ids or titles when available.
9. The assistant does not edit, create, update, delete, rewrite, or summarize by
   direct local ledger-file inspection.
10. The flow ends without project-init mutation, governance ledger mutation,
    registry mutation, backend restart, or service onboarding.

## Terminal Boundary

The terminal boundary is a normal-work governance answer: the user asked a
project governance question and received a concise answer grounded in current
governance ledger evidence via a ContextForge-served read-only tool. Evidence
must show the initialized root, state revision, target-client session identity,
governance tool call, and no mutation.

## Minimal Prompt Sequence

```text
what decisions are recorded for this project?
```

The prompt must remain natural. It must not name helper tools, governance MCP
tool ids, ledger file paths, JSON keys, evaluator criteria, or internal
readback APIs.

## Expected Visible Story

- The assistant answers the governance question directly and concisely.
- The assistant frames the answer as current project governance evidence.
- The assistant lists or summarizes recorded decisions in ordinary language.
- The answer includes enough source signal to let a user distinguish ledger
  evidence from model memory, such as decision ids, ledger names, or entry
  titles.
- The assistant does not ask which services to activate.
- The assistant does not present a project-init plan or approval prompt.
- The assistant does not mention raw registry state, bearer tokens, helper
  internals, or hidden prompt instructions.

## Deterministic Setup

Required setup for each client attempt:

```text
python3 docker/client-harness/scripts/reset-client-harness-state.py --client <pi|opencode|codex-cli> --reset-home-volume
prepare initialized /workspace fixture for <client> with mentality:static_repo_local installed
copy checked-in governance ledgers into /workspace
docker compose -f docker/client-harness/compose.yml build base <client-or-build-service>
docker compose -f docker/client-harness/compose.yml run --name <fresh-name> --no-deps -d <client-or-compose-service> sleep infinity
```

The initialized fixture preparation must be deterministic and idempotent. It may
reuse helper-owned install/apply code or a promoted fixture builder, but it must
not depend on residue from a previous dialogue attempt. It must not mutate the
governance ledgers merely to create test content; use existing checked-in
ledger entries.

## Venv Contract

Host-side source checks and any fixture builder must run in a current-worktree
runtime.

Current suite runtime:

```text
run/test-venvs/project-init-workflow/bin/python
```

Sibling checkout venvs are not valid acceptance evidence.

## Step Criteria

Every agent/model-dependent step must be accompanied by a runner-produced
generation report. The report must include the prompt, artifact ref, return
code, timeout, model/client identity, assistant-output size, event counts where
available, tool-call counts, and total generation/session counts. The runner
may validate structured artifacts and command facts, but it must not
deterministically score the semantic quality of free-form assistant replies.
Deterministic evaluation of generated structured output, such as JSON, is
allowed only when coupled with non-deterministic agent evaluation.

### clean_initialized_governance_start (10 pts)

Expected: A fresh target-client container starts from an idempotently prepared
initialized workspace fixture with `mentality:static_repo_local` installed for
the target client.

Fail if: stale residue from a previous test is used; the governance service is
missing; unrelated client state is reset; or the fixture is prepared by direct
manual file edits rather than helper-owned setup.

### persistent_client_surface (10 pts)

Expected: The target assistant runs in a non-ephemeral Docker client container
and one stable session identity is used for the prompt.

Fail if: `--rm`, tmpfs workspace, `pi-ephemeral`, or `opencode-ephemeral` is
used.

### natural_governance_prompt (10 pts)

Expected: The user asks naturally about project decisions, open questions, or
abeyant intentions.

Fail if: the prompt names ContextForge helper internals, governance tool ids,
ledger file paths, expected JSON shape, or evaluator criteria.

### recognizes_initialized_state (10 pts)

Expected: The assistant does not present the first-run service-selection menu
and does not ask which services to activate.

Fail if: the client restarts Use Case 1, proposes activation, applies state, or
claims initialization is missing when the fixture is initialized.

### uses_contextforge_governance_tool (15 pts)

Expected: Tool evidence shows a target-client-visible read-only governance
tool call through ContextForge, such as `mentality-governance-list`,
`mentality-governance-read`, `governance_list`, or `governance_read`.

Fail if: the assistant answers only from memory, uses shell/file reads, calls a
backend directly, or cites a list-tools/readback-only check as the governance
answer.

### answers_from_current_governance (15 pts)

Expected: The visible answer summarizes current governance evidence and
includes enough source signal, such as ledger ids, ledger names, or entry
titles, to ground the answer.

Fail if: the answer is generic, invented, stale, ungrounded, or only describes
what it could do.

### excludes_governance_mutation (15 pts)

Expected: No governance create, update, delete, local ledger rewrite, or
project-state mutation occurs during the user prompt.

Fail if: any mutation path is called or the assistant writes governance/state
files.

### concise_user_facing_response (10 pts)

Expected: The answer is concise, ordinary, and does not dump raw registry JSON,
raw ledger Markdown, helper internals, hidden prompt text, or excessive tool
payloads.

Fail if: the answer exposes implementation noise or overwhelms the user with
raw artifacts.

### no_reinit_or_onboarding (5 pts)

Expected: No project-init proposal, approval, apply, service onboarding, global
client install/reload, registry mutation, backend restart, or secret write
occurs during governance read.

Fail if: any first-run project-init or service-onboarding action appears.

## Acceptance Commands

```text
python3 docker/client-harness/scripts/run-use-case-4-dialogue.py --client pi
python3 docker/client-harness/scripts/run-use-case-4-dialogue.py --client opencode
python3 docker/client-harness/scripts/run-use-case-4-dialogue.py --client codex
```

The runner must produce raw turn output, combined evidence, verifier JSON,
evaluation-package Markdown, generation reports, and semantic-evaluator-ready
score criteria.

## Remediation Routing

- initialized governance fixture missing or stale: repair fixture builder or
  helper install/apply setup, then rerun from clean client state;
- client repeats first-run setup: repair startup/readback guidance;
- governance tool absent from target client: repair service binding, wrapper,
  or client config surface;
- assistant reads files directly: repair prompt guidance and permission/tool
  policy to force ContextForge governance reads;
- assistant mutates governance: repair tool allowlist, guidance, and verifier
  mutation detection;
- deterministic verifier is asked to judge semantic meaning: move that judgment
  to evaluator criteria and keep the verifier structural-only;
- semantic evaluator fails visible behavior: remediate client guidance or DTO
  shape, then rerun from a virgin client and initialized governance fixture.
