#!/usr/bin/env python3
"""One-time line-ending normalizer for files that should be LF in Git.

Usage:
    python scripts/fix_lf_endings_once.py
    python scripts/fix_lf_endings_once.py path/to/file1 path/to/file2
"""

from __future__ import annotations

from pathlib import Path
import sys


DEFAULT_TARGETS = [
    "static/js/calculations.js",
    "templates/finance/monthly_form_detail.html",
]


def normalize_to_lf(raw: bytes) -> bytes:
    # Convert CRLF and lone CR to LF.
    return raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def process_file(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, f"missing: {path.as_posix()}"

    raw = path.read_bytes()
    normalized = normalize_to_lf(raw)

    if normalized == raw:
        return False, f"unchanged: {path.as_posix()}"

    path.write_bytes(normalized)
    return True, f"normalized: {path.as_posix()}"


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    arg_targets = sys.argv[1:]
    targets = arg_targets if arg_targets else DEFAULT_TARGETS

    changed = 0
    for target in targets:
        target_path = Path(target)
        if not target_path.is_absolute():
            target_path = repo_root / target_path

        did_change, message = process_file(target_path)
        if did_change:
            changed += 1
        print(message)

    print(f"done: {changed} file(s) normalized to LF")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
