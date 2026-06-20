# Pi Post-Reload Stale State / Raw Status Bug - 2026-06-20

## Observed

Immediately after ContextForge tool installation and a Pi `/reload`, Pi told
the user that the project state still showed `shim_activation_planned` and
`pending_reload`, even though the user had already issued reload.

User-observed transcript excerpt:

```text
Here's a summary of the available services and their tools:

1. context7 — context7-local-resolve-library-id, context7-local-query-docs
2. exa-search — web-search-exa, web-fetch-exa
3. github — search-repositories, list-issues, get-file-contents
4. mentality — mentality-governance-list, mentality-governance-read,
   governance_list, governance_read
5. playwright — list-tools, browser-snapshot
6. ssh-tmux — ssh-tmux-list-sessions, ssh-tmux-get-snapshot, list_sessions,
   get_snapshot
7. web-search — web-search, fetch-content

Note: The project state shows shim_activation_planned status for all services,
meaning you'll need to run /reload in Pi for these tools to become actively
available.

Reload was already issued

It appears the ContextForge tools are not yet active — the context7:canonical
service reports "not running," and the project state still shows
shim_activation_planned with pending_reload status. A full reload of the Pi
session (or a restart) is required before the newly installed ContextForge
tools register and become available for use.

After a successful reload, the tools listed above (context7, exa-search,
github, mentality, playwright, ssh-tmux, web-search) should become available.
```

## Why This Is A Bug

After installation and `/reload`, Pi should not continue to expose stale
`pending_reload` / `shim_activation_planned` state as though reload had not
happened.

The user-facing behavior is especially poor because it:

- repeats low-level helper/project-state status to the user;
- says reload is required after the user already reloaded;
- implies installed services are not usable without clearly distinguishing
  actual missing target-client tools from stale reload bookkeeping;
- exposes tool inventories and state labels as if they were ordinary user UX.

The ideal post-install/reload UX is that Pi either:

1. sees the newly installed ContextForge tools and answers normally using them;
2. gives a concise actionable reload/restart repair message if reload truly did
   not take effect; or
3. reports a precise client registration defect without raw helper JSON/status
   leakage.

## Expected Behavior

- After successful install, Pi tells the user the selected services are
  installed and that `/reload` or a new session is required, then stops.
- After `/reload`, Pi should not still surface `pending_reload` or
  `shim_activation_planned` as a normal user-facing status if the reload was
  actually observed.
- If the tools still are not registered after reload, Pi should state a concise
  client registration problem and provide the next practical action.
- Raw helper JSON/status terms such as `cf_project_init_list_capabilities`,
  `shim_activation_planned`, `pending_reload`, `next_turn`, or service-state
  internals should not be shown to ordinary users unless they explicitly ask
  for diagnostics.

## Investigation Scope

An active investigation agent should check whether similar post-install/reload
stale-state or raw helper/status leakage appears in other client types,
especially OpenCode and Codex.

The investigation should distinguish:

- Pi display/tool-detail behavior;
- helper public payload verbosity;
- stale project-state reload bookkeeping;
- real target-client tool registration failure;
- expected reload boundary versus repeated reload interrogation.

## Acceptance Criteria

- Reproduce or explain the Pi post-install `/reload` stale-state path.
- Identify whether the source is Pi prompt guidance, Pi shim reload-state
  stamping, helper readback semantics, or target-client tool registration.
- Add tests or harness coverage proving a successful reload does not continue
  to tell the user reload is pending.
- Ensure ordinary user-visible Pi replies avoid raw helper JSON/status leakage
  unless diagnostics are explicitly requested.
- Check OpenCode and Codex for analogous behavior and either include them in
  the fix or file/link client-specific follow-up issues.

## Related Context

- #290 fixed the earlier Pi Serena defer continuation/apply sequencing bug.
- The live #290 verifier still noted Pi visible placeholder/status polish as a
  residual quality issue.
- This bug is separate from service validation. It is about post-install reload
  UX, stale state, and user-visible raw helper/status exposure.

## Remediation Note - 2026-06-20

Bounded remediation changes:

- Pi shim activation now records project-init client reload acknowledgement
  during `session_start` and diagnostic Pi readback activation when the project
  state still has Pi reload pending.
- Helper readback now exposes a structured `current_session_boundary` and
  derived `target_client_user_state`, so normal user-visible readback can say
  reload is acknowledged without replaying raw labels such as
  `shim_activation_planned` or `pending_reload`.
- Raw diagnostic state remains available in structured fields for debugging;
  ordinary `assistant_visible_response` is intended to suppress internal status
  terms unless diagnostics are explicitly requested.

Source verification:

- `ProjectInitActivationWorkflowTests.test_pi_reload_acknowledgement_changes_normal_readback_contract`
  passed.
- `tests.test_project_init_activation_workflow -v`: 118 tests OK.
- `tests.test_project_init_scripts -v`: 104 tests OK.
- `node --check pi-extensions/contextforge-global-shim/index.ts` passed.
- `git diff --check` passed.

Live Pi Docker verification:

- Verifier: `codex-agent:019ee6e5-f391-7371-ab0c-78c8ce4efa7e`.
- Evidence root:
  `docker/client-harness/evidence/issue-292/pi-fix-verify/20260620T211931Z/`.
- Isolated run details: container `cf-issue292-pi-20260620t211931z`,
  home volume `cf-issue292-pi-home-20260620t211931z`, Pi session
  `issue292-pi-20260620T211931Z`.
- Prompt sequence: `hello`, `1`, `approve`, `/reload`,
  `what ContextForge tools are available?`.
- Result: PASS, 9/10. Before reload, project state still had
  `pending_reload` / `shim_activation_planned` as expected. `/reload` recorded
  `reload_acknowledged`. Post-reload text-mode output listed the available
  ContextForge `context7` tools cleanly without replaying `pending_reload`,
  `shim_activation_planned`, or a reload-required message.
- Text-mode output:
  `docker/client-harness/evidence/issue-292/pi-fix-verify/20260620T211931Z/logs/turn6-post-reload-tools-text.txt`.
- Final state:
  `docker/client-harness/evidence/issue-292/pi-fix-verify/20260620T211931Z/logs/state-after-reload-full.json`.

Residual risk:

- JSON-mode `cf_project_tool_availability` output still includes a proof caveat
  phrase for diagnostic/audit use. The ordinary text-mode Pi UX is clean, so
  this is not the stale reload defect, but it remains a possible helper-wording
  polish item if strict ordinary-output suppression is later applied to
  JSON-mode harness output too.
