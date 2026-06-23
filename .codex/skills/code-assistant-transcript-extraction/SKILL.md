---
name: code-assistant-transcript-extraction
description: Extract highly readable HTML dialogue artifacts from Pi, OpenCode, or Codex code-assistant transcripts/session exports, preserving user/assistant-visible turns separately from summarized tool evidence and raw transcript paths.
---

# Code Assistant Transcript Extraction

Use this skill when a controller needs readable transcript evidence from Pi,
OpenCode, or Codex sessions. The output is for evidence packaging and
evaluator review, not semantic scoring.

## Core Rule

Separate visible dialogue from hidden/tool/raw evidence:

- user and assistant visible text belongs in the main dialogue timeline;
- thinking/reasoning traces, when present in exports, belong in an
  agent-side hidden thinking summary and must be clearly labeled as not visible
  user-facing dialogue;
- tool calls and tool responses belong in a compact evidence summary lane;
- raw transcript files stay where they are and are referenced by path;
- scripts may parse, segment, count, normalize, and summarize structure, but
  must not judge whether assistant prose satisfies a requirement.

Do not paste full tool-call arguments, full tool outputs, hidden reasoning, or
raw JSON streams into the HTML. If a reviewer needs raw evidence, link or cite
the original transcript path.

## Script

Run:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codex/skills/code-assistant-transcript-extraction/scripts/extract_dialogue.py \
  --format auto \
  --output-dir generated/transcript-extracts \
  --json \
  path/to/transcript.jsonl path/to/other-transcript.txt
```

If `.venv` is unavailable, use the worktree's approved Python runtime. The
script uses only the Python standard library.

Format selection:

- `auto`: detect Codex JSONL, OpenCode JSONL/JSON, or text/Markdown dialogue.
- `codex`: Codex Desktop/CLI session JSONL with `response_item` records.
- `opencode`: OpenCode JSONL event streams or JSON/Markdown exports.
- `pi`: native Pi JSONL session exports, Pi text captures, or Markdown dialogue
  extracts.

Outputs:

- one `.html` file per input transcript;
- optional `.dialogue.json` sidecar when `--json` is passed;
- both files go under `--output-dir`, which defaults to
  `generated/transcript-extracts/`.

## Expected Workflow

1. Preserve raw transcript/session exports in the existing evidence location.
2. Run `extract_dialogue.py` against those paths with the narrowest known
   `--format`; use `auto` only when the source is mixed or uncertain.
3. Review the HTML for structural extraction errors, especially on Pi text
   captures without explicit `User`/`Assistant` markers.
4. Hand the HTML plus raw transcript paths to the semantic evaluator. The HTML
   is an aid to review, not the acceptance oracle.

## Limitations

- Native Pi JSONL session exports are parsed from structured `message` records.
  Visible `user` and `assistant` message text becomes the conversation; tool
  call and result records are summarized without raw arguments or output.
- Pi plain-text captures are reliable only when turns are marked with labels
  such as `User`, `Assistant`, `Human`, or `Pi`. Unmarked Pi text output is kept
  as a low-confidence assistant-visible block.
- OpenCode and Codex export schemas drift. The script intentionally keeps
  unknown records out of visible dialogue and counts them as hidden/other
  evidence instead of guessing.
- Secret redaction is conservative and pattern-based. Keep raw files in
  ignored evidence paths and do not publish generated artifacts before review.
