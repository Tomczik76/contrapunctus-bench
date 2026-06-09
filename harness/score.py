#!/usr/bin/env python3
"""Aggregate the committed per-piece engine reports into the headline tables.

Self-contained: Python 3.9+ stdlib only. No engine, no sbt, no model
environments — `make score` runs this against the committed JSON under
results/<date>/ and reprints every number in the README.

Inputs (one file per engine, same row schema):

    results/<date>/contrapunctus.report.json
    results/<date>/augmentednet.report.json
    results/<date>/analysisgnn.report.json
    results/<date>/music21.report.json

Each report is {"engine": ..., "timestamp": ..., "rows": [...]} where a row is

    {"mode": "single-pick", "group": "<genre>", "piece": "<name>",
     "total": <events>, "exact": n, "sameChordGained": n, "inversionGained": n,
     "conventionGained": n, "sharedBassGained": n, "secondaryDiatonicGained": n}

i.e. per-piece counts of ground-truth events landing in each match tier
(see methodology/match-tiers.md). Only mode == "single-pick" rows are
scored — the fully-autonomous single-prediction mode, the one comparable
across engines.

Aggregation rules (mirrors the private build_benchmarks.py exactly):

  * Tonal aggregates exclude the `monteverdi` group (pre-tonal; reported
    separately) and the legacy `baseline-9` group (dissolved 2026-05-26;
    exclusion kept defensively).
  * Common subset = intersection of (group, piece) keys across ALL four
    engines. An engine that fails on a piece (see methodology/corpus.md
    "Known engine failures") removes that piece from the comparison for
    EVERY engine — no engine is scored on a piece another engine skipped.
  * The common subset is pinned: the first run writes
    results/<date>/common_subset.json; later runs FAIL if the recomputed
    intersection differs. This is the coverage gate — a partial rival
    cache cannot silently change the evaluated piece set and flip a
    verdict (it has, historically; hence the pin).
  * Micro ("all pieces") = event-weighted percentage over the whole
    common subset. Chorale-tilted (370 of 505 pieces are chorales).
  * Genre-balanced = macro-average: per-genre event-weighted exact%,
    then the unweighted mean over the 9 tonal genres. Each genre is one
    observation regardless of piece count. This is the headline.
  * a-d ("annotator-defensible") = exact + the five tier gains. Cite
    only with the per-tier breakdown visible (methodology/match-tiers.md).

Output: results/<date>/scores.json + the tables on stdout.

Usage:
    python3 harness/score.py [results/<date>]   # default: newest results dir
    python3 harness/score.py --check            # also verify README numbers
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_ROOT = REPO_ROOT / "results"

# Groups excluded from the tonal aggregates. Monteverdi (Books 3-5
# madrigals, 1592-1605) is pre-tonal — Roman-numeral analysis of modal
# polyphony is a different task; it is reported in its own section.
# baseline-9 was dissolved into proper genres on 2026-05-26; the guard
# stays so a stale report can never leak it back into an aggregate.
EXCLUDED_GROUPS = {"monteverdi", "baseline-9"}

TIER_GAINS = [
    "sameChordGained",
    "inversionGained",
    "conventionGained",
    "sharedBassGained",
    "secondaryDiatonicGained",
]

ENGINES = [
    # (file stem, display name, year, type, source note)
    ("contrapunctus", "Contrapunctus (routed keys + learned chord-ID)", 2026,
     "hybrid: rules + learned chord-ID re-ranker", "contrapunctus.app/engine"),
    ("augmentednet", "AugmentedNet 11+ (RNalt)", 2021,
     "neural (CNN)", "Nápoles López et al., ISMIR 2021"),
    ("analysisgnn", "AnalysisGNN v1.0", 2024,
     "neural (GNN)", "Karystinaios 2024"),
    ("music21", "Music21 10.1.0 (keys given)", 2024,
     "rule-based; NOT autonomous — scored with the analyst's local key",
     "Cuthbert et al."),
]


def load_report(path: Path) -> dict:
    """Load one engine report; return {(group, piece): row} for single-pick rows."""
    with path.open() as f:
        doc = json.load(f)
    rows = doc.get("rows", doc)
    out: dict[tuple[str, str], dict] = {}
    for r in rows:
        if r.get("mode") != "single-pick":
            continue
        key = (r["group"], r["piece"])
        if key in out:
            raise SystemExit(f"{path.name}: duplicate single-pick row for {key}")
        out[key] = r
    if not out:
        raise SystemExit(f"{path.name}: no single-pick rows found")
    return out


def pct(numer: int, denom: int) -> float:
    return round(100.0 * numer / denom, 2) if denom else 0.0


def aggregate(rows: list[dict]) -> dict:
    """Event-weighted tier aggregate over a list of per-piece rows."""
    total = sum(r["total"] for r in rows)
    exact = sum(r["exact"] for r in rows)
    gains = {g: sum(r[g] for r in rows) for g in TIER_GAINS}
    ad = exact + sum(gains.values())
    cum = exact
    cumulative = {"exact": pct(exact, total)}
    for g in TIER_GAINS:
        cum += gains[g]
        cumulative["+ " + g.replace("Gained", "")] = pct(cum, total)
    return {
        "events": total,
        "exact_pct": pct(exact, total),
        "a_d_pct": pct(ad, total),
        "cumulative_tiers_pct": cumulative,
    }


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    check = "--check" in sys.argv[1:]

    if args:
        results_dir = Path(args[0])
        if not results_dir.is_absolute():
            results_dir = (REPO_ROOT / results_dir).resolve()
    else:
        candidates = sorted(d for d in RESULTS_ROOT.iterdir() if d.is_dir())
        if not candidates:
            raise SystemExit("no results/<date>/ directories found")
        results_dir = candidates[-1]

    print(f"results: {results_dir.relative_to(REPO_ROOT)}\n")

    data: dict[str, dict[tuple[str, str], dict]] = {}
    for stem, name, *_ in ENGINES:
        path = results_dir / f"{stem}.report.json"
        if not path.exists():
            raise SystemExit(f"missing report: {path}")
        data[stem] = load_report(path)
        n_tonal = sum(1 for (g, _p) in data[stem] if g not in EXCLUDED_GROUPS)
        print(f"  {stem:14s} {len(data[stem]):4d} single-pick piece rows "
              f"({n_tonal} tonal)")

    # ── Common subset (tonal genres only) + coverage gate ────────────────
    tonal_keys = {
        stem: {k for k in rows if k[0] not in EXCLUDED_GROUPS}
        for stem, rows in data.items()
    }
    common = set.intersection(*tonal_keys.values())
    common_events = sum(data["contrapunctus"][k]["total"] for k in common)

    pin_path = results_dir / "common_subset.json"
    piece_list = sorted(f"{g}/{p}" for (g, p) in common)
    if pin_path.exists():
        pinned = json.loads(pin_path.read_text())
        if pinned["pieces"] != piece_list:
            got, want = set(piece_list), set(pinned["pieces"])
            raise SystemExit(
                "COVERAGE GATE FAILED: recomputed common subset differs from "
                f"the pinned roster ({pin_path.name}).\n"
                f"  missing from reports: {sorted(want - got)[:10]}\n"
                f"  unexpected extras:    {sorted(got - want)[:10]}\n"
                "A partial engine report silently changes the comparison "
                "subset; regenerate the offending report or update the pin "
                "deliberately (and say so in PROVENANCE.md)."
            )
        print(f"\ncoverage gate: OK ({len(common)} pieces match the pinned roster)")
    else:
        pin_path.write_text(json.dumps(
            {"_doc": "Pinned 4-engine common subset. score.py fails if the "
                     "recomputed intersection differs — see the coverage-gate "
                     "note in harness/score.py.",
             "n_pieces": len(piece_list),
             "events": common_events,
             "pieces": piece_list}, indent=1) + "\n")
        print(f"\ncoverage gate: pinned {len(common)} pieces → {pin_path.name}")

    groups = sorted({g for (g, _p) in common})

    # ── Aggregates ────────────────────────────────────────────────────────
    scores: dict = {
        "_doc": "Computed by harness/score.py from the four *.report.json "
                "files in this directory. Do not edit by hand.",
        "common_subset": {"pieces": len(common), "events": common_events},
        "micro": {}, "balanced": {}, "per_group": [], "pre_tonal": {},
    }

    for stem, name, year, etype, source in ENGINES:
        rows = [data[stem][k] for k in common]
        agg = aggregate(rows)
        scores["micro"][stem] = {"name": name, "year": year, "type": etype,
                                 "source": source, **agg}

    per_group_rows = []
    for g in groups:
        keys = [k for k in common if k[0] == g]
        entry = {"group": g, "n_pieces": len(keys),
                 "events": sum(data["contrapunctus"][k]["total"] for k in keys)}
        for stem, *_ in ENGINES:
            agg = aggregate([data[stem][k] for k in keys])
            entry[stem] = agg["exact_pct"]
            entry[stem + "_ad"] = agg["a_d_pct"]
        winners = sorted(((entry[stem], stem) for stem, *_ in ENGINES), reverse=True)
        entry["winner"] = winners[0][1]
        per_group_rows.append(entry)
    scores["per_group"] = per_group_rows

    for stem, name, *_ in ENGINES:
        genre_exacts = [r[stem] for r in per_group_rows]
        genre_ads = [r[stem + "_ad"] for r in per_group_rows]
        scores["balanced"][stem] = {
            "name": name,
            "exact_pct": round(sum(genre_exacts) / len(genre_exacts), 2),
            "a_d_pct": round(sum(genre_ads) / len(genre_ads), 2),
            "wins": sum(1 for r in per_group_rows if r["winner"] == stem),
        }

    # ── Pre-tonal (Monteverdi) — reported separately, never aggregated ───
    monte_keys = {
        stem: {k for k in rows if k[0] == "monteverdi"}
        for stem, rows in data.items()
    }
    monte_common = set.intersection(*monte_keys.values())
    if monte_common:
        scores["pre_tonal"] = {
            "_doc": "Monteverdi madrigals (Books 3-5, 1592-1605). Modal "
                    "pre-tonal polyphony — EXPLORATORY, outside every tonal "
                    "aggregate. Computed on the 4-engine common subset (same "
                    "basis as the tonal tables). NOTE: contrapunctus.app/engine "
                    "reports Monteverdi per-engine-own-coverage (48 pieces) "
                    "rather than on the common subset, so these numbers are not "
                    "meant to match that section piece-for-piece.",
            "pieces": len(monte_common),
            "engines": {
                stem: aggregate([data[stem][k] for k in monte_common])
                for stem, *_ in ENGINES
            },
        }

    out_path = results_dir / "scores.json"
    out_path.write_text(json.dumps(scores, indent=1) + "\n")

    # ── Print the README tables ───────────────────────────────────────────
    print(f"\ncommon subset: {len(common)} pieces, {common_events} events "
          f"({len(groups)} tonal genres)\n")

    print("GENRE-BALANCED (macro-average over genres — the headline)")
    print(f"  {'engine':48s} {'exact%':>8s} {'a-d%':>8s} {'genre wins':>11s}")
    for stem, name, *_ in ENGINES:
        b = scores["balanced"][stem]
        print(f"  {name:48s} {b['exact_pct']:8.2f} {b['a_d_pct']:8.2f} "
              f"{b['wins']:>8d}/{len(groups)}")

    print("\nALL PIECES (micro, event-weighted — chorale-tilted)")
    print(f"  {'engine':48s} {'exact%':>8s} {'a-d%':>8s}")
    for stem, name, *_ in ENGINES:
        m = scores["micro"][stem]
        print(f"  {name:48s} {m['exact_pct']:8.2f} {m['a_d_pct']:8.2f}")

    print("\nPER GENRE (exact%, event-weighted within genre)")
    header = f"  {'genre':22s} {'pieces':>6s}" + "".join(
        f" {stem[:12]:>13s}" for stem, *_ in ENGINES)
    print(header)
    for r in per_group_rows:
        line = f"  {r['group']:22s} {r['n_pieces']:6d}"
        for stem, *_ in ENGINES:
            mark = "*" if r["winner"] == stem else " "
            line += f" {r[stem]:12.2f}{mark}"
        print(line)
    print("  (* = best engine in that genre)")

    if scores["pre_tonal"]:
        pt = scores["pre_tonal"]
        print(f"\nPRE-TONAL — Monteverdi madrigals ({pt['pieces']} pieces, "
              "outside all aggregates above)")
        for stem, name, *_ in ENGINES:
            e = pt["engines"][stem]
            print(f"  {name:48s} {e['exact_pct']:8.2f} {e['a_d_pct']:8.2f}")

    print(f"\nwrote {out_path.relative_to(REPO_ROOT)}")

    if check:
        check_readme(scores)


def check_readme(scores: dict) -> None:
    """Verify every numeric claim in README.md matches scores.json."""
    readme = (REPO_ROOT / "README.md").read_text()
    missing = []
    for stem, *_ in ENGINES:
        for val in (scores["balanced"][stem]["exact_pct"],
                    scores["micro"][stem]["exact_pct"]):
            if f"{val:.2f}" not in readme:
                missing.append(f"{stem}: {val:.2f}")
    for r in scores["per_group"]:
        if f"{r['contrapunctus']:.2f}" not in readme:
            missing.append(f"per-group {r['group']}: {r['contrapunctus']:.2f}")
    if missing:
        raise SystemExit("README CHECK FAILED — numbers not found in README.md:\n  "
                         + "\n  ".join(missing))
    print("README check: all headline + per-group numbers present in README.md")


if __name__ == "__main__":
    main()
