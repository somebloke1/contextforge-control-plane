# Use Case 5a Package: Service Localization Taxonomy

## Status

Queue state: selected after accepted UC1, UC2, UC3, UC4, and UC7.

Controller state: accepted for the current branch evidence set.

Acceptance report:
`run/holistic-orchestrator/reports/uc5a-controller-acceptance-20260620T020742Z.md`.

Accepted evidence:

The raw evidence paths below are local ignored artifacts; this package and the
linked GitHub issue/PR updates are the durable tracked summary.

- Source evidence:
  `docker/client-harness/evidence/use-case-5a/taxonomy/taxonomy-use-case-5a-evidence-20260620T020549Z.md`
- Evaluation package:
  `docker/client-harness/evidence/use-case-5a/taxonomy/taxonomy-evaluation-package-20260620T020549Z.md`
- Metadata:
  `docker/client-harness/evidence/use-case-5a/taxonomy/taxonomy-metadata-20260620T020549Z.json`
- Structural verifier:
  `docker/client-harness/evidence/use-case-5a/taxonomy/taxonomy-verifier-20260620T020549Z.json`
- Semantic evaluator: Feynman `019ee2c7-39b9-7180-8664-df756f2e9168`,
  PASS 99/100.

GitHub source: issue #270, "Define service localization taxonomy for #247
readiness."

Parent umbrella: issue #247, "Ordinary use case 05: Add a useful project
service with plan and approval."

Adjacent slices: #259 readiness matrix, #260 Context7 first single-service
lifecycle, #269 selection-shape validation.

## Method Binding

This package localizes the reusable method in
`holistic_orchestrated_pipeline_spec.md`,
`docs/use-cases/dependency-mesh.md`, and
`docker/client-harness/DIALOGUE_EVALUATION_METHOD.md`.

UC5a is a development prerequisite slice for UC5, not the full user-facing
service-selection dialogue. Its target surface is the taxonomy artifact that
later client dialogues use to avoid false activation claims. It therefore has
no Pi/OpenCode dialogue target in this slice. Acceptance requires current
source/tests evidence plus non-Spark semantic evaluation of the taxonomy and
matrix artifacts.

## Full Story

1. Refresh live GitHub issue/PR context for #247, #270, #259, #260, and PR
   #271.
2. Preserve the accepted lower-layer evidence from UC1, UC2, UC3, UC4, and UC7.
3. Inspect the current taxonomy and readiness artifacts:
   - `docs/contextforge-service-localization-taxonomy.md`;
   - `docs/contextforge-service-localization-taxonomy.json`;
   - `docs/contextforge-service-readiness-matrix.json`;
   - `tests/test_service_readiness_matrix.py`.
4. Ensure the taxonomy defines the lifecycle/localization classes required by
   #270:
   - shared canonical service;
   - user-scoped or credential-scoped service;
   - project-scoped service instance;
   - session-scoped service;
   - repo-local/static service;
   - client-global bootstrap/hook/helper;
   - not-a-service menu option.
5. Ensure the taxonomy gives mapping rules for when to instantiate once, per
   user/credential, per project, per session, or not at all.
6. Ensure the taxonomy maps the current helper menu examples:
   `context7`, `exa-search`, `github`, `mentality`,
   `openzeppelin-solidity-contracts`, `playwright`, `ssh-tmux`, `web-search`,
   `serena`, and `None`.
7. Ensure the readiness matrix uses the structured taxonomy and can be consumed
   by #259, #260-#268, #269, and #247 without treating all services as the same
   readiness shape.
8. Run current-worktree tests that verify structured artifacts and matrix
   coverage. Deterministic tests may inspect JSON structure and enum/value
   relationships, but must not use string or regex matching over free-form
   prose as a semantic gate.
9. Assemble an evaluation package containing the source artifacts, test output,
   structural verifier output, and scorecard.
10. Dispatch a non-Spark semantic evaluator to judge whether the taxonomy
    satisfies #270 and safely supports #259/#247.

## Terminal Boundary

UC5a ends when the taxonomy artifact is accepted as a sufficient prerequisite
for readiness matrix work. It does not accept #247, #259, #260, #269, or any
Pi/OpenCode service-selection flow.

## Expected Artifact Story

- The taxonomy distinguishes service lifecycle/localization classes in a way
  agents can use before claiming readiness.
- The structured contract provides machine-readable type ids, instantiation
  rules, readiness evidence expectations, mapping rules, and menu examples.
- The Markdown doc remains a human-readable explanation, not the deterministic
  acceptance oracle.
- The readiness matrix points at the structured taxonomy contract.
- `None` remains a not-a-service user-flow option, not a service readiness
  surface.
- Client-global hooks/helpers remain separate from project service activation.
- Credential-scoped services do not claim readiness from secret presence alone.
- Session-scoped services do not use side effects as proof.
- Project-scoped services require project-root/instance identity.
- Repo-local/static services preserve repo governance boundaries.

## Deterministic Setup

Required setup for the source-evidence attempt:

```text
run/test-venvs/project-init-workflow/bin/python
```

The runner must execute from the current worktree and must not borrow a sibling
checkout venv.

## Venv Contract

Host-side source checks must run in a current-worktree runtime.

Current suite runtime:

```text
run/test-venvs/project-init-workflow/bin/python
```

Sibling checkout venvs are not valid acceptance evidence.

## Step Criteria

This use case has no model-dependent target-client dialogue turn. The semantic
evaluator still must score the authored artifact and the total source evidence
package. Deterministic checks may validate command status, artifact presence,
JSON parseability, required structured fields, enum relationships, and test
results. They must not judge the meaning of prose.

### issue_context_refreshed (10 pts)

Expected: Evidence includes current issue/PR readback for #247, #270, #259,
#260, and PR #271.

Fail if: package acceptance relies only on stale dependency-mesh text.

### structured_taxonomy_contract (20 pts)

Expected: A structured taxonomy contract exists and defines required types with
meaning, instantiation rule, and readiness evidence fields.

Fail if: the only gate is Markdown string matching, or required lifecycle types
are missing.

### menu_example_mapping (15 pts)

Expected: The structured taxonomy maps every current helper menu item and
classifies `None` as `not_a_service`.

Fail if: helper-offered services are omitted, conflated, or silently mapped to
generic service readiness.

### readiness_matrix_consumability (15 pts)

Expected: The readiness matrix points at the structured taxonomy contract and
uses taxonomy ids that exist in that contract.

Fail if: #259 cannot consume the taxonomy directly.

### architecture_boundary (15 pts)

Expected: The taxonomy preserves the distinction between service identity,
project-local binding, credential boundary, project instance, session runtime,
repo-local static source, client-global bootstrap, and not-a-service flow.

Fail if: client configs or helper hooks are treated as service identities, or
global/client-home mutation is implied as project service activation.

### evidence_requirements (15 pts)

Expected: Each type has readiness evidence expectations strong enough to
prevent #247 from claiming all-services success without per-service proof or an
explicit blocked/non-action result.

Fail if: backend health, direct bridge checks, credentials, or local files alone
can be mistaken for target-client readiness.

### deterministic_boundary (10 pts)

Expected: Deterministic checks remain structural and source-level; semantic
artifact adequacy is judged by the evaluator.

Fail if: deterministic code scores prose meaning, uses regex/string matching as
a semantic gate, or replaces the evaluator.

## Acceptance Commands

```text
run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_service_readiness_matrix -v
run/test-venvs/project-init-workflow/bin/python docker/client-harness/scripts/run-use-case-5a-taxonomy.py
```

The runner produces source evidence, verifier JSON, evaluation-package
Markdown, and semantic-evaluator-ready criteria.

## Remediation Routing

- missing taxonomy type: repair structured taxonomy and human doc, then rerun;
- menu mapping omission: repair structured taxonomy and readiness matrix, then
  rerun;
- matrix cannot consume taxonomy: repair matrix schema/linkage and tests;
- Markdown-only gate: move deterministic checks to structured JSON;
- taxonomy overclaims service readiness: repair type definitions and evidence
  expectations;
- package lacks issue context: refresh GitHub readback and rerun evidence
  assembly;
- evaluator fails semantic adequacy: remediate source artifact, rerun tests and
  source evidence package, then dispatch a new non-Spark evaluator.
