#!/usr/bin/env python3
"""Derive AugmentedNet's per-piece train/validation/test splits for OUR
benchmark pieces FROM AUGMENTEDNET'S OWN DATASET MANIFEST, and write
them to `harness/augnet_splits.json` (committed).

Why: the `split` labels hand-maintained in `augnet_comparison.py` were
wrong for half the corpus (2026-06-09 audit). Verified directly from
the AugmentedNet checkout (`AugmentedNet/data/*.py`):

  - data/__init__.py: training collections are abc (Beethoven Op.18
    quartets), bps, haydnsun, keymodt, mps (Mozart sonatas DCML),
    tavern, wir (When-in-Rome incl. OpenScore lieder), wirwtc (WTC).
  - wirwtc.splits: ALL 24 WTC preludes are in the dataset
    (12 training / 6 validation / 6 test) — the old labels said
    "P1,P2 training, P3 test, rest OOD".
  - wir.splits: 39 of our 46 Schubert lieder (27T/6V/6Te), 2 of 9
    Brahms lieder, chorales {1..20}∖{11,15} (12T/3V/3Te), and a
    Monteverdi subset are in the dataset — the old labels said the
    lieder were all OOD.

This script is the single source of truth going forward: it imports
AugmentedNet's `data` package and maps every annotation file to our
corpus-relative piece path. `augnet_comparison.py` and
`augnet_oos_balanced.py` consume the committed JSON (with the
hand-label fallback only when the JSON is absent).

Run (needs the AugmentedNet checkout, no venv activation required —
the data package is pure-Python dicts):

    python3 harness/augnet_splits_dump.py

Re-run + re-commit the JSON whenever the AugmentedNet checkout is
updated to a different release.
"""

import json
import os
import re
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENGINE_HOME = os.environ.get(
    "CONTRAPUNCTUS_ENGINE_HOME",
    os.path.expanduser("~/.cache/contrapunctus/engines"),
)
AUGNET_REPO = os.path.join(ENGINE_HOME, "AugmentedNet")
OUT_PATH = os.path.join(_SCRIPT_DIR, "augnet_splits.json")

# BPS sonata-number → (opus dir, movement is encoded in the key).
# AugmentedNet's bps keys index Beethoven sonatas 1-32; our corpus has
# 4 first movements from BPS-FH.
BPS_SONATA_TO_OUR_DIR = {
    5:  "Piano_Sonatas/Beethoven,_Ludwig_van/Op010_No1",
    8:  "Piano_Sonatas/Beethoven,_Ludwig_van/Op013(Pathetique)",
    17: "Piano_Sonatas/Beethoven,_Ludwig_van/Op031_No2",
    24: "Piano_Sonatas/Beethoven,_Ludwig_van/Op078",
}

# Both prefixes are When-in-Rome layout: the submodule and AugNet's
# own `corrections/WiR` overlay (used for re-encoded movements, e.g.
# several Op.18 quartets, TAVERN K353/K398).
_WIR_PREFIXES = ("rawdata/When-in-Rome/Corpus/", "rawdata/corrections/WiR/Corpus/")
_ANALYSIS_SUFFIX = re.compile(r"/analysis(_[A-Za-z])?\.txt$")


def _strip_wir_prefix(annotation_path: str):
    """Return the WiR-relative dir if `annotation_path` is under either
    WiR prefix (analysis suffix stripped), else None. Handles
    `/analysis.txt`, `/analysis_A.txt`, `/analysis_B.txt` (TAVERN's
    dual-encoder files — the previous `.rsplit('/analysis.txt')` left
    the `_A.txt`/`_B.txt` suffix attached, so every TAVERN piece fell
    through to OOD)."""
    for pfx in _WIR_PREFIXES:
        if annotation_path.startswith(pfx):
            return _ANALYSIS_SUFFIX.sub("", annotation_path[len(pfx):])
    return None


def _wir_rel_to_ours(rel: str):
    """Map a WiR-relative annotation dir (already prefix+suffix
    stripped) to OUR corpus rel-path conventions (category renames +
    zero-padding)."""
    m = re.match(
        r"^Etudes_and_Preludes/Bach,_Johann_Sebastian/The_Well-Tempered_Clavier_I/(\d+)$", rel)
    if m:
        return (f"Keyboard_Other/Bach,_Johann_Sebastian/"
                f"The_Well-Tempered_Clavier_I/{int(m.group(1)):02d}")
    m = re.match(
        r"^Early_Choral/Bach,_Johann_Sebastian/Chorales/(\d+)$", rel)
    if m:
        return (f"Early_Choral/Bach,_Johann_Sebastian/Chorales/"
                f"{int(m.group(1)):03d}")
    m = re.match(
        r"^Early_Choral/Monteverdi,_Claudio/Madrigals_Book_(\d)/(\d+)$", rel)
    if m:
        return f"Madrigals/Monteverdi,_Claudio/Book_{m.group(1)}/{int(m.group(2)):02d}"
    # Beethoven Op.18 quartets: AugNet writes `Op18_NoN`, OUR corpus
    # zero-pads to `Op018_NoN` (Haydn's `Op20_NoN` is NOT padded in our
    # corpus, so this rule is Op.18-specific to match our convention).
    m = re.match(
        r"^Quartets/Beethoven,_Ludwig_van/Op18_No(\d)/(\d)$", rel)
    if m:
        return f"Quartets/Beethoven,_Ludwig_van/Op018_No{m.group(1)}/{m.group(2)}"
    # OpenScore-LiederCorpus and Variations_and_Grounds (TAVERN) match
    # our layout verbatim once the analysis suffix is stripped.
    return rel


def _key_to_ours(collection: str, key: str, annotation_path: str):
    """Map one AugmentedNet dataset key to our corpus rel-path, or None
    when the piece isn't in our benchmark layout (e.g. keymodt)."""
    wir = _strip_wir_prefix(annotation_path)
    if wir is not None:
        return _wir_rel_to_ours(wir)

    if collection == "tavern":
        # Keys like "tavern-beethoven-woo64-a" / "tavern-mozart-k265-b"
        # (encoder suffix optional / variable). Normalise digits out.
        m = re.search(r"woo[-_]?(\d+)", key, re.IGNORECASE)
        if m:
            return f"Variations_and_Grounds/Beethoven,_Ludwig_van/_/WoO_{int(m.group(1))}"
        m = re.search(r"k[-_]?(\d+)", key, re.IGNORECASE)
        if m:
            return f"Variations_and_Grounds/Mozart,_Wolfgang_Amadeus/_/K{int(m.group(1))}"
        return None

    if collection == "mps":
        # Keys like "mps-k279-1".
        m = re.search(r"k[-_]?(\d+)[-_](\d+)", key, re.IGNORECASE)
        if m:
            return f"Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K{int(m.group(1))}/{int(m.group(2))}"
        return None

    if collection == "abc":
        # Keys like "abc-op18-no1-1" (DCML ABC = Beethoven quartets).
        m = re.search(r"op[-_]?18[-_]?no[-_]?(\d+)[-_](\d+)", key, re.IGNORECASE)
        if m:
            return f"Quartets/Beethoven,_Ludwig_van/Op018_No{int(m.group(1))}/{int(m.group(2))}"
        return None  # other opuses aren't in our benchmark

    if collection == "haydnsun":
        # Keys like "haydnsun-op20-no3-4".
        m = re.search(r"op[-_]?20[-_]?no[-_]?(\d+)[-_](\d+)", key, re.IGNORECASE)
        if m:
            return f"Quartets/Haydn,_Franz_Joseph/Op20_No{int(m.group(1))}/{int(m.group(2))}"
        return None

    if collection == "bps":
        # Keys like "bps-05-op010-no1-1" or "bps-5-1" — extract the
        # leading sonata number; BPS is first movements only.
        m = re.search(r"bps[-_]?(\d+)", key, re.IGNORECASE)
        if m:
            our_dir = BPS_SONATA_TO_OUR_DIR.get(int(m.group(1)))
            if our_dir:
                return f"{our_dir}/1"
        return None

    return None  # keymodt etc. — not in our benchmark


# Seen-ness priority when a piece appears under several keys (e.g.
# TAVERN encoders a+b in different splits): if ANY encoding was
# trained on, the piece is in-sample.
_PRIORITY = {"training": 0, "validation": 1, "test": 2}


def main():
    if not os.path.isdir(AUGNET_REPO):
        sys.exit(f"ERROR: AugmentedNet checkout not found at {AUGNET_REPO} "
                 f"(set CONTRAPUNCTUS_ENGINE_HOME)")
    sys.path.insert(0, AUGNET_REPO)
    from AugmentedNet.data import available_collections  # noqa: E402

    out: dict[str, str] = {}
    unmatched: list[str] = []
    for collection, module in available_collections.items():
        duples = module.annotation_score_duples
        for split, keys in module.splits.items():
            for key in keys:
                ann = duples.get(key, (None,))[0]
                if ann is None:
                    unmatched.append(f"{collection}:{key} (no duple)")
                    continue
                ours = _key_to_ours(collection, key, ann)
                if ours is None:
                    # Not part of our benchmark corpus — fine (keymodt,
                    # ABC opuses beyond 18, BPS sonatas we don't carry,
                    # non-benchmark lieder, …). Record for the report.
                    unmatched.append(f"{collection}:{key}")
                    continue
                prev = out.get(ours)
                if prev is None or _PRIORITY[split] < _PRIORITY[prev]:
                    out[ours] = split

    doc = {
        "_meta": {
            "source": "AugmentedNet/data/*.py splits (local checkout)",
            "augnet_repo": "$CONTRAPUNCTUS_ENGINE_HOME/AugmentedNet",  # sanitized: never write the absolute home path into the committed JSON
            "note": ("piece → AugmentedNet split. Pieces ABSENT from this "
                     "map are out-of-dataset (OOD) for AugmentedNet. When a "
                     "piece appears under several dataset keys (TAVERN a/b "
                     "encoders), the most-seen split wins "
                     "(training > validation > test)."),
        },
        "splits": dict(sorted(out.items())),
    }
    with open(OUT_PATH, "w") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
    by_split = {}
    for v in out.values():
        by_split[v] = by_split.get(v, 0) + 1
    print(f"wrote {OUT_PATH}: {len(out)} benchmark pieces in AugNet's dataset "
          f"({by_split})")
    print(f"unmatched dataset keys (not in our benchmark): {len(unmatched)}")
    for u in unmatched[:25]:
        print(f"  {u}")
    if len(unmatched) > 25:
        print(f"  ... and {len(unmatched) - 25} more")


if __name__ == "__main__":
    main()
