# Use Case 11 Controller Acceptance - 2026-06-20

## Scope

Use Case 11 covers seeing and applying project-specific tool guidance while
using a selected ContextForge capability.

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
  `docs/use-cases/use-case-11/package.md`
- Pi accepted combined evidence:
  `docker/client-harness/evidence/use-case-11/pi/pi-use-case-11-evidence-20260620T074721Z.md`
- Pi accepted evaluation package:
  `docker/client-harness/evidence/use-case-11/pi/pi-evaluation-package-20260620T074721Z.md`
- Pi accepted verifier JSON:
  `docker/client-harness/evidence/use-case-11/pi/pi-verifier-20260620T074721Z.json`
- Pi accepted metadata:
  `docker/client-harness/evidence/use-case-11/pi/pi-metadata-20260620T074721Z.json`
- OpenCode accepted combined evidence:
  `docker/client-harness/evidence/use-case-11/opencode/opencode-use-case-11-evidence-20260620T082020Z.md`
- OpenCode accepted evaluation package:
  `docker/client-harness/evidence/use-case-11/opencode/opencode-evaluation-package-20260620T082020Z.md`
- OpenCode accepted verifier JSON:
  `docker/client-harness/evidence/use-case-11/opencode/opencode-verifier-20260620T082020Z.json`
- OpenCode accepted metadata:
  `docker/client-harness/evidence/use-case-11/opencode/opencode-metadata-20260620T082020Z.json`
- Codex accepted combined evidence:
  `docker/client-harness/evidence/use-case-11/codex/codex-use-case-11-evidence-20260620T190744Z.md`
- Codex accepted evaluation package:
  `docker/client-harness/evidence/use-case-11/codex/codex-evaluation-package-20260620T190744Z.md`
- Codex accepted verifier JSON:
  `docker/client-harness/evidence/use-case-11/codex/codex-verifier-20260620T190744Z.json`
- Codex accepted metadata:
  `docker/client-harness/evidence/use-case-11/codex/codex-metadata-20260620T190744Z.json`

## Structured Findings

Accepted runs reported:

- two natural user prompts;
- one stable target-client session id across both turns;
- clean target-client reset and home-volume reset;
- fresh non-ephemeral runner container;
- initialized `/workspace` fixture with `context7:canonical`;
- separated `project_service_graph`, `target_client_projection`,
  `target_client_visibility`, and `target_client_proof` fields;
- verifier failures: none.

All accepted runs reported verifier failures: none. Codex uses the
authenticated Docker baseline image rather than a disposable mounted home
volume, so its metadata records the post-setup home reset as not applicable
while still proving stale container removal, virgin `/workspace` reset, fresh
non-ephemeral setup/runner containers, and empty API-key environment variables.

Pi accepted run:

- session id: `uc11-pi-20260620T074721Z`;
- first turn called ContextForge guidance lookup and surfaced workflow guidance
  before docs content;
- follow-up used Context7 projected tools to answer the OpenCode config-file
  reading question.

OpenCode accepted run:

- session id: `ses_11be20716ffe8MulbJNfrBj3id`;
- first turn reported one visible guidance generation and zero tool events;
- follow-up used Context7 resolve/query tools and produced a docs-backed
  OpenCode configuration answer.

Codex accepted run:

- session id: `019ee66e-99cc-7b61-9cf7-911c7bb36a4f`;
- runtime readback showed the project-local Context7 MCP route visible through
  the ContextForge wrapper;
- guidance metadata readback found source-defined Context7 guidance for
  `context7-local-resolve-library-id` and `context7-local-query-docs`;
- first turn used Context7 resolve/query tools and surfaced practical
  project-docs-lookup guidance for OpenCode configuration questions;
- follow-up resumed the same Codex session and used Context7 query-docs to
  produce a docs-backed OpenCode config-file reading order.

## Semantic Evaluation

Initial UC11 semantic evaluation failed for both clients:

- OpenCode: FAIL, 62/100.
- Pi: FAIL, 65/100.

Those failures showed that the project-specific docs lookup guidance was not
being surfaced cleanly. OpenCode initially routed through OpenCode-native docs
behavior and web fetches. Pi initially reached Context7 tools but did not
surface project guidance before answering docs content.

After remediation, Pi evaluator agent `019ee401-e6f1-7d13-bad0-6d40e8efd806`
reviewed the Pi evidence.

Verdict:

- Pi: PASS, 90/100.
- Failure classification: none.

Evaluator findings:

- first turn used `cf_contextforge_guidance_lookup`;
- visible guidance was surfaced before docs content;
- follow-up used the selected Context7 projected tools;
- evidence kept project graph, target-client projection, visibility, and proof
  separate;
- no all-client readiness overclaim was made.

OpenCode required multiple remediation loops. The accepted evaluator agent
`019ee420-46a1-7c03-ad3a-87c85b01f061` reviewed the final OpenCode evidence.

Verdict:

- OpenCode: PASS, 88/100.
- Failure classification: none.

Evaluator findings:

- turn 1 surfaced plain guidance before docs content;
- turn 1 had `tool_event_count: 0`;
- turn 2 stayed in the same session and used Context7 resolve/query tools;
- extra follow-up helper, skill, and read events were route noise and not a
  semantic bypass because the final answer applied the surfaced guidance and
  used Context7 docs tooling;
- project graph, target-client projection, visibility, and proof remained
  distinct.

Initial Codex evaluator agent `019ee66b-5b78-7df2-b286-c642eef52604` reviewed
the first Codex evidence and returned PASS, 93/100, while flagging two
evidence weaknesses: no explicit post-setup home-reset explanation for Codex
and indirect guidance-readback evidence.

Codex remediation strengthened the runner and package:

- the runner now records a dedicated Context7 guidance metadata source readback
  from `scripts/register_tool_guidance.py`;
- the metadata declares that post-setup home-volume reset is not applicable for
  Codex because the authenticated compose service uses a local-only
  OAuth-preserving baseline image rather than a disposable mounted home volume;
- the package documents the same Codex authenticated-image boundary and the
  requirement to keep API-key environment variables empty.

Remediated Codex evaluator agent `019ee66f-975e-71f2-9437-e1bf0573dae6`
reviewed the accepted Codex evidence.

Verdict:

- Codex: PASS, 98/100.
- Failure classification: none.

Evaluator findings:

- setup/reset was adequate and preserved OAuth state through the authenticated
  image without using API-key auth;
- runtime visibility showed Context7 enabled through the ContextForge wrapper;
- project graph, Codex projection, target-client visibility, and proof remained
  separate;
- turn 1 resolved and queried OpenCode through Context7, then surfaced
  practical user-facing guidance;
- turn 2 resumed the same session and queried Context7 docs for OpenCode config
  files;
- no raw prompt/resource JSON, scoring criteria, helper payloads, onboarding
  restart, all-client readiness, or automatic-alignment overclaim appeared.

## Remediation Included

- Added UC11 package, runner, verifier wrapper, and evaluator package
  generation.
- Added UC11-specific semantic criteria to the shared structural verifier.
- Added Pi guidance lookup fallback for the project docs lookup capability when
  an approved Context7 route exists but no registered prompt/resource matches.
- Added OpenCode routing for project-docs-lookup guidance questions.
- Reworked OpenCode message transformation to mutate hook arrays in place with
  `splice`, because assignment to `output.messages` did not reliably control
  the live `opencode run` hook.
- Preserved standard OpenCode tools. No global tool disabling was used.
- Added Codex runner/verifier support for UC11 using the authenticated Docker
  baseline, explicit API-key env blanking, Codex session-id extraction, and
  target-client projection metadata.
- Added Codex guidance metadata readback and documented the authenticated-image
  home-reset boundary.

## Verification

Worker and controller verification covered:

```text
node --check docker/client-harness/config/opencode/plugins/contextforge-project-init.js
```

Result: pass.

```text
tsc --noEmit --target ES2022 --module NodeNext --moduleResolution NodeNext --skipLibCheck --types node pi-extensions/contextforge-global-shim/index.ts
```

Result: pass.

```text
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_contextforge_docker_harness -v
```

Result: 32 passed.

```text
run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_contextforge_docker_harness -v
```

Result: 36 passed.

```text
python3 -m py_compile docker/client-harness/scripts/run-use-case-11-dialogue.py docker/client-harness/scripts/verify-use-case-11-e2e-evidence.py tests/test_use_case1_e2e_gate.py scripts/codex_project_init_hook.py
```

Result: pass.

```text
run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_use_case1_e2e_gate.UseCase1E2EGateTests.test_use_case11_runner_and_verifier_support_codex tests.test_use_case1_e2e_gate.UseCase1E2EGateTests.test_use_case8_runner_and_verifier_support_codex tests.test_use_case1_e2e_gate.UseCase1E2EGateTests.test_use_case6_runner_and_verifier_support_codex -v
```

Result: 3 passed.

```text
git diff --check
```

Result: pass.

## Residual Risk

Non-blocking:

- Pi guidance lookup used a static fallback because no registered prompt or
  resource matched the project docs lookup request. The evaluator judged the
  user-facing interaction adequate, but registered guidance should be improved
  later if the product requires prompt/resource provenance.
- OpenCode turn 2 included extra helper, skill, and read events before Context7.
  The evaluator judged these as route noise rather than a bypass because turn 1
  guidance was clean and turn 2 used Context7 resolve/query tools before the
  final docs answer.
- The accepted OpenCode first-turn guidance is concise and does not explicitly
  name ContextForge in every sentence. It still satisfies the localized
  user-facing story by giving the project docs lookup workflow before docs
  content.
- The accepted Codex first-turn guidance names Context7 and uses the project
  docs route, but it could more explicitly say "ContextForge provides this
  route" and bound the claim to the current Codex/project session in visible
  prose. The evaluator judged this non-blocking.

## Boundary

This acceptance does not claim cross-client automatic service-set alignment,
all-client readiness, provider credential validity, backend restart behavior,
live ContextForge registry mutation, global client mutation, readiness report
completion, uncataloged service onboarding, or final handoff. Those remain
downstream or separate issue surfaces.
