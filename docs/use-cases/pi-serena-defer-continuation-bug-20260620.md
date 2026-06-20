# Pi Serena Defer Continuation Bug - 2026-06-20

Source transcript:
`docker/client-harness/workspace/pi-session-2026-06-20T20-32-11-574Z_019ee6bb-db36-730d-bf16-727f37de6882.html`

Reviewer: `codex-agent:019ee6bf-1163-7cc0-bb64-4e3d53d9bffc`

## Observed

In Pi session export
`pi-session-2026-06-20T20-32-11-574Z_019ee6bb-db36-730d-bf16-727f37de6882.html`,
project-init begins correctly but fails after the Serena follow-up.

Flow:

- `7544c1c7` / `2026-06-20T20:32:23.138Z`: Pi presents the ContextForge
  service menu.
- `cbd4d65a` / `20:32:45.153Z`: user selects `1,2,3,4,6,7,8,9`, including
  Serena.
- `4084e43a` / `20:32:52.570Z`: assistant emits visible internal narration,
  then calls direct fallback `cf_project_init_propose`.
- `a5ec693e` / `20:32:53.004Z`: helper returns Serena language/defer next
  turn, with `3` = defer.
- `c25f69ca` / `20:33:08.460Z`: user replies `3`.
- `8b9e91ae` and `f50fb8ae`: `cf_project_init_continue` returns the original
  service-selection menu twice instead of consuming the Serena defer answer.
- `f9a9dbfe`: assistant calls `cf_project_init_apply` with `dryRun:false`
  before explicit plan approval.
- `319224b9`: apply fails with `no cached project-init plan is available`.
- `753ae815` and `654d693e`: assistant exposes internal recovery/debug text.
- Final visible message `3aa7d64f` asks `Approve or decline?` after recovery,
  but the session never reaches installed/reload-required.

## Why This Is A Bug

UC1 Pi project-init should be a bounded package-install flow. It must not drift
into internal helper mechanics, fallback tool experimentation, or unapproved
apply calls.

This transcript shows at least two failures:

1. The normal continuation route does not preserve or consume the Serena defer
   response. A numeric `3` in the Serena language question should mean `defer`,
   not restart service selection.
2. Ordinary Pi flow exposes and uses fallback project-init tools. The assistant
   calls direct `cf_project_init_propose` and `cf_project_init_apply`, including
   an unapproved `dryRun:false` apply attempt.

The failure is pre-reload-boundary. This is not a post-install validation
overreach; install never succeeds.

## Expected Behavior

After the user selects services including Serena and then chooses `3` for
defer:

1. `cf_project_init_continue` consumes the Serena defer response exactly once.
2. The assistant shows the plan for selected non-Serena services and asks for
   explicit approval.
3. After approval, the helper applies the selected package once.
4. The assistant says only that selected ContextForge tools are installed and
   reload/new Pi session is required.
5. The flow stops. No validation, probing, reload interrogation, challenge
   mechanics, or internal helper narration.

## Evidence

Transcript:
`docker/client-harness/workspace/pi-session-2026-06-20T20-32-11-574Z_019ee6bb-db36-730d-bf16-727f37de6882.html`

Anchors:

- session id: `019ee6bb-db36-730d-bf16-727f37de6882`
- service menu: `7544c1c7`, `2026-06-20T20:32:23.138Z`
- user service selection: `cbd4d65a`, `20:32:45.153Z`
- Serena defer prompt: tool result `a5ec693e`, `20:32:53.004Z`
- user defer response: `c25f69ca`, `20:33:08.460Z`
- repeated continuation regression to service menu: `8b9e91ae`, `f50fb8ae`
- unapproved direct apply call: `f9a9dbfe`
- apply failure: `319224b9`, message `no cached project-init plan is available`
- internal narration leakage: `753ae815`, `654d693e`
- final prompt, no installed/reload boundary: `3aa7d64f`

Controller verification: decoded the HTML `session-data` base64 and confirmed
all listed anchors and the apply failure text are present in the export.

## Acceptance Criteria

- Pi `cf_project_init_continue` correctly consumes Serena language/defer
  replies and returns the next approval/install step.
- Numeric Serena option `3` maps to defer in the active Serena question context.
- Ordinary Pi project-init continuation does not expose or rely on direct
  fallback `propose`, `approve`, or `apply` tools.
- No `cf_project_init_apply` call can occur before explicit approval and a
  cached approved plan.
- Assistant emits no visible internal helper/debug/recovery narration during
  project-init.
- Successful apply ends with installed plus reload/new-session-required and
  then stops.

## Parent Context

This came from the issue workspace `cf-controlplane-issue-270-259-260`.
Related lanes include #247, #259, #260, #268, #270, and the ordinary
project-init/use-case SuperLoop.

## Residual Uncertainty

The transcript alone cannot prove whether the root cause is Pi prompt wording,
the `cf_project_init_continue` helper state machine, client transcript parsing,
or tool exposure policy. Strong follow-up evidence would be the helper's
persisted project-init state immediately before and after user reply `3`, plus
a minimal replay showing whether `cf_project_init_continue` can see the active
Serena question context.
