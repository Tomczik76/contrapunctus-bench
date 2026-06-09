#!/usr/bin/env python3
"""Generate corpus/manifest.json — the per-piece provenance list.

This repo does NOT redistribute scores or analyst Roman-numeral files.
The ground truth is derived at build time from the When-in-Rome git
submodule (+ a few fetched score sources); the manifest is the committed
record of WHAT is evaluated and WHERE each piece comes from.

Source of the piece list + event counts: the published page data
(`benchmarks.json::per_piece`) in the engine repo, located via
$CONTRAPUNCTUS_APP_ROOT (default ../contrapunctus). Event counts are as
the engine's rntxt parser counts ground-truth events (other engines'
parsers can differ by a few events on repeat-notation pieces; see
methodology/protocol.md).

Per-corpus licensing is recorded best-effort with the canonical source
URL. Scores and analyses carry their own licenses at those URLs; "varies
/ see source" is used wherever When-in-Rome re-bundles an external corpus
whose score license is not a single blanket one (the When-in-Rome README
states "these external licences vary"). When-in-Rome's own new content
and format conversions are CC BY-SA 4.0.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
APP_ROOT = Path(os.environ.get("CONTRAPUNCTUS_APP_ROOT",
                               REPO_ROOT.parent / "contrapunctus"))
BENCHMARKS = APP_ROOT / "frontend" / "src" / "data" / "benchmarks.json"

# Per-genre provenance. analysis_* = the analyst Roman-numeral ground
# truth; score_* = the notes the engines analyze. Licenses are recorded
# at the corpus level; per-piece licensing follows its genre's entry.
CORPORA = {
    "chorales": {
        "display": "Bach chorales (Riemenschneider 1-371)",
        "period": "Late Baroque (~1730)", "texture": "homophonic SATB",
        "score_source": "Craig Sapp, bach-370-chorales (Riemenschneider, **kern)",
        "score_url": "https://github.com/craigsapp/bach-370-chorales",
        "score_license": "see source (Humdrum **kern edition)",
        "analysis_source": "When-in-Rome (Early_Choral/Bach/Chorales)",
        "analysis_url": "https://github.com/MarkGotham/When-in-Rome",
        "analysis_license": "CC BY-SA 4.0",
    },
    "bach-wtc": {
        "display": "Bach WTC I (24 preludes + 2 fugues)",
        "period": "Late Baroque (1722)", "texture": "figural keyboard / fugal",
        "score_source": "When-in-Rome (Keyboard_Other/Bach/WTC I)",
        "score_url": "https://github.com/MarkGotham/When-in-Rome",
        "score_license": "CC BY-SA 4.0 (When-in-Rome)",
        "analysis_source": "When-in-Rome",
        "analysis_url": "https://github.com/MarkGotham/When-in-Rome",
        "analysis_license": "CC BY-SA 4.0",
    },
    "beethoven-bps-fh": {
        "display": "Beethoven sonatas (BPS-FH)",
        "period": "Classical/Early Romantic (1798-1809)",
        "texture": "figural keyboard, dense",
        "score_source": "Chen & Su 2018, Beethoven Piano Sonatas w/ Functional "
                        "Harmony (re-bundled in When-in-Rome)",
        "score_url": "https://github.com/Tsung-Ping/functional-harmony",
        "score_license": "see source",
        "analysis_source": "BPS-FH via When-in-Rome",
        "analysis_url": "https://github.com/MarkGotham/When-in-Rome",
        "analysis_license": "CC BY-SA 4.0 (When-in-Rome conversion; original: see source)",
    },
    "beethoven-op18": {
        "display": "Beethoven Op.18 string quartets",
        "period": "Classical/Early Romantic (1798-1800)",
        "texture": "string quartet",
        "score_source": "When-in-Rome (Quartets/Beethoven/Op018)",
        "score_url": "https://github.com/MarkGotham/When-in-Rome",
        "score_license": "CC BY-SA 4.0 (When-in-Rome)",
        "analysis_source": "When-in-Rome",
        "analysis_url": "https://github.com/MarkGotham/When-in-Rome",
        "analysis_license": "CC BY-SA 4.0",
    },
    "haydn-op20": {
        "display": "Haydn Op.20 quartets (Sun)",
        "period": "Classical (1772)", "texture": "string quartet",
        "score_source": "HaydnSun (Devaney & Mangru) via When-in-Rome",
        "score_url": "https://github.com/MarkGotham/When-in-Rome",
        "score_license": "CC BY-SA 4.0 (When-in-Rome)",
        "analysis_source": "HaydnSun via When-in-Rome",
        "analysis_url": "https://github.com/MarkGotham/When-in-Rome",
        "analysis_license": "CC BY-SA 4.0",
    },
    "mozart-sonatas-dcml": {
        "display": "Mozart piano sonatas (DCMLab)",
        "period": "Classical (1773-88)", "texture": "figural keyboard",
        "score_source": "DCMLab mozart_piano_sonatas (re-bundled in When-in-Rome)",
        "score_url": "https://github.com/DCMLab/mozart_piano_sonatas",
        "score_license": "see source (DCML)",
        "analysis_source": "DCMLab via When-in-Rome",
        "analysis_url": "https://github.com/MarkGotham/When-in-Rome",
        "analysis_license": "CC BY-SA 4.0 (When-in-Rome conversion; original: see source)",
    },
    "schubert-lieder": {
        "display": "Schubert lieder",
        "period": "Early Romantic (1815-28)", "texture": "voice + piano",
        "score_source": "OpenScore Lieder Corpus (CC0) via When-in-Rome",
        "score_url": "https://github.com/OpenScore/Lieder",
        "score_license": "CC0",
        "analysis_source": "When-in-Rome (OpenScore-LiederCorpus)",
        "analysis_url": "https://github.com/MarkGotham/When-in-Rome",
        "analysis_license": "CC BY-SA 4.0",
    },
    "brahms-lieder": {
        "display": "Brahms lieder",
        "period": "Late Romantic (1853-68)", "texture": "voice + piano",
        "score_source": "OpenScore Lieder Corpus (CC0) via When-in-Rome",
        "score_url": "https://github.com/OpenScore/Lieder",
        "score_license": "CC0",
        "analysis_source": "When-in-Rome (OpenScore-LiederCorpus)",
        "analysis_url": "https://github.com/MarkGotham/When-in-Rome",
        "analysis_license": "CC BY-SA 4.0",
    },
    "tavern": {
        "display": "TAVERN theme-and-variation sets",
        "period": "Classical/Early Romantic", "texture": "variation form",
        "score_source": "TAVERN (Devaney et al.) re-bundled in When-in-Rome",
        "score_url": "https://github.com/jcdevaney/TAVERN",
        "score_license": "see source",
        "analysis_source": "TAVERN via When-in-Rome",
        "analysis_url": "https://github.com/MarkGotham/When-in-Rome",
        "analysis_license": "CC BY-SA 4.0 (When-in-Rome conversion; original: see source)",
    },
    "monteverdi": {
        "display": "Monteverdi madrigals (Books 3-5)",
        "period": "Early Baroque (1592-1605)", "texture": "polyphonic SATB (modal)",
        "tonal": False,
        "score_source": "music21 bundled corpus (Monteverdi madrigals)",
        "score_url": "https://github.com/cuthbertLab/music21/tree/master/music21/corpus/monteverdi",
        "score_license": "BSD-3-Clause (music21 toolkit/corpus)",
        "analysis_source": "music21 bundled .rntxt",
        "analysis_url": "https://github.com/cuthbertLab/music21/tree/master/music21/corpus/monteverdi",
        "analysis_license": "BSD-3-Clause (music21)",
    },
}


def main() -> None:
    if not BENCHMARKS.exists():
        raise SystemExit(
            f"cannot find {BENCHMARKS}\n"
            "Set CONTRAPUNCTUS_APP_ROOT to the engine-app checkout that holds "
            "frontend/src/data/benchmarks.json (the published page data).")
    per_piece = json.loads(BENCHMARKS.read_text())["per_piece"]

    # The pinned 4-engine common subset (written by harness/score.py) from
    # the newest date-stamped release. Override with CONTRAPUNCTUS_RESULTS.
    results_override = os.environ.get("CONTRAPUNCTUS_RESULTS")
    if results_override:
        common_path = Path(results_override) / "common_subset.json"
    else:
        dated = sorted((REPO_ROOT / "results").glob("*/"))
        common_path = (dated[-1] / "common_subset.json") if dated else REPO_ROOT / "results" / "_none_"
    common = set()
    if common_path.exists():
        common = {p.split("/", 1)[1] for p in
                  json.loads(common_path.read_text())["pieces"]}

    pieces = []
    by_genre: dict[str, int] = {}
    for r in per_piece:
        g = r["group_id"]
        by_genre[g] = by_genre.get(g, 0) + 1
        pieces.append({
            "id": r["piece"],
            "genre": g,
            "events": r["events"],
            "source_url": r["source_url"],
            "in_common_subset": r["piece"] in common,
        })
    pieces.sort(key=lambda p: (p["genre"], p["id"]))

    manifest = {
        "_doc": "Per-piece provenance for the cross-engine benchmark. This "
                "repo does not redistribute scores or analyst RN files — they "
                "are derived from the When-in-Rome submodule + fetched sources "
                "at build time (see corpus/prep/). 'events' = ground-truth RN "
                "events as the engine's parser counts them. 'in_common_subset' "
                "marks the 505 pieces scored in the head-to-head (all four "
                "engines produce output). See methodology/corpus.md.",
        "counts": {
            "total_pieces": len(pieces),
            "tonal_pieces": sum(1 for p in pieces if p["genre"] != "monteverdi"),
            "common_subset_pieces": sum(1 for p in pieces if p["in_common_subset"]),
            "by_genre": dict(sorted(by_genre.items())),
        },
        "corpora": CORPORA,
        "pieces": pieces,
    }

    out = REPO_ROOT / "corpus" / "manifest.json"
    out.write_text(json.dumps(manifest, indent=1) + "\n")
    print(f"wrote {out.relative_to(REPO_ROOT)}: {len(pieces)} pieces, "
          f"{manifest['counts']['common_subset_pieces']} in common subset")
    # sanity: every genre seen has a corpora entry
    missing = sorted(set(by_genre) - set(CORPORA))
    if missing:
        raise SystemExit(f"genres without a CORPORA provenance entry: {missing}")


if __name__ == "__main__":
    main()
