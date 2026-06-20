# Use Case 8 Controller Acceptance - 2026-06-20

## Scope

Use Case 8 covers using a ContextForge tool and then asking a follow-up in the
same target-client session.

Accepted target clients:

- Pi
- OpenCode
- Codex

## Controller Judgment

Accepted.

Controller acceptance is based on clean non-ephemeral target-client containers,
initialized `/workspace` fixtures with `context7:canonical`, two-turn
same-session CLI evidence, deterministic structure-only verification, and
non-Spark semantic evaluator review. Deterministic checks did not judge
generated prose meaning.

## Evidence

- Package:
  `docs/use-cases/use-case-8/package.md`
- Pi accepted combined evidence:
  `docker/client-harness/evidence/use-case-8/pi/pi-use-case-8-evidence-20260620T070347Z.md`
- Pi accepted evaluation package:
  `docker/client-harness/evidence/use-case-8/pi/pi-evaluation-package-20260620T070347Z.md`
- Pi accepted verifier JSON:
  `docker/client-harness/evidence/use-case-8/pi/pi-verifier-20260620T070347Z.json`
- Pi accepted metadata:
  `docker/client-harness/evidence/use-case-8/pi/pi-metadata-20260620T070347Z.json`
- OpenCode accepted combined evidence:
  `docker/client-harness/evidence/use-case-8/opencode/opencode-use-case-8-evidence-20260620T065808Z.md`
- OpenCode accepted evaluation package:
  `docker/client-harness/evidence/use-case-8/opencode/opencode-evaluation-package-20260620T065808Z.md`
- OpenCode accepted verifier JSON:
  `docker/client-harness/evidence/use-case-8/opencode/opencode-verifier-20260620T065808Z.json`
- OpenCode accepted metadata:
  `docker/client-harness/evidence/use-case-8/opencode/opencode-metadata-20260620T065808Z.json`
- Codex accepted combined evidence:
  `docker/client-harness/evidence/use-case-8/codex/codex-use-case-8-evidence-20260620T184942Z.md`
- Codex accepted evaluation package:
  `docker/client-harness/evidence/use-case-8/codex/codex-evaluation-package-20260620T184942Z.md`
- Codex accepted verifier JSON:
  `docker/client-harness/evidence/use-case-8/codex/codex-verifier-20260620T184942Z.json`
- Codex accepted metadata:
  `docker/client-harness/evidence/use-case-8/codex/codex-metadata-20260620T184942Z.json`

## Structured Findings

Both accepted runs reported:

- two natural user prompts;
- one stable target-client session id across both turns;
- clean target-client reset and home-volume reset;
- fresh non-ephemeral runner container;
- initialized `/workspace` fixture with `context7:canonical`;
- successful turn commands with no timeouts;
- verifier failures: none.

Pi accepted run:

- session id: `uc8-pi-20260620T070347Z`;
- first turn used Context7 resolve-library-id and query-docs tools;
- follow-up used Context7 query-docs for `/anomalyco/opencode`.

OpenCode accepted run:

- session id: `ses_11c2d4a1effeno0idGtINMYT72`;
- first turn used Context7 resolve-library-id and query-docs tools;
- follow-up used Context7 query-docs for the selected OpenCode documentation
  result.

Codex accepted run:

- session id: `019ee65e-17c7-71a1-aad7-de2b7f4f0dfa`;
- first turn used the ContextForge-provided Context7 `resolve-library-id`
  tool and selected `/anomalyco/opencode`;
- follow-up resumed the same Codex session and used Context7 `query-docs` for
  `/anomalyco/opencode` configuration docs.

## Semantic Evaluation

Initial evaluator agent `019ee3d4-16c7-7863-9457-e242874213d6` reviewed the
first Pi and OpenCode UC8 evidence.

Verdict:

- OpenCode: PASS, about 96/100.
- Pi: FAIL, about 82/100.
- Overall: FAIL before remediation.

The Pi failure was an implementation defect: the first Pi run used the correct
Context7 tools, but visibly detoured through project-init/reload state before
ordinary docs lookup. The accepted remediation tightened Pi and OpenCode
normal-use guidance so ordinary docs, library, package, API, and configuration
lookup questions route directly to Context7 service tools without
project-init continuation or readback detours.

Remediated Pi evaluator agent `019ee3dc-1808-70b1-9871-d5d9a09da7d0` reviewed
the second Pi evidence.

Verdict:

- Pi: PASS, 94/100.
- Failure classification: none.

Evaluator findings:

- prompts were natural and uncoached;
- setup/session evidence supports a clean non-ephemeral same-session run;
- first turn used ContextForge Context7 docs tooling;
- follow-up used the prior `/anomalyco/opencode` result in the same session;
- no first-run onboarding, visible project-init/readback detour,
  validation/probing, backend restart, registry/global mutation,
  readiness/reload overclaim, or hidden prompt leakage remained.

Initial Codex controller inspection failed the first UC8 package:

- failed package:
  `docker/client-harness/evidence/use-case-8/codex/codex-evaluation-package-20260620T184656Z.md`;
- failure classification: tested-client routing/guidance defect;
- Codex saw the project-local Context7 MCP server, but answered through shell,
  OpenAI-docs/manual, and web-search routes instead of using the installed
  ContextForge Context7 tools.

Codex remediation added normal-use hook guidance for initialized projects with
`context7:canonical`: ordinary docs/library/package/API/configuration prompts
must use the Context7 MCP tools directly, must not start with visible text,
shell commands, web search, OpenAI-docs/manual lookup, project-state readback,
or project-init continuation.

Remediated Codex evaluator agent `019ee65f-122a-7821-951b-51c77f955d58`
reviewed the accepted Codex evidence.

Verdict:

- Codex: PASS, 100/100.
- Fatal failures: none.

Evaluator findings:

- prompts were natural and uncoached;
- setup/session evidence supports a clean non-ephemeral same-session run;
- first turn used ContextForge Context7 `resolve-library-id`;
- follow-up used the prior `/anomalyco/opencode` result in the same session and
  called Context7 `query-docs`;
- no first-run onboarding, readback-only substitution, memory-only answer,
  shell/web/OpenAI-docs substitution after remediation, validation/probing,
  forbidden mutation, readiness overclaim, or hidden prompt leakage remained.

## Remediation Included

- Added UC8 package, runner, verifier wrapper, and evaluator package generation.
- Added UC8-specific semantic criteria to the shared structural verifier.
- Added normal-use guidance for ordinary docs/library/package/API/configuration
  questions so target clients use Context7 tools directly.
- Added a regression test that the Pi/OpenCode normal-use guidance routes docs
  lookups without project-init continuation detours.
- Added Codex normal-use Context7 hook guidance, UC8 Codex runner/verifier
  support, and regression coverage for avoiding shell/OpenAI-docs/web-search
  substitution on ordinary docs prompts.

## Verification

Fresh verification:

```text
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_contextforge_docker_harness -v
```

Result: 32 passed.

```text
run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_contextforge_docker_harness -v
```

Result: 36 passed.

```text
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_project_init_activation_workflow -v
```

Result: 107 passed.

```text
run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_project_init_activation_workflow -v
```

Result: 115 passed.

```text
run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_project_init_scripts -v
```

Result: 102 passed.

```text
run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_project_init_scripts.SerenaManagerTests.test_codex_normal_docs_prompt_uses_context7_guidance tests.test_project_init_scripts.SerenaManagerTests.test_codex_state_readback_prompt_uses_readonly_helper_guidance tests.test_project_init_scripts.SerenaManagerTests.test_codex_project_init_negative_choice_continuation_context_records_decision tests.test_use_case1_e2e_gate.UseCase1E2EGateTests.test_use_case8_runner_and_verifier_support_codex -v
```

Result: 4 passed.

```text
node --check docker/client-harness/config/opencode/plugins/contextforge-project-init.js && node --check pi-extensions/contextforge-global-shim/index.ts
```

Result: pass.

```text
git diff --check
```

Result: pass.

## Residual Risk

Non-blocking:

- Pi still emitted brief visible prefaces before tool calls. The semantic
  evaluator did not treat those as blocking because they did not leak hidden
  routing, restart onboarding, or substitute readback/readiness for tool use.
- UC8 proves Context7 docs-tool use and same-session follow-up. It does not
  claim every ContextForge service supports same-session follow-up equally.

## Boundary

This acceptance does not claim service onboarding, cross-client automatic
service-set alignment, provider credential validity, backend restart behavior,
live ContextForge registry mutation, global client mutation, readiness report
completion, or final handoff. Those remain downstream or separate issue
surfaces.
