---
name: code-assistant-dialogue-validation
description: Validate ContextForge client use cases by delegating to a code-assistant validation agent that drives real Pi/OpenCode/Codex/Gemini command-line dialogue sessions end to end, with a stable session id, continuation across reload/new-session boundaries, observed assistant/tool outputs, and no scripted substitution for agent behavior.
---

# Code Assistant Dialogue Validation

Use this skill when a ContextForge acceptance gate depends on how a code
assistant actually behaves in a client session. This skill is for delegated
dev-agent validation of dialogue, not for replacing the dialogue with scripts.

## Core Rule

A scripted smoke test can prepare the environment or audit captured evidence.
It cannot satisfy a human-facing dialogue gate. The pass must come from a
validator agent conducting the same interaction a human would conduct through
the target client CLI.

## Roles

- Controller: assigns the validation lease, owns acceptance, GitHub/Project
  state, merge/ready decisions, and remediation sequencing.
- Dialogue validator: a delegated dev agent that drives one target client from
  the command line and reports observed evidence.
- Verifier scripts: audit the captured transcript after the validator run; they
  do not create acceptance evidence.

## Required Lease Shape

The controller lease must include:

- target client and use case, for example `Pi / Use Case 1 context7`;
- exact worktree and branch;
- allowed Docker/client surfaces;
- forbidden host/global/client config, secrets, registry, systemd, production,
  and destructive actions;
- required prompts to send to the client;
- expected reload/new-session continuation behavior;
- transcript path and session id capture method;
- stop condition: pass all expected outcomes or stop at first agent-behavior
  failure with evidence.

The validator must not decide PR readiness. It returns evidence only.

## Dialogue Validation Procedure

1. Start the target client from the command line in the approved harness.
2. Record the command line, cwd, target client, model, and session id.
3. Use the client as an assistant, not as a script runner.
4. Send the same prompts a human would send for the use case.
5. When the helper requires reload or new session, continue the same validation
   thread using the client-supported continuation/resume mechanism and record
   the continued session id.
6. Capture full user, assistant, tool-call, and tool-output transcript.
7. Continue remediation/testing loops only when the controller assigns a new
   validation lease after a fix.
8. Stop when the expected outcome passes cleanly or the first blocking
   behavior failure is observed.

## Pass Criteria

A dialogue validation pass requires:

- one coherent validation thread with stable session identity or explicit
  continuation chain;
- the assistant sees project-init guidance through the target client surface;
- the assistant chooses no service, approval, reload, validation, or skip action
  on behalf of the user;
- the assistant uses helper/project-init tools for discovery, proposal,
  approval/apply, reload acknowledgement, and validation recording;
- target-client validation uses the actual visible ContextForge tool or
  client shim, not backend health, shell commands, package CLIs, direct stdio,
  local files, or invented JSON;
- the assistant calls safe probe before record-validation;
- no helper rejection is needed to teach the required sequence;
- final readback is initialized/passed for the selected service and target
  client.

## Failure Conditions

Fail the gate and return evidence if any of these occur:

- no stable session id or continuation chain;
- model lacks the expected client-visible tools;
- assistant calls record-validation before the safe probe;
- assistant invents `validation_results`;
- assistant uses shell/package/backend substitutes for target-client proof;
- helper returns permission, insufficient validation, missing-field, or
  equivalent rejection during a supposed passing run;
- assistant claims completion while target-client validation is pending,
  skipped, presumed, or failed;
- any forbidden mutation surface is touched.

## Output Contract

The validator report must include:

- validator agent id and controller lease id;
- client, command line, cwd, model, session id, and transcript path;
- pass/fail verdict for each expected outcome;
- first failure point with line references or excerpt;
- exact non-actions observed;
- verifier command and output, if a verifier exists;
- residual risk and requested controller action.

The controller may use verifier scripts to audit this report, but acceptance
requires the dialogue transcript itself.
