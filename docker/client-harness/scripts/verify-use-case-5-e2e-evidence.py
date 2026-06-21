#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from dialogue_structural_verifier import verify_dialogue_structure


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify Use Case 5 dialogue evidence structure.")
    parser.add_argument("--client", choices=["pi", "opencode", "codex"], required=True)
    parser.add_argument("--shape", choices=["single", "curated", "all"], required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--session-id", default="")
    parser.add_argument("--format", choices=["json"], default="json")
    args = parser.parse_args(argv)

    expected_counts = {"single": 3, "curated": 3, "all": 4}
    result = verify_dialogue_structure(
        use_case="use-case-5",
        client=args.client,
        evidence_path=args.evidence,
        metadata_path=args.metadata,
        session_id=args.session_id,
        expected_prompt_count=expected_counts[args.shape],
    )
    result["shape"] = args.shape
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
