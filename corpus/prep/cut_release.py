#!/usr/bin/env python3
"""Cut a dated release: ingest a fresh engine report, regenerate the rest.

`make bench` is the deliberately-unrunnable full path (re-runs every rival
model). This is the lighter, routine path: the engine app refreshed its
numbers, and this repo must resync — copy the fresh engine report in, decide
rival reuse EMPIRICALLY, re-aggregate, regenerate the README tables, and
print the prose-review checklist. Run via:

    make release DATE=2026-06-10 [RIVALS=carry|fresh] [PRIOR=2026-06-09]

Steps:

 1. Slim $CONTRAPUNCTUS_APP_ROOT/corpus/target/corpus-report.json to
    single-pick rows (sorted by group/piece, canonical field order — the
    same schema as every committed report) and write it to
    results/<DATE>/contrapunctus.report.json. The report's embedded
    git_sha is compared against the app's published benchmarks.json
    meta.git_sha_short — a mismatch is a loud warning (the parity gate
    below is the real arbiter).

 2. Rival reports. RIVALS=carry (default) copies the prior release's
    three rival reports forward byte-for-byte. RIVALS=fresh re-slims the
    maintainer-side comparison outputs for the two neural rivals
    ($AUGNET_REPORT, $ANALYSISGNN_REPORT; defaults under /tmp where the
    engine app's refresh writes them) — use it when the carry-forward
    attempt fails the parity gate because the rivals' fixed outputs were
    re-scored against updated ground truth. Music21 is a fixed external
    tool and is always carried forward unless $MUSIC21_REPORT is set.
    Do not assume which mode is right: run carry first and let the
    coverage gate + parity gate decide (that is the point of them).

 3. Re-aggregate via harness/score.py (writes scores.json and pins or
    validates common_subset.json — the coverage gate), then regenerate
    the README's generated table regions (--write-readme) and print the
    prose-change checklist against the prior release (--diff-prose).

 4. Parity gate: the freshly computed scores must reproduce the app's
    published benchmarks.json `cross_engine`, `cross_engine_balanced`,
    and `cross_engine_per_group` numbers to the decimal. If they do not,
    the release is NOT publishable — the discrepancy must be understood
    first (stale engine report, partial rival cache, subset drift).

 5. Print the release checklist (what passed, what needs a human).

Stdlib only. Reads the engine app at runtime via $CONTRAPUNCTUS_APP_ROOT
(default ../contrapunctus, like corpus/prep/build_manifest.py).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS_ROOT = REPO_ROOT / "results"
APP_ROOT = Path(os.environ.get("CONTRAPUNCTUS_APP_ROOT",
                               REPO_ROOT.parent / "contrapunctus"))

# Canonical slimmed-report schema: field order matches every committed
# report byte-for-byte (validated against the 2026-06-09 release).
ROW_FIELDS = ["mode", "group", "piece", "total", "exact", "sameChordGained",
              "inversionGained", "conventionGained", "sharedBassGained",
              "secondaryDiatonicGained"]
SLIM_DOC = ("Per-piece tier-count report on the 'single-pick' autonomous "
            "mode. One row per piece: total = ground-truth events; exact + "
            "the five *Gained counters partition the matched events by tier "
            "(see methodology/match-tiers.md). Slimmed to single-pick rows "
            "only (internal per-detector / key-accuracy diagnostic modes "
            "removed). Aggregate with `python3 harness/score.py`.")

# Where the engine app's refresh leaves the re-scored rival comparison
# reports on the maintainer's machine (RIVALS=fresh). Override via env.
FRESH_RIVAL_DEFAULTS = {
    "augmentednet": ("AUGNET_REPORT", "/tmp/augnet-report.json"),
    "analysisgnn": ("ANALYSISGNN_REPORT", "/tmp/analysisgnn-report.json"),
    "music21": ("MUSIC21_REPORT", None),  # fixed tool: carry unless forced
}

# scores.json stem -> benchmarks.json cross_engine_per_group row field.
PER_GROUP_FIELD = {
    "contrapunctus": "ours",
    "augmentednet": "augnet",
    "analysisgnn": "analysisgnn",
    "music21": "music21",
}
STEMS = list(PER_GROUP_FIELD)


def slim_report(src: dict) -> str:
    """Single-pick rows only, sorted, canonical field order, 1-space indent."""
    out: dict = {"engine": src["engine"]}
    if "engine_version" in src:
        out["engine_version"] = src["engine_version"]
    if "git_sha" in src:
        out["git_sha"] = src["git_sha"]
    out["timestamp"] = src["timestamp"]
    out["mode"] = "single-pick"
    out["_doc"] = SLIM_DOC
    rows = [r for r in src["rows"] if r.get("mode") == "single-pick"]
    if not rows:
        raise SystemExit("source report has no single-pick rows")
    rows.sort(key=lambda r: (r["group"], r["piece"]))
    out["rows"] = [{k: r[k] for k in ROW_FIELDS} for r in rows]
    return json.dumps(out, indent=1) + "\n"


def check_parity(scores: dict, bench: dict) -> list[str]:
    """Compare scores.json against the app's published benchmarks.json.

    Returns a list of mismatch descriptions (empty = parity holds). Engines
    are matched by position: both sides list them in the same fixed order
    (ours, AugmentedNet, AnalysisGNN, Music21); display names evolve and are
    not compared.
    """
    bad: list[str] = []

    def cmp(label: str, got, want) -> None:
        if got != want:
            bad.append(f"{label}: scores.json {got} != benchmarks.json {want}")

    m = re.match(r"(\d+)-piece common \(([\d,]+) events\)",
                 bench["cross_engine"].get("subset", ""))
    if m:
        cmp("common-subset pieces", scores["common_subset"]["pieces"],
            int(m.group(1)))
        cmp("common-subset events", scores["common_subset"]["events"],
            int(m.group(2).replace(",", "")))
    else:
        bad.append("could not parse benchmarks.json cross_engine.subset")

    for i, stem in enumerate(STEMS):
        eng = bench["cross_engine"]["engines"][i]
        cmp(f"micro {stem} exact", scores["micro"][stem]["exact_pct"],
            eng["exact"])
        cmp(f"micro {stem} a-d", scores["micro"][stem]["a_d_pct"],
            eng["total_a_d"])

        beng = bench["cross_engine_balanced"]["engines"][i]
        cmp(f"balanced {stem} exact", scores["balanced"][stem]["exact_pct"],
            beng["exact"])
        cmp(f"balanced {stem} a-d", scores["balanced"][stem]["a_d_pct"],
            beng["total_a_d"])

        wins = bench["cross_engine_balanced"]["wins_by_group"][i]
        cmp(f"wins {stem}", scores["balanced"][stem]["wins"], wins["wins"])

    site_rows = {r["group_id"]: r
                 for r in bench["cross_engine_per_group"]["rows"]}
    ours_rows = {r["group"]: r for r in scores["per_group"]}
    if sorted(site_rows) != sorted(ours_rows):
        bad.append(f"per-group genre sets differ: {sorted(ours_rows)} vs "
                   f"{sorted(site_rows)}")
    for g in sorted(set(site_rows) & set(ours_rows)):
        site, ours = site_rows[g], ours_rows[g]
        cmp(f"per-group {g} n_pieces", ours["n_pieces"], site["n_pieces"])
        for stem, field in PER_GROUP_FIELD.items():
            cmp(f"per-group {g} {stem} exact", ours[stem], site[field])
            cmp(f"per-group {g} {stem} a-d", ours[stem + "_ad"],
                site[field + "_ad"])
        cmp(f"per-group {g} delta-vs-augnet",
            round(ours["contrapunctus"] - ours["augmentednet"], 2),
            site["delta_vs_augnet"])
    return bad


def main() -> None:
    p = argparse.ArgumentParser(
        description="Cut a dated release from the engine app's fresh report.")
    p.add_argument("--date", required=True,
                   help="release date, YYYY-MM-DD (the results/<DATE> dir)")
    p.add_argument("--rivals", choices=["carry", "fresh"], default="carry",
                   help="carry rival reports from the prior release "
                        "(default) or re-slim the fresh comparison outputs")
    p.add_argument("--prior", default=None,
                   help="prior release date to carry from / diff against "
                        "(default: newest existing results/<date>)")
    args = p.parse_args()

    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.date):
        raise SystemExit(f"--date must be YYYY-MM-DD, got {args.date!r} "
                         "(make release DATE=YYYY-MM-DD)")

    out_dir = RESULTS_ROOT / args.date
    priors = sorted(d.name for d in RESULTS_ROOT.iterdir()
                    if d.is_dir() and d.name != args.date)
    prior = args.prior or (priors[-1] if priors else None)
    if prior is None:
        raise SystemExit("no prior release found to carry rivals from "
                         "(pass --prior)")
    prior_dir = RESULTS_ROOT / prior
    if not prior_dir.is_dir():
        raise SystemExit(f"prior release {prior_dir} does not exist")

    src_report = APP_ROOT / "corpus" / "target" / "corpus-report.json"
    bench_path = APP_ROOT / "frontend" / "src" / "data" / "benchmarks.json"
    for f, hint in ((src_report, "run the engine app's corpus refresh first"),
                    (bench_path, "set CONTRAPUNCTUS_APP_ROOT")):
        if not f.exists():
            raise SystemExit(f"cannot find {f} — {hint}")

    print(f"release: results/{args.date}  (prior: {prior}, "
          f"rivals: {args.rivals})")
    print(f"engine app: {APP_ROOT}")
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── 1. the engine report ─────────────────────────────────────────────
    src = json.loads(src_report.read_text())
    bench = json.loads(bench_path.read_text())
    sha = src.get("git_sha", "")
    site_sha = bench.get("meta", {}).get("git_sha_short", "")
    (out_dir / "contrapunctus.report.json").write_text(slim_report(src))
    n_rows = sum(1 for r in src["rows"] if r.get("mode") == "single-pick")
    print(f"\ncontrapunctus.report.json: {n_rows} single-pick rows from "
          f"{src_report}")
    print(f"  report git_sha: {sha}")
    if site_sha and sha.startswith(site_sha):
        print(f"  matches benchmarks.json meta.git_sha_short ({site_sha})")
    else:
        print(f"  *** WARNING: does NOT match benchmarks.json "
              f"meta.git_sha_short ({site_sha}).")
        print("      The report may be stale, or it was regenerated at a "
              "later, behavior-identical")
        print("      commit — the parity gate below decides; record the "
              "situation in PROVENANCE.md.")

    # ── 2. rival reports ─────────────────────────────────────────────────
    for stem, (env_var, fresh_default) in FRESH_RIVAL_DEFAULTS.items():
        dst = out_dir / f"{stem}.report.json"
        override = os.environ.get(env_var)
        fresh_path = override or (fresh_default if args.rivals == "fresh"
                                  else None)
        if fresh_path:
            fp = Path(fresh_path)
            if not fp.exists():
                raise SystemExit(f"fresh rival report missing: {fp} "
                                 f"(set ${env_var} or rerun the app refresh)")
            dst.write_text(slim_report(json.loads(fp.read_text())))
            print(f"{dst.name}: re-slimmed from {fp} (re-scored)")
        else:
            shutil.copyfile(prior_dir / dst.name, dst)
            print(f"{dst.name}: carried forward from results/{prior}")

    # ── 3. re-aggregate + regenerate the README tables ───────────────────
    print()
    score_py = REPO_ROOT / "harness" / "score.py"
    cmd = [sys.executable, str(score_py), str(out_dir), "--write-readme",
           "--diff-prose", str(prior_dir / "scores.json")]
    res = subprocess.run(cmd)
    if res.returncode != 0:
        raise SystemExit(
            f"\nscore.py failed (exit {res.returncode}). If the COVERAGE "
            "GATE fired: the common subset\nshifted under the carried-forward "
            "rivals — re-run with RIVALS=fresh (re-scored rival\nreports), "
            "or, for a not-yet-published release dir whose pin came from an "
            "earlier\nattempt, delete results/" + args.date +
            "/common_subset.json and re-run deliberately.")

    # ── 4. parity gate vs the published page data ────────────────────────
    scores = json.loads((out_dir / "scores.json").read_text())
    mismatches = check_parity(scores, bench)
    print()
    if mismatches:
        print("PARITY GATE FAILED — scores.json does not reproduce the app's "
              "benchmarks.json:")
        for mm in mismatches:
            print(f"  ✗ {mm}")
        print("\nDO NOT PUBLISH. Understand the discrepancy first "
              "(stale engine report? rival\nreports re-scored upstream? "
              "subset drift?). If the rivals were re-scored against\n"
              "updated ground truth, re-run with RIVALS=fresh.")
        raise SystemExit(2)
    print("PARITY GATE: OK — scores.json reproduces benchmarks.json "
          "cross_engine,\n  cross_engine_balanced, and "
          "cross_engine_per_group to the decimal.")

    # ── 5. checklist ─────────────────────────────────────────────────────
    print(f"""
RELEASE CHECKLIST — results/{args.date}
  [auto] coverage gate: passed (see score.py output above)
  [auto] parity vs app benchmarks.json: passed
  [auto] README generated tables: rewritten from scores.json
  [hand] PROSE REVIEW warnings above — fix the narrative by hand
  [hand] write results/{args.date}/PROVENANCE.md (which reports were
         regenerated vs carried forward, and why; engine git SHA)
  [hand] rerun `make manifest` if the corpus counts changed
  [hand] `make check`, then review `git diff` and commit""")


if __name__ == "__main__":
    main()
