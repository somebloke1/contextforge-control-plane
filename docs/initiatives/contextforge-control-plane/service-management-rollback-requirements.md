# Service Management Rollback Requirements

This document records the requirements reset for the ContextForge helper after
abandoning product-surface agent-guided onboarding of arbitrary new MCP
services.

## Status

Drafted through live operator dialogue. This document is intentionally updated
as decisions are made.

## Decision 1: Abandoned Product Scope

Agent-guided onboarding of unknown or new MCP services is fully abandoned from
ordinary product behavior.

The helper must not expose ordinary Pi, OpenCode, Codex, or other client flows
that ask a tested or user-facing assistant to research an unknown MCP service,
infer npm packages, determine transports, write Dockerfiles, create arbitrary
ContextForge registration JSON, or guide service creation from a URL/source
lead.

The replacement scope is management of known ContextForge service offerings.
The helper may still facilitate instantiation of known services when the
service offering declares that instantiation is part of its model.

Known service scope classes must include at least:

- `global`: one shared service instance or binding;
- `per_project`: a service instance or binding scoped to a project, as in the
  original Serena-style model;
- `per_user`: a service instance or binding scoped to a user or credential
  boundary.

## Decision 2: Service Source Of Truth

The source of truth for service offerings is the ContextForge registry/catalog
only.

The helper must not maintain a static local service offering list as product
truth. It must derive the available service menu and management options from
current ContextForge registry/catalog state, including service metadata needed
to distinguish global, per-project, and per-user service models.

Repo-local templates, generated fixtures, or historical service-onboarding
artifacts may support development or migration, but they are not authoritative
product input for what ordinary clients may offer.

## Decision 3: Offering And Instance Model

ContextForge must represent known service offerings independently from concrete
service instances.

A service offering is the catalog-level declaration that a known service exists
and may be used or instantiated. It carries metadata such as service identity,
scope model, user-facing description, whether instantiation is available, and
what scope input is required.

A service instance is the concrete realized service surface for the relevant
scope. For `per_project` services such as the original Serena model, each
project may require a separate instance to preserve project isolation. The
historical implementation may have represented those project-specific Serena
instances as uniquely named MCP servers or virtual servers; the exact
ContextForge representation must be confirmed from current implementation and
registry semantics before remediating code.

Some ContextForge records that appear as "services" to the helper may already
be scoped instances of an underlying service type. For example, if four
projects each have a separate Serena surface, ContextForge may expose four
project-specific MCP services, virtual servers, or equivalent records rather
than one abstract Serena type plus four child records. The helper must be able
to differentiate:

- service type/offering records;
- already-materialized scoped service instances;
- records that combine offering and instance semantics because of how
  ContextForge represents MCP services or virtual servers.

Therefore, not every helper-manageable service is "something to install" or
"something to instantiate." Some are already-instantiated project-specific or
user-specific service records that the helper should identify, manage, repair,
enable, disable, or remove according to their metadata and scope.

Not every non-global service requires a separate backend process or server
instance. Some services may use one shared service instance while receiving an
individuating, client-side-signaled request characteristic. For example,
`mentality` may be able to serve multiple projects from one service instance
when the current working directory or project path is supplied as request
context and used to select the project-local governance store.

The target model does not require a separate durable `client_binding` or
`client_projection` entity as a third layer. Client visibility/configuration may
still need to be generated or refreshed, but the durable service-management
model should first be expressed in terms of:

1. known ContextForge service offering;
2. concrete service instance or request-context isolation model.

## Decision 4: Initial Locality Assumption

The initial rollback version assumes the ContextForge server and ContextForge
helper run on the same system as the project workspaces they manage.

Under this assumption:

- a central MCP service such as `mentality` may access or write to the current
  project directory when the request supplies the required project context;
- the helper may instantiate project-scoped services such as `serena` under the
  central ContextForge-controlled directory structure;
- the helper does not need to solve arbitrary remote-client filesystem access,
  remote workspace mounting, or cross-host project path translation in the
  first rollback version.

Remote clients remain a later design concern. The v1 service-management helper
should not overgeneralize its model around arbitrary IP-addressed clients until
the local-central model is coherent, implemented, and tested.

## Decision 5: V1 Lifecycle Operations

The v1 helper must expose lifecycle operations for known ContextForge service
offerings under the local-central assumption.

Required operations:

- `list_offerings`: show known ContextForge service offerings and their scope
  model, including `global`, `per_project`, and `per_user`.
- `status`: for the current project/user/client context, report available
  offerings, whether a required project/user instance exists, whether the
  relevant service is running or reachable, and whether the current client
  requires reload.
- `instantiate`: for `per_project` or `per_user` offerings, create the required
  local-central instance under ContextForge-managed storage.
- `enable`: make a global/shared or already-instantiated service available to
  the current project/client configuration.
- `disable`: stop exposing a service to the current project/client while
  preserving backing instance state.
- `remove_instance`: delete a per-project or per-user instance. This operation
  must require explicit data-loss approval when service state would be
  destroyed.
- `repair`: reconcile a known offering or instance whose config, service
  record, runtime status, or client-visible configuration is broken.
- `reload_status`: report reload-needed and reload-complete state clearly,
  without reintroducing the abandoned validation ritual.

`disable` and `remove_instance` are distinct. `disable` is a visibility or
configuration operation that preserves state. `remove_instance` is a lifecycle
destruction operation and requires stronger approval boundaries.

## Decision 6: Known Service Offering Definition

A known service offering is any service represented in ContextForge with the
metadata required for helper management.

The helper must not rely on a repo-local hardcoded allowlist to decide which
services are known. A service becomes helper-manageable by being present in the
ContextForge registry/catalog with appropriate metadata, including its scope
model and lifecycle capabilities.

If a service is present in ContextForge but lacks the required helper metadata,
the helper may report it as present but not helper-manageable, and should
explain the missing metadata fields rather than inventing defaults.

## Decision 7: Allowed Mutation Surfaces

The helper may mutate all required state surfaces when the operation is for a
known service offering and the relevant approval boundary has been satisfied.

Allowed mutation surfaces include:

- project-local state, such as `.project/context_forge_state.json`,
  project-local helper metadata, and project-local generated client config;
- client-local configuration needed for Pi, OpenCode, Codex, or another
  supported client to load ContextForge-managed tools;
- ContextForge registry/catalog state, including virtual server associations,
  tool/server mappings, service instance records, and prompt/resource bindings;
- runtime or service state, including starting or restarting a known service
  instance, creating a per-project service home, or creating process/service
  configuration.

Mutation authority is operation-specific. For example, `enable` may write
project-local state and client-local configuration, while `instantiate` or
`repair` may also need ContextForge registry and runtime/service mutation.

Before mutation, the helper should provide a preview or change package that
names the operation, target service offering, target scope, affected surfaces,
approval requirement, expected reload impact, rollback behavior, and data-loss
risk.

## Decision 8: Required Helper Metadata

A ContextForge service is helper-manageable only when its registry/catalog
record supplies the metadata required for service management.

Required metadata:

- canonical service identity, such as `service_id` or canonical name;
- display name;
- description;
- `scope_model`, at least one of `global`, `per_project`, or `per_user`;
- `instance_model`, describing whether the service is represented as a shared
  global instance, separate service instance, virtual server, MCP server,
  request-context-isolated service, or another ContextForge-native pattern;
- `required_context`, such as project path, cwd, user identity, or credential
  reference when the scope or instance model requires it;
- `client_support`, describing supported clients or the client configuration
  strategy;
- `reload_required`, describing whether enable, disable, instantiate, repair,
  or remove operations require a client reload;
- health or readiness probe metadata sufficient for the helper to determine
  whether the service or instance is reachable.
- abstract agent-facing guidance;
- detailed agent-facing guidance available on demand.

Lifecycle capabilities do not need to be enumerated as required metadata for
the initial version. The helper should assume the standard lifecycle operations
are available for a helper-manageable service unless another declared service
property or operation-specific guard blocks them.

The following are not required service metadata for v1 helper manageability:

- a detailed state policy;
- a detailed approval policy.

The helper still must enforce operation-level approval boundaries from its own
rules, especially for mutation, data loss, and runtime/service changes.

## Decision 9: Required Agent Guidance

Every helper-manageable service must expose agent-facing guidance through
ContextForge metadata or ContextForge-bound prompt/resource records.

Required guidance layers:

- abstract guidance: compact proactive guidance suitable for initialization or
  service-list presentation, explaining what the service does, when to use it,
  and major constraints without flooding the assistant or user;
- detailed guidance: on-demand guidance the assistant can retrieve when it is
  about to use or manage the service and needs fuller tool, workflow, safety,
  state, or interpretation instructions.

The helper should not make ordinary users read the guidance as raw setup text.
It should supply or expose guidance in the appropriate agent-facing channel and
keep user-facing service management output concise.

## Decision 10: Simplified Authority Model

The rollback design assumes that an agent connecting to the helper is operating
on behalf of an admin-level user who is implicitly authorized to manage the
local ContextForge service environment.

The helper must still require confirmations for safety-sensitive operations so
that accidental or misunderstood changes are avoided. These confirmations are
ordinary operator confirmations, not strict client identity or secure
authorization proofs.

The prior client-security and validation machinery is out of scope for this
rollback direction. The helper should not require flows whose purpose is to
securely verify the client, challenge the client identity, require low-level
secret echoes, or prove that the assistant is authorized beyond the fact that
it is connected and the operator confirms the requested action.

Consequences:

- remove or disable client-verification rituals that do not directly prevent
  accidental mutation;
- prefer clear preview-and-confirm flows over security challenge flows;
- confirmations should name the target service, target scope, changed
  surfaces, reload impact, and data-loss risk;
- destructive operations still require explicit confirmation because they can
  cause loss or disruption, not because the helper is authenticating the user.

## Decision 11: User-Facing Service Presentation

The normal user-facing service list must be concise: one line per service.

Each line should include:

- service display name;
- one single-word status for the current project context;
- a succinct description.

Example shape:

```text
Context7 - Enabled - Library documentation lookup.
Serena - Available - Project-scoped code intelligence.
Mentality - Enabled - Project governance memory.
GitHub - Disabled - Repository and issue operations.
```

The helper may offer more detail, but should only provide expanded registry,
runtime, scope, metadata, guidance, JSON, or troubleshooting detail if the user
asks for it or affirms a prompt offering more information.

Normal service-list output must not expose low-level IDs, tokens, registry
records, tool-call internals, or configuration payloads.

## Decision 12: Simple Project Status Vocabulary

The service list should use a small single-word status vocabulary:

- `Available`: the service offering exists in ContextForge and can be installed
  or instantiated for the current project context.
- `Enabled`: the service has been installed, instantiated, or configured for
  the current project context.
- `Disabled`: the service is intentionally disabled for the current project or
  client context.

Services whose state is unknown should not be listed in the ordinary service
menu. Unknown or malformed records may appear in explicit diagnostics or
troubleshooting output, but not in the normal concise menu.

The helper should advise the user that reload is required after changes. It
should not maintain or expose a detailed reload finite-state-machine as an
ordinary user-facing concern.

If a service fails in a way that looks like a missed reload, the helper or
assistant should remind the user that a reload may be needed. It should not
micromanage, scrutinize, or block the user or client agent at every turn merely
because some state detail is not perfectly synchronized.

The design goal is to assist and enable the user and client agent, not to
interrogate or obstruct them.

## Decision 13: Simple User Action Vocabulary

The ordinary user-facing action vocabulary should stay simple:

- `list`
- `enable`
- `disable`
- `remove`
- `repair`
- `details`

The helper should avoid ordinary visible terms such as install, instantiate,
activate, bind, project, registry, virtual server, MCP server, or client
projection unless the user asks for technical details or troubleshooting.

`enable` is the normal visible action for making a service usable in the
current project context. Internally, `enable` may create a project-scoped or
user-scoped instance, update ContextForge records, update project-local state,
or update client configuration as required by the service metadata. The normal
user-facing flow should summarize this as enabling the service and advising a
reload after completion.

Example:

```text
Enable Serena?
This will prepare Serena for this project and update the client configuration.
Reload after it completes.
```

## Decision 14: Gate Philosophy

The only gates in the rollback helper are gates that help serve the user's
intent.

The helper should not add gates whose purpose is to block, interrogate, police,
or second-guess an authorized user or client agent. Gates exist to avoid
mishaps, clarify intent, preview meaningful consequences, and prevent
incoherent operations.

Examples of appropriate gates:

- ask for confirmation before changing service configuration;
- ask for confirmation before destructive removal;
- prevent removing or disabling a service that is not enabled or present in the
  relevant context;
- prevent enabling a service that lacks required helper metadata;
- prevent an operation when the target service cannot be identified;
- show a concise preview when the operation has meaningful side effects.

Examples of inappropriate gates:

- challenge-response rituals to prove client identity;
- asking the user to repeat low-level keys or hashes already generated by the
  helper;
- blocking normal progress because reload state is not perfectly modeled;
- forcing validation rituals after an operation has completed;
- requiring technical details when the user's request is clear and the helper
  can safely perform the intended action.

## Decision 15: Remove Confirmation

Destructive `remove` operations require typed-name confirmation.

When a remove operation may delete a project-scoped or user-scoped service
instance, persistent state, service home, service record, or equivalent durable
surface, the helper must ask the user to type the service display name or
canonical service name to confirm.

Example:

```text
Remove Serena from this project and delete its project-local state?
Type "Serena" to confirm.
```

This typed confirmation applies to destructive removal. It does not apply to
ordinary `disable`, which preserves backing state, nor to non-destructive
details, list, status, or repair-preview operations.

## Decision 16: Repair Behavior

`repair` is an optimistic enabling operation.

The helper should identify likely broken or missing pieces and offer to fix
them with ordinary confirmation. Repair is not a forensic investigation unless
the user asks for diagnostics.

When supported by service metadata and the local-central assumption, repair may
recreate missing project/client configuration, refresh ContextForge records,
restart known service instances, or regenerate the minimal state needed to make
the known service usable again.

Example:

```text
Repair Serena?
This will recreate missing project configuration and refresh the service record.
Reload after it completes.
```

Repair output should stay concise and action-oriented. Detailed diagnostics,
registry records, logs, and low-level config should be shown only when the user
asks for troubleshooting detail.

## Decision 17: V1 Client Scope

The initial rollback implementation should focus on Pi and OpenCode.

Codex support may follow after the Pi and OpenCode service-management flows are
coherent, implemented, and tested. Codex should not block the first rollback
slice unless a shared abstraction requires a small compatibility hook while
building Pi/OpenCode support.

## Decision 18: Pi Helper And Gateway Surface

The Pi coding assistant no longer has the ContextForge helper extension in the
current target state. The rollback implementation must restore the helper
extension for Pi before Pi can be considered ready for acceptance testing.

For MCP gateway access in Pi, prefer the `pi-mcp-adapter` extension because it
supports lazy loading of bridged MCP tools. A different Pi gateway surface is
allowed only if implementation evidence shows a concrete blocker and the
fallback is documented.

Before Pi acceptance work, disable the unrelated `telos` extension when Pi
supports disabling extensions through configuration. If Pi does not support a
clean disable operation, back up the `telos` extension state and remove it from
the test surface. `telos` is an artifact of a separate project and must not
participate in ContextForge helper acceptance evidence.

## Decision 19: Post-Rollback Acceptance

The rollback acceptance gate is not arbitrary-service onboarding proof.

Deterministic tests should cover service metadata structure, status/action
state transitions, JSON and config shape, command completion, and evidence
packaging. They may simulate ordinary user interaction patterns in code for
major action sequences, but they must not judge free-form assistant meaning
with string or regex matching.

Final user-value acceptance requires real Docker Pi and/or OpenCode target
client sessions using only the qwen 3.6 a3b tested-assistant model. These
sessions must verify, from the target assistant's perspective, that known
services are visible with the simple vocabulary and that enabled services are
actually usable. If one v1 client is temporarily blocked, the blocker must be
recorded and claims must be limited to the exercised client.

Acceptance containers must mount a valid client-scoped ContextForge credential
for the live gateway under test. A missing, stale, or wrong-gateway bearer
token invalidates target-client tool-use claims because wrappers may fail before
the tested assistant can see the enabled service tools.

No human simulator is required for the rollback helper. The acceptance flow
uses simple, standard prompts that exercise expected user actions and
sequences; semantic evaluator review may still be used for final human-facing
quality where needed.

## Decision 20: Obsolete Onboarding Work Disposition

Active work whose product direction is arbitrary-service onboarding, managed
npm-stdio onboarding, Time/Memory foil onboarding proof, simulated-human
onboarding semantic gates, or forced validation rituals is superseded by this
rollback unless explicitly retained as historical evidence or internal
development-only material.

Superseded work should be closed, hidden, retired, or rewritten so it does not
remain an attractive active roadmap path for future agents. Reusable code may
be salvaged only after it is reshaped around known ContextForge service
management.

## Decision 21: SuperLoop Stop Time And Successor Goal

The current autonomous rollback work window stops at `2026-06-25 05:49 CDT`.
At that time, stop starting new work and prepare a pause/wrap-up report unless
the user redirects.

The evolved SuperGoal created at the next work-series boundary must explicitly
carry the active stop time when a stop time exists. It must also preserve the
reproductive clause: the final task of every bounded work series is to
formulate and activate the evolved successor goal before starting the next
grouped sequence.

## Open Questions

The following decisions are still pending:

1. Whether per-project instantiated services should be represented as MCP
   servers, virtual servers, gateway service records, or another ContextForge
   native entity.
2. How request-context-isolated services declare required context such as
   project path, cwd, user identity, or credential boundary.
3. Which retained onboarding artifacts, if any, should remain accessible as
   historical/internal development-only material rather than being deleted.
4. Whether the first implementation slice should remove obsolete MCP tool
   names entirely or leave explicit tombstone responses that route assistants
   to known-service management.
