#!/usr/bin/env python3
"""Parity-test harness/score.py against every committed release.

For each results/<date>/ directory: copy its four *.report.json files and
the pinned common_subset.json to a scratch dir, re-run score.py there, and
require the regenerated scores.json to match the committed one on every
NUMBER (aggregates, per-group rows, tier ladders, pins, winners).

Presentation metadata is excluded from the comparison: the `name`, `year`,
`type`, and `source` strings in ENGINES (and the `_doc` strings) may
legitimately evolve — e.g. an engine rename — without invalidating a
release's published numbers. Everything else must be exact: the floats are
round()ed at creation, so equality is well-defined.

Running in a scratch dir keeps the committed scores.json / common_subset.json
untouched and exercises the coverage gate against the committed pin.

Stdlib only, like everything under harness/.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_ROOT = REPO_ROOT / "results"
SCORE_PY = REPO_ROOT / "harness" / "score.py"

PRESENTATION_KEYS = {"name", "year", "type", "source", "_doc"}


def strip_presentation(node):
    """Drop display-only strings, keep every number and structural key."""
    if isinstance(node, dict):
        return {k: strip_presentation(v) for k, v in node.items()
                if k not in PRESENTATION_KEYS}
    if isinstance(node, list):
        return [strip_presentation(v) for v in node]
    return node


def first_difference(a, b, path="$"):
    """Human-oriented pointer at the first mismatch between two trees."""
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                return f"{path}.{k}: present in only one side"
            d = first_difference(a[k], b[k], f"{path}.{k}")
            if d:
                return d
        return None
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return f"{path}: list lengths {len(a)} != {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            d = first_difference(x, y, f"{path}[{i}]")
            if d:
                return d
        return None
    if a != b:
        return f"{path}: {a!r} != {b!r}"
    return None


def check_release(release_dir: Path) -> None:
    committed = release_dir / "scores.json"
    if not committed.exists():
        raise SystemExit(f"{release_dir.name}: no committed scores.json")

    with tempfile.TemporaryDirectory(prefix="score-parity-") as tmp:
        scratch = Path(tmp) / release_dir.name
        scratch.mkdir()
        for f in release_dir.glob("*.report.json"):
            shutil.copyfile(f, scratch / f.name)
        # Copy the pin so the coverage gate is exercised, not re-created.
        shutil.copyfile(release_dir / "common_subset.json",
                        scratch / "common_subset.json")

        res = subprocess.run(
            [sys.executable, str(SCORE_PY), str(scratch)],
            capture_output=True, text=True)
        if res.returncode != 0:
            raise SystemExit(
                f"{release_dir.name}: score.py failed in the scratch dir "
                f"(exit {res.returncode})\n{res.stdout}\n{res.stderr}")

        got = strip_presentation(json.loads((scratch / "scores.json")
                                            .read_text()))
        want = strip_presentation(json.loads(committed.read_text()))
        diff = first_difference(got, want)
        if diff:
            raise SystemExit(
                f"{release_dir.name}: regenerated scores.json diverges from "
                f"the committed one — first difference: {diff}")
    print(f"OK: {release_dir.name} re-aggregates to its committed "
          "scores.json (numbers exact; coverage gate green)")


def main() -> None:
    releases = sorted(d for d in RESULTS_ROOT.iterdir() if d.is_dir())
    if not releases:
        raise SystemExit("no results/<date>/ directories found")
    for d in releases:
        check_release(d)


if __name__ == "__main__":
    main()
