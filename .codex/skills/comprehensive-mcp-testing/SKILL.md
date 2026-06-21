---
name: comprehensive-mcp-testing
description: Orchestrate ContextForge comprehensive MCP service testing through real Pi and OpenCode command-line client sessions. Use when Codex needs to create or run service-by-service MCP test packages, exercise all safe functions through the configured semantic-test model profile, triage service-specific versus cross-client wrapper failures, update GitHub evidence, or refine the comprehensive MCP testing method as new failures are learned.
---

# Comprehensive MCP Testing

## Core Rule

Treat this as a semantic, model-engaged test regimen. Deterministic tooling may establish structure, runtime facts, command exit status, JSON validity, endpoint reachability, file existence, and evidence packaging. It must not decide whether free-form assistant prose satisfies a service interaction requirement. Use SO judgment or a non-Spark evaluator for meaning.

Short of direct user testing, usability evidence comes from a broad and diverse
set of semantic test bundles with runners dispatched by sub-agents. The bundle
set must deliberately explore plausible user behaviors and map each behavior to
the actual Pi/OpenCode client surface under test. Do not substitute one large
happy-path transcript for coverage. Because tested assistant context is finite
even when the configured semantic-test model changes, split coverage into
small, focused tests with compact prompts and isolated evidence packages.
Package semantic-test evidence manifest-first: provide compact metadata, stepwise
generation reports, targeted excerpts, and raw transcript paths instead of
pasting large transcripts or multi-service histories into one prompt.

## Operating Loop

1. Re-anchor on the current branch, issue map, runner, and evidence paths.
2. Define the service/client slice before running it: service issue, client type, safe functions, user-behavior bundle, mutating-function policy, expected evidence, and failure triage target.
3. Start from a virgin target-client harness state. Reset the target client container/home volume/workspace rather than calculating cleanup deltas.
4. Run a real Pi or OpenCode command-line session with the configured semantic-test model profile, using a stable session identity for each interaction phase.
5. Keep prompts natural, short, and minimally sufficient. Do not coach the tested assistant with tool-call names unless the use case explicitly requires that signal.
6. Require the tested assistant to use the ContextForge-installed tools exposed in the client session. Direct upstream package execution, shell scripts, or hand-written MCP clients are bypass evidence, not successful service use.
7. Preserve raw transcripts, command ledgers, summaries, and any container/runtime readback needed to reproduce the run.
8. Have an evaluator or SO read the evidence semantically and classify outcomes. Search or parse transcripts only to locate evidence, not to score meaning.
9. Triage findings:
   - Service tool/schema/upstream/guidance/credential defects go to that service's Comprehensive `<name>` MCP Testing issue.
   - Shared reload, wrapper, auth, token, client, reset, prompt-noise, model-context, or runner defects go to the cross-MCP issue.
10. Remediate the smallest process/code defect that makes the requested final state more true.
11. Update GitHub and the branch before dispatching wider agents.
12. Refine this skill when a new recurrent testing lesson appears, then validate and commit the skill change before relying on that lesson in the next wider wave.

## Runner

Use the branch-local runner first:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
  docker/client-harness/scripts/run-comprehensive-mcp-service-dialogue.py \
  --client pi \
  --service context7 \
  --contextforge-env-file /path/to/ignored/contextforge.env \
  --timeout 420 \
  --no-build
```

Supported clients are `pi` and `opencode`. Supported services are defined in `docker/client-harness/comprehensive-mcp-testing-services.json`.

For client-visible ContextForge tool tests, provide an ignored harness env file with admin credentials so the runner can create a short-lived scoped token for the selected virtual server. The runner must not print or persist the raw token and must revoke it after the run.

When proving a non-default ContextForge harness, explicitly set both the gateway base URL and an isolated token cache. Do not let helper defaults silently target the legacy 4444 server while the intended proof is against the Docker successor gateway, for example 4445.

Read [method.md](references/method.md) when selecting services, interpreting runner output, dispatching evaluators, or refining the package.

## Host-Side Validation Floor

Do not stop at "pytest is unavailable." This repository's default Python
validation surface is `unittest` plus `py_compile`; pytest absence is not a
permission to skip focused tests or post a passive limitation. If the
branch-local `.venv` exists but lacks pytest, run the applicable `unittest`,
`py_compile`, skill validation, Node syntax check, or runner dry-run that
matches the changed files.

Every branch/worktree used for this testing loop must have its own local
`.venv`; create or repair it with `uv venv .venv` if missing before validation.
If a changed slice genuinely requires a dependency that the branch-local
`.venv` lacks, install it into that `.venv` or create/reuse an ignored
current-worktree test venv such as `run/test-venvs/<suite>/`. Never borrow a
sibling checkout venv, and never claim validation is blocked solely because the
root has no dependency manifest. If no executable validation is possible,
record a concrete blocker with owner, issue/PR link, and the attempted fallback
commands before making any readiness claim.

## Semantic Model Discipline

Assume tested Pi/OpenCode sessions have limited usable context regardless of
the currently configured provider/model. Activate only the target service for a
service slice unless testing multi-service behavior. Avoid all-service
activation, huge tool catalogs, and long prompt narratives. Split large
services into smaller function groups if needed, but preserve full untruncated
use-case stories in the package and evidence. Keep evaluator packets
manifest-first with targeted excerpts and raw artifact references, not
transcript dumps.

Before launching another model-backed client session, check for active
runner/client/model processes, existing evidence from the current slice, and
target-client containers left from the prior run. Distinguish loaded local
model residency from active generation when a local model profile is in use:
GPU memory held by a local model server with near-zero utilization is not the
same signal as an in-flight tested-assistant turn. Do not stack duplicate
sessions just because the controller lost conversational context. If GPU
utilization is pegged, identify whether a known test slice is still running
before dispatching more model work; stop only sessions owned by this testing
loop or ask the SO when ownership is unclear.

Use [method.md](references/method.md#active-session-stewardship) for the concrete preflight/readback commands and ownership rules.

Before broad fan-out, maintain a one-line active-slice ledger in the issue
comment, evidence summary, or controller notes: service, client, container,
session ids, evidence root, start time, current state, and owner. Refresh that
ledger before starting any new model-backed turn. If the only signal is resident
GPU memory at 0% utilization, treat it as loaded-model residency, not a reason
to kill or duplicate sessions. If a slice-owned container remains after the
turn, either reuse it deliberately for readback or preserve evidence and reset
it before the next attempt.

## Bypass Rule

If the tested assistant writes scripts, runs `npx`, invokes upstream MCP packages directly, or manually drives JSON-RPC over stdio instead of using client-visible ContextForge tools, classify the run as not accepted. Preserve the output because it may prove the upstream service works, but triage the client-visible ContextForge exposure failure separately.

Also classify the run as not accepted when the assistant answers through a
non-target route, including shell commands, web search, manual/OpenAI docs,
memory, direct upstream execution, or another MCP service, instead of the
ContextForge-installed service under test.

## Delegation

Use gpt-5.5/non-Spark agents for semantic evaluation of model-agent interactions. Use Spark only for bounded mechanical tasks such as summarizing command ledgers, checking links, drafting issue index text, or patching obvious repetitive documentation.

The controller retains GitHub privileges and final acceptance. Subagents return evidence and recommendations, not readiness authority.

## Refinement Trigger

Patch this skill when a failure reveals a reusable lesson about prompt shape, reset strategy, evidence packaging, semantic-model context limits, evaluator criteria, or GitHub triage. Do not bury repeated lessons only in issue comments.

Refinement is part of the testing loop. After each slice, write a short learning note in the controller evidence or issue comment that says either `skill-update-needed`, `method-update-needed`, `candidate-only`, or `no-method-change`. For each durable lesson, decide whether it belongs in the short `SKILL.md` operating rules or the detailed `references/method.md` guidance, make the smallest durable edit, run the skill validator, and include the refinement in the same branch/GitHub evidence stream as the test work that produced it. If a lesson is uncertain, record it as a candidate in the relevant issue instead of turning it into a rule prematurely.
