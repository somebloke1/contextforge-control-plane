# ContextForge Codex Wrapper Lifecycle Runbook

This runbook covers Codex stdio wrapper proliferation for the local
ContextForge gateway. It is evidence-first: capture state before cleanup, target
only the stale wrapper class, and do not restart ContextForge services or write
the ContextForge database for this issue.

## Diagnosis

Capture the live process, fd, cgroup, and socket state:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/diagnose_contextforge_wrappers.py process-report \
  > /tmp/contextforge-wrapper-process-report.json
```

Summarize counts:

```sh
.venv/bin/python - <<'PY'
import json
data = json.load(open("/tmp/contextforge-wrapper-process-report.json"))
print(json.dumps({
    "counts": data["counts"],
    "wrapper_counts_by_server_name": data["wrapper_counts_by_server_name"],
}, indent=2, sort_keys=True))
PY
```

New wrapper launches can appear in short bursts when Codex Desktop opens or
reloads MCP sessions. Treat immediate wrapper and `CLOSE-WAIT` counts as a
point-in-time snapshot, not as the terminal state. Re-run the process report
after the configured idle window, default 300 seconds, before deciding whether
wrappers are leaking. Healthy lifecycle evidence is bounded drain to zero stale
wrappers and zero wrapper-owned `CLOSE-WAIT` sockets without service restarts
or broad process cleanup.

Time the `mentality_governance_list` path without mutating ledgers:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/diagnose_contextforge_wrappers.py time-mentality-path \
  --repo /home/dgk/gdrive/__CMU/classes/00_MathFoundationsML \
  --timeout 20
```

Expected healthy timing shape is:

- `governance_registry.list_entries`: local Python call, usually sub-ms.
- `scripts/governance_mcp.py` stdio: process startup cost, usually hundreds of ms.
- `http://127.0.0.1:9100/mcp`: bridge call, usually tens of ms or lower.
- `http://127.0.0.1:4444/servers/<mentality_server_id>/mcp/`: ContextForge virtual server, usually tens of ms.
- `scripts/contextforge_mcp_wrapper.py mentality_server`: wrapper startup plus call, usually hundreds of ms.

## Interpretation

Codex Desktop owns stdio wrapper lifecycle. Stale wrappers seen under the Codex
Desktop app scope are not systemd units and are not owned by the ContextForge
gateway or backend services.

The old wrapper command line is:

```sh
/home/dgk/workspace/context-portal/.venv/bin/python -m mcpgateway.wrapper --timeout 120
```

That stock wrapper exits on stdin EOF, stdout failure, SIGINT, or SIGTERM. It
does not have a process idle timeout. New launches through
`scripts/contextforge_mcp_wrapper.py` add:

- structured start/stop/error logs on stderr;
- `CONTEXTFORGE_WRAPPER_SERVER_NAME` process attribution;
- `MCP_SERVER_URL` attribution without token logging;
- parent PID change shutdown;
- default stdin idle shutdown after 300 seconds;
- streamable-HTTP session header preservation;
- response-id-aware return from SSE/NDJSON streams.

Some Linux `/proc/<pid>/environ` views do not show environment updates made
after process start. The diagnostic script therefore reports wrapper
`server_name` from `CONTEXTFORGE_WRAPPER_SERVER_NAME` when visible and falls
back to the `scripts/contextforge_mcp_wrapper.py <server-name>` command-line
argument for current wrappers.

## Safe Cleanup

Only perform cleanup after reviewing the diagnostic report. The intended cleanup
target is exact old-style wrappers whose parent is the Codex Desktop runtime and
whose command line is `python -m mcpgateway.wrapper --timeout 120`.

Preview exact targets:

```sh
.venv/bin/python - <<'PY'
from pathlib import Path

for proc in sorted(Path("/proc").iterdir(), key=lambda p: int(p.name) if p.name.isdigit() else -1):
    if not proc.name.isdigit():
        continue
    pid = int(proc.name)
    try:
        cmd = proc.joinpath("cmdline").read_bytes().replace(b"\0", b" ").decode()
        status = proc.joinpath("status").read_text()
    except OSError:
        continue
    if " -m mcpgateway.wrapper --timeout 120" not in cmd:
        continue
    ppid = next((line.split()[1] for line in status.splitlines() if line.startswith("PPid:")), "?")
    print(pid, "ppid=" + ppid, cmd)
PY
```

With explicit user approval, terminate only those exact PIDs with SIGTERM:

```sh
kill -TERM <pid> <pid> ...
```

Then re-run `process-report` and verify:

- wrapper count drops to the expected current-session set;
- `CLOSE-WAIT` sockets to `127.0.0.1:4444` drop for terminated wrappers;
- ContextForge user units remain active;
- a fresh `time-mentality-path` call succeeds.

Do not use `pkill python`, do not kill by broad `mcpgateway` substring, and do
not restart `contextforge-gateway.service` or backend services unless later
evidence identifies a separate service-side fault.

## Stale Serena Test Units

The `contextforge-serena-context-portal.service` unit is the canonical Serena
backend for this repository; `context-portal` is the current compatibility slug
in that runtime identifier. Test units named
`contextforge-serena-test-new-proj-*.service` are disposable only after their
instance directories and target project paths are confirmed to be stale test
assets.

Evidence capture:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/inspect_stale_serena_test_units.py
systemctl --user --no-pager --plain list-units 'contextforge-serena-test*' 'contextforge*serena*'
find server-instances -maxdepth 2 -name instance.json -path '*serena-test*' -print
```

The inspector is read-only. It classifies canonical, project-scoped, and
`test-new-proj` Serena units, records that cleanup is not allowed from the
inspection step, and prints the explicit approval boundary for any later stop,
disable, unit-file removal, project-tree deletion, server-instance deletion, or
ContextForge registry cleanup.

With explicit user approval, stop stale test units first, then disable them:

```sh
systemctl --user stop contextforge-serena-test-new-proj-01-53f38d98c1fc.service
systemctl --user disable contextforge-serena-test-new-proj-01-53f38d98c1fc.service
```

Repeat per reviewed stale test unit. Do not stop
`contextforge-serena-context-portal.service` as part of test-unit cleanup.
