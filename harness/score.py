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
    python3 harness/score.py --write-readme     # regenerate the README's three
                                                #   generated table regions from
                                                #   the computed scores
    python3 harness/score.py --diff-prose results/<prior>/scores.json
                                                # print prose-relevant deltas vs a
                                                #   prior release (warnings only)

The README's three headline tables live between
`<!-- BEGIN GENERATED: <name> -->` / `<!-- END GENERATED: <name> -->`
sentinels and are rewritten by --write-readme; the surrounding prose is
hand-written and NEVER touched by this script. --diff-prose is the bridge
between the two: it flags score changes the narrative may depend on
(winner flips, win-tally moves, threshold crossings, lead changes) so a
release can't silently outrun its prose.
"""

from __future__ import annotations

import argparse
import json
import math
import re
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

ENGINE_STEMS = [e[0] for e in ENGINES]

# ── README table generation (--write-readme) ─────────────────────────────
#
# The three headline tables in README.md are generated regions wrapped in
# <!-- BEGIN GENERATED: <name> --> / <!-- END GENERATED: <name> --> markers.
# Numbers inside them come from the scores dict; everything outside them is
# hand-written prose this script never touches.
#
# The label strings below are EDITORIAL — bold markers, parentheticals and
# footnotes are baked in verbatim (they carry judgment, e.g. music21's
# "keys given" caveat). The renderer only computes the numbers and bolds
# the leading value per column. Rename an engine here deliberately; the
# faithfulness contract is that re-running --write-readme on an unchanged
# results dir is a byte-for-byte no-op on README.md.

README_LABELS = {
    # stem -> {balanced: row label in the genre-balanced table,
    #          type:     the Type cell in the genre-balanced table,
    #          short:    row label in the all-pieces table,
    #          winner:   the Winner-column name in the per-genre table}
    "contrapunctus": {
        "balanced": "**Contrapunctus** (routed keys + learned chord-ID)",
        "type": "hybrid: rules + learned re-ranker",
        "short": "**Contrapunctus**",
        "winner": "Contrapunctus",
    },
    "augmentednet": {
        "balanced": "AugmentedNet 11+ (RNalt), ISMIR 2021",
        "type": "neural (CNN)",
        "short": "AugmentedNet 11+",
        "winner": "AugmentedNet",
    },
    "analysisgnn": {
        "balanced": "AnalysisGNN v1.0, 2024",
        "type": "neural (GNN)",
        "short": "AnalysisGNN v1.0",
        "winner": "AnalysisGNN",
    },
    "music21": {
        "balanced": "Music21 10.1.0 *(keys given — not autonomous)*",
        "type": "rule-based",
        "short": "Music21 10.1.0 *(keys given)*",
        "winner": "Music21",
    },
}

GENRE_DISPLAY = {
    "bach-wtc": "Bach WTC I",
    "beethoven-bps-fh": "Beethoven BPS-FH",
    "beethoven-op18": "Beethoven Op.18",
    "brahms-lieder": "Brahms lieder",
    "chorales": "Bach chorales",
    "haydn-op20": "Haydn Op.20",
    "mozart-sonatas-dcml": "Mozart sonatas (DCML)",
    "schubert-lieder": "Schubert lieder",
    "tavern": "TAVERN variations",
}

MINUS = "−"  # the hand-written tables use a real minus sign, not a hyphen


def fmt_signed(delta: float) -> str:
    return f"+{delta:.2f}" if delta >= 0 else f"{MINUS}{abs(delta):.2f}"


def group_delta(row: dict) -> float:
    """Contrapunctus's lead over AugmentedNet in one genre (rounded values)."""
    return round(row["contrapunctus"] - row["augmentednet"], 2)


def render_genre_balanced(scores: dict) -> str:
    n_groups = len(scores["per_group"])
    best = max(ENGINE_STEMS, key=lambda s: scores["balanced"][s]["exact_pct"])
    most_wins = max(ENGINE_STEMS, key=lambda s: scores["balanced"][s]["wins"])
    lines = ["| Engine | Type | Exact % | a-d % | Genres won |",
             "|---|---|--:|--:|--:|"]
    for stem in ENGINE_STEMS:
        b = scores["balanced"][stem]
        lab = README_LABELS[stem]
        exact = f"{b['exact_pct']:.2f}"
        if stem == best:
            exact = f"**{exact}**"
        wins = f"{b['wins']} / {n_groups}"
        if stem == most_wins:
            wins = f"**{wins}**"
        lines.append(f"| {lab['balanced']} | {lab['type']} | {exact} "
                     f"| {b['a_d_pct']:.2f} | {wins} |")
    return "\n".join(lines)


def render_all_pieces(scores: dict) -> str:
    best = max(ENGINE_STEMS, key=lambda s: scores["micro"][s]["exact_pct"])
    lines = ["| Engine | Exact % | a-d % |",
             "|---|--:|--:|"]
    for stem in ENGINE_STEMS:
        m = scores["micro"][stem]
        exact = f"{m['exact_pct']:.2f}"
        if stem == best:
            exact = f"**{exact}**"
        lines.append(f"| {README_LABELS[stem]['short']} | {exact} "
                     f"| {m['a_d_pct']:.2f} |")
    return "\n".join(lines)


def render_per_genre(scores: dict) -> str:
    rows = sorted(scores["per_group"],
                  key=lambda r: (-group_delta(r), r["group"]))
    max_delta_group = rows[0]["group"]  # the headline gap gets the bold Δ
    lines = ["| Genre | Pieces | Contrapunctus | AugmentedNet | AnalysisGNN "
             "| Music21 | Winner | Δ vs AugNet |",
             "|---|--:|--:|--:|--:|--:|---|--:|"]
    for r in rows:
        g = r["group"]
        if g not in GENRE_DISPLAY:
            raise SystemExit(f"--write-readme: no GENRE_DISPLAY entry for "
                             f"genre {g!r} — add one (refusing to print a raw id)")
        cells = []
        for stem in ENGINE_STEMS:
            v = f"{r[stem]:.2f}"
            if r["winner"] == stem:
                v = f"**{v}**"
            cells.append(v)
        delta = fmt_signed(group_delta(r))
        if g == max_delta_group:
            delta = f"**{delta}**"
        lines.append(f"| {GENRE_DISPLAY[g]} | {r['n_pieces']} | "
                     + " | ".join(cells)
                     + f" | {README_LABELS[r['winner']]['winner']} | {delta} |")
    return "\n".join(lines)


def write_readme(scores: dict) -> None:
    """Rewrite the three generated table regions in README.md, nothing else."""
    readme_path = REPO_ROOT / "README.md"
    text = readme_path.read_text()
    tables = {
        "genre-balanced": render_genre_balanced(scores),
        "per-genre": render_per_genre(scores),
        "all-pieces": render_all_pieces(scores),
    }
    for name, table in tables.items():
        begin = f"<!-- BEGIN GENERATED: {name} -->"
        end = f"<!-- END GENERATED: {name} -->"
        i, j = text.find(begin), text.find(end)
        if i < 0 or j < 0 or j < i:
            raise SystemExit(f"--write-readme: sentinel pair for {name!r} not "
                             "found in README.md — restore the markers")
        text = text[:i + len(begin)] + "\n" + table + "\n" + text[j:]
    readme_path.write_text(text)
    print(f"README.md: regenerated tables: {', '.join(tables)}")


# ── Prose-change detector (--diff-prose) ─────────────────────────────────
#
# The interpretive prose (winner-flip sentences, win-tally narrative,
# memorization caveats, negative results) is hand-written — it is the
# credibility layer and stays human judgment. This detector makes it
# impossible to MISS a score change that prose depends on: it compares the
# freshly computed scores against a prior release's scores.json and prints
# a review checklist. Warnings only; it changes nothing.

def diff_prose(scores: dict, old_path: Path, results_dir: Path) -> None:
    old = json.loads(old_path.read_text())
    warns: list[str] = []

    old_pg = {r["group"]: r for r in old.get("per_group", [])}
    new_pg = {r["group"]: r for r in scores["per_group"]}
    for g in sorted(set(old_pg) | set(new_pg)):
        ow = old_pg.get(g, {}).get("winner")
        nw = new_pg.get(g, {}).get("winner")
        if ow != nw:
            warns.append(f"WINNER CHANGED in {g}: {ow} → {nw} — review every "
                         "prose mention of this genre (loss/win sentences, caveats)")

    tally_moves = []
    for stem in ENGINE_STEMS:
        o = old.get("balanced", {}).get(stem, {}).get("wins")
        n = scores["balanced"][stem]["wins"]
        if o != n:
            tally_moves.append(f"{stem} {o} → {n}")
    if tally_moves:
        warns.append("WIN TALLY changed: " + ", ".join(tally_moves)
                     + " — review the 'X / 9 genres' narrative")

    for level in ("balanced", "micro"):
        label = "genre-balanced" if level == "balanced" else "all-pieces (micro)"
        for stem in ENGINE_STEMS:
            o = old.get(level, {}).get(stem, {}).get("exact_pct")
            n = scores[level][stem]["exact_pct"]
            if o is not None and math.floor(o / 10) != math.floor(n / 10):
                threshold = 10 * max(math.floor(o / 10), math.floor(n / 10))
                warns.append(f"{stem} {label} exact crossed {threshold}%: "
                             f"{o:.2f} → {n:.2f} — state plainly if the prose "
                             "mentions it (no hype)")
        o_lead = (old.get(level, {}).get("contrapunctus", {}).get("exact_pct", 0)
                  - old.get(level, {}).get("augmentednet", {}).get("exact_pct", 0))
        n_lead = (scores[level]["contrapunctus"]["exact_pct"]
                  - scores[level]["augmentednet"]["exact_pct"])
        if (o_lead > 0) != (n_lead > 0):
            warns.append(f"LEAD SIGN FLIP vs AugmentedNet ({label}): "
                         f"{o_lead:+.2f}pp → {n_lead:+.2f}pp — rewrite the "
                         "headline claim")
        elif abs(n_lead - o_lead) > 0.5:
            warns.append(f"lead vs AugmentedNet moved ({label}): "
                         f"{o_lead:+.2f}pp → {n_lead:+.2f}pp — update any "
                         "quoted '+X.XXpp' in the prose")

    for g in sorted(set(old_pg) & set(new_pg)):
        o, n = old_pg[g]["contrapunctus"], new_pg[g]["contrapunctus"]
        if (o < 50) != (n < 50):
            warns.append(f"contrapunctus crossed 50% in {g}: {o:.2f} → {n:.2f}")

    oc, nc = old.get("common_subset", {}), scores["common_subset"]
    if (oc.get("pieces"), oc.get("events")) != (nc["pieces"], nc["events"]):
        warns.append(f"COMMON SUBSET changed: {oc.get('pieces')} pieces / "
                     f"{oc.get('events')} events → {nc['pieces']} / "
                     f"{nc['events']} — update the counts sentence under the "
                     "all-pieces table and rerun `make manifest`")

    readme = (REPO_ROOT / "README.md").read_text()
    stale = sorted({d for d in re.findall(r"results/(\d{4}-\d{2}-\d{2})", readme)
                    if d != results_dir.name})
    if stale:
        warns.append("README prose still references "
                     + ", ".join(f"results/{d}/" for d in stale)
                     + f" — repoint the latest-release mentions at "
                       f"results/{results_dir.name}/")

    print(f"\nPROSE REVIEW — deltas vs {old_path} that the hand-written "
          "narrative may depend on:")
    if warns:
        for w in warns:
            print(f"  • {w}")
        print("  (nothing was changed automatically — fix the prose by hand, "
              "then rerun --check)")
    else:
        print("  no prose-relevant deltas detected")


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


def rel(path: Path) -> Path:
    """Path relative to the repo root when inside it (prettier output);
    the absolute path otherwise (e.g. a scratch dir in tests)."""
    try:
        return path.relative_to(REPO_ROOT)
    except ValueError:
        return path


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
    parser = argparse.ArgumentParser(
        description="Aggregate the committed per-piece engine reports into "
                    "the headline tables.")
    parser.add_argument("results_dir", nargs="?", default=None,
                        help="results/<date> directory (default: newest)")
    parser.add_argument("--check", action="store_true",
                        help="verify every README number matches scores.json")
    parser.add_argument("--write-readme", action="store_true",
                        help="rewrite the README's generated table regions "
                             "from the computed scores")
    parser.add_argument("--diff-prose", metavar="OLD_SCORES_JSON", default=None,
                        help="print prose-relevant deltas vs a prior "
                             "release's scores.json (warnings only)")
    opts = parser.parse_args()

    if opts.results_dir:
        results_dir = Path(opts.results_dir)
        if not results_dir.is_absolute():
            results_dir = (REPO_ROOT / results_dir).resolve()
    else:
        candidates = sorted(d for d in RESULTS_ROOT.iterdir() if d.is_dir())
        if not candidates:
            raise SystemExit("no results/<date>/ directories found")
        results_dir = candidates[-1]

    print(f"results: {rel(results_dir)}\n")

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

    print(f"\nwrote {rel(out_path)}")

    if opts.write_readme:
        write_readme(scores)
    if opts.diff_prose:
        old_path = Path(opts.diff_prose)
        if not old_path.is_absolute():
            old_path = (REPO_ROOT / old_path).resolve()
        diff_prose(scores, old_path, results_dir)
    if opts.check:
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
