# Code-Assistant Dialogue Evaluation Method

This is the reusable method for ContextForge client use-case evaluation. A
use-case gate should localize this method instead of rewriting it.

## Method Layer

The method layer is case-independent:

- start each attempt from an idempotently reset target-client instance and a
  virgin test workspace;
- use deterministic scripts for environment reset, command issuance, transcript
  capture, verifier invocation, and package assembly;
- run the tested client as a real assistant in a stable command-line session or
  explicit continuation chain;
- send only minimal natural prompts that a human would plausibly send;
- preserve complete user, assistant, tool-call, and tool-output evidence, with
  any exported package, transcript copy, issue comment, PR comment, or summary
  redacted for passwords, bearer tokens, API keys, JWTs, private keys, and
  other credential values;
- derive separate review surfaces for visible dialogue, hidden/extension
  messages, and tool audit events;
- report stepwise and total generations for every model-dependent use case,
  including prompt, artifact path, return code, timeout, model/client identity,
  assistant-output size, event counts where available, tool-call counts, and
  total generation count;
- treat deterministic verifier output as harness and structured-evidence
  support, not semantic acceptance;
- require a delegated validator narrative and score sheet for semantic
  judgment;
- require the evaluator narrative to identify visible dialogue quality risks
  that do not necessarily fail the use case, including placeholder-only visible
  prefaces before substantive answers, excessive internal terminology, or
  awkward hesitation that a user would experience as low-quality interaction;
- classify failures as runner/package, tested-client behavior,
  environment/setup, or inconclusive;
- remediate and repeat from a fresh target-client instance until the localized
  use-case story passes.

Harness diagnostics must not print raw ContextForge env files or credential
values. If secret-file inspection is necessary, report key presence,
permissions, selected non-secret ids, and redacted values only. Use
`docker/client-harness/scripts/redact-contextforge-secrets.py` for transcript
streams or env-like output before writing them to evidence directories or
copying them into GitHub.

The method layer does not define service ids, prompt text, expected assistant
copy, tool names, or pass/fail story details. Those belong to the localization
layer.

## Localization Layer

The localization layer contains the case-unique content.

Each use case must provide a compact localization artifact with:

- use-case id and target clients;
- prompt sequence;
- clean-start fixture and target-client reset requirements;
- expected visible user-facing story, step by step;
- supporting tool evidence expected for each step;
- required generation reporting for each step and for the whole session;
- forbidden shortcuts and forbidden mutation surfaces;
- client-specific reload/new-session boundary;
- deterministic verifier command;
- scoring criteria, fatal failures, and score threshold;
- required final validator narrative template.

No truncated stories are allowed. The localization must cover setup through the
terminal expected outcome, including failure branches that should block a pass.

## Package Contract

Every runner-generated evaluation package must include both layers:

- `methodology`: a stable summary of this method;
- `use_case_localization`: the case-specific story and criteria;
- raw artifacts and derived review surfaces;
- stepwise and total generation report for all model-dependent turns;
- deterministic verifier result;
- unscored score sheet for validator completion;
- final narrative instructions.

Future use cases should add or modify only the localization artifact and runner
prompt sequence unless the reusable method itself is inadequate.

## Onboarding Process Gates

Service-onboarding process proof is a special dialogue gate. It tests whether
the ContextForge onboarding process works through actual target clients, not
whether Codex can perform source research or implementation in its own
framework. Use the repo-local `contextforge-onboarding-semantic-testing` skill
as the operational test-running skill for this gate; this method only records
the shared dialogue-evidence boundary.

For each onboarding foil, the tested assistant must be a real Pi or OpenCode
client session. Codex subagents may build runners or evaluate evidence, but
they are not valid tested-client substitutes. The tested assistant receives
only the source lead, generic onboarding guidance available through the client,
and answers from a separate simulated human responder.

The simulated human is a composite persona randomly composed per run across a
five-dimensional disposition space: domain knowledge, goal specificity, risk
posture, technical fluency, and interaction style. The persona remains fixed
for the whole run and answers only questions the tested assistant asks. It must
not volunteer package names, tool names, bridge commands, probe payloads,
expected implementation shape, evaluator criteria, or controller memory.

Acceptance requires Pi and OpenCode coverage across at least three distinct
eligible semantic-test model profiles per target client. Deterministic runner
checks may package setup, commands, JSON, files, endpoints, and transcripts,
but semantic adequacy belongs to the evaluator.

## Deterministic Boundary

Deterministic evaluation of generative outputs is disallowed unless the output
is a declared structured artifact, such as JSON, and that deterministic check
is coupled with non-deterministic agent evaluation. Scripts may validate
command status, artifact existence, JSON parseability, schemas, required
fields, and other non-generative or structured contracts. Scripts may also
segment, count, index, and report assistant text and tool traces. They may
check structure, but not meaning. They must not use regexes, keyword matching,
string parsing, or other deterministic pattern matching as a test, gate, score
criterion, semantic observation, or acceptance oracle for free-form assistant
behavior.

For every model-dependent use case, the agent evaluator must receive and score:

- each step generation in sequence;
- the total generation/session report;
- raw transcript and normalized review surfaces;
- structured verifier output;
- the localized scorecard and fatal-failure criteria.

Quality risks such as placeholder-only visible prefaces are semantic evaluator
judgments. Scripts may preserve and segment the visible assistant text for
review, but they must not decide that a free-form reply is or is not a
placeholder by matching strings, regexes, ellipses, token fragments, or other
text patterns.
