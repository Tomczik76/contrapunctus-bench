"""Event-level diff: AugmentedNet vs ours at the exact tier.

⚠ DIAGNOSTIC — the "ours" side reads per-event prediction CSVs exported
by the closed engine's suite to /tmp/contrapunctus-picks/ (not
regenerable from this repo). This module is kept because (a) it hosts
the shared rntxt parsing helpers (`parse_rntxt_with_key_ts`) that
analysisgnn_comparison.py imports, and (b) the diff workflow documents
how miss patterns were analyzed.

For each piece, for each ground-truth event:
  - find our prediction (from /tmp/contrapunctus-picks/*.csv)
  - find AugmentedNet's prediction (from /tmp/augnet-runs/*/score_annotated.rntxt)
  - normalize both
  - report events where AugNet hits at exact tier but we miss

Categorizes the miss type so systematic fixes can be prioritized.
"""

import re
import os
import sys
from collections import Counter, defaultdict

# RN canonicalisation: SHARED canonical port (no music21 dependency).
# This module previously carried its OWN inline normalize — a third
# drifted copy that was even weaker than music21_comparison's (missing
# the alteration-suffix strip, Fr6→Fr43, Ger collapse, #vii strip) and
# was the normalizer AnalysisGNN got scored with. Import the canonical
# one; parity with Scala is enforced by test_rn_normalize_parity.py.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rn_normalize import normalize  # noqa: E402,F401

# __file__-relative paths so the script works from any worktree (the
# previous hardcoded absolute paths silently fell back to the main
# worktree, missing any scores fetched only in a feature branch — like
# the 350 expanded chorales + Monteverdi madrigals).
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SCRIPT_DIR)  # harness/ -> repo root (standalone bench layout)
CORPUS_ROOT = os.path.join(_REPO_ROOT, "corpus", "When-in-Rome", "Corpus")
SCORES_LOCAL_ROOT = os.path.join(_REPO_ROOT, "corpus", "scores-local")
AUGNET_OUT = "/tmp/augnet-runs"
OURS_PICKS = "/tmp/contrapunctus-picks"

PIECES = []
# Phase 2 corpus expansion (2026-05-26): baseline-9 dissolved into
# proper genres. WTC pieces folded into bach-wtc (all 24 preludes
# + 2 fugues); K545/1, K281/1 into mozart-sonatas-dcml; Op.18/1/2
# into beethoven-op18; Du bist die Ruh into schubert-lieder. Chopin
# Op.28/20 and Brahms Requiem mvt 1 dropped (no expansion path).
# Bach WTC I — all 24 preludes (01-24) + 2 separately-analyzed fugues
for n in range(1, 25):
    num = f"{n:02d}"
    PIECES.append((
        f"Bach WTC I Prelude {num}",
        f"Keyboard_Other/Bach,_Johann_Sebastian/The_Well-Tempered_Clavier_I/{num}",
        f"WTC_I_P{num}",
    ))
for fugue_num in ("19_fugue", "22_fugue"):
    label_n = fugue_num.split("_")[0]
    PIECES.append((
        f"Bach WTC I Fugue {label_n}",
        f"Keyboard_Other/Bach,_Johann_Sebastian/The_Well-Tempered_Clavier_I/{fugue_num}",
        f"WTC_I_F{label_n}",
    ))
# All 371 Bach Chorales (Riemenschneider). Only chorale 150 is missing
# in craigsapp/bach-370-chorales. Per-piece augnet-runs/ directory is
# generated lazily by run_augnet.sh; comparison evaluates whatever
# directories exist.
for n in range(1, 372):
    PIECES.append((f"Bach Chorale {n:03d}", f"Early_Choral/Bach,_Johann_Sebastian/Chorales/{n:03d}", f"Chorale{n:03d}"))
# 48 Monteverdi madrigals from music21 (Books 3-5).
for book, n_pieces in [("3", 20), ("4", 20), ("5", 8)]:
    for p in range(1, n_pieces + 1):
        PIECES.append((
            f"Monteverdi {book}.{p:02d}",
            f"Madrigals/Monteverdi,_Claudio/Book_{book}/{p:02d}",
            f"Monteverdi{book}_{p:02d}",
        ))
PIECES += [
    ("Beethoven Op.10/1 mvt 1",         "Piano_Sonatas/Beethoven,_Ludwig_van/Op010_No1/1",         "BeethovenOp10No1"),
    ("Beethoven Op.13 Pathétique mvt 1", "Piano_Sonatas/Beethoven,_Ludwig_van/Op013(Pathetique)/1", "BeethovenPathetique"),
    ("Beethoven Op.31/2 Tempest mvt 1",  "Piano_Sonatas/Beethoven,_Ludwig_van/Op031_No2/1",         "BeethovenTempest"),
    ("Beethoven Op.78 mvt 1",            "Piano_Sonatas/Beethoven,_Ludwig_van/Op078/1",             "BeethovenOp78"),
    ("Haydn Op.20/3 mvt 4", "Quartets/Haydn,_Franz_Joseph/Op20_No3/4", "HaydnOp20No3mvt4"),
    ("Haydn Op.20/4 mvt 1", "Quartets/Haydn,_Franz_Joseph/Op20_No4/1", "HaydnOp20No4mvt1"),
    ("Haydn Op.20/5 mvt 1", "Quartets/Haydn,_Franz_Joseph/Op20_No5/1", "HaydnOp20No5mvt1"),
    ("Haydn Op.20/6 mvt 4", "Quartets/Haydn,_Franz_Joseph/Op20_No6/4", "HaydnOp20No6mvt4"),
    # 7 Mozart Piano Sonatas (DCML contrasting movements + K545/1
    # and K281/1 absorbed from baseline-9)
    ("Mozart K545/1", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K545/1", "MozartK545mvt1"),
    ("Mozart K281/1", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K281/1", "MozartK281mvt1"),
    ("Mozart K281/2", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K281/2", "MozartK281mvt2"),
    ("Mozart K283/2", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K283/2", "MozartK283mvt2"),
    ("Mozart K310/1", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K310/1", "MozartK310mvt1"),
    ("Mozart K330/2", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K330/2", "MozartK330mvt2"),
    ("Mozart K284/3", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K284/3", "MozartK284mvt3"),
    ("Mozart K279/2", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K279/2", "MozartK279mvt2"),
    ("Mozart K279/3", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K279/3", "MozartK279mvt3"),
    ("Mozart K280/3", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K280/3", "MozartK280mvt3"),
    ("Mozart K281/3", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K281/3", "MozartK281mvt3"),
    ("Mozart K282/1", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K282/1", "MozartK282mvt1"),
    ("Mozart K282/2", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K282/2", "MozartK282mvt2"),
    ("Mozart K284/2", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K284/2", "MozartK284mvt2"),
    ("Mozart K309/1", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K309/1", "MozartK309mvt1"),
    ("Mozart K309/2", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K309/2", "MozartK309mvt2"),
    ("Mozart K309/3", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K309/3", "MozartK309mvt3"),
    ("Mozart K310/2", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K310/2", "MozartK310mvt2"),
    ("Mozart K311/1", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K311/1", "MozartK311mvt1"),
    ("Mozart K332/1", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K332/1", "MozartK332mvt1"),
    ("Mozart K457/2", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K457/2", "MozartK457mvt2"),
    ("Mozart K533/2", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K533/2", "MozartK533mvt2"),
    ("Mozart K545/3", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K545/3", "MozartK545mvt3"),
    ("Mozart K570/1", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K570/1", "MozartK570mvt1"),
    ("Mozart K576/1", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K576/1", "MozartK576mvt1"),
    # 11 TAVERN variation sets (Mozart + Beethoven)
    ("Mozart K179 (Fischer Minuet)", "Variations_and_Grounds/Mozart,_Wolfgang_Amadeus/_/K179", "TavernMozartK179"),
    ("Mozart K265 (Twinkle)",        "Variations_and_Grounds/Mozart,_Wolfgang_Amadeus/_/K265", "TavernMozartK265"),
    ("Mozart K354 (Je suis Lindor)", "Variations_and_Grounds/Mozart,_Wolfgang_Amadeus/_/K354", "TavernMozartK354"),
    ("Mozart K398 (Salve tu)",       "Variations_and_Grounds/Mozart,_Wolfgang_Amadeus/_/K398", "TavernMozartK398"),
    ("Mozart K501 (Andante 4hands)", "Variations_and_Grounds/Mozart,_Wolfgang_Amadeus/_/K501", "TavernMozartK501"),
    ("Mozart K573 (Duport Minuet)",  "Variations_and_Grounds/Mozart,_Wolfgang_Amadeus/_/K573", "TavernMozartK573"),
    ("Beethoven WoO 64 (Swiss)",         "Variations_and_Grounds/Beethoven,_Ludwig_van/_/WoO_64", "TavernBeethovenWoO64"),
    ("Beethoven WoO 65 (Venni amore)",   "Variations_and_Grounds/Beethoven,_Ludwig_van/_/WoO_65", "TavernBeethovenWoO65"),
    ("Beethoven WoO 70 (Nel cor)",       "Variations_and_Grounds/Beethoven,_Ludwig_van/_/WoO_70", "TavernBeethovenWoO70"),
    ("Beethoven WoO 75 (Es kommt)",      "Variations_and_Grounds/Beethoven,_Ludwig_van/_/WoO_75", "TavernBeethovenWoO75"),
    ("Beethoven WoO 77 (Original)",      "Variations_and_Grounds/Beethoven,_Ludwig_van/_/WoO_77", "TavernBeethovenWoO77"),
]

# Beethoven Op.18 string quartets — all 6 × 4 mvts = 24 movements.
for q in range(1, 7):
    for mvt in range(1, 5):
        PIECES.append((
            f"Beethoven Op.18/{q} mvt {mvt}",
            f"Quartets/Beethoven,_Ludwig_van/Op018_No{q}/{mvt}",
            f"BeethovenOp18No{q}mvt{mvt}",
        ))

# Schubert lieder — 46 songs across Winterreise, Schwanengesang, Schöne
# Müllerin, and singletons.
PIECES += [
    ("Schubert Die Sterne D.939",       "OpenScore-LiederCorpus/Schubert,_Franz/4_Lieder,_Op.96/1_Die_Sterne,_D.939",                "SchubertDieSterne"),
    ("Schubert Das Wandern",            "OpenScore-LiederCorpus/Schubert,_Franz/Die_schöne_Müllerin,_D.795/01_Das_Wandern",          "SchubertDasWandern"),
    ("Schubert Wohin",                  "OpenScore-LiederCorpus/Schubert,_Franz/Die_schöne_Müllerin,_D.795/02_Wohin",                "SchubertWohin"),
    ("Schubert Pause",                  "OpenScore-LiederCorpus/Schubert,_Franz/Die_schöne_Müllerin,_D.795/12_Pause",                "SchubertPause"),
    ("Schubert Trockne Blumen",         "OpenScore-LiederCorpus/Schubert,_Franz/Die_schöne_Müllerin,_D.795/18_Trockne_Blumen",       "SchubertTrockneBlumen"),
    ("Schubert Ave Maria",              "OpenScore-LiederCorpus/Schubert,_Franz/Op.52/6_Ellens_Gesang_III,_D.839_(Ave_Maria)",       "SchubertAveMaria"),
    ("Schubert Du bist die Ruh",        "OpenScore-LiederCorpus/Schubert,_Franz/Op.59/3_Du_bist_die_Ruh",                            "SchubertDuBistDieRuh"),
    ("Schubert Das Rosenband D.280",    "OpenScore-LiederCorpus/Schubert,_Franz/_/Das_Rosenband,_D.280",                             "SchubertDasRosenband"),
    ("Schubert Liebesbotschaft",        "OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/01_Liebesbotschaft",           "SchubertLiebesbotschaft"),
    ("Schubert Kriegers Ahnung",        "OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/02_Kriegers_Ahnung",           "SchubertKriegersAhnung"),
    ("Schubert Frühlingssehnsucht",     "OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/03_Frühlingssehnsucht",        "SchubertFruhlingssehnsucht"),
    ("Schubert Ständchen",              "OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/04_Ständchen",                 "SchubertStandchen"),
    ("Schubert Aufenthalt",             "OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/05_Aufenthalt",                "SchubertAufenthalt"),
    ("Schubert In der Ferne",           "OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/06_In_der_Ferne",              "SchubertInDerFerne"),
    ("Schubert Abschied",               "OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/07_Abschied",                  "SchubertAbschied"),
    ("Schubert Der Atlas",              "OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/08_Der_Atlas",                 "SchubertDerAtlas"),
    ("Schubert Ihr Bild",               "OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/09_Ihr_Bild",                  "SchubertIhrBild"),
    ("Schubert Das Fischermädchen",     "OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/10_Das_Fischermädchen",        "SchubertDasFischermadchen"),
    ("Schubert Die Stadt",              "OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/11_Die_Stadt",                 "SchubertDieStadt"),
    ("Schubert Am Meer",                "OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/12_Am_Meer",                   "SchubertAmMeer"),
    ("Schubert Der Doppelgänger",       "OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/13_Der_Doppelgänger",          "SchubertDerDoppelganger"),
    ("Schubert Die Taubenpost",         "OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/14_Die_Taubenpost",            "SchubertDieTaubenpost"),
]
# Winterreise (24 songs)
for n, name in [
    (1, "Gute_Nacht"), (2, "Die_Wetterfahne"), (3, "Gefror’ne_Thränen"),
    (4, "Erstarrung"), (5, "Der_Lindenbaum"), (6, "Wasserfluth"),
    (7, "Auf_dem_Flusse"), (8, "Rückblick"), (9, "Irrlicht"),
    (10, "Rast_(Spätere_Fassung)"), (11, "Frühlingstraum"),
    (12, "Einsamkeit_(Urspruengliche_Fassung)"), (13, "Die_Post"),
    (14, "Der_greise_Kopf"), (15, "Die_Kraehe"), (16, "Letzte_Hoffnung"),
    (17, "Im_Dorfe"), (18, "Der_stuermische_Morgen"), (19, "Täuschung"),
    (20, "Der_Wegweiser"), (21, "Das_Wirthshaus"), (22, "Muth"),
    (23, "Die_Nebensonnen"), (24, "Der_Leiermann_(Spätere_Fassung)"),
]:
    short = name.split("_(")[0].replace("_", " ")
    safe = name.split("_(")[0].replace("_", "").replace("’", "")
    PIECES.append((
        f"Schubert Winterreise {n:02d} {short}",
        f"OpenScore-LiederCorpus/Schubert,_Franz/Winterreise,_D.911/{n:02d}_{name}",
        f"SchubertW{n:02d}{safe}",
    ))

# Brahms lieder — 9 songs (Marienlieder Op.22 cycle + 2 orphans).
PIECES += [
    ("Brahms Liebe und Frühling II",          "OpenScore-LiederCorpus/Brahms,_Johannes/6_Songs,_Op.3/3_Liebe_und_Frühling_II",       "BrahmsLiebeUndFruhling2"),
    ("Brahms Liebesklage des Mädchens",       "OpenScore-LiederCorpus/Brahms,_Johannes/7_Lieder,_Op.48/3_Liebesklage_des_Mädchens",  "BrahmsLiebesklage"),
    ("Brahms Marienlieder 1 Der englische Gruss", "OpenScore-LiederCorpus/Brahms,_Johannes/Marienlieder,_Op.22/1_Der_englische_Gruss",  "BrahmsMarien1"),
    ("Brahms Marienlieder 2 Marias Kirchgang",    "OpenScore-LiederCorpus/Brahms,_Johannes/Marienlieder,_Op.22/2_Marias_Kirchgang",      "BrahmsMarien2"),
    ("Brahms Marienlieder 3 Marias Wallfahrt",    "OpenScore-LiederCorpus/Brahms,_Johannes/Marienlieder,_Op.22/3_Marias_Wallfahrt",      "BrahmsMarien3"),
    ("Brahms Marienlieder 4 Der Jäger",           "OpenScore-LiederCorpus/Brahms,_Johannes/Marienlieder,_Op.22/4_Der_Jäger",             "BrahmsMarien4"),
    ("Brahms Marienlieder 5 Ruf zur Maria",       "OpenScore-LiederCorpus/Brahms,_Johannes/Marienlieder,_Op.22/5_Ruf_zur_Maria",         "BrahmsMarien5"),
    ("Brahms Marienlieder 6 Magdalena",           "OpenScore-LiederCorpus/Brahms,_Johannes/Marienlieder,_Op.22/6_Magdalena",             "BrahmsMarien6"),
    ("Brahms Marienlieder 7 Marias Lob",          "OpenScore-LiederCorpus/Brahms,_Johannes/Marienlieder,_Op.22/7_Marias_Lob",            "BrahmsMarien7"),
]


def parse_rntxt_with_key_ts(path):
    """Parse rntxt → list of (measure, beat, key_letter_alt_mode_isMinor,
    rn, time_sig). The per-event time signature (the `Time Signature:`
    declaration in effect at the event) feeds the aligners' per-measure
    beat units — matching the engine-side per-event TS handling — so
    mid-piece TS changes stay aligned.

    Expands `mX-Y = mA-B` repeat-equality declarations by cloning events
    from source measures into target measures (apples-to-apples with the
    engine parser's repeat expansion). Without this, ground-truth event
    counts are mismatched between the Python diff script and the engine
    suite, causing false-positive misses in the diff.
    """
    events = []
    repeats = []
    current_key = None
    current_ts = "4/4"
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("Time Signature:"):
                current_ts = line.split(":", 1)[1].strip()
                continue
            if not line or line.startswith(("Note:", "Composer:", "Title:", "Analyst:", "Proofreader:",
                                            "Form:", "Pedal:", "Tempo:", "Movement:",
                                            "Piece:")):
                continue
            if re.match(r'^var\d', line) or line.startswith("!"):
                continue
            # Range repeat-equality declaration: `m12-15 = m8-11`. The
            # leading `m` on the source range is optional in some
            # When-in-Rome files (e.g. `m175-182 = 167-174` in
            # Pathétique). Without the `m?` we miss those lines.
            rm = re.match(r'^m(\d+)-(\d+)\s*=\s*m?(\d+)-(\d+)\s*$', line)
            if rm:
                repeats.append((
                    int(rm.group(1)), int(rm.group(2)),
                    int(rm.group(3)), int(rm.group(4)),
                ))
                continue
            # Single-measure equality: `m14 = m12` — clone exactly one
            # measure's events into another. Used in Pathétique and a
            # handful of other When-in-Rome rntxt files.
            rs = re.match(r'^m(\d+)\s*=\s*m?(\d+)\s*$', line)
            if rs:
                tgt = int(rs.group(1))
                src = int(rs.group(2))
                repeats.append((tgt, tgt, src, src))
                continue
            if "=" in line:
                continue

            m = re.match(r'^m(\d+)\s+(.*)$', line)
            if not m:
                continue
            measure = int(m.group(1))
            rest = m.group(2)
            tokens = rest.split()
            beat = 1.0
            for tok in tokens:
                bm = re.match(r'^b(\d+(?:\.\d+)?)$', tok)
                if bm:
                    beat = float(bm.group(1))
                    continue
                km = re.match(r'^([A-Ga-g][#b]?):$', tok)
                if km:
                    raw = km.group(1)
                    is_minor = raw[0].islower()
                    current_key = (raw, is_minor)
                    continue
                # Phrase-boundary markers (`||`, `:||`, `||:`) and the
                # cesura `||` are not chord labels — they're structural
                # markers. The engine's parser skips them; the Python
                # side previously appended them as bogus "events"
                # which then read as "engine missed at this beat"
                # despite there being nothing to predict. Filter here.
                if tok in ("||", ":||", "||:", ":||:"):
                    continue
                if current_key:
                    events.append((measure, beat, current_key, tok, current_ts))
    # Expand repeats: clone events from source to target measures.
    by_measure = {}
    for ev in events:
        by_measure.setdefault(ev[0], []).append(ev)
    for tgt_start, tgt_end, src_start, src_end in repeats:
        offset = tgt_start - src_start
        for src_m in range(src_start, src_end + 1):
            for ev in by_measure.get(src_m, []):
                _, beat, key, rn, ts = ev
                events.append((src_m + offset, beat, key, rn, ts))
    events.sort(key=lambda e: (e[0], e[1]))
    return events


def parse_rntxt_with_key(path):
    """Legacy 4-tuple view of [[parse_rntxt_with_key_ts]] — same events
    without the time-signature column. Kept for this module's own diff
    loops; new aligner code should use the _ts variant."""
    return [(m, b, k, rn) for (m, b, k, rn, _ts) in parse_rntxt_with_key_ts(path)]


def find_augnet_at(events, target_measure, target_beat):
    """Find AugmentedNet event at-or-before (target_measure, target_beat)."""
    best = None
    for m, b, k, rn in events:
        if (m, b) <= (target_measure, target_beat):
            best = rn
        else:
            break
    return best


def load_ours(label):
    """Load our predictions from CSV: {(measure, beat): (expected, picked)}."""
    path = f"{OURS_PICKS}/{label}.csv"
    out = {}
    with open(path) as f:
        next(f)  # header
        for line in f:
            parts = line.rstrip("\n").split(",")
            if len(parts) != 4:
                continue
            measure = int(parts[0])
            beat = float(parts[1])
            expected = parts[2]
            picked = parts[3]
            out[(measure, beat)] = (expected, picked)
    return out


def categorize_miss(expected, ours, augnet_hit):
    """Classify why we missed at exact when AugNet hit.

    Categories:
    - empty_pick:        we picked nothing (engine had no candidates)
    - power_chord:       we picked Vn / In (power chord) where expected has 7
    - wrong_inversion:   right chord, wrong inversion (V vs V6 vs V64)
    - missing_seventh:   we picked triad, expected has 7 (V vs V7)
    - extra_seventh:     we picked 7-chord, expected is triad
    - wrong_quality:     V vs V+, vii vs viio, etc.
    - sharp_vii_diff:    #vii vs vii prefix differ
    - cad_vs_v:          Cad64 vs V vs I64 differ
    - secondary_dom_diff: V/X label differ (X spelling, vs diatonic)
    - chord_identity:    completely different chord (ii vs V)
    - other:             anything else
    """
    if not ours:
        return "empty_pick"
    # Power chord
    if re.match(r'^[ivIV]+5$', ours):
        return "power_chord"
    # Strip everything after / for chord identity comparison
    def split(rn):
        if "/" in rn:
            return rn.split("/", 1)
        return (rn, None)
    e_base, e_target = split(expected)
    o_base, o_target = split(ours)
    # Sharp vii prefix diff
    if e_base.lstrip("#") == o_base.lstrip("#") and e_base.startswith("#") != o_base.startswith("#"):
        return "sharp_vii_diff"
    # Cad64
    if expected.startswith("Cad") or ours.startswith("Cad"):
        return "cad_vs_v"
    # Secondary-target differ
    if e_target != o_target:
        return "secondary_dom_diff"
    # Strip figured bass for inversion check
    def strip_fb(rn):
        return re.sub(r'\d+$', '', rn)
    if strip_fb(e_base) == strip_fb(o_base):
        return "wrong_inversion"
    # Triad vs 7-chord
    def is_seventh(rn):
        m = re.search(r'(\d+)$', rn)
        if m:
            n = int(m.group(1))
            return n in (7, 65, 43, 42)
        return False
    if not is_seventh(o_base) and is_seventh(e_base):
        return "missing_seventh"
    if is_seventh(o_base) and not is_seventh(e_base):
        return "extra_seventh"
    # Quality differ (o vs ø vs no marker)
    def strip_q(rn):
        return re.sub(r'[oøΔ+]', '', rn)
    if strip_q(e_base) != strip_q(o_base) and strip_fb(strip_q(e_base)) == strip_fb(strip_q(o_base)):
        return "wrong_quality"
    return "chord_identity"


def main():
    print()
    print("=" * 120)
    print("Event-level diff: events where AugNet hits EXACT and we MISS")
    print("=" * 120)
    cat_counter = Counter()
    examples_by_cat = defaultdict(list)
    total_their_only = 0
    total_our_only = 0
    total_both = 0
    total_neither = 0

    for label, rel_path, augnet_name in PIECES:
        gt_path = f"{CORPUS_ROOT}/{rel_path}/analysis.txt"
        augnet_path = f"{AUGNET_OUT}/{augnet_name}/score_annotated.rntxt"
        ours = load_ours(augnet_name)

        if not os.path.exists(augnet_path):
            print(f"  {label}: no augnet output")
            continue

        gt_events = parse_rntxt_with_key(gt_path)
        augnet_events = parse_rntxt_with_key(augnet_path)

        their_only = 0
        our_only = 0
        for measure, beat, (key_str, is_minor), gt_rn in gt_events:
            expected = normalize(gt_rn)
            if not expected:
                continue
            their_raw = find_augnet_at(augnet_events, measure, beat)
            their = normalize(their_raw) if their_raw else None
            their_hit_exact = (their is not None and their == expected)

            ours_entry = ours.get((measure, beat))
            if ours_entry is None:
                our_picked = ""
            else:
                _, our_picked = ours_entry
            our_hit_exact = (our_picked == expected)

            if their_hit_exact and not our_hit_exact:
                their_only += 1
                cat = categorize_miss(expected, our_picked, their)
                cat_counter[cat] += 1
                examples_by_cat[cat].append((label, measure, beat, expected, our_picked, their))
            elif our_hit_exact and not their_hit_exact:
                our_only += 1
            elif our_hit_exact and their_hit_exact:
                total_both += 1
            else:
                total_neither += 1

        total_their_only += their_only
        total_our_only += our_only
        print(f"  {label:<28} AugNet exact-only={their_only:<4} Ours exact-only={our_only:<4}")

    print()
    print("-" * 80)
    print(f"AGGREGATE: AugNet-only exact: {total_their_only}, Ours-only exact: {total_our_only}, Both: {total_both}, Neither: {total_neither}")
    print(f"Net deficit (AugNet wins - ours wins): {total_their_only - total_our_only}")
    print()
    print("Miss categories (where AugNet hit exact but we missed):")
    for cat, count in cat_counter.most_common():
        print(f"  {cat:<22} {count}")
    print()
    show_all = "--all" in sys.argv
    limit = 100 if show_all else 5
    print(f"Top {limit if not show_all else 'all'} examples per category:")
    for cat, count in cat_counter.most_common():
        print(f"\n[{cat}] ({count} total)")
        for ex in examples_by_cat[cat][:limit]:
            label, m, b, exp, ours_p, theirs = ex
            print(f"  {label:<28} m{m}\tb{b}\texp={exp}\tours={ours_p}\ttheirs={theirs}")


if __name__ == "__main__":
    main()
