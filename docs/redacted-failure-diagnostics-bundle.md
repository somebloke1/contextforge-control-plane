# Redacted Failure Diagnostics Bundle

Issue: #189

`scripts/control_plane_redaction.py` exposes
`build_failure_diagnostics_bundle()` for failed add, repair, verify, and
activation flows. The bundle is a compact operator starting point, not a
runtime mutation, approval receipt, registry record, or readiness claim.

Use it when a helper or service-validation path fails and the next operator or
agent needs one redacted packet that names:

- service slug and canonical ContextForge service identity;
- registry id or virtual-server id when either id is known;
- transport path and bridge or transceiver reason;
- client visibility target;
- last probe command and result summary;
- failing call shape with secrets redacted;
- next safe diagnostic action.

The builder validates the workflow value, requires the core service, transport,
client, probe, failing-call, and next-action fields, and returns
`redaction_status: redacted`. It uses the same recursive redaction helpers as
the broader diagnostic bundle and rejects caller-supplied raw sensitive values
that remain in the result.

## Non-Actions

This bundle does not approve or perform ContextForge registry mutation, service
creation, bridge creation, Docker/container work, client/global config changes,
hook trust changes, helper apply/recovery changes, secret handling, or readiness
promotion. If a failure is later repaired, the repaired path still needs the
normal consent, trace, readback, and client-visible evidence for that layer.
