# ContextForge Service-Offering Metadata

Status: draft implementation contract for issue #389 Decision 2.

## Requirement

The helper's ordinary service discovery surface must be derived at runtime from
ContextForge registry/catalog records plus ContextForge-hosted helper metadata.
It must not derive the product service menu from repo-local code constants,
`server-instances/*/instance.json`, or client-local configuration.

Local files may seed or repair ContextForge records through an explicit operator
migration script. After migration, runtime helper discovery reads ContextForge.

## Storage

Store one JSON metadata document per helper-manageable service offering as a
ContextForge `Resource`.

Resource metadata:

- `uri`: `contextforge://control-plane/service-offerings/<offering-id>/v1`
- `name`: `service_offering_<offering-id>_v1`
- `title`: human title for operators
- `mimeType`: `application/json`
- `tags`: include `contextforge-service-offering` and `service-offering`
- `visibility`: public, unless a later access-control decision changes this
- `content`: JSON document described below

Concrete currently runnable offerings must name the ContextForge virtual server
by `runtime.server_id` and associate this resource with that server via
`associatedResources`. Server and gateway names are secondary diagnostics, not
primary identity. A future catalog record that describes an instantiable type
but not a current server instance may exist unassociated, but it is not an
active runtime offering until its lifecycle and instantiation contract
explicitly say so.

## Content Schema

Schema URI: `contextforge://schemas/service-offering/v1`

Required fields:

- `schema_uri`: exact schema URI above
- `metadata_version`: integer, starting at `1`
- `resource_uri`: the metadata resource URI
- `offering_id`: stable slug unique inside this ContextForge installation
- `service_family`: canonical service family slug, such as `context7`
- `display_name`: concise one-line name for user-facing menus
- `description`: concise one-line description for user-facing menus
- `aliases`: list of user input aliases accepted by helper lookup
- `scope_model`: one of `global`, `per_project`, `per_user`
- `instantiation_class`: generic lifecycle class, such as
  `shared_canonical`, `credential_scoped`, `session_scoped`,
  `static_repo_local`, or `instance_per_project`
- `binding`: object defining the project-state binding key
- `runtime`: object linking the offering to CF runtime records
- `helper`: object defining supported helper operations and required context
- `guidance`: object linking abstract and detailed usage guidance
- `lifecycle`: one of `active`, `retired`, `deprecated`
- `provenance`: object describing source and migration history

Recommended v1 extension fields for precise diagnostics and future instance
selection:

- `scope_type`: concrete isolation signal such as
  `provider_credential_scope`, `caller_supplied_local_repo`, or
  `single_workspace_code_intelligence`
- `instance_model`: concrete runtime/instance strategy; defaults to the
  instantiation class when no more specific model is declared

Runtime discovery must remain compatible with already-seeded v1 metadata that
omits these extensions and derive conservative display defaults from
`scope_model` and `instantiation_class`.

`binding` shapes:

```json
{"mode": "literal", "value": "context7:canonical"}
```

```json
{"mode": "project_hash_template", "template": "serena:{project_hash_12}"}
```

The helper may perform generic template expansion for documented placeholders
such as `{project_hash_12}`. It must not infer service-specific bindings from
server names, gateway names, tags, or repo-local manifests.

`runtime` fields:

- `server_id`: required for active concrete runtime offerings
- `server_name`: diagnostic readback aid
- `gateway_id` and/or `gateway_name`: runtime linkage or diagnostics
- `reload_required`: boolean
- `health`: optional read-only health hints

`helper` fields:

- `actions_supported`: subset of `list`, `enable`, `disable`, `remove`,
  `repair`, `details`
- `required_context`: structured hints such as project root, credential scope,
  request context, or session scope requirements
- `client_support`: per-client support hints for Pi, OpenCode, Codex, and
  future clients

The runtime descriptor emitted to the helper must preserve these nested helper
fields, `runtime.reload_required`, the guidance object, and the concrete
`scope_type`/`instance_model`; it must not silently replace them with empty
legacy top-level defaults.

`guidance` fields:

- `abstract_resource_uri` or `abstract_prompt_name`
- `detail_resource_uri` or `detail_prompt_name`
- The helper should surface abstract guidance proactively where appropriate and
  leave detailed guidance lazy.

## Runtime Retrieval

The helper runtime discovery algorithm is:

1. Authenticate to the active ContextForge server using the client-scoped env
   available to the helper process.
2. Read `/resources?include_inactive=true&limit=1000`.
3. Select only resources tagged `contextforge-service-offering` or
   `service-offering`.
4. For each selected resource, fetch `/resources/{id}` to obtain full content.
   Resource list rows are not authoritative for content completeness.
5. Parse and validate the JSON content shape.
6. Read `/servers?include_inactive=true&limit=1000` and
   `/gateways?include_inactive=true&limit=1000`.
7. Match active concrete metadata to runtime records by explicit
   `runtime.server_id`, then verify that the metadata resource ID is associated
   to that virtual server. Names may explain diagnostics but must not select
   the authoritative server when an ID is missing or mismatched.
8. Emit helper service rows only for valid active metadata records with a
   resolvable runtime record, unless a future instantiation-only contract
   explicitly permits a not-yet-created runtime.
9. Derive `Available`, `Enabled`, or `Disabled` from project state only after
   the offering identity and binding are obtained from metadata.

No fallback should create a product service offering from tag order, server
name, gateway name, local manifest content, or code constants.

If ContextForge cannot be read, fail visibly with
`contextforge_catalog_unavailable` and perform no project file changes.
Malformed collection/detail response shapes are catalog read failures, not
evidence for an empty catalog, and must use the same fail-visible outcome.

Invalid, ambiguous, or conflicting metadata is skipped with diagnostic evidence,
not converted into an inferred offering. Conflicts include duplicate
`offering_id`, duplicate expanded binding, more than one service-offering
resource associated to one concrete server, one active concrete metadata
resource associated to multiple concrete servers, invalid JSON, wrong
`schema_uri`, inactive lifecycle, disabled server, disabled gateway when a
gateway is identified, or a mismatch between `runtime.server_id` and server
association.

If project state contains an enabled/disabled service whose current CF metadata
has disappeared, the normal product menu must not resurrect it as a current
offering. A separate recovery/orphan surface may help clean stale project-local
exposure, but it must label that state as orphaned rather than available.

Enable, repair, disable, and remove must operate from the CF-derived service
descriptor. In particular, enable must not pass a bare binding string into a
path that re-resolves service identity from local manifests. The chosen
descriptor from server metadata is the service contract for the operation.

## Migration

Add an operator script that seeds or refreshes current service-offering metadata
into ContextForge resources and associates the resulting resource IDs to virtual
servers. That script may read `server-instances/*/instance.json` as a migration
input only.

The script must:

- require or report an explicit ContextForge target base URL and matching
  client-scoped env when operating on the 4445 development instance
- use ContextForge API routes, not direct database writes
- read live resources, servers, gateways, and associations during dry-run so
  create/update/association actions describe target state without mutation
- include every canonical service family represented by the intended catalog;
  current development scope includes Time and Chrome DevTools as well as the
  original nine offerings
- upsert resources by URI
- when a managed Resource's URI has drifted, identify it by the stable managed
  reserved name and update that Resource even when tags also drift; reject
  conflicting URI/name matches instead of creating a duplicate
- compare the complete managed resource contract (`uri`, names and description,
  MIME type, JSON content, tags, visibility, and owner) using the stock list and
  detail response shapes before deciding that an existing resource is unchanged
- preserve unrelated existing server tool/resource/prompt associations
- avoid printing secrets or reflecting HTTP response bodies in diagnostics
- fail visibly when a requested or canonical family has no usable migration seed
- report the selected target/env sources, API stage/path/outcome diagnostics,
  created, updated, unchanged, associated, skipped, and errored records
- support dry-run JSON output

## Tests

Deterministic tests must cover:

- service rows are produced from CF resource content, not local manifests
- tagged resources are fetched by `/resources/{id}` before parsing content
- CF servers without service-offering metadata are omitted from the product menu
- binding mismatches cannot silently report an enabled service as available
- literal and project-hash-template bindings produce expected project-state keys
- ContextForge catalog read failures return a fail-visible no-mutation result
- migration preserves existing server associations
- nested helper/runtime/guidance fields survive runtime discovery
- credential-scoped services are represented as per-user rather than global
- dry-run reads target state while performing no mutation
- all intended canonical service families are covered or fail visibly

Live acceptance still requires qwen-backed Pi and OpenCode runs after the
metadata move, but deterministic tests own only structure, state, and command
completion.
