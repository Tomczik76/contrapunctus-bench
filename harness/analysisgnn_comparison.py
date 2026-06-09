"""Compare AnalysisGNN (Karystinaios's current RN-GNN, ChordGNN's successor)
output to ground-truth analysis on the same 37-piece corpus we benchmark
AugmentedNet against.

AnalysisGNN output format (`<piece>_analysis.csv`):
    cadence,localkey,tonkey,quality,root,bass,inversion,degree1,degree2,
    romanNumeral,onset,s_measure
One row per 16th-note onset (or finer in non-4/4 meters). The
`romanNumeral` column is the RN label (e.g. "V7", "iv", "viio7/V"),
`localkey` is the current local-key letter ("C", "g", "Eb"), `s_measure`
is the 1-indexed measure number, `onset` is in absolute quarter-notes
from piece start.

For each ground-truth event `(measure, beat)`:
  1. Filter AnalysisGNN rows to s_measure == measure.
  2. Find the row whose onset (relative to the measure start) is
     closest to (beat - 1) * beat_unit_in_quarters.
  3. Read off the romanNumeral. Compose `localkey:romanNumeral` and
     run it through `normalize` — same canonicalization as the
     ground truth.

Reports per-piece + aggregate match rates at the same exact /
same-chord / interpretive tiers `augnet_comparison.py` uses.
"""

import csv
import os
import re
import sys
from collections import defaultdict

# __file__-relative path so this worktree's augnet_vs_ours_diff is
# imported (not the main worktree's — which can have a different
# PIECES list when feature branches expand the corpus).
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from augnet_vs_ours_diff import (
    normalize,
    parse_rntxt_with_key_ts,  # canonical rntxt parser w/ repeat expansion + per-event TS
    CORPUS_ROOT,
    PIECES,
)
from music21_comparison import classify_per_rule
from rn_normalize import rntxt_beats_per_measure

ANALYSISGNN_OUT = "/tmp/analysisgnn-runs"

# Tier-label → JSON group-id mapping. Mirrors augnet_comparison.py so
# the orchestrator can union JSON across engines cleanly. Phase 2 corpus
# expansion (2026-05-26): baseline-9 dissolved; added bach-wtc,
# beethoven-op18, schubert-lieder, brahms-lieder.
_GROUP_ID = {
    "Bach Chorales":             "chorales",
    "Monteverdi Madrigals":      "monteverdi",
    "Bach WTC I":                "bach-wtc",
    "Beethoven BPS-FH":          "beethoven-bps-fh",
    "Beethoven Op.18 Quartets":  "beethoven-op18",
    "Haydn Op.20":               "haydn-op20",
    "Mozart Sonatas (DCML)":     "mozart-sonatas-dcml",
    "Schubert Lieder":           "schubert-lieder",
    "Brahms Lieder":             "brahms-lieder",
    "TAVERN":                    "tavern",
}


def parse_time_signature(rntxt_path):
    """Read `Time Signature:` from the rntxt header. Returns (num, denom)."""
    with open(rntxt_path) as f:
        for line in f:
            line = line.strip()
            if line.lower().startswith(("time signature:", "time sig:")):
                ts = line.split(":", 1)[1].strip()
                m = re.match(r"(\d+)\s*/\s*(\d+)", ts)
                if m:
                    return int(m.group(1)), int(m.group(2))
    return 4, 4  # default 4/4


DEGREE_NUMERALS = {
    1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII",
}


def construct_rn(row):
    """Build an RN label from the AnalysisGNN multi-task columns.

    The `romanNumeral` column itself is from a separate prediction head
    and is empirically inconsistent with the more reliable `degree1` /
    `quality` / `inversion` predictions (verified by spot-checking
    Chorale 003 pickup: `romanNumeral=i` but degree1=5/quality=major
    triad/root=E, which is V — and V is what the analyst wrote).

    Build the label ourselves:
      - degree1 (1-7) → roman numeral letter (uppercase by default)
      - degree1 accidental prefix ("#7", "b6") → preserve as a "#" or
        "b" prefix on the numeral
      - quality determines case + suffix:
          major triad  → uppercase, no suffix
          minor triad  → lowercase, no suffix
          diminished triad → lowercase + "°"
          augmented triad  → uppercase + "+"
          *seventh*    → as triad + "7" (then figured-bass shaping
                         from inversion)
      - inversion (0-3) → figured-bass suffix:
          triad: 0→"", 1→"6", 2→"64"
          7-chord: 0→"7", 1→"65", 2→"43", 3→"42"
      - degree2 (when not "None"): append "/<degree2_numeral>" for
        tonicizations.
    """
    degree1_raw = row["degree1"]
    if not degree1_raw or degree1_raw == "None":
        return ""
    # degree1 may carry an accidental prefix: "#7", "b6", "7"
    prefix = ""
    while degree1_raw and degree1_raw[0] in "#b":
        prefix += degree1_raw[0]
        degree1_raw = degree1_raw[1:]
    try:
        d1 = int(degree1_raw)
    except ValueError:
        return ""
    if d1 < 1 or d1 > 7:
        return ""
    quality = (row.get("quality") or "").strip()
    inv_raw = row.get("inversion") or "0"
    try:
        inv = int(inv_raw)
    except ValueError:
        inv = 0
    # Determine triad case + suffix
    if "minor" in quality and "seventh" not in quality:
        numeral = DEGREE_NUMERALS[d1].lower()
        quality_marker = ""
        is_seventh = False
    elif "diminished" in quality and "seventh" not in quality:
        numeral = DEGREE_NUMERALS[d1].lower()
        quality_marker = "°"
        is_seventh = False
    elif "augmented" in quality and "seventh" not in quality:
        numeral = DEGREE_NUMERALS[d1]
        quality_marker = "+"
        is_seventh = False
    elif "half-diminished seventh" in quality or "half diminished seventh" in quality:
        numeral = DEGREE_NUMERALS[d1].lower()
        quality_marker = "ø"
        is_seventh = True
    elif "diminished seventh" in quality:
        numeral = DEGREE_NUMERALS[d1].lower()
        quality_marker = "°"
        is_seventh = True
    elif "minor seventh" in quality:
        numeral = DEGREE_NUMERALS[d1].lower()
        quality_marker = ""
        is_seventh = True
    elif "dominant seventh" in quality or "major-minor seventh" in quality:
        numeral = DEGREE_NUMERALS[d1]
        quality_marker = ""
        is_seventh = True
    elif "major seventh" in quality:
        numeral = DEGREE_NUMERALS[d1]
        quality_marker = ""  # could append Δ but corpus uses bare "7"
        is_seventh = True
    elif "seventh" in quality:
        numeral = DEGREE_NUMERALS[d1]
        quality_marker = ""
        is_seventh = True
    else:  # default to major triad
        numeral = DEGREE_NUMERALS[d1]
        quality_marker = ""
        is_seventh = False

    # Figured bass from inversion
    if is_seventh:
        fb = {0: "7", 1: "65", 2: "43", 3: "42"}.get(inv, "7")
    else:
        fb = {0: "", 1: "6", 2: "64"}.get(inv, "")

    label = f"{prefix}{numeral}{quality_marker}{fb}"

    # Secondary tonicization
    degree2_raw = row.get("degree2") or "None"
    if degree2_raw and degree2_raw != "None":
        d2_prefix = ""
        d2_clean = degree2_raw
        while d2_clean and d2_clean[0] in "#b":
            d2_prefix += d2_clean[0]
            d2_clean = d2_clean[1:]
        try:
            d2 = int(d2_clean)
            if 1 <= d2 <= 7:
                # The target's case follows the natural diatonic quality
                # in the local-key major-mode convention: V/V, V/vi,
                # V/IV etc. For simplicity, use lowercase for ii/iii/vi
                # and uppercase for I/IV/V/VII.
                t_numeral = DEGREE_NUMERALS[d2]
                if d2 in (2, 3, 6):
                    t_numeral = t_numeral.lower()
                label += f"/{d2_prefix}{t_numeral}"
        except ValueError:
            pass
    return label


def load_analysisgnn_csv(csv_path):
    """Read the CSV → list of (s_measure, onset, constructed_rn, localkey).

    Onset is float (quarter-notes from piece start). Returns rows sorted
    by (s_measure, onset). `constructed_rn` is built from
    degree1/quality/inversion/degree2 instead of the unreliable
    `romanNumeral` column.
    """
    rows = []
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                m = int(r["s_measure"])
                o = float(r["onset"])
                key = r["localkey"]
            except (KeyError, ValueError):
                continue
            rn = construct_rn(r)
            rows.append((m, o, rn, key))
    rows.sort(key=lambda x: (x[0], x[1]))
    return rows


def measure_starts(rows):
    """Compute the absolute-quarter-note onset where each s_measure begins."""
    starts = {}
    for m, o, _, _ in rows:
        if m not in starts or o < starts[m]:
            starts[m] = o
    return starts


def build_s_measure_spans(rows, fallback_len):
    """s_measure → (onset, actual_quarter_length), measured from the
    CSV's OWN per-measure onsets. Per-measure actual lengths replace
    the old uniform `(measure-1) × typical` extrapolation, which broke
    on mid-piece time-signature changes (the same bug class fixed in
    our Scala aligner and in music21_comparison). The last measure
    inherits the previous measure's length (or `fallback_len`)."""
    starts = measure_starts(rows)
    nums = sorted(starts)
    spans = {}
    for i, m in enumerate(nums):
        if i + 1 < len(nums):
            length = starts[nums[i + 1]] - starts[m]
        elif i > 0:
            length = spans[nums[i - 1]][1]
        else:
            length = fallback_len
        spans[m] = (starts[m], max(length, 1e-9))
    return spans


def compute_anacrusis_shift(spans):
    """1 when s_measure 1 is a short pickup — the rntxt analyst calls
    the pickup m0 and the first full measure m1, while Partitura's
    s_measure numbering counts the pickup as s_measure=1. 0 otherwise.
    (Same heuristic as the previous compute_rntxt_m1_onset, now
    expressed as a measure-number shift so per-measure spans can be
    looked up directly.)"""
    nums = sorted(spans)
    if len(nums) < 2 or nums[0] != 1:
        return 0
    first_len = spans[nums[0]][1]
    typical = spans[nums[1]][1]
    return 1 if first_len < typical * 0.95 else 0


def find_prediction(rows, spans, anacrusis_shift, target_measure, target_beat, time_sig):
    """Find the AnalysisGNN prediction at rntxt (target_measure, target_beat).

    The rntxt measure maps to s_measure via the anacrusis shift; the
    beat is scaled into the measure's ACTUAL length using the time
    signature in effect at the event (per-event TS from the rntxt) —
    mirroring the Scala eventToTick semantics. Returns
    "localkey:romanNumeral" or None when the measure is outside the
    prediction CSV (the caller counts that as a miss)."""
    s_m = target_measure + anacrusis_shift
    if s_m not in spans:
        return None
    m_off, m_len = spans[s_m]
    bpm = max(rntxt_beats_per_measure(time_sig), 1)
    rel = (target_beat - 1.0) * m_len / bpm
    target_onset = m_off + min(max(rel, 0.0), m_len - 1e-6)
    best = None
    for m, o, rn, key in rows:
        if o > target_onset + 0.125:
            break
        # at-or-before — keep updating to the latest
        best = (rn, key, o)
    if best is None:
        return None
    rn, key, _ = best
    return f"{key}:{rn}"


def main():
    print()
    print("=" * 110)
    print("AnalysisGNN vs ground-truth (37-piece corpus)")
    print("=" * 110)

    rows_template = f"{{label:<28s}} {{events:>6}}  exact %  {{exact_pct:>6.2f}}  ({{exact:>4}}/{{events}})"
    print(f"{'Piece':<28s} {'Events':>6s}  exact %       (matches)")
    print("-" * 110)

    grand_total = 0
    grand_exact = 0
    per_tier = defaultdict(lambda: {"total": 0, "exact": 0})
    # Per-piece per-rule counters for JSON output. Each entry:
    # (label, group_id, total, exact, sc, conv, sb, sd)
    json_rows = []

    for label, rel_path, agnn_name, *rest in PIECES:
        # Prefer submodule rntxt; fall back to scores-local (Monteverdi
        # madrigals live entirely under scores-local).
        rntxt_path = f"{CORPUS_ROOT}/{rel_path}/analysis.txt"
        if not os.path.exists(rntxt_path):
            from augnet_vs_ours_diff import SCORES_LOCAL_ROOT
            alt = f"{SCORES_LOCAL_ROOT}/{rel_path}/analysis.txt"
            if os.path.exists(alt):
                rntxt_path = alt
        csv_path = f"{ANALYSISGNN_OUT}/{agnn_name}/{agnn_name}_analysis.csv"
        if not os.path.exists(rntxt_path):
            print(f"  {label}: no rntxt at {rntxt_path}, skipping")
            continue
        if not os.path.exists(csv_path):
            print(f"  {label}: no analysisgnn CSV at {csv_path}, skipping")
            continue

        gt = parse_rntxt_with_key_ts(rntxt_path)
        ts_num, ts_denom = parse_time_signature(rntxt_path)
        # Header-TS bar length — only the last-measure fallback for the
        # span builder; alignment proper uses per-measure actual spans
        # + each event's own TS.
        fallback_len = ts_num * (4.0 / ts_denom)

        rows = load_analysisgnn_csv(csv_path)
        spans = build_s_measure_spans(rows, fallback_len)
        anacrusis_shift = compute_anacrusis_shift(spans)

        total = 0
        exact = 0
        # Per-rule counters mirroring the Scala test's ComparisonCounts
        # (used for the JSON report). Mutually exclusive — each event
        # lands in exactly one bucket via classify_per_rule's priority.
        per_rule = [0, 0, 0, 0, 0, 0]  # exact, same_chord, inversion, convention, shared_bass, secondary_diatonic
        # Per-beat key-accuracy: total beats with both GT key and
        # AnalysisGNN key, plus correct matches.
        key_total = 0
        key_correct = 0
        for measure, beat, key, gt_rn, ev_ts in gt:
            expected = normalize(gt_rn)
            if not expected:
                continue
            total += 1
            pred_raw = find_prediction(rows, spans, anacrusis_shift, measure, beat, ev_ts)
            if pred_raw is None:
                continue
            # Strip the key prefix the engine emits ("C:I" → "I")
            # the same way the ground-truth normalizer does.
            pred_key, _, pred_rn = pred_raw.partition(":")
            pred = normalize(pred_rn)
            if pred == expected:
                exact += 1
            # Key-accuracy: compare AnalysisGNN's localkey letter to
            # the analyst's. Both use case-as-mode convention ("C" =
            # C major, "g" = g minor) so a direct string match works
            # for the common case. Bb vs B-flat alt-spellings could
            # diverge — those will count as misses for now (small
            # fraction of total).
            key_total += 1
            gt_key_str = key[0]  # raw letter from parse_rntxt_with_key
            if pred_key.strip() == gt_key_str.strip():
                key_correct += 1
            # Per-rule attribution for the JSON report. Uses the same
            # classifier as the Scala test + AugNet comparison, so the
            # `same_chord` / `shared_bass` etc. columns are apples-to-
            # apples across engines.
            # parse_rntxt_with_key returns key = (raw_letter, is_minor_bool)
            is_minor = key[1]
            tier = classify_per_rule(expected, is_minor, pred)
            if tier == "exact":                per_rule[0] += 1
            elif tier == "same_chord":         per_rule[1] += 1
            elif tier == "inversion":          per_rule[2] += 1
            elif tier == "convention":         per_rule[3] += 1
            elif tier == "shared_bass":        per_rule[4] += 1
            elif tier == "secondary_diatonic": per_rule[5] += 1

        pct = 100.0 * exact / total if total else 0.0
        print(f"{label:<28s} {total:>6d}  {pct:>6.2f}%       ({exact}/{total})")

        grand_total += total
        grand_exact += exact

        # Tier aggregation: figure out which sub-corpus this piece is in.
        # Order matters — TAVERN comes BEFORE the BPS-FH check because
        # `TavernBeethovenWoO64` also `startswith("Beethoven")`.
        # Phase 2 corpus expansion (2026-05-26): added WTC, Op.18,
        # Schubert/Brahms lieder; baseline-9 dissolved.
        if "Chorale" in agnn_name:
            tier_name = "Bach Chorales"
        elif agnn_name.startswith("Monteverdi"):
            tier_name = "Monteverdi Madrigals"
        elif agnn_name.startswith("WTC_I_"):
            tier_name = "Bach WTC I"
        elif agnn_name.startswith("Tavern"):
            tier_name = "TAVERN"
        elif agnn_name.startswith("MozartK") and "mvt" in agnn_name:
            tier_name = "Mozart Sonatas (DCML)"
        elif agnn_name.startswith("BeethovenOp18No"):
            tier_name = "Beethoven Op.18 Quartets"
        elif agnn_name.startswith("Schubert"):
            tier_name = "Schubert Lieder"
        elif agnn_name.startswith("Brahms"):
            tier_name = "Brahms Lieder"
        elif agnn_name.startswith("Beethoven") and agnn_name != "Beethoven":
            tier_name = "Beethoven BPS-FH"
        elif agnn_name.startswith("Haydn"):
            tier_name = "Haydn Op.20"
        else:
            tier_name = "unknown"
        per_tier[tier_name]["total"] += total
        per_tier[tier_name]["exact"] += exact
        json_rows.append((label, _GROUP_ID.get(tier_name, "unknown"), total, *per_rule, key_total, key_correct))

    print("-" * 110)
    if grand_total == 0:
        # No piece produced any comparable events — almost always because the
        # raw per-piece CSVs under /tmp/analysisgnn-runs were purged (e.g. the
        # macOS /tmp reaper clears files older than ~3 days; the empty piece
        # dirs survive but their *_analysis.csv contents are gone). Fail with
        # an actionable message instead of a cryptic ZeroDivisionError, and
        # WITHOUT overwriting /tmp/analysisgnn-report.json (so a stale-but-real
        # report isn't clobbered with an empty one).
        print(
            "GRAND TOTAL: 0 pieces matched — no *_analysis.csv under "
            "/tmp/analysisgnn-runs (the raw inference cache was purged). "
            "Re-run AnalysisGNN inference:\n"
            "    bash harness/engines/analysisgnn/run_analysisgnn.sh",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"{'GRAND TOTAL':<28s} {grand_total:>6d}  {100.0 * grand_exact / grand_total:>6.2f}%       ({grand_exact}/{grand_total})")
    print()
    print("Per-tier:")
    for tier_name, st in per_tier.items():
        pct = 100.0 * st["exact"] / st["total"] if st["total"] else 0.0
        print(f"  {tier_name:<24s} {st['total']:>6d}  {pct:>6.2f}%   ({st['exact']}/{st['total']})")

    # ── JSON report for the orchestrator ──
    import json, datetime
    out_path = "/tmp/analysisgnn-report.json"
    all_rows = []
    for (label, group, total, ex, sc, inv, co, sb, sd, kt, kc) in json_rows:
        all_rows.append({
            "mode": "single-pick",
            "group": group,
            "piece": label,
            "total": total,
            "exact": ex,
            "sameChordGained": sc,
            "inversionGained": inv,
            "conventionGained": co,
            "sharedBassGained": sb,
            "secondaryDiatonicGained": sd,
        })
        if kt > 0:
            all_rows.append({
                "mode": "key-acc-analysisgnn",
                "group": group,
                "piece": label,
                "total": kt,
                "exact": kc,
                "sameChordGained": 0,
                "inversionGained": 0,
                "conventionGained": 0,
                "sharedBassGained": 0,
                "secondaryDiatonicGained": 0,
            })
    doc = {
        "engine": "analysisgnn",
        "engine_version": "v1.0.0-default-model",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "rows": all_rows,
    }
    with open(out_path, "w") as f:
        json.dump(doc, f, indent=2)
    print(f"[corpus-report] wrote {len(all_rows)} rows to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
