#!/usr/bin/env python3
"""Idempotent managed-record helpers for the npm-stdio host substrate."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping


HOST_SERVICE_ID = "npm-stdio-host"
INDEX_SCHEMA_URI = "contextforge://control-plane/npm-stdio-host-index/v1"
INDEX_PATH = Path("server-instances") / HOST_SERVICE_ID / "index.json"


def stable_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def project_root_from_package(package: Mapping[str, Any]) -> Path:
    root = package.get("project_root")
    if not isinstance(root, str) or not root:
        raise RuntimeError("runtime/apply package project_root is required for npm-stdio host records")
    return Path(root).resolve(strict=False)


def install_contract(package: Mapping[str, Any]) -> Mapping[str, Any]:
    contract = package.get("install_artifact_contract")
    if not isinstance(contract, Mapping):
        raise RuntimeError("runtime/apply package is missing install_artifact_contract")
    return contract


def npm_record_artifact(package: Mapping[str, Any]) -> Mapping[str, Any]:
    contract = install_contract(package)
    artifacts = contract.get("artifacts")
    if not isinstance(artifacts, Mapping):
        raise RuntimeError("install_artifact_contract.artifacts is required")
    record = artifacts.get("npm_stdio_service_record")
    if not isinstance(record, Mapping):
        raise RuntimeError("install_artifact_contract.artifacts.npm_stdio_service_record is required")
    content = record.get("content")
    if not isinstance(content, Mapping):
        raise RuntimeError("npm_stdio_service_record.content is required")
    if content.get("host_service") != HOST_SERVICE_ID:
        raise RuntimeError(f"npm_stdio_service_record.host_service must be {HOST_SERVICE_ID}")
    return record


def record_path(package: Mapping[str, Any]) -> Path:
    root = project_root_from_package(package)
    artifact = npm_record_artifact(package)
    raw_path = artifact.get("path")
    if not isinstance(raw_path, str) or not raw_path:
        raise RuntimeError("npm_stdio_service_record.path is required")
    path = Path(raw_path)
    if not path.is_absolute():
        path = root / path
    resolved = path.resolve(strict=False)
    if root not in (resolved, *resolved.parents):
        raise RuntimeError(f"npm_stdio_service_record.path escapes project root: {raw_path}")
    if root / "server-instances" not in (resolved, *resolved.parents):
        raise RuntimeError(f"npm_stdio_service_record.path must be under server-instances: {raw_path}")
    return resolved


def index_path(project_root: Path) -> Path:
    return (project_root / INDEX_PATH).resolve(strict=False)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def relative_to_root(project_root: Path, path: Path) -> str:
    return str(path.resolve(strict=False).relative_to(project_root))


def empty_index() -> dict[str, Any]:
    return {"schema_uri": INDEX_SCHEMA_URI, "host_service": HOST_SERVICE_ID, "records": {}}


def load_index(project_root: Path) -> dict[str, Any]:
    path = index_path(project_root)
    if not path.exists():
        return empty_index()
    data = read_json(path)
    if not isinstance(data, dict):
        raise RuntimeError(f"npm-stdio host index is not a JSON object: {path}")
    if not isinstance(data.get("records"), dict):
        data["records"] = {}
    data.setdefault("schema_uri", INDEX_SCHEMA_URI)
    data.setdefault("host_service", HOST_SERVICE_ID)
    return data


def upsert_from_runtime_package(package: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    root = project_root_from_package(package)
    artifact = npm_record_artifact(package)
    content = dict(artifact["content"])
    service_binding = str(content.get("service_binding") or "").strip()
    if not service_binding:
        raise RuntimeError("npm_stdio_service_record.content.service_binding is required")
    path = record_path(package)
    idx_path = index_path(root)
    previous_record = read_json(path) if path.exists() else None
    previous_index = load_index(root) if idx_path.exists() else None
    digest = stable_digest(content)
    current_digest = stable_digest(previous_record) if isinstance(previous_record, Mapping) else ""
    action = "already_applied" if current_digest == digest else ("updated" if previous_record is not None else "created")
    write_json_atomic(path, content)

    index = load_index(root)
    index["records"][service_binding] = {
        "service_binding": service_binding,
        "record_path": relative_to_root(root, path),
        "content_digest": digest,
        "host_service": HOST_SERVICE_ID,
    }
    write_json_atomic(idx_path, index)
    result = {
        "action": action,
        "service_binding": service_binding,
        "record_path": str(path),
        "index_path": str(idx_path),
        "content_digest": digest,
        "mutation_performed": action != "already_applied",
    }
    rollback_token = {
        "project_root": str(root),
        "record_path": str(path),
        "index_path": str(idx_path),
        "previous_record": previous_record,
        "previous_index": previous_index,
        "service_binding": service_binding,
    }
    return result, rollback_token


def rollback_upsert(rollback_token: Mapping[str, Any]) -> dict[str, Any]:
    path = Path(str(rollback_token["record_path"]))
    idx_path = Path(str(rollback_token["index_path"]))
    previous_record = rollback_token.get("previous_record")
    previous_index = rollback_token.get("previous_index")
    actions: list[dict[str, Any]] = []
    try:
        if isinstance(previous_record, Mapping):
            write_json_atomic(path, dict(previous_record))
            actions.append({"target": str(path), "action": "restored_previous_record", "ok": True})
        elif path.exists():
            path.unlink()
            actions.append({"target": str(path), "action": "removed_created_record", "ok": True})
        if isinstance(previous_index, Mapping):
            write_json_atomic(idx_path, dict(previous_index))
            actions.append({"target": str(idx_path), "action": "restored_previous_index", "ok": True})
        elif idx_path.exists():
            index = read_json(idx_path)
            service_binding = str(rollback_token.get("service_binding") or "")
            if isinstance(index, dict) and isinstance(index.get("records"), dict):
                index["records"].pop(service_binding, None)
                if index["records"]:
                    write_json_atomic(idx_path, index)
                    actions.append({"target": str(idx_path), "action": "removed_created_index_entry", "ok": True})
                else:
                    idx_path.unlink()
                    actions.append({"target": str(idx_path), "action": "removed_empty_created_index", "ok": True})
        return {"ok": True, "actions": actions, "residual_cleanup_risk": ""}
    except Exception as exc:  # pragma: no cover - defensive report path
        actions.append({"target": str(path), "action": "rollback_failed", "ok": False, "error": str(exc)})
        return {"ok": False, "actions": actions, "residual_cleanup_risk": str(exc)}


def delete_service_record(project_root: str | Path, service_binding: str) -> dict[str, Any]:
    root = Path(project_root).resolve(strict=False)
    idx_path = index_path(root)
    index = load_index(root)
    entry = index.get("records", {}).pop(service_binding, None)
    actions: list[dict[str, Any]] = []
    if isinstance(entry, Mapping) and entry.get("record_path"):
        path = (root / str(entry["record_path"])).resolve(strict=False)
        if path.exists():
            path.unlink()
            actions.append({"target": str(path), "action": "removed_record", "ok": True})
    if index.get("records"):
        write_json_atomic(idx_path, index)
        actions.append({"target": str(idx_path), "action": "updated_index", "ok": True})
    elif idx_path.exists():
        idx_path.unlink()
        actions.append({"target": str(idx_path), "action": "removed_empty_index", "ok": True})
    return {"ok": True, "service_binding": service_binding, "actions": actions}


def view_service_record(project_root: str | Path, service_binding: str) -> dict[str, Any]:
    root = Path(project_root).resolve(strict=False)
    idx_path = index_path(root)
    index = load_index(root)
    entry = index.get("records", {}).get(service_binding)
    record: Any = None
    record_path_value = ""
    record_exists = False
    if isinstance(entry, Mapping) and entry.get("record_path"):
        path = (root / str(entry["record_path"])).resolve(strict=False)
        record_path_value = str(path)
        record_exists = path.exists()
        if record_exists:
            record = read_json(path)
    return {
        "ok": True,
        "service_binding": service_binding,
        "index_path": str(idx_path),
        "index_exists": idx_path.exists(),
        "index_entry": entry if isinstance(entry, Mapping) else None,
        "record_path": record_path_value,
        "record_exists": record_exists,
        "record": record,
        "mutation_performed": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    upsert = subparsers.add_parser("upsert", help="Create or converge a managed npm-stdio service record from a runtime package.")
    upsert.add_argument("--package-json", type=Path, required=True)
    delete = subparsers.add_parser("delete", help="Delete a managed npm-stdio service record by service binding.")
    delete.add_argument("--project-root", type=Path, required=True)
    delete.add_argument("--service-binding", required=True)
    view = subparsers.add_parser("view", help="Read a managed npm-stdio service record and index entry by service binding.")
    view.add_argument("--project-root", type=Path, required=True)
    view.add_argument("--service-binding", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "upsert":
        package = json.loads(args.package_json.read_text(encoding="utf-8"))
        result, _rollback_token = upsert_from_runtime_package(package)
    elif args.command == "delete":
        result = delete_service_record(args.project_root, args.service_binding)
    elif args.command == "view":
        result = view_service_record(args.project_root, args.service_binding)
    else:  # pragma: no cover - argparse enforces this
        raise RuntimeError(f"unsupported command: {args.command}")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
