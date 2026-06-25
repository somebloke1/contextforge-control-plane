#!/usr/bin/env python3
"""Observe the latest semantic/model-involved harness session.

The command stores discovery state in ``~/.sess-obs.json``.  Harness runners can
write a live ``sess-obs-stream.jsonl`` file; when that is unavailable this tool
falls back to completed ``turn-*.raw.txt`` evidence files.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

STATE_PATH = Path.home() / ".sess-obs.json"
EVIDENCE_ROOT = Path("docker/client-harness/evidence")
KNOWN_STORY_ROOT = EVIDENCE_ROOT / "known-service-management-state-story"
STREAM_NAME = "sess-obs-stream.jsonl"
SUPPORTED_CLIENTS = ("opencode", "pi", "codex")
LABELS = {"Prompt", "Assistant", "Thinking"}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_repo_path(path: str | Path) -> Path:
    p = Path(path).expanduser()
    if p.is_absolute():
        return p
    return repo_root() / p


def load_json_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def render_block(label: str, text: str) -> str:
    if label not in LABELS:
        raise ValueError(f"unsupported block label: {label}")
    return f"########## START {label} ##########\n\n{text}\n\n########## END {label} ##########\n\n"


def emit_block(label: str, text: str) -> None:
    if not text:
        return
    sys.stdout.write(render_block(label, text))
    sys.stdout.flush()


def latest_run_root(client_type: str | None = None) -> Path:
    roots: list[Path] = []
    search_clients = [client_type] if client_type else list(SUPPORTED_CLIENTS)
    for client in search_clients:
        if not client:
            continue
        client_root = resolve_repo_path(KNOWN_STORY_ROOT / client)
        if client_root.exists():
            roots.extend(path for path in client_root.iterdir() if path.is_dir())
    if not roots:
        raise FileNotFoundError("no semantic-test evidence run directories found")
    return max(roots, key=lambda path: (path.stat().st_mtime_ns, str(path)))


def client_from_run_root(run_root: Path) -> str:
    parent = run_root.parent.name
    return parent if parent in SUPPORTED_CLIENTS else "unknown"


def extract_session_id_from_text(text: str) -> str:
    patterns = [
        r'"session_id"\s*:\s*"([^"]+)"',
        r'"sessionID"\s*:\s*"([^"]+)"',
        r'"id"\s*:\s*"(service-state-[^"]+)"',
        r"\bses_[A-Za-z0-9_:-]+",
        r"\bservice-state-[A-Za-z0-9_.:-]+",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        return match.group(1) if match.groups() else match.group(0)
    return ""


def discover_run(run_root: Path) -> dict[str, Any]:
    run_root = run_root.resolve()
    client_type = client_from_run_root(run_root)
    summary_path = run_root / "run-summary.json"
    session_id = ""
    prompts: list[str] = []
    if summary_path.exists():
        try:
            summary = load_json_file(summary_path)
            session_id = str(summary.get("session_id") or "")
            prompts = [str(item) for item in summary.get("prompts", []) if isinstance(item, str)]
        except Exception:
            pass
    if not session_id:
        stream_path = run_root / STREAM_NAME
        if stream_path.exists():
            session_id = extract_session_id_from_text(stream_path.read_text(encoding="utf-8", errors="replace"))
    if not session_id:
        for raw in sorted(run_root.glob("turn-*.raw.txt")):
            session_id = extract_session_id_from_text(raw.read_text(encoding="utf-8", errors="replace"))
            if session_id:
                break
    return {
        "version": 1,
        "source_type": "semantic_test_session",
        "client_type": client_type,
        "session_id": session_id,
        "run_id": run_root.name,
        "output_root": str(run_root),
        "stream_path": str(run_root / STREAM_NAME),
        "summary_path": str(summary_path),
        "raw_glob": str(run_root / "turn-*.raw.txt"),
        "prompts": prompts,
        "last_offset": 0,
        "last_raw_files": [],
        "updated_at": utc_now_iso(),
    }


def load_state(path: Path) -> dict[str, Any]:
    try:
        state = load_json_file(path)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"state file missing: {path}; run `scripts/sess_obs.py refresh` first") from exc
    if not isinstance(state, dict):
        raise ValueError(f"state file must contain a JSON object: {path}")
    return state


def cmd_refresh(args: argparse.Namespace) -> int:
    run_root = resolve_repo_path(args.run_root) if args.run_root else latest_run_root(args.client_type)
    state = discover_run(run_root)
    write_json_atomic(args.state_path, state)
    print(json.dumps(state, indent=2, sort_keys=True))
    return 0


def parse_json_line(line: str) -> dict[str, Any] | None:
    line = line.strip()
    if not line.startswith("{"):
        return None
    try:
        value = json.loads(line)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def stringify_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                block_type = block.get("type")
                if block_type == "text":
                    parts.append(str(block.get("text") or ""))
                elif block_type == "thinking":
                    parts.append(str(block.get("thinking") or ""))
                elif block_type == "image":
                    parts.append(f"[{block.get('mimeType') or 'image'} image]")
            elif block:
                parts.append(str(block))
        return "\n".join(part for part in parts if part)
    return str(content)


def assistant_content_blocks(content: Any) -> Iterable[tuple[str, str]]:
    if isinstance(content, str):
        if content:
            yield "Assistant", content
        return
    if not isinstance(content, list):
        text = stringify_content(content)
        if text:
            yield "Assistant", text
        return
    assistant: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            if block:
                assistant.append(str(block))
            continue
        block_type = block.get("type")
        if block_type == "thinking":
            if assistant:
                yield "Assistant", "\n".join(part for part in assistant if part)
                assistant = []
            thinking = str(block.get("thinking") or "")
            if thinking:
                yield "Thinking", thinking
        elif block_type == "text":
            assistant.append(str(block.get("text") or ""))
    if assistant:
        yield "Assistant", "\n".join(part for part in assistant if part)


def blocks_from_event(event: dict[str, Any]) -> Iterable[tuple[str, str]]:
    event_type = event.get("type")
    if event_type in {"prompt", "assistant", "thinking"}:
        label = {"prompt": "Prompt", "assistant": "Assistant", "thinking": "Thinking"}[str(event_type)]
        text = str(event.get("text") or "")
        if text:
            yield label, text
        return

    # OpenCode --format json events.
    part = event.get("part")
    if isinstance(part, dict):
        part_type = part.get("type")
        if event_type == "text" or part_type == "text":
            text = str(part.get("text") or event.get("text") or "")
            if text:
                yield "Assistant", text
        elif part_type in {"thinking", "reasoning"}:
            text = str(part.get("text") or part.get("thinking") or "")
            if text:
                yield "Thinking", text
        return

    # Pi --mode json events. Use completed messages to avoid duplicate deltas.
    if event_type == "message_end":
        message = event.get("message")
        if not isinstance(message, dict):
            return
        role = message.get("role")
        if role == "assistant":
            yield from assistant_content_blocks(message.get("content"))
        elif role == "user":
            text = stringify_content(message.get("content"))
            if text:
                yield "Prompt", text


def iter_stdout_json_lines(raw_text: str) -> Iterable[str]:
    in_stdout = False
    for line in raw_text.splitlines():
        if line == "STDOUT:":
            in_stdout = True
            continue
        if line == "STDERR:":
            break
        if in_stdout and line.strip().startswith("{"):
            yield line


def prompt_for_turn(raw_path: Path, prompts: list[str]) -> str:
    match = re.search(r"turn-(\d+)\.raw\.txt$", raw_path.name)
    if match:
        index = int(match.group(1))
        if 1 <= index <= len(prompts):
            return prompts[index - 1]
    # Best effort for old evidence if no run-summary exists: pull the last shell-quoted
    # argument from COMMAND is brittle, so do not invent a prompt.
    return ""


def emit_raw_file(raw_path: Path, prompts: list[str]) -> None:
    prompt = prompt_for_turn(raw_path, prompts)
    if prompt:
        emit_block("Prompt", prompt)
    raw_text = raw_path.read_text(encoding="utf-8", errors="replace")
    seen: set[tuple[str, str]] = set()
    for line in iter_stdout_json_lines(raw_text):
        event = parse_json_line(line)
        if event is None:
            continue
        for label, text in blocks_from_event(event):
            key = (label, text)
            if key in seen:
                continue
            seen.add(key)
            emit_block(label, text)


def stream_from_raw_files(state: dict[str, Any], *, follow: bool, poll_seconds: float, state_path: Path) -> None:
    output_root = Path(str(state.get("output_root") or ""))
    if not output_root.exists():
        raise FileNotFoundError(f"output_root missing: {output_root}")
    prompts = [str(item) for item in state.get("prompts", []) if isinstance(item, str)]
    seen = set(str(item) for item in state.get("last_raw_files", []))
    while True:
        emitted = False
        for raw_path in sorted(output_root.glob("turn-*.raw.txt")):
            key = str(raw_path)
            if key in seen:
                continue
            emit_raw_file(raw_path, prompts)
            seen.add(key)
            emitted = True
            state["last_raw_files"] = sorted(seen)
            state["updated_at"] = utc_now_iso()
            write_json_atomic(state_path, state)
        if not follow:
            return
        if not emitted:
            time.sleep(poll_seconds)


def stream_from_jsonl(path: Path, state: dict[str, Any], *, follow: bool, poll_seconds: float, state_path: Path) -> None:
    offset = int(state.get("last_offset") or 0)
    with path.open("r", encoding="utf-8") as handle:
        if offset > 0:
            handle.seek(offset)
        while True:
            line = handle.readline()
            if not line:
                state["last_offset"] = handle.tell()
                state["updated_at"] = utc_now_iso()
                write_json_atomic(state_path, state)
                if not follow:
                    return
                time.sleep(poll_seconds)
                continue
            event = parse_json_line(line)
            if event is None:
                continue
            if event.get("session_id") and event.get("session_id") != state.get("session_id"):
                state["session_id"] = event.get("session_id")
            for label, text in blocks_from_event(event):
                emit_block(label, text)


def cmd_stream(args: argparse.Namespace) -> int:
    if args.latest:
        run_root = latest_run_root(args.client_type)
        state = discover_run(run_root)
    else:
        state = load_state(args.state_path)
    if state.get("source_type") != "semantic_test_session":
        raise ValueError("~/.sess-obs.json does not describe a semantic_test_session; run refresh")
    if args.from_start:
        state["last_offset"] = 0
        state["last_raw_files"] = []
    write_json_atomic(args.state_path, state)
    stream_path = Path(str(state.get("stream_path") or ""))
    if stream_path.exists():
        stream_from_jsonl(stream_path, state, follow=args.follow, poll_seconds=args.poll_seconds, state_path=args.state_path)
    else:
        stream_from_raw_files(state, follow=args.follow, poll_seconds=args.poll_seconds, state_path=args.state_path)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-path", type=Path, default=STATE_PATH, help="state file path (default: ~/.sess-obs.json)")
    sub = parser.add_subparsers(dest="command", required=True)

    refresh = sub.add_parser("refresh", help="discover latest semantic test run and update ~/.sess-obs.json")
    refresh.add_argument("--client-type", choices=SUPPORTED_CLIENTS, default=None)
    refresh.add_argument("--run-root", type=Path, default=None, help="specific evidence run directory")
    refresh.set_defaults(func=cmd_refresh)

    stream = sub.add_parser("stream", help="stream Prompt/Assistant/Thinking blocks")
    stream.add_argument("--latest", action="store_true", help="discover the latest run before streaming")
    stream.add_argument("--client-type", choices=SUPPORTED_CLIENTS, default=None, help="client filter for --latest")
    stream.add_argument("--from-start", action="store_true", help="ignore stored offsets and replay from the beginning")
    stream.add_argument("--no-follow", dest="follow", action="store_false", help="exit after current content is consumed")
    stream.add_argument("--poll-seconds", type=float, default=0.5)
    stream.set_defaults(func=cmd_stream, follow=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except BrokenPipeError:
        return 0
    except Exception as exc:  # noqa: BLE001 - CLI should report operational failures concisely.
        print(f"sess-obs: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
