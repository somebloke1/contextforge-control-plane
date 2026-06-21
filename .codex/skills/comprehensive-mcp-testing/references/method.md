# Comprehensive MCP Testing Method

## Service Issue Map

The current comprehensive testing issue set is:

- #307 context7
- #308 mentality
- #309 ssh-tmux
- #310 playwright
- #311 exa-search
- #312 github
- #313 web-search
- #314 openzeppelin-solidity-contracts
- #315 serena
- #316 cross-MCP themes and global findings

Verify live issue state before relying on this map if GitHub work has progressed.

## Slice Contract

Each test slice must declare:

- `service`: ContextForge service slug.
- `client`: `pi` or `opencode`.
- `model`: qwen-backed tested assistant, currently local `qwen3.6-a3b` in the harness.
- `state`: target-client virgin reset; no stale container/home/workspace state.
- `prompt`: natural, short, sufficient user request.
- `evidence`: raw turn transcripts, command ledger, run summary, runtime readback, and evaluator narrative.
- `acceptance`: every safe function is actually attempted through the tested assistant, mutating functions are skipped or constrained with a safe dry-run/no-op rationale, and defects are triaged to the correct issue.

The phrase "through the tested assistant" means through ContextForge-installed tools visible in that client session. Direct package execution, direct stdio JSON-RPC, shell scripts, or upstream tool calls outside the client-visible ContextForge tool surface do not satisfy the slice.

For ContextForge-hosted service slices, the runner must create a scoped token for the target virtual server and pass it into the client container via a temporary env file. A checked-in `contextforge.env.example` or an empty mounted client-scoped directory is not sufficient. The raw access token must not appear in summaries, command ledgers, GitHub comments, or transcripts, and the token must be revoked after the run.

## Evaluation Boundary

Allowed deterministic checks:

- process return codes and timeouts
- existence and schema of `run-summary.json`
- JSON validity for structured outputs
- command ledger completeness
- container/runtime readback
- tool inventory structure
- endpoint reachability and HTTP status classes

Disallowed deterministic checks:

- regex or string-match pass/fail over assistant prose
- pattern-matched claims that a function was semantically exercised
- treating hidden thinking/tool text as a substitute for user-visible success

Structured JSON may be checked structurally, but semantic adequacy still requires non-deterministic evaluation.

## Prompt Shape

Prefer prompts like:

```text
Test the Context7 MCP service now. Use the MCP tools already exposed in this assistant session; do not use shell scripts, package installs, or direct upstream calls as substitutes. Use each safe function once if visible. Skip mutating functions unless there is a dry-run or no-op target. If the service tools are not visible, say that directly. Do not test unrelated services or governance routes. Keep the report under 20 lines with function, result, and issue target (#307 for context7, #316 for shared wrapper/client problems).
```

Avoid prompts that:

- list low-level helper calls to perform unless testing helper behavior.
- pre-narrate the desired conclusion.
- invite broad codebase exploration when the target is service use.
- activate every service when a single-service slice is under test.

## Bypass Evidence

A run may prove that an upstream MCP package works while still failing the ContextForge client test. Mark the run as not accepted when the assistant:

- writes a script to spawn the upstream MCP package directly.
- uses shell commands or package managers as the service invocation path.
- hand-drives JSON-RPC over stdio outside the client-visible tool interface.
- reports `target-client-visible=false` and then substitutes a direct upstream call.

Preserve those artifacts and triage them as useful isolation evidence, not as service-pass evidence.

## Failure Classification

Classify as cross-MCP (#316) when the dominant failure is:

- reload/session lifecycle
- wrapper startup, closed transport, or idle timeout
- client token/auth propagation
- noisy helper state shown to user
- target-client reset/idempotency
- qwen context blow-up or timeout caused by too much tool universe or prompt bulk
- runner/evidence package defect

Classify as service-specific when the dominant failure is:

- missing or wrong service tool
- upstream service unavailable or malformed
- service-specific credentials or token scope
- function schema mismatch
- service-specific guidance defect
- one service's mutating-function safety policy

When uncertain, write the finding to #316 with a link to the service issue and make the uncertainty explicit.

## Evidence Package

A complete package includes:

- `run-summary.json`
- one raw transcript per activation/test turn
- command ledger with exact client commands
- reset result and postcondition
- runtime readback
- evaluator narrative that describes the session step by step from the evaluator's perspective
- issue triage recommendation with evidence paths

The runner does not decide semantic pass/fail. The evaluator narrative is part of the signal.

## Controller Discipline

Before dispatching wider runners:

1. Run at least one control slice yourself.
2. Fix runner/package defects exposed by the control slice.
3. Push the branch and record the evidence in GitHub.
4. Dispatch bounded agents only after the invocation pattern is stable.

While agents run, maintain GitHub and branch hygiene rather than idling.
