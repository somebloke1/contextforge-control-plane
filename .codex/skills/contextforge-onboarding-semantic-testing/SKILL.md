---
name: contextforge-onboarding-semantic-testing
description: Run ContextForge MCP service-onboarding semantic process gates through real Pi and OpenCode target-client sessions. Use when Codex needs to design, run, evaluate, or refine source-lead-only onboarding proofs where a tested assistant starts from an upstream URL or lead, a simulated human responder answers questions, model-profile quorum evidence is required, and Codex subagents must not substitute for target-client behavior.
---

# ContextForge Onboarding Semantic Testing

## Overview

Use this skill for onboarding-process proof, not for already-registered MCP
service-use proof. The object under test is whether generic ContextForge
onboarding support can take a new source lead to target-client-visible service
use through real Pi and OpenCode assistants.
This skill is not for already-registered MCP service-use proof.

For ordinary service-use proof after a service is already registered, use
`comprehensive-mcp-testing`. For generic use-case dialogue evaluation, use
`code-assistant-dialogue-validation`.

## Required Artifacts

Before acting, read the relevant local artifacts:

- `docker/client-harness/ONBOARDING_SEMANTIC_PROCESS_GATE.md`
- `docker/client-harness/onboarding-semantic-process-scenarios.json`
- `docker/client-harness/DIALOGUE_EVALUATION_METHOD.md`
- `docs/initiatives/contextforge-control-plane/service-onboarding-helper.md`

Load only additional runner code, issue text, or evidence files needed for the
current foil.

## Claim Boundary

Do not claim a foil is accepted because Codex, a shell script, or a backend
probe succeeded. Acceptance requires evidence that real Pi and real OpenCode
target-client assistants progressed through the generic onboarding process and
then saw and safely used the onboarded service through ContextForge.

If the foil is already present in the target ContextForge surface before the
run starts, the run is invalid. "Present" includes an MCP service, service
tools, virtual server, service-bound prompt, service-bound resource, or any
client activation-menu entry for the foil. Treat current menu/readback checks
as a minimum visible preflight, not as the whole cleanup contract.

Codex subagents may build runners, package evidence, review GitHub state, or
evaluate transcripts. They are never the tested assistant for this gate.

## Role Split

- Controller: owns branch/GitHub state, runner package readiness, remediation,
  and final acceptance.
- Tested assistant: real Pi or OpenCode client session launched through the
  Docker client harness.
- Simulated human responder: separate persona that answers only the tested
  assistant's user-facing questions.
- Deterministic runner: resets state, launches clients, selects one model
  profile per run, records transcripts, and packages evidence.
- Semantic evaluator: non-Spark model or SO that judges meaning, route
  adequacy, claim boundaries, and process success.

## Veil Rule

The tested assistant receives only the source lead, generic ContextForge
onboarding guidance available in the target client, and answers from the
simulated human. Do not provide service-specific package names, tool names,
bridge commands, probe payloads, expected implementation shape, controller
memory, evaluator criteria, or prior-run conclusions.

The runner and evaluator may know the criteria, but that knowledge must not
enter prompts sent to the tested assistant.

Acceptance-matrix runs should use a reactive simulated-human responder that
reads the tested assistant's previous visible output and produces the next
persona-consistent user message. Seeded prompt sequences are acceptable for
runner smoke/debug checks, but they are not equivalent to a model-backed
responder answering the actual questions asked.

## Persona Sampling

For each client/model run, randomly compose one simulated-human persona across
these five dimensions and keep it stable for the whole dialogue:

- `domain_knowledge`
- `goal_specificity`
- `risk_posture`
- `technical_fluency`
- `interaction_style`

Record the seed and vector. The persona may answer questions, say it does not
know, or ask the tested assistant to decide from source research. It must not
rescue the assistant with hidden implementation hints.

## Run Matrix

For each onboarding foil, acceptance requires:

- target clients: `pi` and `opencode`;
- at least three distinct eligible semantic-test model profiles per target
  client;
- isolated home, workspace, scoped credentials, container name, session id, and
  evidence root per client/model/persona run;
- at least one low-knowledge persona, one higher-knowledge persona, and two
  distinct risk postures across the accepted matrix.
- enough interaction budget for the persona and outcome, without treating a
  fixed turn count as acceptance. The semantic evaluator judges whether the
  dialogue was truncated, over-guided, unnecessarily long, or complete with no
  loss of required outcome.
- semantic evaluation of interaction efficiency, taking the sampled persona's
  natural overhead as given and judging whether the assistant avoided needless
  detours, repeated explanations, premature approvals, overlong procedural
  narration, and premature truncation.

Do not move to the next foil until the current foil passes this matrix or the
controller explicitly records a blocked state with owner and remediation path.

## Runner Requirements

Use the onboarding semantic-process runners, not the comprehensive
already-registered-service runners:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
  docker/client-harness/scripts/run-onboarding-semantic-process-quorum.py \
  --client pi \
  --foil time \
  --timeout 420 \
  --no-build
```

Use `run-onboarding-semantic-process-dialogue.py` only for one
client/model/persona slice, debugging, or a runner-invoking agent that supplies
persona-consistent prompts with `--prompt` or `--prompt-file`.

The runner may deterministically verify reset postconditions, command status,
JSON structure, artifact existence, endpoint reachability, transcript capture,
credential cleanup, and preexisting-foil absence in structured ContextForge
readbacks. It must not evaluate generated assistant meaning through string
matching, regex matching, keyword matching, or transcript pattern scoring.

The runner package should emit a manifest-first evidence bundle with:

- foil id and source lead;
- target client, model profile, provider route preference, persona seed/vector,
  and session ids;
- command ledger and reset/readback evidence;
- stepwise and total generation reports;
- raw transcript paths and targeted excerpts;
- structured runtime/ContextForge/target-client readbacks;
- evaluator score sheet and final narrative prompt.

If a deterministic check fails before real dialogue begins, report setup
failure. Do not rewrite the story into a scripted substitute.

## Evaluation

Use a non-Spark semantic evaluator for pass/fail judgment. The evaluator must
judge whether the tested assistant:

- stayed behind the veil;
- asked suitable questions or proceeded from source research when questions
  were unnecessary;
- surfaced key implementation decisions methodically;
- used generic ContextForge onboarding support rather than controller memory or
  direct upstream shortcuts;
- kept source, backend, ContextForge registry, target-client-visible, and
  accepted claims separate;
- handled reload or new-session boundaries clearly;
- produced clear, low-noise user-facing copy;
- demonstrated target-client-visible service listing and a safe service call;
- moved efficiently relative to persona, task complexity, and required outcome;
- identified residual risks honestly.

Classify failures as runner defect, simulated-human defect, tested-client
behavior defect, generic-support gap, model inadequacy, service-specific
defect, or environment/setup defect. Route each finding to the correct issue
or remediation branch.

## Refinement

When a failure reveals a reusable lesson about source-lead packaging,
question-answer persona behavior, runner isolation, model adequacy, evidence
shape, or evaluator criteria, patch this skill or the referenced gate artifact
before wider fan-out. Do not bury durable method lessons only in issue
comments.
