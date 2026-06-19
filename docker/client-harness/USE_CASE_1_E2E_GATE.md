# Use Case 1 End-to-End Agent Gate

This gate applies to PR #271 and the first cumulative #247 service slice:
`context7:canonical` through Pi client Docker and OpenCode client Docker.

Human validation must not be requested until this gate has passed with full
agent-session evidence for both clients. Source tests, direct helper calls,
backend probes, smoke scripts, and hand-shaped validation payloads are useful
diagnostics, but they are not substitutes for this gate.

## Required Order

1. Run the existing source/unit/static checks.
2. Rebuild any changed client harness images.
3. Run the Pi end-to-end agent session from the command line.
4. Run the OpenCode end-to-end agent session from the command line.
5. Verify the two captured transcripts with
   `scripts/verify-use-case-1-e2e-evidence.py`.
6. If any required outcome fails, remediate the source/harness/prompt defect,
   rerun the affected source checks, rebuild changed images, rerun the full
   affected agent session from the command line, and rerun the verifier.
7. Repeat testing -> remediation -> testing until both clients pass every
   expected outcome in observed agent interaction evidence.
8. Only after all prior steps pass, ask for human validation.

If either client fails, the branch remains in agent repair. Do not ask the
operator to discover the next failure by hand.

This is a loop, not a one-shot checklist. A partial pass followed by a later
agent failure resets the gate to remediation. A helper rejection that the agent
eventually recovers from is still a failed gate when the required user-facing
interaction was supposed to be clean. Human testing is an acceptance check after
agent evidence passes; it is not the mechanism for discovering ordinary
integration failures.

## What Counts As End-to-End Agent Evidence

Each client needs one continuous command-line agent session with a stable
session id. The evidence must show the real model-driven assistant behavior,
not only helper or shell probes.

The transcript must include:

- the session id used for the run;
- the command line used to start or resume the session;
- the complete user prompts and assistant/tool outputs for the lifecycle;
- service discovery/menu presentation for `context7:canonical`;
- service selection using the helper-discovered service id;
- scoped approval and apply of only project-local state/config;
- reload or new-session acknowledgement when required;
- target-client-visible Context7 safe probe output;
- helper validation recording from the observed safe probe result;
- final initialized/passed readback;
- explicit non-actions for host/global client config, legacy/live
  ContextForge, secrets, trust, systemd, and production registry state.

Captured summaries are not enough. The evidence must contain the observed tool
calls and outputs that prove the agent followed the flow.

The expected outcome is not merely that a final helper field says initialized.
The observed agent interaction must complete the use case cleanly: correct
service menu, correct selection, scoped approval, required reload/new-session
step, correct target-client safe probe, validation recording from that observed
probe, and a final initialized/passed readback with no forbidden substitutes or
rejection-driven learning loop.

## Pi Pass Criteria

The Pi evidence must show:

- a persistent Pi session id, either in the captured transcript or supplied to
  the verifier with `--session-id`;
- the session ran from the Pi client Docker harness against `/workspace`;
- `qwen3.6-a3b` was the active model;
- `context7:canonical` was selected from helper-discovered choices;
- reload was acknowledged with `cf_project_init_record_client_reload`;
- validation used `cf_contextforge_pi_validate`;
- `cf_contextforge_pi_validate` returned `pi_validation_complete`;
- validation was recorded with `cf_project_init_record_validation`;
- final helper output contained `status=validation_recorded` and
  `project_status=initialized`.

The Pi gate fails if the agent uses shell substitutes such as
`python3 -m context7_*`, `which context7-*`, `npx @upstash/context7-mcp`, direct
backend probes, or local file inspection as validation proof. Pi validation must
go through the Pi-visible ContextForge shim/tool surface.

## OpenCode Pass Criteria

The OpenCode evidence must show:

- the OpenCode session id, such as `ses_...`;
- the session ran from the OpenCode client Docker harness against `/workspace`;
- `qwen3.6-a3b` was the active model;
- the first prompt or resume context exposed the project-init helper flow;
- `context7:canonical` was selected from helper-discovered choices;
- new-session reload was acknowledged with
  `cf_project_init_record_client_reload`;
- validation called the actual OpenCode-visible Context7 tool, for example
  `context7_context7-local-resolve-library-id`;
- only after that safe probe did the agent call
  `cf_project_init_record_validation`;
- final helper output contained `status=validation_recorded` and
  `project_status=initialized`.

The OpenCode gate fails if the agent calls record-validation before the safe
Context7 tool call, even if a later retry succeeds. A successful human-facing
flow cannot depend on helper rejections to teach the required sequence.

## Cross-Client Failure Conditions

Any of the following blocks human validation:

- missing stable session id;
- missing complete assistant/tool output transcript;
- `validation_results_insufficient`, permission-intent failures, or equivalent
  helper rejection during the supposed passing run;
- `TOOL_NOT_FOUND`, missing Context7 local CLI/module, or direct package
  fallback presented as validation;
- backend-only ContextForge health, direct bridge checks, local shell commands,
  or direct `npx` stdio calls used as target-client proof;
- final initialized/active claim without target-client-visible validation
  proof;
- any host/global Pi or OpenCode config mutation;
- any legacy/live ContextForge, production service, systemd, secret, OAuth,
  trust-token, or registry mutation.

## Verifier

Run the verifier on the captured artifacts before posting a ready/human-test
recommendation:

```sh
python3 docker/client-harness/scripts/verify-use-case-1-e2e-evidence.py \
  --client pi \
  --evidence docker/client-harness/evidence/use-case-1/pi-session.md \
  --session-id <pi-session-id>

python3 docker/client-harness/scripts/verify-use-case-1-e2e-evidence.py \
  --client opencode \
  --evidence docker/client-harness/evidence/use-case-1/opencode-session.md
```

The verifier is a gate, not a repair tool. If it fails, keep the work in agent
repair and attach the verifier output to the issue/PR.

## Human Validation Handoff

The human validation handoff must be a single PR comment titled
`Human Validation Checklist for PR #271`. It must include:

- links or paths to the passing Pi and OpenCode agent transcripts;
- verifier command lines and pass output for both clients;
- the exact PR head SHA;
- the human commands to rerun the same surfaces;
- known non-actions and remaining out-of-scope slices.

Do not ask for human validation from scattered issue comments or partial smoke
evidence.
