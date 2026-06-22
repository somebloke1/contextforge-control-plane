#!/usr/bin/env python3
"""Manage npm-stdio service processes inside the shared npm-stdio host."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

import npm_stdio_host_records


RUNTIME_SCHEMA_URI = "contextforge://control-plane/npm-stdio-host-runtime/v1"
SERVICES_ROOT = Path("server-instances") / npm_stdio_host_records.HOST_SERVICE_ID / "services"
NPM_STDIO_PORT_BASE = 20_000
NPM_STDIO_PORT_SPAN = 30_000
TRANSCEIVER_PYTHON = os.environ.get(
    "CONTEXTFORGE_TRANSCEIVER_PYTHON",
    "/opt/contextforge-transceiver-venv/bin/python",
)


def stable_digest(value: Any) -> str:
    return npm_stdio_host_records.stable_digest(value)


def service_slug(service_binding: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in service_binding.lower()).strip(".-")


def service_dir(project_root: Path, service_binding: str) -> Path:
    root = project_root.resolve(strict=False)
    path = (root / SERVICES_ROOT / service_slug(service_binding)).resolve(strict=False)
    if root not in (path, *path.parents):
        raise RuntimeError("service runtime directory escapes project root")
    return path


def runtime_state_path(project_root: Path, service_binding: str) -> Path:
    return service_dir(project_root, service_binding) / "runtime-state.json"


def endpoint_port(service_binding: str) -> int:
    digest = hashlib.sha256(service_binding.encode("utf-8")).hexdigest()
    return NPM_STDIO_PORT_BASE + (int(digest[:8], 16) % NPM_STDIO_PORT_SPAN)


def default_endpoint(service_binding: str) -> dict[str, Any]:
    port = endpoint_port(service_binding)
    return {
        "host": "0.0.0.0",
        "port": port,
        "container_url": f"http://npm-stdio-host:{port}/mcp",
        "streamable_http_url": f"http://npm-stdio-host:{port}/mcp",
        "sse_url": f"http://npm-stdio-host:{port}/sse",
    }


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def record_for_binding(project_root: Path, service_binding: str) -> tuple[dict[str, Any], Path]:
    view = npm_stdio_host_records.view_service_record(project_root, service_binding)
    if not view.get("record_exists"):
        raise RuntimeError(f"managed npm-stdio record is absent for {service_binding}")
    record = view.get("record")
    if not isinstance(record, dict):
        raise RuntimeError(f"managed npm-stdio record is not a JSON object for {service_binding}")
    return record, Path(str(view["record_path"]))


def package_install_spec(record: Mapping[str, Any]) -> str:
    package = str(record.get("package") or "").strip()
    if not package:
        raise RuntimeError("managed npm-stdio record package is required")
    version = str(record.get("version_policy") or "").strip()
    if version and version not in {"latest", "source-verified-or-pinned"} and not package.endswith(f"@{version}"):
        return f"{package}@{version}"
    return package


def stdio_command(record: Mapping[str, Any]) -> list[str]:
    stdio = record.get("stdio") if isinstance(record.get("stdio"), Mapping) else {}
    command = str(stdio.get("command") or "").strip()
    args = stdio.get("args")
    if not command:
        raise RuntimeError("managed npm-stdio record stdio.command is required")
    result = shlex.split(command)
    if isinstance(args, Sequence) and not isinstance(args, (str, bytes, bytearray)):
        result.extend(str(item) for item in args if str(item).strip())
    return result


def endpoint(record: Mapping[str, Any], service_binding: str) -> dict[str, Any]:
    raw = record.get("endpoint") if isinstance(record.get("endpoint"), Mapping) else {}
    merged = default_endpoint(service_binding)
    merged.update({key: value for key, value in raw.items() if value not in ("", None)})
    return merged


def process_cmdline(pid: int) -> str:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return ""
    return raw.replace(b"\x00", b" ").decode(errors="replace")


def pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def bridge_state_running(state: Mapping[str, Any] | None) -> bool:
    if not state:
        return False
    pid = int(state.get("pid") or 0)
    if not pid_running(pid):
        return False
    cmdline = process_cmdline(pid)
    if not cmdline:
        return False
    endpoint_value = state.get("endpoint") if isinstance(state.get("endpoint"), Mapping) else {}
    port = str(endpoint_value.get("port") or "")
    return "mcpgateway.translate" in cmdline and (not port or f"--port {port}" in cmdline)


def stop_pid(pid: int, *, timeout: float = 5.0) -> bool:
    if not pid_running(pid):
        return True
    os.kill(pid, signal.SIGTERM)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not pid_running(pid):
            return True
        time.sleep(0.1)
    if pid_running(pid):
        os.kill(pid, signal.SIGKILL)
    return not pid_running(pid)


def bridge_probe_host(host: str) -> str:
    return "127.0.0.1" if host in {"", "0.0.0.0", "::"} else host


def wait_for_bridge_endpoint(
    bridge_endpoint: Mapping[str, Any],
    process: subprocess.Popen,
    *,
    timeout: float = 10.0,
    interval: float = 0.1,
) -> dict[str, Any]:
    host = bridge_probe_host(str(bridge_endpoint.get("host") or "127.0.0.1"))
    port = int(bridge_endpoint["port"])
    deadline = time.time() + timeout
    attempts = 0
    last_error = ""
    while time.time() < deadline:
        attempts += 1
        if process.poll() is not None:
            raise RuntimeError(f"bridge process exited during readiness wait with code {process.returncode}")
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return {"ready": True, "host": host, "port": port, "attempts": attempts}
        except OSError as exc:
            last_error = str(exc)
            time.sleep(interval)
    raise RuntimeError(f"bridge endpoint did not become reachable at {host}:{port}: {last_error}")


def read_state(project_root: Path, service_binding: str) -> dict[str, Any] | None:
    path = runtime_state_path(project_root, service_binding)
    if not path.exists():
        return None
    data = read_json(path)
    return data if isinstance(data, dict) else None


def runtime_environment(record: Mapping[str, Any], runtime_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    package_bin = runtime_dir / "package" / "node_modules" / ".bin"
    env["PATH"] = f"{package_bin}{os.pathsep}{env.get('PATH', '')}"
    environment = record.get("environment") if isinstance(record.get("environment"), Mapping) else {}
    raw_values = environment.get("values") if isinstance(environment.get("values"), Mapping) else {}
    for key, value in raw_values.items():
        name = str(key).strip()
        if name and value is not None:
            env[name] = str(value)
    variables = environment.get("variables")
    if isinstance(variables, Sequence) and not isinstance(variables, (str, bytes, bytearray)):
        for item in variables:
            if not isinstance(item, Mapping):
                continue
            name = str(item.get("name") or item.get("key") or "").strip()
            if not name:
                continue
            secret = bool(item.get("secret") or item.get("is_secret") or item.get("isSecret"))
            value = item.get("value")
            if not secret and value is not None:
                env[name] = str(value)
    return env


def install_package(record: Mapping[str, Any], runtime_dir: Path, *, runner=subprocess.run) -> dict[str, Any]:
    package_spec = package_install_spec(record)
    package_dir = runtime_dir / "package"
    package_dir.mkdir(parents=True, exist_ok=True)
    install_digest = stable_digest({"package_spec": package_spec})
    marker = package_dir / ".contextforge-install-digest"
    if marker.exists() and marker.read_text(encoding="utf-8").strip() == install_digest:
        return {"action": "already_applied", "package_spec": package_spec, "install_digest": install_digest}
    package_json = package_dir / "package.json"
    if not package_json.exists():
        package_json.write_text('{"private":true,"type":"module","dependencies":{}}\n', encoding="utf-8")
    runner(
        ["npm", "install", "--prefix", str(package_dir), "--omit=dev", package_spec],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    marker.write_text(install_digest + "\n", encoding="utf-8")
    return {"action": "installed", "package_spec": package_spec, "install_digest": install_digest}


def launch_bridge(
    record: Mapping[str, Any],
    service_binding: str,
    runtime_dir: Path,
    *,
    popen=subprocess.Popen,
) -> dict[str, Any]:
    bridge_endpoint = endpoint(record, service_binding)
    port = int(bridge_endpoint["port"])
    env = runtime_environment(record, runtime_dir)
    cmd = [
        TRANSCEIVER_PYTHON,
        "-m",
        "mcpgateway.translate",
        "--stdio",
        shlex.join(stdio_command(record)),
        "--expose-sse",
        "--expose-streamable-http",
        "--host",
        str(bridge_endpoint.get("host") or "0.0.0.0"),
        "--port",
        str(port),
        "--logLevel",
        "info",
    ]
    log_path = runtime_dir / "bridge.log"
    log_handle = log_path.open("ab")
    process = popen(cmd, cwd=runtime_dir, stdout=log_handle, stderr=subprocess.STDOUT, start_new_session=True, env=env)
    time.sleep(0.2)
    try:
        if process.poll() is not None:
            raise RuntimeError(f"bridge process exited during startup with code {process.returncode}")
        readiness = wait_for_bridge_endpoint(bridge_endpoint, process)
    except Exception:
        log_handle.close()
        stop_pid(int(process.pid))
        raise
    log_handle.close()
    return {"pid": int(process.pid), "command": cmd, "log_path": str(log_path), "endpoint": bridge_endpoint, "readiness": readiness}


def record_port_conflicts(project_root: Path, service_binding: str, record: Mapping[str, Any]) -> list[dict[str, Any]]:
    desired_port = int(endpoint(record, service_binding)["port"])
    conflicts: list[dict[str, Any]] = []
    root = project_root.resolve(strict=False)
    records_root = root / "server-instances" / npm_stdio_host_records.HOST_SERVICE_ID / "services"
    for path in records_root.glob("*/runtime-state.json"):
        try:
            state = read_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(state, Mapping) or state.get("service_binding") == service_binding:
            continue
        raw_endpoint = state.get("endpoint") if isinstance(state.get("endpoint"), Mapping) else {}
        if int(raw_endpoint.get("port") or -1) == desired_port and bridge_state_running(state):
            conflicts.append({"service_binding": state.get("service_binding"), "port": desired_port, "pid": state.get("pid")})
    index = npm_stdio_host_records.load_index(root)
    for other_binding, entry in (index.get("records") or {}).items():
        if other_binding == service_binding or not isinstance(entry, Mapping):
            continue
        try:
            other_path = (root / str(entry["record_path"])).resolve(strict=False)
            other_record = read_json(other_path)
        except (KeyError, OSError, json.JSONDecodeError):
            continue
        if isinstance(other_record, Mapping):
            other_endpoint = endpoint(other_record, str(other_binding))
            if int(other_endpoint.get("port") or -1) == desired_port:
                conflicts.append({"service_binding": other_binding, "port": desired_port, "record_path": str(other_path)})
    return conflicts


def runtime_state(
    *,
    service_binding: str,
    record_path: Path,
    runtime_dir: Path,
    record: Mapping[str, Any],
    content_digest: str,
    install: Mapping[str, Any],
    bridge: Mapping[str, Any],
    action: str,
    mutation_performed: bool,
) -> dict[str, Any]:
    return {
        "schema_uri": RUNTIME_SCHEMA_URI,
        "service_binding": service_binding,
        "record_path": str(record_path),
        "runtime_dir": str(runtime_dir),
        "content_digest": content_digest,
        "record_snapshot": dict(record),
        "pid": bridge["pid"],
        "running": True,
        "install": dict(install),
        "endpoint": bridge["endpoint"],
        "bridge_command": bridge["command"],
        "log_path": bridge["log_path"],
        "action": action,
        "mutation_performed": mutation_performed,
    }


def restore_previous_runtime(
    previous_state: Mapping[str, Any],
    *,
    project_root: Path,
    service_binding: str,
    record_path: Path,
    runtime_dir: Path,
    runner=subprocess.run,
    popen=subprocess.Popen,
) -> dict[str, Any] | None:
    record = previous_state.get("record_snapshot") if isinstance(previous_state.get("record_snapshot"), Mapping) else None
    if not record:
        return None
    install = install_package(record, runtime_dir, runner=runner)
    bridge = launch_bridge(record, service_binding, runtime_dir, popen=popen)
    restored = runtime_state(
        service_binding=service_binding,
        record_path=record_path,
        runtime_dir=runtime_dir,
        record=record,
        content_digest=str(previous_state.get("content_digest") or stable_digest(record)),
        install=install,
        bridge=bridge,
        action="rollback_restored_previous_runtime",
        mutation_performed=True,
    )
    write_json_atomic(runtime_state_path(project_root, service_binding), restored)
    return restored


def apply_service(project_root: str | Path, service_binding: str, *, runner=subprocess.run, popen=subprocess.Popen) -> dict[str, Any]:
    root = Path(project_root).resolve(strict=False)
    record, record_path = record_for_binding(root, service_binding)
    if str(record.get("transport") or "").lower() != "stdio":
        raise RuntimeError("managed npm-stdio host only accepts stdio records")
    runtime_dir = service_dir(root, service_binding)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    desired_digest = stable_digest(record)
    previous_state = read_state(root, service_binding)
    if previous_state and previous_state.get("content_digest") == desired_digest and bridge_state_running(previous_state):
        previous_state["action"] = "already_applied"
        previous_state["record_path"] = str(record_path)
        previous_state["running"] = True
        previous_state["mutation_performed"] = False
        return previous_state
    conflicts = record_port_conflicts(root, service_binding, record)
    if conflicts:
        raise RuntimeError(f"managed npm-stdio endpoint port conflict for {service_binding}: {conflicts}")
    install = install_package(record, runtime_dir, runner=runner)
    stopped_previous = False
    if previous_state and previous_state.get("pid") and bridge_state_running(previous_state):
        stopped_previous = stop_pid(int(previous_state["pid"]))
    try:
        bridge = launch_bridge(record, service_binding, runtime_dir, popen=popen)
    except Exception as exc:
        restored = None
        if previous_state and stopped_previous:
            try:
                restored = restore_previous_runtime(
                    previous_state,
                    project_root=root,
                    service_binding=service_binding,
                    record_path=record_path,
                    runtime_dir=runtime_dir,
                    runner=runner,
                    popen=popen,
                )
            except Exception as restore_exc:
                raise RuntimeError(
                    "bridge launch failed and previous runtime restoration failed: "
                    f"{exc}; restore_error={restore_exc}"
                ) from exc
        raise RuntimeError(
            "bridge launch failed; previous runtime restored"
            if restored
            else f"bridge launch failed before any previous runtime could be restored: {exc}"
        ) from exc
    state = runtime_state(
        service_binding=service_binding,
        record_path=record_path,
        runtime_dir=runtime_dir,
        record=record,
        content_digest=desired_digest,
        install=install,
        bridge=bridge,
        action="updated" if previous_state else "created",
        mutation_performed=True,
    )
    write_json_atomic(runtime_state_path(root, service_binding), state)
    return state


def view_service(project_root: str | Path, service_binding: str) -> dict[str, Any]:
    root = Path(project_root).resolve(strict=False)
    record_view = npm_stdio_host_records.view_service_record(root, service_binding)
    state = read_state(root, service_binding)
    running = bridge_state_running(state)
    return {
        "schema_uri": RUNTIME_SCHEMA_URI,
        "service_binding": service_binding,
        "mutation_performed": False,
        "host_record": record_view,
        "runtime_state_path": str(runtime_state_path(root, service_binding)),
        "runtime_state": state,
        "running": running,
    }


def delete_service(project_root: str | Path, service_binding: str) -> dict[str, Any]:
    root = Path(project_root).resolve(strict=False)
    state = read_state(root, service_binding)
    actions: list[dict[str, Any]] = []
    if state and state.get("pid"):
        if bridge_state_running(state):
            ok = stop_pid(int(state["pid"]))
            actions.append({"action": "stop_bridge_process", "target": str(state["pid"]), "ok": ok})
        else:
            actions.append({"action": "stale_bridge_pid_not_running", "target": str(state["pid"]), "ok": True})
    runtime_dir = service_dir(root, service_binding)
    if runtime_dir.exists():
        shutil.rmtree(runtime_dir)
        actions.append({"action": "remove_runtime_dir", "target": str(runtime_dir), "ok": True})
    else:
        actions.append({"action": "runtime_dir_absent", "target": str(runtime_dir), "ok": True})
    return {
        "schema_uri": RUNTIME_SCHEMA_URI,
        "service_binding": service_binding,
        "mutation_performed": any(action["action"] != "runtime_dir_absent" for action in actions),
        "actions": actions,
        "running": False,
        "rollback_result": "passed" if all(action.get("ok") for action in actions) else "partial",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("apply", "view", "delete"):
        sub = subparsers.add_parser(name)
        sub.add_argument("--project-root", type=Path, required=True)
        sub.add_argument("--service-binding", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "apply":
        result = apply_service(args.project_root, args.service_binding)
    elif args.command == "view":
        result = view_service(args.project_root, args.service_binding)
    elif args.command == "delete":
        result = delete_service(args.project_root, args.service_binding)
    else:  # pragma: no cover
        raise RuntimeError(f"unsupported command: {args.command}")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
