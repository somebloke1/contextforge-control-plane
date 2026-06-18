# cf-controlplane Serena Compatibility Readiness

Date: 2026-06-17

This note is part of issue #37 activation readiness. It does not provision
Serena, mutate live ContextForge, change global Codex config, alter systemd, or
edit the legacy `/home/dgk/workspace/legacy-controlplane-archive` checkout.

## Current State

`cf-controlplane` has project-local Codex activation evidence and the canonical
Serena source/manifest home is now present. Runtime/client-visible Serena
closure is still not complete. The readiness inspector derives the expected
canonical Serena identity from the current root:

```text
server-instances/serena-cf-controlplane-d46fe58a2a20
serena_cf_controlplane_d46fe58a2a20_server
serena:d46fe58a2a20
```

That canonical backend home exists on `dev-root`, and
`scripts/inspect_project_init_readiness.py --no-processes` reports
`canonical_instance_present` with no readiness warnings. Treat this as
canonical source/readiness evidence, not as runtime closure. #50 still owns
service ownership reconciliation, ContextForge virtual-server readback,
project-local Codex `serena` visibility, and target-client-visible validation.

The current runtime caveat is concrete: read-only verifier evidence shows port
9108 is open, but the canonical user unit is inactive and the listener is not
classified as the canonical manifest owner. Draft PR #73 adds verifier
diagnostics for that distinction.

The caller-owned Serena metadata under `.serena/project.yml` is not a
compatibility service slug. It should use the active project name
`cf-controlplane`; stale `project_name: "cf-controlplane"` values are now a
readiness concern in the dirty-checkout rebind preflight.

## Inspector Contract

`scripts/inspect_project_init_readiness.py` now reports:

- `activation_artifacts.serena_project_instance.expected` for the canonical
  `cf-controlplane` Serena identity;
- `activation_artifacts.serena_project_instance.legacy` for the compatibility
  `serena-cf-controlplane-d46fe58a2a20` tree;
- `activation_artifacts.serena_project_instance.readiness_decision` with
  `hard_requirement: true`;
- `activation_artifacts.compatibility_identifiers.references` with file-level
  `contextforge://cf-controlplane/` and `serena-cf-controlplane-d46fe58a2a20` references.

Use this readback to classify source readiness separately from runtime/client
validation. Do not treat a direct backend probe or open port as proof that the
ContextForge virtual server and project-local Codex Serena surface are ready.

## Approval Boundary

The next Serena implementation slice must reconcile and validate the existing
canonical instance without broad runtime mutation. It needs separate approval
before live registry, service, systemd, global client config, hook/trust,
process cleanup, or stale compatibility retirement. At minimum, closure needs:

- canonical unit/process ownership for the configured Serena port;
- ContextForge gateway and virtual-server readback for the canonical names;
- virtual-server tool filtering proof that scope-changing project activation is
  not exposed;
- project-local Codex `serena` visibility, or an explicit decision that Codex
  should not consume Serena directly;
- target-client-visible validation evidence.

## Evidence Command

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
  scripts/inspect_project_init_readiness.py \
  --project-root /home/dgk/workspace/cf-controlplane \
  --client-type codex \
  --no-processes \
  --pretty
```
