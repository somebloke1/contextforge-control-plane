#!/usr/bin/env python3
"""Extract readable HTML dialogue from code-assistant transcript exports.

This script performs deterministic structure extraction only. It summarizes
tool evidence without printing raw tool payloads and never judges dialogue
quality.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


VISIBLE_ROLES = {"user", "assistant"}
HIDDEN_ROLES = {"system", "developer", "tool"}
SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|password|secret|bearer)\s*[:=]\s*([^\s,;]+)"),
    re.compile(r"(?i)authorization\s*[:=]\s*bearer\s+([A-Za-z0-9._~+/=-]{16,})"),
    re.compile(r"\b(sk-[A-Za-z0-9_-]{16,})\b"),
]


@dataclass
class DialogueTurn:
    role: str
    text: str
    source: str
    line: int | None = None
    timestamp: str | None = None
    confidence: str = "high"


@dataclass
class ToolSummary:
    kind: str
    name: str
    source: str
    line: int | None = None
    timestamp: str | None = None
    status: str | None = None
    input_keys: list[str] | None = None
    output_chars: int | None = None
    arguments_chars: int | None = None
    truncated: bool | None = None
    note: str | None = None


@dataclass
class ExtractionResult:
    input_path: str
    detected_format: str
    turns: list[DialogueTurn]
    tool_summaries: list[ToolSummary]
    thinking_summaries: list[ToolSummary]
    hidden_counts: dict[str, int]
    warnings: list[str]


def redact(text: str) -> str:
    result = text
    for pattern in SECRET_PATTERNS:
        if pattern.groups >= 2:
            result = pattern.sub(lambda m: f"{m.group(1)}=[REDACTED]", result)
        else:
            result = pattern.sub("[REDACTED]", result)
    return result


def stable_slug(path: Path) -> str:
    digest = hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:10]
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "-", path.stem).strip("-") or "transcript"
    return f"{stem}-{digest}"


def parse_json_lines(path: Path) -> list[tuple[int, dict[str, Any]]]:
    records: list[tuple[int, dict[str, Any]]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            value = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            records.append((line_number, value))
    return records


def load_json_value(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return None


def detect_format(path: Path, requested: str) -> str:
    if requested != "auto":
        return requested
    if path.suffix.lower() == ".jsonl":
        records = parse_json_lines(path)
        sample = [record for _, record in records[:20]]
        if any(record.get("type") == "response_item" or "payload" in record for record in sample):
            return "codex"
        if any("sessionID" in record or record.get("type") in {"step_start", "tool_use", "text"} for record in sample):
            return "opencode"
    if path.suffix.lower() == ".json":
        value = load_json_value(path)
        if isinstance(value, dict) and any(key in value for key in ("messages", "sessionID", "parts", "mcp")):
            return "opencode"
    return "pi"


def text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                value = item.get("text") or item.get("content")
                if isinstance(value, str):
                    parts.append(value)
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(part for part in parts if part)
    if isinstance(content, dict):
        value = content.get("text") or content.get("content")
        return value if isinstance(value, str) else ""
    return ""


def summarize_keys(value: Any) -> list[str] | None:
    if isinstance(value, dict):
        return sorted(str(key) for key in value.keys())[:20]
    return None


def safe_len(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, str):
        return len(value)
    try:
        return len(json.dumps(value, ensure_ascii=False, sort_keys=True))
    except (TypeError, ValueError):
        return len(str(value))


def parse_codex(path: Path) -> ExtractionResult:
    turns: list[DialogueTurn] = []
    tools: list[ToolSummary] = []
    thinking: list[ToolSummary] = []
    hidden_counts: dict[str, int] = {}
    warnings: list[str] = []
    for line, record in parse_json_lines(path):
        timestamp = record.get("timestamp")
        record_type = str(record.get("type", "unknown"))
        payload = record.get("payload")
        if record_type != "response_item" or not isinstance(payload, dict):
            hidden_counts[record_type] = hidden_counts.get(record_type, 0) + 1
            continue
        payload_type = str(payload.get("type", "unknown"))
        if payload_type == "message":
            role = str(payload.get("role", "")).lower()
            text = redact(text_from_content(payload.get("content"))).strip()
            if role in VISIBLE_ROLES and text:
                turns.append(DialogueTurn(role=role, text=text, source="codex.message", line=line, timestamp=timestamp))
            else:
                hidden_counts[f"message.{role or 'unknown'}"] = hidden_counts.get(f"message.{role or 'unknown'}", 0) + 1
        elif payload_type == "function_call":
            name = str(payload.get("name") or "unknown_tool")
            tools.append(
                ToolSummary(
                    kind="call",
                    name=name,
                    source="codex.function_call",
                    line=line,
                    timestamp=timestamp,
                    arguments_chars=safe_len(payload.get("arguments")),
                    note="Arguments summarized by length only.",
                )
            )
        elif payload_type == "function_call_output":
            tools.append(
                ToolSummary(
                    kind="response",
                    name=str(payload.get("call_id") or "tool_response"),
                    source="codex.function_call_output",
                    line=line,
                    timestamp=timestamp,
                    output_chars=safe_len(payload.get("output")),
                    note="Output summarized by length only.",
                )
            )
        elif payload_type == "reasoning":
            thinking.append(
                ToolSummary(
                    kind="agent-side thinking",
                    name="codex reasoning",
                    source="codex.reasoning",
                    line=line,
                    timestamp=timestamp,
                    output_chars=safe_len(payload.get("summary") or payload.get("content") or payload.get("encrypted_content")),
                    note="Thinking/reasoning trace present. Content omitted because it is not user-visible dialogue.",
                )
            )
        else:
            hidden_counts[f"response_item.{payload_type}"] = hidden_counts.get(f"response_item.{payload_type}", 0) + 1
    if not turns:
        warnings.append("No visible Codex user/assistant messages were extracted.")
    return ExtractionResult(str(path), "codex", turns, tools, thinking, hidden_counts, warnings)


def parse_opencode(path: Path) -> ExtractionResult:
    turns: list[DialogueTurn] = []
    tools: list[ToolSummary] = []
    thinking: list[ToolSummary] = []
    hidden_counts: dict[str, int] = {}
    warnings: list[str] = []

    records = parse_json_lines(path) if path.suffix.lower() == ".jsonl" else []
    if not records and path.suffix.lower() == ".json":
        value = load_json_value(path)
        records = list(flatten_json_records(value))

    if not records:
        return parse_text_dialogue(path, "opencode")

    for line, record in records:
        timestamp = record.get("timestamp")
        record_type = str(record.get("type", "unknown"))
        part = record.get("part") if isinstance(record.get("part"), dict) else {}
        role = str(record.get("role") or part.get("role") or "").lower()
        text = record.get("text") or part.get("text")
        if record_type == "text" and isinstance(text, str) and text.strip():
            turns.append(DialogueTurn(role="assistant", text=redact(text.strip()), source="opencode.text", line=line, timestamp=str(timestamp)))
        elif role in VISIBLE_ROLES:
            extracted = redact(text_from_content(record.get("content") or part.get("content") or text)).strip()
            if extracted:
                turns.append(DialogueTurn(role=role, text=extracted, source="opencode.message", line=line, timestamp=str(timestamp)))
        elif record_type == "tool_use" or part.get("type") == "tool":
            state = part.get("state") if isinstance(part.get("state"), dict) else {}
            tools.append(
                ToolSummary(
                    kind="call-response",
                    name=str(part.get("tool") or record.get("tool") or "unknown_tool"),
                    source="opencode.tool",
                    line=line,
                    timestamp=str(timestamp),
                    status=str(state.get("status")) if state.get("status") is not None else None,
                    input_keys=summarize_keys(state.get("input")),
                    output_chars=safe_len(state.get("output")),
                    truncated=bool((state.get("metadata") or {}).get("truncated")) if isinstance(state.get("metadata"), dict) else None,
                    note="Tool input/output summarized; raw payload omitted.",
                )
            )
        elif record_type in {"reasoning", "thinking"} or part.get("type") in {"reasoning", "thinking"}:
            thinking.append(
                ToolSummary(
                    kind="agent-side thinking",
                    name=str(part.get("type") or record_type),
                    source="opencode.thinking",
                    line=line,
                    timestamp=str(timestamp),
                    output_chars=safe_len(record.get("text") or part.get("text") or record.get("content") or part.get("content")),
                    note="Thinking/reasoning trace present. Content omitted because it is not user-visible dialogue.",
                )
            )
        else:
            hidden_counts[record_type] = hidden_counts.get(record_type, 0) + 1

    if not turns:
        warnings.append("No visible OpenCode user/assistant messages were extracted from structured records.")
    return ExtractionResult(str(path), "opencode", turns, tools, thinking, hidden_counts, warnings)


def flatten_json_records(value: Any) -> Iterable[tuple[int, dict[str, Any]]]:
    if isinstance(value, dict):
        if any(key in value for key in ("type", "role", "part", "content", "text")):
            yield (None, value)  # type: ignore[arg-type]
        for key in ("messages", "parts", "events", "items"):
            child = value.get(key)
            if isinstance(child, list):
                for index, item in enumerate(child, 1):
                    if isinstance(item, dict):
                        yield (index, item)
    elif isinstance(value, list):
        for index, item in enumerate(value, 1):
            if isinstance(item, dict):
                yield (index, item)


ROLE_MARKER_RE = re.compile(r"^(?:#{1,6}\s*)?(?:\*\*)?\s*(User|Human|Assistant|Pi|Codex|OpenCode)\s*(?:\*\*)?\s*:?\s*$", re.I)
INLINE_ROLE_RE = re.compile(r"^(User|Human|Assistant|Pi|Codex|OpenCode)\s*:\s*(.*)$", re.I)


def normalized_role(label: str) -> str:
    lowered = label.lower()
    if lowered in {"user", "human"}:
        return "user"
    return "assistant"


def parse_text_dialogue(path: Path, detected: str) -> ExtractionResult:
    turns: list[DialogueTurn] = []
    tools: list[ToolSummary] = []
    thinking: list[ToolSummary] = []
    hidden_counts: dict[str, int] = {}
    warnings: list[str] = []
    current_role: str | None = None
    current_start: int | None = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal current_role, current_start, buffer
        text = redact("\n".join(buffer).strip())
        if current_role and text:
            turns.append(DialogueTurn(role=current_role, text=text, source=f"{detected}.text", line=current_start))
        current_role = None
        current_start = None
        buffer = []

    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for line_number, line in enumerate(lines, 1):
        marker = ROLE_MARKER_RE.match(line.strip())
        inline = INLINE_ROLE_RE.match(line.strip())
        if marker:
            flush()
            current_role = normalized_role(marker.group(1))
            current_start = line_number
            continue
        if inline:
            flush()
            current_role = normalized_role(inline.group(1))
            current_start = line_number
            if inline.group(2):
                buffer.append(inline.group(2))
            continue
        if current_role:
            if line.startswith("```") and "json" in line.lower():
                hidden_counts["fenced_json_blocks"] = hidden_counts.get("fenced_json_blocks", 0) + 1
            buffer.append(line)
    flush()

    if not turns and lines:
        turns.append(
            DialogueTurn(
                role="assistant",
                text=redact("\n".join(lines).strip()),
                source=f"{detected}.unmarked_text",
                line=1,
                confidence="low",
            )
        )
        warnings.append("Input had no explicit turn markers; preserved as one low-confidence assistant-visible block.")
    return ExtractionResult(str(path), detected, turns, tools, thinking, hidden_counts, warnings)


def parse_pi(path: Path) -> ExtractionResult:
    records = parse_json_lines(path) if path.suffix.lower() == ".jsonl" else []
    if not records or not any(isinstance(record.get("message"), dict) for _, record in records):
        return parse_text_dialogue(path, "pi")

    turns: list[DialogueTurn] = []
    tools: list[ToolSummary] = []
    thinking: list[ToolSummary] = []
    hidden_counts: dict[str, int] = {}
    warnings: list[str] = []

    for line, record in records:
        timestamp = record.get("timestamp")
        record_type = str(record.get("type", "unknown"))
        if record_type == "message" and isinstance(record.get("message"), dict):
            message = record["message"]
            role = str(message.get("role", "")).lower()
            if role == "toolresult":
                tools.append(
                    ToolSummary(
                        kind="response",
                        name=str(message.get("toolName") or "tool_result"),
                        source="pi.tool_result",
                        line=line,
                        timestamp=str(timestamp),
                        status="error" if message.get("isError") else "success",
                        output_chars=safe_len(message.get("content")),
                        note="Tool result summarized by status and output length only.",
                    )
                )
                continue

            if role == "assistant" and isinstance(message.get("content"), list):
                tool_call_found = False
                for item in message["content"]:
                    if isinstance(item, dict) and item.get("name") and "arguments" in item:
                        tool_call_found = True
                        tools.append(
                            ToolSummary(
                                kind="call",
                                name=str(item.get("name") or "tool_call"),
                                source="pi.tool_call",
                                line=line,
                                timestamp=str(timestamp),
                                arguments_chars=safe_len(item.get("arguments")),
                                note="Tool call summarized by name and argument length only.",
                            )
                        )
                if tool_call_found:
                    continue

            text = redact(text_from_content(message.get("content"))).strip()
            if role in VISIBLE_ROLES and text:
                turns.append(DialogueTurn(role=role, text=text, source="pi.message", line=line, timestamp=str(timestamp)))
            else:
                hidden_counts[f"message.{role or 'unknown'}"] = hidden_counts.get(f"message.{role or 'unknown'}", 0) + 1
            continue

        if record_type in {"thinking", "reasoning"}:
            thinking.append(
                ToolSummary(
                    kind="agent-side thinking",
                    name=record_type,
                    source="pi.thinking",
                    line=line,
                    timestamp=str(timestamp),
                    output_chars=safe_len(record.get("content") or record.get("message")),
                    note="Thinking/reasoning trace present. Content omitted because it is not user-visible dialogue.",
                )
            )
            continue

        if record_type == "custom_message":
            custom_type = str(record.get("customType") or "custom_message")
            display = bool(record.get("display"))
            if display:
                text = redact(text_from_content(record.get("content"))).strip()
                if text:
                    turns.append(
                        DialogueTurn(
                            role="assistant",
                            text=text,
                            source=f"pi.custom_message.{custom_type}",
                            line=line,
                            timestamp=str(timestamp),
                            confidence="medium",
                        )
                    )
                    continue
            if "tool" in custom_type.lower():
                tools.append(
                    ToolSummary(
                        kind="custom tool evidence",
                        name=custom_type,
                        source="pi.custom_message",
                        line=line,
                        timestamp=str(timestamp),
                        output_chars=safe_len(record.get("content")),
                        note="Custom Pi tool-related payload summarized by length only.",
                    )
                )
            else:
                hidden_counts[f"custom_message.{custom_type}"] = hidden_counts.get(f"custom_message.{custom_type}", 0) + 1
            continue

        hidden_counts[record_type] = hidden_counts.get(record_type, 0) + 1

    if not turns:
        warnings.append("No visible Pi user/assistant messages were extracted from structured records.")
    return ExtractionResult(str(path), "pi", turns, tools, thinking, hidden_counts, warnings)


def extract(path: Path, requested_format: str) -> ExtractionResult:
    detected = detect_format(path, requested_format)
    if detected == "codex":
        return parse_codex(path)
    if detected == "opencode":
        return parse_opencode(path)
    if detected == "pi":
        return parse_pi(path)
    raise ValueError(f"Unsupported format: {detected}")


def render_text_block(text: str) -> str:
    escaped = html.escape(text)
    return escaped.replace("\n", "<br>\n")


def render_html(result: ExtractionResult, title: str | None) -> str:
    page_title = title or f"Dialogue Extract: {Path(result.input_path).name}"
    generated = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    turn_count = len(result.turns)
    tool_count = len(result.tool_summaries)
    thinking_count = len(result.thinking_summaries)
    warning_count = len(result.warnings)
    hidden_count = sum(result.hidden_counts.values())
    source_path = html.escape(result.input_path)
    body_parts = [
        "<!doctype html>",
        "<html lang=\"en\">",
        "<head>",
        "<meta charset=\"utf-8\">",
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
        f"<title>{html.escape(page_title)}</title>",
        "<style>",
        CSS,
        "</style>",
        "</head>",
        "<body>",
        "<main>",
        f"<header><p class=\"eyebrow\">Transcript Narrative</p><h1>{html.escape(page_title)}</h1></header>",
    ]
    body_parts.append("<section class=\"panel dialogue\"><h2>Conversation</h2>")
    if result.turns:
        for index, turn in enumerate(result.turns, 1):
            role_class = "user" if turn.role == "user" else "assistant"
            body_parts.append(
                f"<article class=\"turn {role_class}\"><div class=\"turn-label\">"
                f"<span>{index}</span><strong>{html.escape(turn.role.title())}</strong></div>"
                f"<div class=\"turn-body\"><div class=\"text\">{render_text_block(turn.text)}</div></div></article>"
            )
    else:
        body_parts.append("<p class=\"empty\">No visible user/assistant turns were extracted.</p>")
    body_parts.append("</section>")
    body_parts.append("<section class=\"panel\"><h2>Agent-Side Thinking</h2>")
    body_parts.append("<p class=\"note\">Thinking or reasoning traces are marked here when present. Their content is omitted because it is not user-visible dialogue.</p>")
    if result.thinking_summaries:
        body_parts.append("<div class=\"tools thinking\">")
        for item in result.thinking_summaries:
            body_parts.append(render_tool(item))
        body_parts.append("</div>")
    else:
        body_parts.append("<p class=\"empty\">No thinking or reasoning traces were detected.</p>")
    body_parts.append("</section>")
    body_parts.append("<section class=\"panel\"><h2>Tool Evidence Summary</h2>")
    body_parts.append("<p class=\"note\">Tool calls and responses are summarized only. Full arguments, outputs, hidden reasoning, and raw JSON are intentionally omitted.</p>")
    if result.tool_summaries:
        body_parts.append("<div class=\"tools\">")
        for tool in result.tool_summaries:
            body_parts.append(render_tool(tool))
        body_parts.append("</div>")
    else:
        body_parts.append("<p class=\"empty\">No tool call or tool response summaries were extracted.</p>")
    body_parts.append("</section>")
    body_parts.append("<details class=\"panel details\"><summary>Extraction details</summary>")
    body_parts.append(f"<p class=\"source\">Raw transcript: <code>{source_path}</code></p>")
    body_parts.append(f"<p class=\"generated\">Generated: <time>{generated}</time></p>")
    body_parts.append("<section class=\"stats\" aria-label=\"Extraction summary\">")
    body_parts.append(stat("Visible turns", turn_count))
    body_parts.append(stat("Tool summaries", tool_count))
    body_parts.append(stat("Thinking traces", thinking_count))
    body_parts.append(stat("Hidden records", hidden_count))
    body_parts.append(stat("Warnings", warning_count))
    body_parts.append("</section>")
    if result.warnings:
        body_parts.append("<section class=\"warning\"><h2>Warnings</h2><ul>")
        for warning in result.warnings:
            body_parts.append(f"<li>{html.escape(warning)}</li>")
        body_parts.append("</ul></section>")
    if result.hidden_counts:
        body_parts.append("<section><h2>Hidden / Other Records</h2><table><thead><tr><th>Record type</th><th>Count</th></tr></thead><tbody>")
        for key, value in sorted(result.hidden_counts.items()):
            body_parts.append(f"<tr><td><code>{html.escape(key)}</code></td><td>{value}</td></tr>")
        body_parts.append("</tbody></table></section>")
    body_parts.append("</details>")
    body_parts.extend(["</main>", "</body>", "</html>"])
    return "\n".join(body_parts)


def stat(label: str, value: int) -> str:
    return f"<div class=\"stat\"><span>{value}</span><strong>{html.escape(label)}</strong></div>"


def metadata_line(source: str, line: int | None, timestamp: str | None, confidence: str | None = None) -> str:
    parts = [html.escape(source)]
    if line is not None:
        parts.append(f"line {line}")
    if timestamp:
        parts.append(html.escape(str(timestamp)))
    if confidence and confidence != "high":
        parts.append(f"confidence: {html.escape(confidence)}")
    return " | ".join(parts)


def render_tool(tool: ToolSummary) -> str:
    rows = [
        ("Kind", tool.kind),
        ("Name", tool.name),
        ("Source", metadata_line(tool.source, tool.line, tool.timestamp)),
    ]
    if tool.status:
        rows.append(("Status", tool.status))
    if tool.input_keys:
        rows.append(("Input keys", ", ".join(tool.input_keys)))
    if tool.arguments_chars is not None:
        rows.append(("Argument chars", str(tool.arguments_chars)))
    if tool.output_chars is not None:
        rows.append(("Output chars", str(tool.output_chars)))
    if tool.truncated is not None:
        rows.append(("Truncated", str(tool.truncated).lower()))
    if tool.note:
        rows.append(("Note", tool.note))
    row_html = "\n".join(f"<dt>{html.escape(label)}</dt><dd>{html.escape(value)}</dd>" for label, value in rows)
    return f"<article class=\"tool\"><dl>{row_html}</dl></article>"


CSS = """
:root {
  color-scheme: light;
  --bg: #f7f8fa;
  --panel: #ffffff;
  --ink: #17202a;
  --muted: #5b6675;
  --border: #d8dee8;
  --user: #0f6b6e;
  --assistant: #6f4e10;
  --tool: #364f7a;
  --thinking: #6f3f74;
  --warn: #8a4b00;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font: 16px/1.5 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
main {
  width: min(1120px, calc(100% - 32px));
  margin: 0 auto;
  padding: 32px 0 56px;
}
header { margin-bottom: 24px; }
h1 { margin: 0 0 10px; font-size: clamp(28px, 4vw, 46px); line-height: 1.08; letter-spacing: 0; }
h2 { margin: 0 0 16px; font-size: 22px; letter-spacing: 0; }
code { background: #edf1f5; padding: 2px 5px; border-radius: 4px; }
.eyebrow, .generated, .source, .note, .empty { color: var(--muted); }
.eyebrow { margin: 0 0 8px; font-weight: 700; text-transform: uppercase; font-size: 12px; letter-spacing: .08em; }
.source, .generated { margin: 6px 0; overflow-wrap: anywhere; }
.stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}
.stat, .panel {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 8px;
}
.stat { padding: 14px 16px; }
.stat span { display: block; font-size: 30px; font-weight: 800; line-height: 1; }
.stat strong { display: block; margin-top: 6px; color: var(--muted); font-size: 13px; }
.panel { padding: 20px; margin-top: 18px; }
.warning { border-color: #e3b26b; background: #fff8ed; color: var(--warn); }
details.panel summary {
  cursor: pointer;
  font-weight: 800;
  color: var(--muted);
}
details.panel[open] summary { margin-bottom: 14px; }
.turn {
  display: grid;
  grid-template-columns: 124px minmax(0, 1fr);
  gap: 16px;
  border-top: 1px solid var(--border);
  padding: 18px 0;
}
.turn:first-of-type { border-top: 0; padding-top: 0; }
.turn-label { display: flex; align-items: start; gap: 8px; color: var(--muted); }
.turn-label span {
  display: inline-grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  color: #fff;
  font-size: 13px;
  font-weight: 800;
  background: var(--assistant);
}
.turn.user .turn-label span { background: var(--user); }
.turn-label strong { padding-top: 2px; }
.turn-body { min-width: 0; }
.text {
  background: #fbfcfd;
  border-left: 4px solid var(--assistant);
  padding: 12px 14px;
  border-radius: 0 8px 8px 0;
  overflow-wrap: anywhere;
}
.turn.user .text { border-left-color: var(--user); }
.tools {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 12px;
}
.tool {
  border: 1px solid var(--border);
  border-left: 4px solid var(--tool);
  border-radius: 8px;
  padding: 12px 14px;
  background: #fbfcfd;
}
.thinking .tool { border-left-color: var(--thinking); }
dl { margin: 0; display: grid; grid-template-columns: 120px minmax(0, 1fr); gap: 6px 10px; }
dt { color: var(--muted); font-weight: 700; }
dd { margin: 0; overflow-wrap: anywhere; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 8px 10px; border-top: 1px solid var(--border); text-align: left; vertical-align: top; }
th { color: var(--muted); font-size: 13px; }
@media (max-width: 680px) {
  main { width: min(100% - 20px, 1120px); padding-top: 20px; }
  .panel { padding: 14px; }
  .turn { grid-template-columns: 1fr; gap: 8px; }
  dl { grid-template-columns: 1fr; }
}
"""


def write_outputs(result: ExtractionResult, output_dir: Path, write_json: bool, title: str | None) -> tuple[Path, Path | None]:
    output_dir.mkdir(parents=True, exist_ok=True)
    input_path = Path(result.input_path)
    slug = stable_slug(input_path)
    html_path = output_dir / f"{slug}.html"
    html_path.write_text(render_html(result, title), encoding="utf-8")
    json_path = None
    if write_json:
        json_path = output_dir / f"{slug}.dialogue.json"
        json_path.write_text(json.dumps(asdict(result), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return html_path, json_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract readable HTML dialogue from code-assistant transcripts.")
    parser.add_argument("transcripts", nargs="+", type=Path, help="Input transcript/export paths.")
    parser.add_argument("--format", choices=["auto", "pi", "opencode", "codex"], default="auto", help="Transcript format.")
    parser.add_argument("--output-dir", type=Path, default=Path("generated/transcript-extracts"), help="Directory for HTML and JSON outputs.")
    parser.add_argument("--json", action="store_true", help="Also write a normalized .dialogue.json sidecar.")
    parser.add_argument("--title", help="Optional HTML title. Used for a single input or as a prefix for multiple inputs.")
    args = parser.parse_args()

    failures = 0
    for input_path in args.transcripts:
        if not input_path.exists():
            print(f"ERROR missing input: {input_path}")
            failures += 1
            continue
        result = extract(input_path, args.format)
        title = args.title
        if title and len(args.transcripts) > 1:
            title = f"{title}: {input_path.name}"
        html_path, json_path = write_outputs(result, args.output_dir, args.json, title)
        print(
            json.dumps(
                {
                    "input": str(input_path),
                    "format": result.detected_format,
                    "html": str(html_path),
                    "json": str(json_path) if json_path else None,
                    "turns": len(result.turns),
                    "tool_summaries": len(result.tool_summaries),
                    "thinking_summaries": len(result.thinking_summaries),
                    "warnings": result.warnings,
                },
                sort_keys=True,
            )
        )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
