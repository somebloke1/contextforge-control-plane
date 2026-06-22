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
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

import npm_stdio_host_records


RUNTIME_SCHEMA_URI = "contextforge://control-plane/npm-stdio-host-runtime/v1"
SERVICES_ROOT = Path("server-instances") / npm_stdio_host_records.HOST_SERVICE_ID / "services"
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
    return 9300 + (int(digest[:4], 16) % 500)


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


def read_state(project_root: Path, service_binding: str) -> dict[str, Any] | None:
    path = runtime_state_path(project_root, service_binding)
    if not path.exists():
        return None
    data = read_json(path)
    return data if isinstance(data, dict) else None


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
    env = os.environ.copy()
    package_bin = runtime_dir / "package" / "node_modules" / ".bin"
    env["PATH"] = f"{package_bin}{os.pathsep}{env.get('PATH', '')}"
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
    if process.poll() is not None:
        log_handle.close()
        raise RuntimeError(f"bridge process exited during startup with code {process.returncode}")
    log_handle.close()
    return {"pid": int(process.pid), "command": cmd, "log_path": str(log_path), "endpoint": bridge_endpoint}


def apply_service(project_root: str | Path, service_binding: str, *, runner=subprocess.run, popen=subprocess.Popen) -> dict[str, Any]:
    root = Path(project_root).resolve(strict=False)
    record, record_path = record_for_binding(root, service_binding)
    if str(record.get("transport") or "").lower() != "stdio":
        raise RuntimeError("managed npm-stdio host only accepts stdio records")
    runtime_dir = service_dir(root, service_binding)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    desired_digest = stable_digest(record)
    previous_state = read_state(root, service_binding)
    if previous_state and previous_state.get("content_digest") == desired_digest and pid_running(int(previous_state.get("pid") or 0)):
        previous_state["action"] = "already_applied"
        previous_state["record_path"] = str(record_path)
        previous_state["running"] = True
        previous_state["mutation_performed"] = False
        return previous_state
    if previous_state and previous_state.get("pid"):
        stop_pid(int(previous_state["pid"]))
    install = install_package(record, runtime_dir, runner=runner)
    bridge = launch_bridge(record, service_binding, runtime_dir, popen=popen)
    state = {
        "schema_uri": RUNTIME_SCHEMA_URI,
        "service_binding": service_binding,
        "record_path": str(record_path),
        "runtime_dir": str(runtime_dir),
        "content_digest": desired_digest,
        "pid": bridge["pid"],
        "running": True,
        "install": install,
        "endpoint": bridge["endpoint"],
        "bridge_command": bridge["command"],
        "log_path": bridge["log_path"],
        "action": "updated" if previous_state else "created",
        "mutation_performed": True,
    }
    write_json_atomic(runtime_state_path(root, service_binding), state)
    return state


def view_service(project_root: str | Path, service_binding: str) -> dict[str, Any]:
    root = Path(project_root).resolve(strict=False)
    record_view = npm_stdio_host_records.view_service_record(root, service_binding)
    state = read_state(root, service_binding)
    running = bool(state and pid_running(int(state.get("pid") or 0)))
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
        ok = stop_pid(int(state["pid"]))
        actions.append({"action": "stop_bridge_process", "target": str(state["pid"]), "ok": ok})
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
