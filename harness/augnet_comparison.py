"""Compare AugmentedNet output to ground-truth analysis on the same corpus.

For each piece:
  1. Parse ground truth (corpus analysis.txt) → list of (measure, beat, expected_RN)
  2. Parse AugmentedNet output (score_annotated.rntxt) → list of (measure, beat, predicted_RN)
  3. Match each ground-truth event to the corresponding AugmentedNet prediction
     (interpolating from the most-recent AugmentedNet event at-or-before the ground-truth's (measure, beat))
  4. Apply the same RnNormalize logic our test uses, then check strict + total tiers

Reports per-piece + aggregate match rates.
"""

import re
import os
import sys
from collections import Counter

# Reuse the normalization helpers from our music21_comparison script.
# Use a __file__-relative path so this worktree's helpers (not the
# main worktree's) get imported when feature branches expand the
# corpus — the earlier hardcoded absolute path silently fell back to
# the main worktree and reduced PIECES from 550 → 452.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from music21_comparison import (
    normalize,
    expand_simpler_forms,
    expand_inversions,
    expand_cad,
    strip_minor_flat,
)


# __file__-relative paths so the script works from any worktree (the
# previous hardcoded absolute paths silently fell back to the main
# worktree, missing any scores fetched only in a feature branch — like
# the 350 expanded chorales + Monteverdi madrigals).
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SCRIPT_DIR)  # harness/ -> repo root (standalone bench layout)
CORPUS_ROOT = os.path.join(_REPO_ROOT, "corpus", "When-in-Rome", "Corpus")
SCORES_LOCAL_ROOT = os.path.join(_REPO_ROOT, "corpus", "scores-local")
AUGNET_OUT = "/tmp/augnet-runs"

# ── AugmentedNet train/validation/test split provenance ──────────────
# The authoritative source is AugmentedNet's OWN dataset manifest
# (AugmentedNet/data/*.py in the local checkout), exported to the
# committed `augnet_splits.json` by `augnet_splits_dump.py`. The
# hand labels on the PIECES entries below are the FALLBACK when that
# JSON is absent; they were corrected 2026-06-09 after reading the
# manifest directly — the previous labels marked TAVERN / Op.18 /
# most WTC preludes / most Schubert+Brahms lieder as "OOD" when they
# are in fact in AugmentedNet's training collections (data/__init__.py:
# abc, bps, haydnsun, keymodt, mps, tavern, wir, wirwtc).
_AUGNET_SPLITS_CACHE = None


def _augnet_splits():
    global _AUGNET_SPLITS_CACHE
    if _AUGNET_SPLITS_CACHE is None:
        import json as _json
        p = os.path.join(_SCRIPT_DIR, "augnet_splits.json")
        if os.path.exists(p):
            with open(p) as f:
                _AUGNET_SPLITS_CACHE = _json.load(f).get("splits", {})
        else:
            _AUGNET_SPLITS_CACHE = {}
    return _AUGNET_SPLITS_CACHE


def augnet_split_for(rel_path, hand_label):
    """'training' | 'validation' | 'test' | 'OOD' for one of OUR pieces,
    from AugmentedNet's manifest-derived map when available (pieces
    absent from the map are out-of-dataset), else the hand fallback."""
    splits = _augnet_splits()
    if splits:
        return splits.get(rel_path, "OOD")
    return hand_label

PIECES = []

# Phase 2 corpus expansion (2026-05-26): baseline-9 dissolved into
# proper genre buckets. WTC pieces folded into bach-wtc; K545/K281
# into mozart-sonatas-dcml; Op.18 quartet into beethoven-op18;
# Schubert lied into schubert-lieder. Chopin Op.28/20 and Brahms
# Requiem mvt 1 dropped (no expansion path — only orphan members
# of their would-be genres).

# Tier 1f — Bach WTC Book I: all 24 preludes (01-24) + 2 separately-
# analyzed fugues (19_fugue, 22_fugue). ALL 24 preludes are in
# AugmentedNet's `wirwtc` dataset (verified from its data package:
# 12 training / 6 validation / 6 test) — only the two fugues are OOD.
_WTC_AUGNET_SPLITS = (
    {n: "training" for n in (1, 2, 4, 5, 6, 10, 13, 14, 19, 20, 21, 23)}
    | {n: "validation" for n in (7, 9, 11, 16, 17, 18)}
    | {n: "test" for n in (3, 8, 12, 15, 22, 24)}
)
for n in range(1, 25):
    num = f"{n:02d}"
    PIECES.append((
        f"Bach WTC I Prelude {num}",
        f"Keyboard_Other/Bach,_Johann_Sebastian/The_Well-Tempered_Clavier_I/{num}",
        f"WTC_I_P{num}",
        _WTC_AUGNET_SPLITS[n],
    ))
for fugue_num in ("19_fugue", "22_fugue"):
    label_n = fugue_num.split("_")[0]
    PIECES.append((
        f"Bach WTC I Fugue {label_n}",
        f"Keyboard_Other/Bach,_Johann_Sebastian/The_Well-Tempered_Clavier_I/{fugue_num}",
        f"WTC_I_F{label_n}",
        "OOD",
    ))

# Tier 1a — All 371 Bach chorales (Riemenschneider). AugmentedNet's
# `wir` collection contains chorales {1..20} ∖ {11, 15} (12 training /
# 3 validation / 3 test, verified from its data package); 11, 15 and
# 021-371 are OOD for AugNet but in-corpus for us — surfaces
# neural-vs-rule-based generalization on the broader chorale set.
_CHORALE_AUGNET_SPLITS = (
    {n: "training" for n in (1, 3, 5, 6, 7, 8, 9, 12, 13, 17, 18, 20)}
    | {n: "validation" for n in (2, 14, 16)}
    | {n: "test" for n in (4, 10, 19)}
)
for n in range(1, 372):
    PIECES.append((
        f"Bach Chorale {n:03d}",
        f"Early_Choral/Bach,_Johann_Sebastian/Chorales/{n:03d}",
        f"Chorale{n:03d}",
        _CHORALE_AUGNET_SPLITS.get(n, "OOD"),
    ))

# Tier 1.5 — 48 Monteverdi madrigals from music21 (Books 3-5, 1592-1605).
# Pre-tonal, definitely OOD for AugNet.
for book, n_pieces in [("3", 20), ("4", 20), ("5", 8)]:
    for p in range(1, n_pieces + 1):
        PIECES.append((
            f"Monteverdi {book}.{p:02d}",
            f"Madrigals/Monteverdi,_Claudio/Book_{book}/{p:02d}",
            f"Monteverdi{book}_{p:02d}",
            "OOD",
        ))

# Tier 1b — 4 Beethoven Sonatas from BPS-FH (AugmentedNet training).
for label, rel, out in [
    ("Beethoven Op.10/1 mvt 1",  "Piano_Sonatas/Beethoven,_Ludwig_van/Op010_No1/1",        "BeethovenOp10No1"),
    ("Beethoven Op.13 Pathétique mvt 1", "Piano_Sonatas/Beethoven,_Ludwig_van/Op013(Pathetique)/1", "BeethovenPathetique"),
    ("Beethoven Op.31/2 Tempest mvt 1",  "Piano_Sonatas/Beethoven,_Ludwig_van/Op031_No2/1",        "BeethovenTempest"),
    ("Beethoven Op.78 mvt 1",     "Piano_Sonatas/Beethoven,_Ludwig_van/Op078/1",            "BeethovenOp78"),
]:
    PIECES.append((label, rel, out, "training"))

# Tier 1c — 4 Haydn Op. 20 movements (HaydnSun — AugmentedNet training).
for label, rel, out in [
    ("Haydn Op.20/3 mvt 4", "Quartets/Haydn,_Franz_Joseph/Op20_No3/4", "HaydnOp20No3mvt4"),
    ("Haydn Op.20/4 mvt 1", "Quartets/Haydn,_Franz_Joseph/Op20_No4/1", "HaydnOp20No4mvt1"),
    ("Haydn Op.20/5 mvt 1", "Quartets/Haydn,_Franz_Joseph/Op20_No5/1", "HaydnOp20No5mvt1"),
    ("Haydn Op.20/6 mvt 4", "Quartets/Haydn,_Franz_Joseph/Op20_No6/4", "HaydnOp20No6mvt4"),
]:
    PIECES.append((label, rel, out, "training"))

# Tier 1d — 7 Mozart Piano Sonatas (DCML contrasting movements).
# K545/1 and K281/1 folded in from baseline-9 (Phase 2 expansion).
# AugNet trained on K545/1 + K281/1 (test/training in original
# baseline); the K281/2..K284/3 movements are OOD.
for label, rel, out, split in [
    ("Mozart K545/1", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K545/1", "MozartK545mvt1", "test"),
    ("Mozart K281/1", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K281/1", "MozartK281mvt1", "training"),
    ("Mozart K281/2", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K281/2", "MozartK281mvt2", "OOD"),
    ("Mozart K283/2", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K283/2", "MozartK283mvt2", "OOD"),
    ("Mozart K310/1", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K310/1", "MozartK310mvt1", "OOD"),
    ("Mozart K330/2", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K330/2", "MozartK330mvt2", "OOD"),
    ("Mozart K284/3", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K284/3", "MozartK284mvt3", "OOD"),
    ("Mozart K279/2", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K279/2", "MozartK279mvt2", "OOD"),
    ("Mozart K279/3", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K279/3", "MozartK279mvt3", "OOD"),
    ("Mozart K280/3", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K280/3", "MozartK280mvt3", "OOD"),
    ("Mozart K281/3", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K281/3", "MozartK281mvt3", "OOD"),
    ("Mozart K282/1", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K282/1", "MozartK282mvt1", "OOD"),
    ("Mozart K282/2", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K282/2", "MozartK282mvt2", "OOD"),
    ("Mozart K284/2", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K284/2", "MozartK284mvt2", "OOD"),
    ("Mozart K309/1", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K309/1", "MozartK309mvt1", "OOD"),
    ("Mozart K309/2", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K309/2", "MozartK309mvt2", "OOD"),
    ("Mozart K309/3", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K309/3", "MozartK309mvt3", "OOD"),
    ("Mozart K310/2", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K310/2", "MozartK310mvt2", "OOD"),
    ("Mozart K311/1", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K311/1", "MozartK311mvt1", "OOD"),
    ("Mozart K332/1", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K332/1", "MozartK332mvt1", "OOD"),
    ("Mozart K457/2", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K457/2", "MozartK457mvt2", "OOD"),
    ("Mozart K533/2", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K533/2", "MozartK533mvt2", "OOD"),
    ("Mozart K545/3", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K545/3", "MozartK545mvt3", "OOD"),
    ("Mozart K570/1", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K570/1", "MozartK570mvt1", "OOD"),
    ("Mozart K576/1", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K576/1", "MozartK576mvt1", "OOD"),
]:
    # `mps` (the complete DCML Mozart sonata corpus) is an AugmentedNet
    # TRAINING collection (data/__init__.py) — the per-row "OOD" labels
    # above were wrong at the collection level. Flip them to "training"
    # as the conservative fallback; the exact per-movement
    # train/validation/test refinement comes from augnet_splits.json
    # (manifest-derived), which overrides these at scoring time.
    PIECES.append((label, rel, out, split if split != "OOD" else "training"))

# Tier 1g — Beethoven Op.18 string quartets, all 6 × 4 mvts = 24
# movements. The DCML ABC corpus (ALL Beethoven quartets, Op.18
# included) is AugmentedNet's `abc` TRAINING collection
# (data/__init__.py) — previously mislabeled OOD here. "training" is
# the conservative collection-level fallback; exact per-movement
# splits come from augnet_splits.json.
for q in range(1, 7):
    for mvt in range(1, 5):
        PIECES.append((
            f"Beethoven Op.18/{q} mvt {mvt}",
            f"Quartets/Beethoven,_Ludwig_van/Op018_No{q}/{mvt}",
            f"BeethovenOp18No{q}mvt{mvt}",
            "training",
        ))

# Tier 1h — Schubert lieder, 46 songs across Winterreise (24),
# Schwanengesang (14), Schöne Müllerin (4), and singletons from
# Op.52, Op.59, Op.96, and Das Rosenband. Op.59/3 was originally
# baseline-9 ("test" split); the rest are OOD.
SCHUBERT_LIEDER_PIECES = [
    ("Schubert Die Sterne D.939",                "OpenScore-LiederCorpus/Schubert,_Franz/4_Lieder,_Op.96/1_Die_Sterne,_D.939",                          "SchubertDieSterne"),
    ("Schubert Das Wandern",                     "OpenScore-LiederCorpus/Schubert,_Franz/Die_schöne_Müllerin,_D.795/01_Das_Wandern",                    "SchubertDasWandern"),
    ("Schubert Wohin",                           "OpenScore-LiederCorpus/Schubert,_Franz/Die_schöne_Müllerin,_D.795/02_Wohin",                          "SchubertWohin"),
    ("Schubert Pause",                           "OpenScore-LiederCorpus/Schubert,_Franz/Die_schöne_Müllerin,_D.795/12_Pause",                          "SchubertPause"),
    ("Schubert Trockne Blumen",                  "OpenScore-LiederCorpus/Schubert,_Franz/Die_schöne_Müllerin,_D.795/18_Trockne_Blumen",                 "SchubertTrockneBlumen"),
    ("Schubert Ave Maria",                       "OpenScore-LiederCorpus/Schubert,_Franz/Op.52/6_Ellens_Gesang_III,_D.839_(Ave_Maria)",                 "SchubertAveMaria"),
    ("Schubert Du bist die Ruh",                 "OpenScore-LiederCorpus/Schubert,_Franz/Op.59/3_Du_bist_die_Ruh",                                     "SchubertDuBistDieRuh"),
    ("Schubert Das Rosenband D.280",             "OpenScore-LiederCorpus/Schubert,_Franz/_/Das_Rosenband,_D.280",                                      "SchubertDasRosenband"),
    ("Schubert Liebesbotschaft",                 "OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/01_Liebesbotschaft",                    "SchubertLiebesbotschaft"),
    ("Schubert Kriegers Ahnung",                 "OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/02_Kriegers_Ahnung",                    "SchubertKriegersAhnung"),
    ("Schubert Frühlingssehnsucht",              "OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/03_Frühlingssehnsucht",                 "SchubertFruhlingssehnsucht"),
    ("Schubert Ständchen",                       "OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/04_Ständchen",                          "SchubertStandchen"),
    ("Schubert Aufenthalt",                      "OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/05_Aufenthalt",                         "SchubertAufenthalt"),
    ("Schubert In der Ferne",                    "OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/06_In_der_Ferne",                       "SchubertInDerFerne"),
    ("Schubert Abschied",                        "OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/07_Abschied",                           "SchubertAbschied"),
    ("Schubert Der Atlas",                       "OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/08_Der_Atlas",                          "SchubertDerAtlas"),
    ("Schubert Ihr Bild",                        "OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/09_Ihr_Bild",                           "SchubertIhrBild"),
    ("Schubert Das Fischermädchen",              "OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/10_Das_Fischermädchen",                 "SchubertDasFischermadchen"),
    ("Schubert Die Stadt",                       "OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/11_Die_Stadt",                          "SchubertDieStadt"),
    ("Schubert Am Meer",                         "OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/12_Am_Meer",                            "SchubertAmMeer"),
    ("Schubert Der Doppelgänger",                "OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/13_Der_Doppelgänger",                   "SchubertDerDoppelganger"),
    ("Schubert Die Taubenpost",                  "OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/14_Die_Taubenpost",                     "SchubertDieTaubenpost"),
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
    SCHUBERT_LIEDER_PIECES.append((
        f"Schubert Winterreise {n:02d} {short}",
        f"OpenScore-LiederCorpus/Schubert,_Franz/Winterreise,_D.911/{n:02d}_{name}",
        f"SchubertW{n:02d}{safe}",
    ))
def _schubert_augnet_split(rel):
    """AugmentedNet `wir` splits for our Schubert lieder (verified from
    its data package, 2026-06-09): 39 of our 46 songs are IN the
    dataset — complete Winterreise (20 training / 3 validation /
    1 test), 12 of 14 Schwanengesang songs (7/2/3), Die Sterne
    (validation), Pause + Du bist die Ruh (test). Only Das Wandern,
    Wohin, Trockne Blumen, Ave Maria, Das Rosenband, Liebesbotschaft
    and Ständchen are genuinely OOD. (Previously everything but Du
    bist die Ruh was mislabeled OOD.)"""
    m = re.search(r"Winterreise,_D\.911/(\d+)_", rel)
    if m:
        n = int(m.group(1))
        if n in (11, 18, 22):
            return "validation"
        if n == 3:
            return "test"
        return "training"
    m = re.search(r"Schwanengesang,_D\.957/(\d+)_", rel)
    if m:
        n = int(m.group(1))
        if n in (2, 3, 6, 9, 11, 12, 14):
            return "training"
        if n in (7, 13):
            return "validation"
        if n in (5, 8, 10):
            return "test"
        return "OOD"  # 01 Liebesbotschaft, 04 Ständchen
    if rel.endswith("1_Die_Sterne,_D.939"):
        return "validation"
    if rel.endswith("/Die_schöne_Müllerin,_D.795/12_Pause"):
        return "test"
    if rel.endswith("/Op.59/3_Du_bist_die_Ruh"):
        return "test"
    return "OOD"


for label, rel, out in SCHUBERT_LIEDER_PIECES:
    PIECES.append((label, rel, out, _schubert_augnet_split(rel)))

# Tier 1i — Brahms lieder, 9 songs across Op.3, Op.22 (Marienlieder),
# Op.48.
BRAHMS_LIEDER_PIECES = [
    ("Brahms Liebe und Frühling II",     "OpenScore-LiederCorpus/Brahms,_Johannes/6_Songs,_Op.3/3_Liebe_und_Frühling_II",       "BrahmsLiebeUndFruhling2"),
    ("Brahms Liebesklage des Mädchens",  "OpenScore-LiederCorpus/Brahms,_Johannes/7_Lieder,_Op.48/3_Liebesklage_des_Mädchens",  "BrahmsLiebesklage"),
    ("Brahms Marienlieder 1 Der englische Gruss", "OpenScore-LiederCorpus/Brahms,_Johannes/Marienlieder,_Op.22/1_Der_englische_Gruss",  "BrahmsMarien1"),
    ("Brahms Marienlieder 2 Marias Kirchgang",    "OpenScore-LiederCorpus/Brahms,_Johannes/Marienlieder,_Op.22/2_Marias_Kirchgang",      "BrahmsMarien2"),
    ("Brahms Marienlieder 3 Marias Wallfahrt",    "OpenScore-LiederCorpus/Brahms,_Johannes/Marienlieder,_Op.22/3_Marias_Wallfahrt",      "BrahmsMarien3"),
    ("Brahms Marienlieder 4 Der Jäger",           "OpenScore-LiederCorpus/Brahms,_Johannes/Marienlieder,_Op.22/4_Der_Jäger",             "BrahmsMarien4"),
    ("Brahms Marienlieder 5 Ruf zur Maria",       "OpenScore-LiederCorpus/Brahms,_Johannes/Marienlieder,_Op.22/5_Ruf_zur_Maria",         "BrahmsMarien5"),
    ("Brahms Marienlieder 6 Magdalena",           "OpenScore-LiederCorpus/Brahms,_Johannes/Marienlieder,_Op.22/6_Magdalena",             "BrahmsMarien6"),
    ("Brahms Marienlieder 7 Marias Lob",          "OpenScore-LiederCorpus/Brahms,_Johannes/Marienlieder,_Op.22/7_Marias_Lob",            "BrahmsMarien7"),
]
for label, rel, out in BRAHMS_LIEDER_PIECES:
    # AugmentedNet `wir` splits (verified): Op.48/3 Liebesklage =
    # training, Op.3/3 Liebe und Frühling II = validation; the 7
    # Marienlieder are genuinely OOD.
    if "7_Lieder,_Op.48/3_" in rel:
        split = "training"
    elif "6_Songs,_Op.3/3_" in rel:
        split = "validation"
    else:
        split = "OOD"
    PIECES.append((label, rel, out, split))

# Tier 1e — 11 TAVERN variation sets (Devaney 2015), Mozart + Beethoven.
# TAVERN IS one of AugmentedNet's training collections
# (data/__init__.py) — the previous "OOD" tag here was wrong and
# contradicted the engine-page prose. "training" is the conservative
# collection-level fallback; exact per-set splits (incl. the a/b
# encoder duplication) come from augnet_splits.json.
for label, rel, out in [
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
]:
    PIECES.append((label, rel, out, "training"))


def parse_rntxt(path):
    """Parse rntxt → list of (measure, beat, key_letter_alt_mode, rn).

    Expands `mX-Y = mA-B` repeat-equality declarations by cloning events
    from source measures into target measures — mirrors music21's
    RomanText parser and the engine parser's repeat expansion, keeping
    the apples-to-apples comparison aligned.
    """
    events = []
    repeats = []
    current_key = None
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith(("Note:", "Composer:", "Title:", "Analyst:", "Proofreader:",
                                              "Form:", "Pedal:", "Tempo:", "Time Signature:", "Movement:",
                                              "Piece:")):
                continue
            if re.match(r'^var\d', line) or line.startswith("!"):
                continue
            # Range repeat-equality: `m12-15 = m8-11`. Leading `m` on
            # source range is optional in some When-in-Rome files
            # (e.g. Pathétique `m175-182 = 167-174`).
            rm = re.match(r'^m(\d+)-(\d+)\s*=\s*m?(\d+)-(\d+)\s*$', line)
            if rm:
                repeats.append((
                    int(rm.group(1)), int(rm.group(2)),
                    int(rm.group(3)), int(rm.group(4)),
                ))
                continue
            # Single-measure equality: `m14 = m12`.
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
                    mode = 'major' if raw[0].isupper() else 'minor'
                    current_key = (raw[0].upper(), raw[1:] if len(raw) > 1 else '', mode)
                    continue
                # Phrase-boundary markers (`||`, `:||`, `||:`, `:||:`) are
                # structural rntxt syntax, not chord labels. Without this
                # filter, augnet event totals inflate by ~5 per chorale
                # (one per phrase boundary), which throws off the
                # head-to-head event counts vs ours / analysisgnn /
                # music21. The engine's parser already skips them.
                if tok in ("||", ":||", "||:", ":||:"):
                    continue
                if current_key:
                    events.append((measure, beat, current_key, tok))
    by_measure = {}
    for ev in events:
        by_measure.setdefault(ev[0], []).append(ev)
    for tgt_start, tgt_end, src_start, src_end in repeats:
        offset = tgt_start - src_start
        for src_m in range(src_start, src_end + 1):
            for ev in by_measure.get(src_m, []):
                _, beat, key, rn = ev
                events.append((src_m + offset, beat, key, rn))
    events.sort(key=lambda e: (e[0], e[1]))
    return events


def find_prediction_at(events, target_measure, target_beat):
    """Find the AugmentedNet event at or just before (target_measure, target_beat).
    Returns the predicted RN string."""
    best = None
    for m, b, k, rn in events:
        if (m, b) <= (target_measure, target_beat):
            best = rn
        else:
            break
    return best


# Reuse the music21_comparison classify (it's identical for our purposes).
# Just import here for clarity.
from music21_comparison import (
    classify,
    classify_per_rule,
    expand_shared_bass_alternatives,
    expand_secondary_diatonic_equivalence,
    write_report,
)


def _load_ours_csv(augnet_name):
    """Load our engine's per-event predictions from /tmp/contrapunctus-picks/
    keyed by (measure, beat).

    ⚠ DIAGNOSTIC ONLY — these CSVs are exported by the closed engine's
    suite (not regenerable from this repo) under ANALYST keychains, so
    the "Ours" column printed by this script is a chord-ID-isolation
    diagnostic, NOT the autonomous headline. Quoting it against AugNet's
    autonomous column overstates us. The published "ours" column comes
    from the committed autonomous report
    (results/<date>/contrapunctus.report.json), never from this file.
    Returns None when the piece has no CSV."""
    csv_path = f"/tmp/contrapunctus-picks/{augnet_name}.csv"
    if not os.path.exists(csv_path):
        return None
    out = {}
    with open(csv_path) as f:
        next(f, None)  # header: measure,beat,expected,picked
        for line in f:
            parts = line.rstrip('\n').split(',')
            if len(parts) < 4:
                continue
            try:
                m = int(parts[0])
                b = float(parts[1])
            except ValueError:
                continue
            picked = parts[3]
            out[(m, b)] = picked
    return out


def _classify_set(expected, predicted, is_minor):
    """Returns per-rule + cumulative-cumulative tier hits for one (expected,
    predicted) pair.

    Returns: (per_rule_tuple, cumulative_tuple) where
      per_rule = (exact, same_chord, convention, shared_bass, secondary_diatonic)
        — exclusive per-rule attribution (each event lands in at most one bucket)
      cumulative = (exact_hit, same_chord_or_better, interpretive_or_better)
        — bool flags matching the legacy 3-tier semantics for the head-to-head
        print table. Derivable from per_rule.
    """
    if predicted is None:
        return ((0, 0, 0, 0, 0, 0), (False, False, False))
    tier = classify_per_rule(expected, is_minor, predicted)
    if tier is None:
        return ((0, 0, 0, 0, 0, 0), (False, False, False))
    per_rule = (
        1 if tier == 'exact' else 0,
        1 if tier == 'same_chord' else 0,
        1 if tier == 'inversion' else 0,
        1 if tier == 'convention' else 0,
        1 if tier == 'shared_bass' else 0,
        1 if tier == 'secondary_diatonic' else 0,
    )
    # Legacy cumulative semantics: each tier is "this tier OR better."
    exact_hit = tier == 'exact'
    sc_hit = tier in ('exact', 'same_chord')
    ip_hit = True  # any non-None tier matches interpretive
    return (per_rule, (exact_hit, sc_hit, ip_hit))


def evaluate(label, rel_path, augnet_name, split):
    """Evaluate AugmentedNet AND our engine on the same ground-truth
    events using the same Python classifier. Returns per-engine event
    counts (both per-rule and cumulative) so the caller can build a
    head-to-head table AND the JSON report.
    """
    # Manifest-derived split overrides the hand fallback when the
    # committed augnet_splits.json exists (see augnet_splits_dump.py).
    split = augnet_split_for(rel_path, split)
    # Analysis path: prefer submodule (where most pieces live), fall
    # back to scores-local (Monteverdi madrigals live entirely there).
    submodule_gt = f"{CORPUS_ROOT}/{rel_path}/analysis.txt"
    local_gt = f"{SCORES_LOCAL_ROOT}/{rel_path}/analysis.txt"
    if os.path.exists(submodule_gt):
        gt_path = submodule_gt
    elif os.path.exists(local_gt):
        gt_path = local_gt
    else:
        gt_path = submodule_gt  # let the existence check below error
    augnet_path = f"{AUGNET_OUT}/{augnet_name}/score_annotated.rntxt"

    if not os.path.exists(gt_path):
        return None
    augnet_events = parse_rntxt(augnet_path) if os.path.exists(augnet_path) else None
    ours = _load_ours_csv(augnet_name)

    gt_events = parse_rntxt(gt_path)

    total = 0
    a_cum = [0, 0, 0]    # AugmentedNet cumulative (exact, sc-or-better, ip-or-better)
    o_cum = [0, 0, 0]    # ours cumulative
    a_rule = [0, 0, 0, 0, 0, 0]  # AugNet per-rule (exact, sc, inv, conv, sb, sd)
    o_rule = [0, 0, 0, 0, 0, 0]  # ours per-rule
    # Key-accuracy: total beats considered + correct-key count. Match =
    # (letter, accidental, mode) all equal, case-insensitive on the
    # letter so AugNet's "C" matches analyst's "c" if their modes
    # agree too. AugNet outputs explicit key declarations alongside
    # each RN — we already parse them above as `key` on each event.
    a_key_correct = 0
    a_key_total = 0

    def _key_match(k1, k2):
        # k = (letter, accidental, mode)
        if k1 is None or k2 is None:
            return False
        return (k1[0].upper() == k2[0].upper()
                and (k1[1] or '') == (k2[1] or '')
                and k1[2] == k2[2])

    for measure, beat, key, rn in gt_events:
        expected = normalize(rn)
        if not expected:
            continue
        total += 1
        is_minor = key[2] == 'minor'

        if augnet_events is not None:
            a_pred = find_prediction_at(augnet_events, measure, beat)
            a_norm = normalize(a_pred) if a_pred else None
            a_pr, a_cu = _classify_set(expected, a_norm, is_minor)
            for i in range(6): a_rule[i] += a_pr[i]
            for i in range(3): a_cum[i] += int(a_cu[i])
            # Per-beat key-accuracy — find AugNet's key at this beat
            # by walking its events. find_prediction_at gives us the
            # RN at (measure, beat); we need the matching key tuple.
            # Simpler approach: walk augnet_events for the (m,b) match.
            a_key = None
            for am, ab, ak, _ in augnet_events:
                if am > measure or (am == measure and ab > beat):
                    break
                a_key = ak
            a_key_total += 1
            if _key_match(a_key, key):
                a_key_correct += 1

        if ours is not None:
            # Our CSV stores per-(measure,beat) picks. The engine suite
            # already applied normalize() but apply it again here for
            # parity with AugmentedNet's normalization path.
            o_raw = ours.get((measure, beat))
            o_norm = normalize(o_raw) if o_raw else None
            o_pr, o_cu = _classify_set(expected, o_norm, is_minor)
            for i in range(6): o_rule[i] += o_pr[i]
            for i in range(3): o_cum[i] += int(o_cu[i])

    return {
        'label': label,
        'split': split,
        'total': total,
        # Cumulative 3-tuple (exact, same-chord-or-better, interp-or-better):
        # consumed by the existing head-to-head print loop.
        'augnet': tuple(a_cum) if augnet_events is not None else None,
        'ours':   tuple(o_cum) if ours is not None else None,
        # Per-rule 6-tuple (exact, sc, inv, conv, sb, sd):
        # consumed by the JSON-report writer.
        'augnet_per_rule': tuple(a_rule) if augnet_events is not None else None,
        'ours_per_rule':   tuple(o_rule) if ours is not None else None,
        # Key accuracy: (total_beats_with_gt_key, correct_beats).
        'augnet_key': (a_key_total, a_key_correct) if augnet_events is not None else None,
    }


if __name__ == '__main__':
    results = []
    for label, rel_path, augnet_name, split in PIECES:
        r = evaluate(label, rel_path, augnet_name, split)
        if r:
            results.append(r)

    print()
    print("=" * 120)
    print("Per-piece head-to-head (exact tier only — same classifier on both)")
    print("=" * 120)
    hdr = f"{'Piece':<28} {'Split':<10} {'Events':<8} {'Ours':<10} {'AugNet':<10} {'Δ (Ours − AugNet)':<18}"
    print(hdr)
    print("-" * 120)
    tot = {'ev': 0, 'a': [0, 0, 0], 'o': [0, 0, 0]}
    # Genre buckets — match the engine suite's genre grouping. Phase 2
    # corpus expansion (2026-05-26): baseline-9 dissolved into proper genres.
    grp_keys = [
        ('Bach Chorales', [f'Bach Chorale {n:03d}' for n in range(1, 372)]),
        ('Monteverdi Madrigals',
            [f'Monteverdi {b}.{p:02d}' for (b, n) in [('3', 20), ('4', 20), ('5', 8)]
             for p in range(1, n + 1)]),
        ('Bach WTC I',
            [f'Bach WTC I Prelude {n:02d}' for n in range(1, 25)] +
            ['Bach WTC I Fugue 19', 'Bach WTC I Fugue 22']),
        ('Beethoven BPS-FH', ['Beethoven Op.10/1 mvt 1','Beethoven Op.13 Pathétique mvt 1',
                               'Beethoven Op.31/2 Tempest mvt 1','Beethoven Op.78 mvt 1']),
        ('Beethoven Op.18 Quartets',
            [f'Beethoven Op.18/{q} mvt {m}' for q in range(1, 7) for m in range(1, 5)]),
        ('Haydn Op.20', ['Haydn Op.20/3 mvt 4','Haydn Op.20/4 mvt 1',
                          'Haydn Op.20/5 mvt 1','Haydn Op.20/6 mvt 4']),
        ('Mozart Sonatas (DCML)', ['Mozart K545/1','Mozart K281/1',
                                    'Mozart K281/2','Mozart K283/2','Mozart K310/1',
                                    'Mozart K330/2','Mozart K284/3',
                                    # 2026-06-08 expansion (seed=42 roster)
                                    'Mozart K279/2','Mozart K279/3','Mozart K280/3',
                                    'Mozart K281/3','Mozart K282/1','Mozart K282/2',
                                    'Mozart K284/2','Mozart K309/1','Mozart K309/2',
                                    'Mozart K309/3','Mozart K310/2','Mozart K311/1',
                                    'Mozart K332/1','Mozart K457/2','Mozart K533/2',
                                    'Mozart K545/3','Mozart K570/1','Mozart K576/1']),
        ('Schubert Lieder', [lbl for lbl, _, _ in SCHUBERT_LIEDER_PIECES]),
        ('Brahms Lieder', [lbl for lbl, _, _ in BRAHMS_LIEDER_PIECES]),
        ('TAVERN', ['Mozart K179 (Fischer Minuet)','Mozart K265 (Twinkle)',
                    'Mozart K354 (Je suis Lindor)','Mozart K398 (Salve tu)',
                    'Mozart K501 (Andante 4hands)','Mozart K573 (Duport Minuet)',
                    'Beethoven WoO 64 (Swiss)','Beethoven WoO 65 (Venni amore)',
                    'Beethoven WoO 70 (Nel cor)','Beethoven WoO 75 (Es kommt)',
                    'Beethoven WoO 77 (Original)']),
    ]
    by_group = {}

    for entry in results:
        lbl, sp, t = entry['label'], entry['split'], entry['total']
        if t == 0:
            continue
        a_str = '       --'
        o_str = '       --'
        d_str = '         --'
        if entry['augnet'] is not None:
            a_ex, a_sc, a_ip = entry['augnet']
            a_str = f"{100*a_ex/t:>6.1f}%"
            tot['a'][0] += a_ex; tot['a'][1] += a_sc; tot['a'][2] += a_ip
        if entry['ours'] is not None:
            o_ex, o_sc, o_ip = entry['ours']
            o_str = f"{100*o_ex/t:>6.1f}%"
            tot['o'][0] += o_ex; tot['o'][1] += o_sc; tot['o'][2] += o_ip
        if entry['augnet'] is not None and entry['ours'] is not None:
            d = 100.0 * (o_ex - a_ex) / t
            d_str = f"{d:+7.1f}%"
        print(f"{lbl:<28} {sp:<10} {t:<8} {o_str:<10} {a_str:<10} {d_str:<18}")
        tot['ev'] += t
        # Bucket by group label
        for gname, members in grp_keys:
            if lbl in members:
                g = by_group.setdefault(gname, {'ev': 0, 'a': [0,0,0], 'o': [0,0,0]})
                g['ev'] += t
                if entry['augnet'] is not None:
                    for i, v in enumerate(entry['augnet']): g['a'][i] += v
                if entry['ours'] is not None:
                    for i, v in enumerate(entry['ours']): g['o'][i] += v
                break

    def print_aggregate(name, ev, o_counts, a_counts):
        if ev == 0:
            return
        o_pct = [100*c/ev for c in o_counts]
        a_pct = [100*c/ev for c in a_counts]
        d_ex = o_pct[0] - a_pct[0]
        print(f"  {name:<28} {ev:>5} ev   "
              f"ours={o_pct[0]:5.1f}/{o_pct[1]:5.1f}/{o_pct[2]:5.1f}%   "
              f"augnet={a_pct[0]:5.1f}/{a_pct[1]:5.1f}/{a_pct[2]:5.1f}%   "
              f"Δexact={d_ex:+5.1f}%")

    print()
    print("=" * 120)
    print("Aggregates (exact / same-chord / interpretive) — Δ is ours − augnet at exact")
    print("=" * 120)
    for gname, _ in grp_keys:
        if gname in by_group:
            g = by_group[gname]
            print_aggregate(gname, g['ev'], g['o'], g['a'])
    print("-" * 120)
    print_aggregate("GRAND TOTAL", tot['ev'], tot['o'], tot['a'])

    # Group-name mapping for JSON (matches the shared group ids).
    json_group = {
        'Bach Chorales':            'chorales',
        'Monteverdi Madrigals':     'monteverdi',
        'Bach WTC I':               'bach-wtc',
        'Beethoven BPS-FH':         'beethoven-bps-fh',
        'Beethoven Op.18 Quartets': 'beethoven-op18',
        'Haydn Op.20':              'haydn-op20',
        'Mozart Sonatas (DCML)':    'mozart-sonatas-dcml',
        'Schubert Lieder':          'schubert-lieder',
        'Brahms Lieder':            'brahms-lieder',
        'TAVERN':                   'tavern',
    }

    def _group_id(lbl):
        for gname, members in grp_keys:
            if lbl in members:
                return json_group.get(gname, gname.lower().replace(' ', '-'))
        return 'unknown'

    # ── Write structured JSON reports — one per engine ──
    augnet_results = [
        (e['label'], e['total']) + e['augnet_per_rule']
        for e in results
        if e.get('augnet_per_rule') is not None
    ]
    ours_results = [
        (e['label'], e['total']) + e['ours_per_rule']
        for e in results
        if e.get('ours_per_rule') is not None
    ]

    # write_report expects rows of (label, total, exact, sc, conv, sb, sd)
    # plus a single (mode, group). AugNet runs touch multiple groups, so
    # we expand the rows here with their group ids and call write_report
    # in legacy single-group mode for each group separately, OR write a
    # combined report manually. Manual write is simpler.
    import json, datetime
    def _write_engine_json(engine_name, version, entries, out_path):
        rows = []
        pr_key = 'augnet_per_rule' if engine_name == 'augnet' else 'ours_per_rule'
        for entry in entries:
            if entry.get(pr_key) is None:
                continue
            pr = entry[pr_key]
            rows.append({
                'mode': 'single-pick',
                'group': _group_id(entry['label']),
                'piece': entry['label'],
                'total': entry['total'],
                'exact': pr[0],
                'sameChordGained': pr[1],
                'inversionGained': pr[2],
                'conventionGained': pr[3],
                'sharedBassGained': pr[4],
                'secondaryDiatonicGained': pr[5],
            })
            # Key-accuracy row — only emitted for AugmentedNet right now
            # (we don't double-record our own key-accuracy here; the
            # canonical "ours" numbers live in the engine suite's
            # committed report).
            if engine_name == 'augnet' and entry.get('augnet_key') is not None:
                kt, kc = entry['augnet_key']
                if kt > 0:
                    rows.append({
                        'mode': 'key-acc-augnet',
                        'group': _group_id(entry['label']),
                        'piece': entry['label'],
                        'total': kt,
                        'exact': kc,
                        'sameChordGained': 0,
                        'inversionGained': 0,
                        'conventionGained': 0,
                        'sharedBassGained': 0,
                        'secondaryDiatonicGained': 0,
                    })
        doc = {
            'engine': engine_name,
            'engine_version': version,
            'timestamp': datetime.datetime.utcnow().isoformat() + 'Z',
            'rows': rows,
        }
        with open(out_path, 'w') as f:
            json.dump(doc, f, indent=2)
        print(f"[corpus-report] wrote {len(rows)} rows to {out_path}", file=sys.stderr)

    _write_engine_json('augnet', 'augnet-v11-rnalt', results, '/tmp/augnet-report.json')
    # Also write our engine's CSV-bridge predictions for debugging the
    # alignment layer. ⚠ NOT comparable to the committed contrapunctus
    # report: the /tmp/contrapunctus-picks CSVs are dumped under ANALYST
    # keychains (chord-ID isolation), while the committed single-pick
    # rows are autonomous (detected keys). Downstream aggregation
    # ignores this file by design.
    _write_engine_json('contrapunctus-via-augnet', 'csv-bridge', results,
                       '/tmp/contrapunctus-via-augnet-report.json')
