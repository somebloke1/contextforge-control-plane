# Comprehensive MCP Testing SuperLoop

This package coordinates comprehensive MCP service testing through actual Pi
and OpenCode qwen-backed client sessions. It is separate from the use-case
lifecycle gates: those prove project-init behavior; this proves post-activation
MCP tool behavior as seen by real clients.

## Issue Map

| Issue | Service | Primary defect context |
| --- | --- | --- |
| #307 | context7 | service-specific docs lookup behavior |
| #308 | mentality | service-specific governance/read behavior |
| #309 | ssh-tmux | service-specific session inspection behavior |
| #310 | playwright | service-specific browser automation behavior |
| #311 | exa-search | service-specific search/fetch behavior |
| #312 | github | service-specific GitHub behavior |
| #313 | web-search | service-specific search/fetch behavior |
| #314 | openzeppelin-solidity-contracts | service-specific Solidity generation behavior |
| #315 | serena | service-specific project code-intelligence behavior |
| #316 | cross-MCP | wrapper, client, auth, reload, session, visibility, and shared harness behavior |

## SuperLoop

For each service and each target client:

1. Start from a dedicated testing branch/worktree.
2. Reset only the target client with the idempotent harness reset script.
3. Use a persistent non-ephemeral Pi or OpenCode container.
4. Use the configured qwen model and record the actual emitted model string.
5. Run the natural all-services activation flow.
6. Start a fresh post-activation client session.
7. Ask the assistant, in ordinary user language, to comprehensively test the
   selected MCP service.
8. Preserve raw transcript, command ledger, runtime readback, tool traces, and
   logs.
9. A non-Spark evaluator judges the transcript and classifies findings.
10. Triage defects to the service-specific issue or #316.
11. Remediate, retest, and loop until the service/client slice passes or a
    blocker is explicitly owned.

## Triage Rules

Route to #316 unless evidence isolates the defect to one service:

- wrapper transport failures;
- token creation, propagation, revocation, or session-termination failures;
- reload/new-session behavior;
- tool trace visibility or excessive low-level user-visible noise;
- reset/idempotency defects;
- shared Pi/OpenCode qwen configuration failures;
- deterministic verifier limitations.

Route to the service issue when evidence isolates the failure to:

- one service's tool schema;
- one service's upstream availability;
- one service's safe-call policy;
- one service's prompt/resource guidance;
- one service's permission or credential boundary.

## Evaluation Boundary

Deterministic scripts may verify command status, JSON shape, evidence presence,
runtime identity, model string, token revocation, endpoint reachability, and
artifact structure. They must not judge the semantic meaning of free-form
assistant prose with string or regex matching.

Semantic pass/fail belongs to a non-Spark evaluator reviewing the raw
transcript and the tester narrative.

## Mutating Tools

Every service must attempt all safe read-only or no-op functions. Mutating
functions require one of:

- a real dry-run flag;
- a disposable fixture resource created for the test;
- a bounded no-op target;
- an explicit skip rationale with risk classification.

Unbounded writes to real GitHub repositories, browser state, SSH sessions,
remote websites, or host/global configs are forbidden by default.
