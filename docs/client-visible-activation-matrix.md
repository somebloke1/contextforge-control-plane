# Client-Visible Activation Matrix

Issue: #89

This matrix defines the expected ContextForge activation/readiness observable
for each currently supported client path. It exists to prevent agents from
judging Pi or OpenCode by Codex hook-banner behavior.

This is a source/docs/tests contract. It does not prove live runtime behavior
and does not authorize runtime, Docker, client-global, hook-trust, registry,
secret, project-init apply, Serena, or retired-checkout mutation.

Use `docs/readiness-claim-guardrails.md` when reporting activation or
validation state. Source readiness, backend readiness, ContextForge readiness,
and target-client readiness are separate claims.

## Matrix

| Client | Activation owner | Expected first-session or first-prompt observable | Explicit readback or invocation path | Missing banner classification | Validation surface |
| --- | --- | --- | --- | --- | --- |
| Codex | Project-local `.codex/config.toml`, project-local hooks, and `contextforge-helper` | Codex project context may show project-init hook/helper guidance after the project is trusted, reloaded, and opened from the approved root. | `codex -C /home/dgk/workspace/cf-controlplane mcp list --json`, project-local `contextforge-helper`, and Codex-visible helper/readback tools. | A missing Codex project hook after the approved Codex reload/trust boundary is a Codex activation problem, not evidence about Pi or OpenCode. | Codex project context plus legacy/live ContextForge read-only evidence only where explicitly labeled. |
| Pi | Global TypeScript extension shim plus `.project/context_forge_state.json` metadata | No Codex-style hook banner is expected. Pi should expose shim/helper tools and guidance through the Pi extension path. | `cf_project_init_*`, `cf_contextforge_pi_readback`, guidance lookup, and `cf_contextforge_pi_validate` through the Pi shim. | Missing a Codex hook banner is expected for Pi. Missing shim tools or guidance in an approved Pi session is the relevant failure. | Pi client Docker for development validation; host Pi global install/reload remains issue #3. |
| OpenCode | Project-local `opencode.json`, `.opencode/plugins/contextforge-project-init.js`, and container/local helper runtime | No Codex-style hook banner is expected. OpenCode should receive project-local plugin/helper behavior from its own configured surface. | `opencode mcp list`, the project-local `contextforge-helper` entry, and `scripts/opencode_project_init_hook.py` behavior where enabled by the fixture. | Missing a Codex hook banner is expected for OpenCode. Missing the helper MCP entry or project plugin behavior in an approved OpenCode session is the relevant failure. | OpenCode client Docker for development validation. |

## Evidence Boundaries

- Backend-only ContextForge health or registry readback is insufficient for a
  client-visible activation claim.
- #62 has reopened for Pi ordinary first-prompt evidence. Historical runtime
  evidence proved selected helper/shim paths, but current acceptance requires
  fresh target-client-visible evidence from the ordinary Pi/OpenCode baseline
  paths against a matching ContextForge surface.
- #62 does not prove host Pi global extension install/reload behavior, host
  OpenCode global config behavior, or Codex project hook activation.
- #3 remains the host Pi global shim install, reload, and live Pi readback
  track.
- Future Pi and OpenCode development validation should continue to use the
  isolated ContextForge dev Docker surface plus the matching client Docker
  foil unless a later approval names another surface.
- The legacy/live ContextForge surface is read-only comparison or operator
  evidence. It is not proof that dev Docker or client Docker flows work.

## Claim Rules

- Report readiness with the vocabulary from
  `docs/readiness-claim-guardrails.md`. Do not collapse `source_ready`,
  `backend_ready`, `contextforge_ready`, and `target_client_ready`.
- Claim `Codex active` only from Codex-visible project-local hook/helper/MCP
  readback after the approved Codex project boundary has been crossed.
- Claim `Pi active` only from Pi-visible shim/helper/guidance or validation
  readback. Do not require a Codex-style hook banner for Pi.
- Claim `OpenCode active` only from OpenCode-visible plugin/helper/MCP readback.
  Do not require a Codex-style hook banner for OpenCode.
- If a client has source fixtures but no current runtime/client evidence, state
  that the source path is prepared and runtime validation remains unproven.
- For #62-style Pi/OpenCode container claims, cite the client Docker runtime
  evidence and label the exercised surface. Do not generalize that evidence to
  host Pi global install/reload or Codex hook behavior.
- For service-specific validation, use
  `docs/safe-client-visible-validation-probes.md` to decide whether the service
  has a known safe target-client-visible probe, a conditional probe, or must
  remain skipped or presumed-working.

## Non-Actions

This matrix does not approve:

- starting, stopping, rebuilding, or deleting Docker containers;
- writing user-global Pi or OpenCode config;
- installing or reloading host Pi extensions;
- changing Codex hook trust/state;
- mutating ContextForge services, registry, systemd, processes, tokens, teams,
  prompts, resources, or databases;
- mutating runtime secrets, OAuth state, bearer tokens, or trust tokens;
- helper/project-init approve, apply, recovery, or validation-state mutation;
- Serena provisioning;
- `.project/context_forge_state.json` rewrites;
- mutation of the retired predecessor checkout.
