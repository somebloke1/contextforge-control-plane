# Use Case 5h Package: exa-search Credential-Scoped Lifecycle

## Status

Queue state: selected after accepted UC1, UC2, UC3, UC4, UC7, UC5a, UC5b,
UC5c, UC5d, UC5e, UC5f, and UC5g.

Controller state: accepted source-level lifecycle slice.

Acceptance evidence:

- Corrected source evidence package:
  `docker/client-harness/evidence/use-case-5h/exa-search-lifecycle/exa-search-lifecycle-evaluation-package-20260620T033636Z.md`.
- Corrected source evidence transcript:
  `docker/client-harness/evidence/use-case-5h/exa-search-lifecycle/exa-search-lifecycle-use-case-5h-evidence-20260620T033636Z.md`.
- Corrected structural verifier:
  `docker/client-harness/evidence/use-case-5h/exa-search-lifecycle/exa-search-lifecycle-verifier-20260620T033636Z.json`,
  with failures `[]`.
- Non-Spark semantic evaluator Ptolemy
  (`019ee315-a08b-77d1-9d83-fe51c20d3ed2`) returned PASS, 100/100,
  with no fatal failures. Its only residual scorecard-weight concern was
  remediated in the runner before controller acceptance.

GitHub source: issue #261, "Decompose #247: exa-search service readiness and
apply proof."

Parent umbrella: issue #247, "Ordinary use case 05: Add a useful project
service with plan and approval."

Prerequisites:

- UC5a / #270 service localization taxonomy.
- UC5b / #259 helper-offered service readiness matrix.
- UC5c / #260 Context7 first service lifecycle proof.
- UC5d / #263 mentality repo-local/static lifecycle proof.
- UC5e / #264 OpenZeppelin shared-canonical lifecycle proof.
- UC5f / #266 ssh-tmux session-scoped lifecycle proof.
- UC5g / #265 Playwright session-scoped lifecycle proof.

Downstream slices: remaining #262, #267, #268 per-service readiness, #269
selection-shape validation, and #247 umbrella acceptance.

## Method Binding

This package localizes the reusable method in
`holistic_orchestrated_pipeline_spec.md`,
`docs/use-cases/dependency-mesh.md`, and
`docker/client-harness/DIALOGUE_EVALUATION_METHOD.md`.

UC5h is a source/docs/tests service-lifecycle slice. It proves the
`exa-search:credential_scoped` project-local plan/apply/readback substrate for
Pi and OpenCode. It does not prove the full #247 ordinary dialogue,
post-refresh target-client visibility, actual provider calls, provider
credential validity, internet search behavior, or Gemini/Exa runtime behavior.

## Ordering Rationale

`exa-search` is selected after Playwright because it is the narrowest remaining
credential-scoped service. It has fewer tools and a smaller mutation surface
than GitHub, and it is narrower than the multi-provider `web-search` service.
Serena remains later because project-scoped provisioning, language choice, and
LSP state are more dependent.

## Full Story

1. Refresh live GitHub issue/PR context for #247, #261, #259, #260, #263, #264,
   #265, #266, #270, and PR #271.
2. Preserve accepted lower-layer evidence from UC1, UC2, UC3, UC4, UC7, UC5a,
   UC5b, UC5c, UC5d, UC5e, UC5f, and UC5g.
3. Inspect the readiness matrix row for `exa-search` and confirm it is owned by
   #261, has taxonomy type `credential_scoped`, and carries credential/no-broad-
   probe boundaries.
4. Exercise source-level single-service lifecycle tests for Pi and OpenCode
   using a current-worktree venv.
5. For Pi, approve/apply `exa-search:credential_scoped` through the helper and
   assert: project state is written, no `opencode.json` is written,
   target-client status is installed, lifecycle activation is shared
   ContextForge service, tool policy is safe-call search/fetch only, no
   provider credential is written, and the flow stops at the Pi reload
   boundary.
6. For OpenCode, approve/apply `exa-search:credential_scoped` through the
   helper and assert: project state plus project-local `opencode.json` are
   written, target-client status is installed, lifecycle activation is shared
   ContextForge service, tool policy is safe-call search/fetch only, no
   provider credential is written, and the flow stops at the new-session
   boundary.
7. Assemble an evaluation package with issue context, artifacts, test output,
   structural verifier output, and scorecard.
8. Dispatch a non-Spark semantic evaluator to judge whether the evidence
   satisfies #261 and safely advances toward #247 without overclaiming.

## Terminal Boundary

UC5h ends when exa-search credential-scoped project-local lifecycle/apply proof
is accepted as a sufficient prerequisite for later #247 multi-service work. It
does not accept #247, #269, remaining services, actual post-refresh
target-client tool visibility, provider credentials, provider availability,
search result quality, or internet/Gemini/Exa runtime proof.

## Expected Artifact Story

- The readiness matrix identifies `exa-search` as credential scoped and routes
  it to #261.
- The source test covers both Pi and OpenCode lifecycle behavior.
- The helper mutates only approved project-local artifacts.
- Pi apply writes project state only and stops at reload-required.
- OpenCode apply writes project state plus project-local `opencode.json` and
  stops at new-session-required.
- No provider credential, API key, token, ignored `.env`, global client config,
  live ContextForge registry state, broad internet probe, direct provider call,
  or post-install search proof is created.
- Tool policy is safe-call search/fetch only and remains credential-scoped.
- Target-client status in project state is an install/binding state, not proof
  of post-refresh tool invocation.

## Deterministic Setup

Required setup for the source-evidence attempt:

```text
run/test-venvs/project-init-workflow/bin/python
```

The runner must execute from the current worktree and must not borrow a sibling
checkout venv.

## Step Criteria

This use case has no model-dependent target-client dialogue turn. The semantic
evaluator still must score the authored artifact and the total source evidence
package. Deterministic checks may validate command status, artifact presence,
JSON parseability, required structured fields, enum relationships, and test
results. They must not judge the meaning of prose.

### issue_context_refreshed (10 pts)

Expected: Evidence includes current issue/PR readback for #247, #261, #259,
#260, #263, #264, #265, #266, #270, and PR #271.

Fail if: package acceptance relies only on stale dependency-mesh text.

### readiness_matrix_binding (15 pts)

Expected: The matrix row for `exa-search` points to #261, has taxonomy type
`credential_scoped`, and carries no-secret/no-broad-probe/no-provider-
availability-overclaim boundaries.

Fail if: readiness is inferred from menu presence alone or the row does not
route to #261.

### pi_lifecycle_apply (15 pts)

Expected: The Pi source test proves approved `exa-search:credential_scoped`
apply writes only project state, records shared ContextForge service lifecycle,
marks the target-client layer installed, preserves safe-call search/fetch
policy, and stops at reload-required.

Fail if: Pi apply writes OpenCode config, global client config, trust state,
secrets, provider credentials, registry state, ignored `.env`, or a
post-install search result.

### opencode_lifecycle_apply (15 pts)

Expected: The OpenCode source test proves approved
`exa-search:credential_scoped` apply writes project state plus project-local
`opencode.json`, records shared lifecycle activation, preserves safe-call
search/fetch policy, marks OpenCode binding status, and stops at new-session-
required.

Fail if: OpenCode apply mutates global config, live ContextForge, secrets,
provider credentials, ignored `.env`, trust state, or a post-install search
result.

### credential_boundary (20 pts)

Expected: The service record remains honest that runtime proof is conditional
on scoped provider credentials and request arguments. Source apply must not
copy, print, invent, commit, or validate provider secrets.

Fail if: the package claims provider readiness, search result quality, Gemini
or Exa runtime success, or target-client search proof from source apply alone.

### source_boundary (10 pts)

Expected: The evidence is honest that UC5h is source/docs/tests lifecycle proof
only, not a target-client dialogue pass or post-refresh tool call.

Fail if: the package claims #247, #269, remaining services, provider runtime
success, credential validity, or tool-use success.

### deterministic_boundary (15 pts)

Expected: Deterministic tests and verifier remain structural and source-level;
semantic adequacy is judged by the evaluator.

Fail if: deterministic code scores prose meaning, uses regex/string matching as
a semantic gate, or replaces the evaluator.

## Acceptance Commands

```text
run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_exa_search_single_service_lifecycle -v
run/test-venvs/project-init-workflow/bin/python docker/client-harness/scripts/run-use-case-5h-exa-search-lifecycle.py
```

The runner produces source evidence, verifier JSON, evaluation-package
Markdown, and semantic-evaluator-ready criteria.

## Remediation Routing

- matrix row mismatch: repair `docs/contextforge-service-readiness-matrix.json`
  and rerun UC5b regression if semantics change materially;
- Pi lifecycle failure: repair helper/project-state binding behavior and rerun
  source tests;
- OpenCode lifecycle failure: repair project-local config planning/apply and
  rerun source tests;
- credential boundary failure: repair service policy and source behavior to
  preserve no-secret/no-provider-runtime-overclaim boundaries;
- target-client overclaim: revise state/readback wording and package criteria;
- deterministic prose gate: move checks to structured JSON and evaluator
  criteria;
- evaluator fails semantic adequacy: remediate source artifacts, rerun tests and
  source evidence package, then dispatch a new non-Spark evaluator.
