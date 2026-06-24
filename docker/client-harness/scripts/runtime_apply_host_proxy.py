#!/usr/bin/env python3
"""Host-side runtime/apply proxy for Docker-isolated client harness sessions."""

from __future__ import annotations

import argparse
import copy
import http.server
import importlib.util
import json
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def host_gateway_runtime_apply_url(port: int) -> str:
    return f"http://host.docker.internal:{port}/runtime/apply"


def load_executor(repo_root: Path) -> Any:
    path = repo_root / "docker" / "contextforge-harness" / "scripts" / "apply_onboarding_runtime_package.py"
    spec = importlib.util.spec_from_file_location("contextforge_runtime_apply_proxy_executor", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load runtime executor at {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def map_client_path_to_host(value: str, *, client_root: str, host_root: Path) -> str:
    client_root = client_root.rstrip("/")
    if value == client_root:
        return str(host_root)
    prefix = client_root + "/"
    if value.startswith(prefix):
        return str(host_root / value.removeprefix(prefix))
    return value


def translate_package_paths_for_host(package: dict[str, Any], *, repo_root: Path, client_project_root: str = "/workspace") -> dict[str, Any]:
    translated = copy.deepcopy(package)
    if translated.get("project_root") == client_project_root:
        translated["project_root"] = str(repo_root)
    provision = translated.get("service_provision_plan")
    if isinstance(provision, dict) and isinstance(provision.get("x_backend_home"), str):
        provision["x_backend_home"] = map_client_path_to_host(
            provision["x_backend_home"],
            client_root=client_project_root,
            host_root=repo_root,
        )
    contract = translated.get("install_artifact_contract")
    artifacts = contract.get("artifacts") if isinstance(contract, dict) else None
    if isinstance(artifacts, dict):
        for artifact in artifacts.values():
            if isinstance(artifact, dict) and isinstance(artifact.get("path"), str):
                artifact["path"] = map_client_path_to_host(
                    artifact["path"],
                    client_root=client_project_root,
                    host_root=repo_root,
                )
    return translated


def npm_stdio_record_path(package: dict[str, Any]) -> str:
    contract = package.get("install_artifact_contract")
    artifacts = contract.get("artifacts") if isinstance(contract, dict) else None
    record = artifacts.get("npm_stdio_service_record") if isinstance(artifacts, dict) else None
    path = record.get("path") if isinstance(record, dict) else None
    if not isinstance(path, str) or not path:
        raise RuntimeError("runtime/apply package missing npm_stdio_service_record.path")
    return path


def client_instance_manifest_path(
    package: dict[str, Any],
    *,
    host_project_root: Path,
    client_project_root: str = "/workspace",
) -> Path:
    record_path = map_client_path_to_host(
        npm_stdio_record_path(package),
        client_root=client_project_root,
        host_root=host_project_root,
    )
    path = Path(record_path).resolve(strict=False).parent / "instance.json"
    root = host_project_root.resolve(strict=False)
    if root / "server-instances" not in (path, *path.parents):
        raise RuntimeError(f"client instance manifest path must be under project server-instances: {path}")
    return path


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def mirror_client_instance_manifest(
    *,
    original_package: dict[str, Any],
    executor_result: dict[str, Any],
    host_project_root: Path,
) -> dict[str, Any] | None:
    manifest_result = executor_result.get("service_instance_manifest")
    if not isinstance(manifest_result, dict):
        return None
    source_path = manifest_result.get("path")
    if not isinstance(source_path, str) or not source_path:
        return None
    source = Path(source_path).resolve(strict=False)
    if not source.exists():
        return {
            "action": "source_missing",
            "source_path": str(source),
            "path": str(client_instance_manifest_path(original_package, host_project_root=host_project_root)),
            "mutation_performed": False,
        }
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"managed instance manifest is not a JSON object: {source}")
    target = client_instance_manifest_path(original_package, host_project_root=host_project_root)
    previous = json.loads(target.read_text(encoding="utf-8")) if target.exists() else None
    action = "already_applied" if isinstance(previous, dict) and previous == payload else ("updated" if previous is not None else "created")
    if action != "already_applied":
        write_json_atomic(target, payload)
    return {
        "action": action,
        "source_path": str(source),
        "path": str(target),
        "service_binding": str(payload.get("service_binding") or ""),
        "mutation_performed": action != "already_applied",
        "claim_boundary": "Docker harness mirror of managed activation manifest into the tested client's project workspace",
    }


class RuntimeApplyProxy(http.server.BaseHTTPRequestHandler):
    server_version = "ContextForgeRuntimeApplyProxy/1.0"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/runtime/apply":
            self.send_json(404, {"ok": False, "error": "unknown runtime/apply proxy path"})
            return
        expected_auth = str(self.server.expected_authorization)  # type: ignore[attr-defined]
        if self.headers.get("Authorization") != expected_auth:
            self.send_json(401, {"ok": False, "error": "unauthorized runtime/apply proxy request"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            request = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            if not isinstance(request, dict):
                raise RuntimeError("runtime/apply proxy request must be a JSON object")
            package = request.get("package")
            target = request.get("target")
            if not isinstance(package, dict):
                raise RuntimeError("runtime/apply proxy request missing package object")
            if not isinstance(target, dict):
                raise RuntimeError("runtime/apply proxy request missing target object")
            executor = self.server.executor  # type: ignore[attr-defined]
            repo_root = self.server.repo_root  # type: ignore[attr-defined]
            host_project_root = self.server.host_project_root  # type: ignore[attr-defined]
            original_package = copy.deepcopy(package)
            package = translate_package_paths_for_host(package, repo_root=repo_root)
            with tempfile.NamedTemporaryFile("w", suffix="-runtime-apply-package.json", encoding="utf-8", delete=True) as handle:
                json.dump(package, handle)
                handle.flush()
                result = executor.run(
                    package_path=Path(handle.name),
                    upstream_url=str(target.get("upstream_url") or ""),
                    gateway_name=str(target.get("gateway_name") or "") or None,
                    server_name=str(target.get("virtual_server_name") or "") or None,
                    apply=bool(request.get("apply", True)),
                    base_url=str(request.get("base_url") or "http://127.0.0.1:4445"),
                    env_file=Path(str(request.get("env_file") or self.server.default_env_file)),  # type: ignore[attr-defined]
                    wait_attempts=int(request.get("wait_attempts") or 12),
                )
            if bool(request.get("apply", True)) and isinstance(result, dict):
                mirrored = mirror_client_instance_manifest(
                    original_package=original_package,
                    executor_result=result,
                    host_project_root=host_project_root,
                )
                if mirrored is not None:
                    result["client_service_instance_manifest"] = mirrored
            self.send_json(200, result)
        except Exception as exc:  # pragma: no cover - defensive runtime path
            failure_report = getattr(exc, "failure_report", None)
            body: dict[str, Any] = {"ok": False, "error": str(exc)}
            if isinstance(failure_report, dict):
                body["failure_report"] = failure_report
                self.send_json(200, body)
            else:
                self.send_json(500, body)

    def send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve(args: argparse.Namespace) -> int:
    if not args.expected_token:
        raise RuntimeError("--expected-token is required")
    repo_root = Path(args.repo_root).resolve()
    server = http.server.ThreadingHTTPServer((args.listen_host, args.port), RuntimeApplyProxy)
    server.expected_authorization = f"Bearer {args.expected_token}"  # type: ignore[attr-defined]
    server.repo_root = repo_root  # type: ignore[attr-defined]
    server.host_project_root = Path(args.host_project_root).resolve()  # type: ignore[attr-defined]
    server.executor = load_executor(repo_root)  # type: ignore[attr-defined]
    server.default_env_file = str(repo_root / "docker" / "contextforge-harness" / "env" / "contextforge.env")  # type: ignore[attr-defined]
    print(
        json.dumps(
            {
                "ready": True,
                "listen_host": args.listen_host,
                "port": args.port,
                "container_url": host_gateway_runtime_apply_url(args.port),
                "host_project_root": str(server.host_project_root),  # type: ignore[attr-defined]
                "repo_root": str(repo_root),
            },
            sort_keys=True,
        ),
        flush=True,
    )
    server.serve_forever()
    return 0


@dataclass
class RuntimeApplyHostProxy:
    port: int
    token: str
    process: subprocess.Popen[str]

    @property
    def container_url(self) -> str:
        return host_gateway_runtime_apply_url(self.port)

    def summary(self) -> dict[str, Any]:
        return {
            "surface": "host_runtime_apply_proxy",
            "container_url": self.container_url,
            "token_present": True,
            "token_value": "ephemeral_redacted",
            "credential_location": "runner_process_memory",
            "container_can_invoke_host_runtime_executor": True,
        }

    def stop(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)


def start_runtime_apply_host_proxy(
    *,
    script_path: Path,
    repo_root: Path,
    host_project_root: Path | None = None,
) -> RuntimeApplyHostProxy:
    port = free_local_port()
    token = "contextforge-runtime-apply-" + secrets.token_urlsafe(24)
    command = [
        sys.executable,
        str(script_path),
        "--serve-runtime-apply",
        "--listen-host",
        "0.0.0.0",
        "--port",
        str(port),
        "--repo-root",
        str(repo_root),
        "--host-project-root",
        str(host_project_root or repo_root),
        "--expected-token",
        token,
    ]
    process = subprocess.Popen(
        command,
        text=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stdout is not None
    deadline = time.time() + 10
    while time.time() < deadline:
        line = process.stdout.readline()
        if line:
            data = json.loads(line)
            if data.get("ready"):
                return RuntimeApplyHostProxy(port=port, token=token, process=process)
        if process.poll() is not None:
            stderr = process.stderr.read() if process.stderr is not None else ""
            raise RuntimeError(f"runtime/apply host proxy exited early: {stderr}")
        time.sleep(0.05)
    process.terminate()
    raise RuntimeError("runtime/apply host proxy did not become ready")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve-runtime-apply", action="store_true")
    parser.add_argument("--listen-host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[3]))
    parser.add_argument("--host-project-root", default="")
    parser.add_argument("--expected-token", default="")
    args = parser.parse_args()
    if not args.host_project_root:
        args.host_project_root = args.repo_root
    if args.serve_runtime_apply:
        return serve(args)
    parser.error("--serve-runtime-apply is required")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
