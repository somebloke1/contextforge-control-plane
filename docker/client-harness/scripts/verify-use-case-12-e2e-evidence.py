#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from dialogue_structural_verifier import verify_dialogue_structure


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify Use Case 12 evidence structure.")
    parser.add_argument("--client", choices=["pi", "opencode", "codex"], required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--session-id", default="")
    args = parser.parse_args(argv)

    result = verify_dialogue_structure(
        use_case="use-case-12",
        client=args.client,
        evidence_path=args.evidence,
        metadata_path=args.metadata,
        session_id=args.session_id,
        expected_prompt_count=2,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
