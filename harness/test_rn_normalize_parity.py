#!/usr/bin/env python3
"""Parity test: the Python `rn_normalize.normalize` must agree with the
engine's Scala normalizer on every label, because OUR engine is scored
by the Scala normalizer while all competitor engines are scored by the
Python one — any drift between them silently biases the cross-engine
benchmark (this is exactly what happened pre-2026-06-09; see
rn_normalize.py's module docstring).

Two layers:
  1. An inline smoke suite covering every normalisation rule —
     runs standalone, no fixture needed.
  2. The full corpus fixture `rn_normalize_fixture.json` (every
     distinct raw RN in the corpus, normalized by the engine's Scala
     normalizer; regenerated in the private engine repo whenever the
     Scala side changes). If the fixture is missing, layer 2 is
     skipped with a warning.

Run after ANY edit to rn_normalize.py:
    python3 harness/test_rn_normalize_parity.py     # or: make test
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rn_normalize import normalize  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "rn_normalize_fixture.json")

# (raw, expected) — expected values are what the engine's SCALA
# normalizer produces, verified rule-by-rule against it.
SMOKE = [
    # Unicode digits / glyphs
    ("V⁷", "V7"),
    ("vii°⁶₅", "viio65"),
    ("♯viio⁶", "viio6"),          # ♯→#, °→o, then #vii strip (no slash)
    ("V⁷/V", "V7/v"),
    # Slash handling: tonicization kept (BOTH cases), figured dropped
    ("V7/V", "V7/v"),
    ("V7/v", "V7/v"),             # lowercase target keeps its slash too
    ("V65/VI", "V65/vi"),
    ("viio7/vi", "viio7/vi"),
    ("V4/3", "V43"),
    ("V6/5", "V65"),
    ("ii/o7", "iiø7"),            # half-diminished shorthand
    ("ii/o", "iiø"),
    # #vii strip: exact-tier, NO-SLASH only
    ("#viio6", "viio6"),
    ("#vii", "vii"),
    ("#viio65/ii", "#viio65/ii"),  # slash form keeps the marker
    # Aug6 canonicalisation
    ("It+6", "It6"),
    ("It⁺⁶", "It6"),
    ("Fr+43", "Fr43"),
    ("Fr6", "Fr43"),
    ("Ger+65", "Ger6"),
    ("Ger65", "Ger6"),
    ("Ger7", "Ger6"),
    ("Ger6", "Ger6"),
    ("Ger65/vi", "Ger6/vi"),
    # Bracket + alteration-suffix strips
    ("V7[no3][add4]", "V7"),
    ("viio64b3", "viio64"),
    ("V7#5", "V7"),
    # Inversion shorthand
    ("ii2", "ii42"),
    ("V2", "V42"),
    ("V42", "V42"),
    ("viio63", "viio6"),
    ("viio63/v", "viio6/v"),
    # Δ elision, ⁺ quality preserved on numerals
    ("IVΔ7", "IV7"),
    ("V+", "V+"),
    ("iii⁺", "iii+"),
    # Misc real-corpus forms
    ("Cad64", "Cad64"),
    ("bII6", "bII6"),
    ("N6", "N6"),
    ("i64", "i64"),
    ("  V7  ", "V7"),
]


def main() -> int:
    failures = []
    for raw, want in SMOKE:
        got = normalize(raw)
        if got != want:
            failures.append(("smoke", raw, want, got))

    fixture_n = 0
    if os.path.exists(FIXTURE):
        with open(FIXTURE) as f:
            doc = json.load(f)
        for entry in doc["entries"]:
            raw, want = entry["raw"], entry["normalized"]
            got = normalize(raw)
            fixture_n += 1
            if got != want:
                failures.append(("fixture", raw, want, got))
    else:
        print(f"WARNING: fixture not found at {FIXTURE} — it is committed "
              "to this repo (restore it from git). It is regenerated in the "
              "private engine repo when the Scala normalizer changes. "
              "Smoke suite only.", file=sys.stderr)

    if failures:
        print(f"FAIL: {len(failures)} parity mismatches "
              f"({len(SMOKE)} smoke + {fixture_n} fixture cases):")
        for layer, raw, want, got in failures[:40]:
            print(f"  [{layer}] {raw!r}: scala={want!r}  python={got!r}")
        if len(failures) > 40:
            print(f"  ... and {len(failures) - 40} more")
        return 1
    print(f"OK: {len(SMOKE)} smoke + {fixture_n} fixture cases agree "
          "with the Scala normalizer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
