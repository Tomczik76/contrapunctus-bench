"""Apples-to-apples comparison: music21 vs our engine on the same 8-piece corpus.

Methodology:
  - Parse rntxt with our OWN regex parser (matches Scala parser's event-counting:
    no repeat expansion, sequential pass)
  - Load score with music21
  - For each rntxt event, find sounding notes in the score at that (measure, beat)
    position, build a chord, call music21.romanNumeralFromChord with the local key
  - Compare to expected after normalization (using our RnNormalize logic ported
    to Python)
  - Mirror the test's 6-tier matching exactly

Reports per-piece and aggregate match rates.
"""

from music21 import converter, chord, roman, key as m21key, note as m21note, pitch
import re
import sys
import os
from fractions import Fraction
from collections import Counter

# Paths are resolved relative to this script's location so the same
# script works correctly from any git worktree (the previous hardcoded
# absolute path silently fell back to the main worktree, missing any
# scores fetched only in a feature branch — like the 350 expanded
# chorales + Monteverdi madrigals that live only in this worktree).
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SCRIPT_DIR)  # harness/ -> repo root (standalone bench layout)
CORPUS_ROOT = os.path.join(_REPO_ROOT, "corpus", "When-in-Rome", "Corpus")
SCORES_LOCAL_ROOT = os.path.join(_REPO_ROOT, "corpus", "scores-local")

# Full corpus — the canonical piece roster (mirrors the engine suite's).
# Music21 evaluates against the same corpus our engine + AugmentedNet
# + AnalysisGNN run on. Phase 2 corpus expansion (2026-05-26):
# baseline-9 dissolved into proper genres; added Bach WTC I (26),
# Beethoven Op.18 quartets (24), Schubert lieder (46), Brahms lieder (9).

# Schubert + Brahms lieder lists shared with augnet_comparison.py — we
# rebuild them locally to keep music21_comparison importable
# stand-alone (augnet_comparison imports from this file at the top, so
# we can't reverse the dependency).
_SCHUBERT_NON_WINTERREISE = [
    ("Schubert Die Sterne D.939",       "OpenScore-LiederCorpus/Schubert,_Franz/4_Lieder,_Op.96/1_Die_Sterne,_D.939"),
    ("Schubert Das Wandern",            "OpenScore-LiederCorpus/Schubert,_Franz/Die_schöne_Müllerin,_D.795/01_Das_Wandern"),
    ("Schubert Wohin",                  "OpenScore-LiederCorpus/Schubert,_Franz/Die_schöne_Müllerin,_D.795/02_Wohin"),
    ("Schubert Pause",                  "OpenScore-LiederCorpus/Schubert,_Franz/Die_schöne_Müllerin,_D.795/12_Pause"),
    ("Schubert Trockne Blumen",         "OpenScore-LiederCorpus/Schubert,_Franz/Die_schöne_Müllerin,_D.795/18_Trockne_Blumen"),
    ("Schubert Ave Maria",              "OpenScore-LiederCorpus/Schubert,_Franz/Op.52/6_Ellens_Gesang_III,_D.839_(Ave_Maria)"),
    ("Schubert Du bist die Ruh",        "OpenScore-LiederCorpus/Schubert,_Franz/Op.59/3_Du_bist_die_Ruh"),
    ("Schubert Das Rosenband D.280",    "OpenScore-LiederCorpus/Schubert,_Franz/_/Das_Rosenband,_D.280"),
    ("Schubert Liebesbotschaft",        "OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/01_Liebesbotschaft"),
    ("Schubert Kriegers Ahnung",        "OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/02_Kriegers_Ahnung"),
    ("Schubert Frühlingssehnsucht",     "OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/03_Frühlingssehnsucht"),
    ("Schubert Ständchen",              "OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/04_Ständchen"),
    ("Schubert Aufenthalt",             "OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/05_Aufenthalt"),
    ("Schubert In der Ferne",           "OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/06_In_der_Ferne"),
    ("Schubert Abschied",               "OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/07_Abschied"),
    ("Schubert Der Atlas",              "OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/08_Der_Atlas"),
    ("Schubert Ihr Bild",               "OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/09_Ihr_Bild"),
    ("Schubert Das Fischermädchen",     "OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/10_Das_Fischermädchen"),
    ("Schubert Die Stadt",              "OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/11_Die_Stadt"),
    ("Schubert Am Meer",                "OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/12_Am_Meer"),
    ("Schubert Der Doppelgänger",       "OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/13_Der_Doppelgänger"),
    ("Schubert Die Taubenpost",         "OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/14_Die_Taubenpost"),
]
_WINTERREISE = [
    (1, "Gute_Nacht"), (2, "Die_Wetterfahne"), (3, "Gefror’ne_Thränen"),
    (4, "Erstarrung"), (5, "Der_Lindenbaum"), (6, "Wasserfluth"),
    (7, "Auf_dem_Flusse"), (8, "Rückblick"), (9, "Irrlicht"),
    (10, "Rast_(Spätere_Fassung)"), (11, "Frühlingstraum"),
    (12, "Einsamkeit_(Urspruengliche_Fassung)"), (13, "Die_Post"),
    (14, "Der_greise_Kopf"), (15, "Die_Kraehe"), (16, "Letzte_Hoffnung"),
    (17, "Im_Dorfe"), (18, "Der_stuermische_Morgen"), (19, "Täuschung"),
    (20, "Der_Wegweiser"), (21, "Das_Wirthshaus"), (22, "Muth"),
    (23, "Die_Nebensonnen"), (24, "Der_Leiermann_(Spätere_Fassung)"),
]
SCHUBERT_LIEDER = list(_SCHUBERT_NON_WINTERREISE)
for n, name in _WINTERREISE:
    short = name.split("_(")[0].replace("_", " ")
    SCHUBERT_LIEDER.append((
        f"Schubert Winterreise {n:02d} {short}",
        f"OpenScore-LiederCorpus/Schubert,_Franz/Winterreise,_D.911/{n:02d}_{name}",
    ))

BRAHMS_LIEDER = [
    ("Brahms Liebe und Frühling II",          "OpenScore-LiederCorpus/Brahms,_Johannes/6_Songs,_Op.3/3_Liebe_und_Frühling_II"),
    ("Brahms Liebesklage des Mädchens",       "OpenScore-LiederCorpus/Brahms,_Johannes/7_Lieder,_Op.48/3_Liebesklage_des_Mädchens"),
    ("Brahms Marienlieder 1 Der englische Gruss", "OpenScore-LiederCorpus/Brahms,_Johannes/Marienlieder,_Op.22/1_Der_englische_Gruss"),
    ("Brahms Marienlieder 2 Marias Kirchgang",    "OpenScore-LiederCorpus/Brahms,_Johannes/Marienlieder,_Op.22/2_Marias_Kirchgang"),
    ("Brahms Marienlieder 3 Marias Wallfahrt",    "OpenScore-LiederCorpus/Brahms,_Johannes/Marienlieder,_Op.22/3_Marias_Wallfahrt"),
    ("Brahms Marienlieder 4 Der Jäger",           "OpenScore-LiederCorpus/Brahms,_Johannes/Marienlieder,_Op.22/4_Der_Jäger"),
    ("Brahms Marienlieder 5 Ruf zur Maria",       "OpenScore-LiederCorpus/Brahms,_Johannes/Marienlieder,_Op.22/5_Ruf_zur_Maria"),
    ("Brahms Marienlieder 6 Magdalena",           "OpenScore-LiederCorpus/Brahms,_Johannes/Marienlieder,_Op.22/6_Magdalena"),
    ("Brahms Marienlieder 7 Marias Lob",          "OpenScore-LiederCorpus/Brahms,_Johannes/Marienlieder,_Op.22/7_Marias_Lob"),
]

PIECES = (
    # Bach WTC I — 24 preludes + 2 separately-analyzed fugues
    [
        (f"Bach WTC I Prelude {n:02d}",
         f"Keyboard_Other/Bach,_Johann_Sebastian/The_Well-Tempered_Clavier_I/{n:02d}")
        for n in range(1, 25)
    ]
    + [
        ("Bach WTC I Fugue 19", "Keyboard_Other/Bach,_Johann_Sebastian/The_Well-Tempered_Clavier_I/19_fugue"),
        ("Bach WTC I Fugue 22", "Keyboard_Other/Bach,_Johann_Sebastian/The_Well-Tempered_Clavier_I/22_fugue"),
    ]
    # All 371 Bach Chorales (Riemenschneider via Kern source — see
    # corpus/prep/README.md for why Kern is preferred). Chorale 150 has
    # no Kern transcription upstream so it's skipped at load time.
    + [
        (f"Bach Chorale {n:03d}",
         f"Early_Choral/Bach,_Johann_Sebastian/Chorales/{n:03d}")
        for n in range(1, 372)
    ]
    # 48 Monteverdi madrigals from music21's bundled corpus (Books 3-5,
    # 1592-1605). Pre-tonal — surfaces in a dedicated "pre-tonal"
    # section, excluded from all-pieces and genre-balanced aggregates.
    + [(f"Monteverdi {b}.{p:02d}",
        f"Madrigals/Monteverdi,_Claudio/Book_{b}/{p:02d}")
       for (b, n) in [("3", 20), ("4", 20), ("5", 8)]
       for p in range(1, n + 1)]
    # 4 Beethoven Sonatas (BPS-FH subset)
    + [
        ("Beethoven Op.10/1 mvt 1", "Piano_Sonatas/Beethoven,_Ludwig_van/Op010_No1/1"),
        ("Beethoven Op.13 Pathétique mvt 1", "Piano_Sonatas/Beethoven,_Ludwig_van/Op013(Pathetique)/1"),
        ("Beethoven Op.31/2 Tempest mvt 1", "Piano_Sonatas/Beethoven,_Ludwig_van/Op031_No2/1"),
        ("Beethoven Op.78 mvt 1", "Piano_Sonatas/Beethoven,_Ludwig_van/Op078/1"),
    ]
    # Beethoven Op.18 String Quartets — 6 × 4 mvts = 24. Op.18 No.1 mvt 2
    # was originally the baseline-9 quartet representative.
    + [
        (f"Beethoven Op.18/{q} mvt {mvt}",
         f"Quartets/Beethoven,_Ludwig_van/Op018_No{q}/{mvt}")
        for q in range(1, 7) for mvt in range(1, 5)
    ]
    # 4 Haydn Op.20 Quartets (HaydnSun overlap with AugmentedNet §6.5.3)
    + [
        ("Haydn Op.20/3 mvt 4", "Quartets/Haydn,_Franz_Joseph/Op20_No3/4"),
        ("Haydn Op.20/4 mvt 1", "Quartets/Haydn,_Franz_Joseph/Op20_No4/1"),
        ("Haydn Op.20/5 mvt 1", "Quartets/Haydn,_Franz_Joseph/Op20_No5/1"),
        ("Haydn Op.20/6 mvt 4", "Quartets/Haydn,_Franz_Joseph/Op20_No6/4"),
    ]
    # 7 Mozart Piano Sonatas. K545/1 + K281/1 (formerly baseline-9)
    # join the DCML contrasting-movement subset.
    + [
        ("Mozart K545/1", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K545/1"),
        ("Mozart K281/1", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K281/1"),
        ("Mozart K281/2", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K281/2"),
        ("Mozart K283/2", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K283/2"),
        ("Mozart K310/1", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K310/1"),
        ("Mozart K330/2", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K330/2"),
        ("Mozart K284/3", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K284/3"),
        ("Mozart K279/2", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K279/2"),
        ("Mozart K279/3", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K279/3"),
        ("Mozart K280/3", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K280/3"),
        ("Mozart K281/3", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K281/3"),
        ("Mozart K282/1", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K282/1"),
        ("Mozart K282/2", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K282/2"),
        ("Mozart K284/2", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K284/2"),
        ("Mozart K309/1", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K309/1"),
        ("Mozart K309/2", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K309/2"),
        ("Mozart K309/3", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K309/3"),
        ("Mozart K310/2", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K310/2"),
        ("Mozart K311/1", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K311/1"),
        ("Mozart K332/1", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K332/1"),
        ("Mozart K457/2", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K457/2"),
        ("Mozart K533/2", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K533/2"),
        ("Mozart K545/3", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K545/3"),
        ("Mozart K570/1", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K570/1"),
        ("Mozart K576/1", "Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K576/1"),
    ]
    # Schubert lieder — 46 songs (Winterreise + Schwanengesang + Müllerin +
    # singletons from Op.52/59/96 + Das Rosenband)
    + list(SCHUBERT_LIEDER)
    # Brahms lieder — 9 songs (Marienlieder Op.22 cycle + Op.3/Op.48 orphans)
    + list(BRAHMS_LIEDER)
    # 11 TAVERN (Theme And Variations Encodings of Roman Numerals,
    # Devaney et al. 2015) variation sets — Mozart + Beethoven.
    # Scores fetched via `corpus/prep/fetch_tavern_scores.py`.
    + [
        ("Mozart K179 (Fischer Minuet)",     "Variations_and_Grounds/Mozart,_Wolfgang_Amadeus/_/K179"),
        ("Mozart K265 (Twinkle)",            "Variations_and_Grounds/Mozart,_Wolfgang_Amadeus/_/K265"),
        ("Mozart K354 (Je suis Lindor)",     "Variations_and_Grounds/Mozart,_Wolfgang_Amadeus/_/K354"),
        ("Mozart K398 (Salve tu)",           "Variations_and_Grounds/Mozart,_Wolfgang_Amadeus/_/K398"),
        ("Mozart K501 (Andante 4hands)",     "Variations_and_Grounds/Mozart,_Wolfgang_Amadeus/_/K501"),
        ("Mozart K573 (Duport Minuet)",      "Variations_and_Grounds/Mozart,_Wolfgang_Amadeus/_/K573"),
        ("Beethoven WoO 64 (Swiss)",         "Variations_and_Grounds/Beethoven,_Ludwig_van/_/WoO_64"),
        ("Beethoven WoO 65 (Venni amore)",   "Variations_and_Grounds/Beethoven,_Ludwig_van/_/WoO_65"),
        ("Beethoven WoO 70 (Nel cor)",       "Variations_and_Grounds/Beethoven,_Ludwig_van/_/WoO_70"),
        ("Beethoven WoO 75 (Es kommt)",      "Variations_and_Grounds/Beethoven,_Ludwig_van/_/WoO_75"),
        ("Beethoven WoO 77 (Original)",      "Variations_and_Grounds/Beethoven,_Ludwig_van/_/WoO_77"),
    ]
)


# ── RN canonicalisation: SHARED with all competitor scorers ──
# Imported from rn_normalize.py — the canonical Python port of the
# engine's Scala normalizer. Do NOT re-define a local copy here:
# this module previously carried its own drifted port (missing the
# lowercase-v/n slash targets, the Ger65/Ger7→Ger6 collapse, and the
# exact-tier #vii strip), which silently biased the cross-engine
# benchmark in our favor. Parity with Scala is enforced by
# test_rn_normalize_parity.py. Re-exported so augnet_comparison.py's
# `from music21_comparison import normalize` keeps working.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rn_normalize import normalize, rntxt_beats_per_measure  # noqa: E402,F401


def expand_simpler_forms(rn, mode='interpretive'):
    """Port of the engine-side expandSimplerForms (Scala).

    mode='same-chord': only reductions that preserve chord identity —
    extensions (V9→V7→V), inverted-7th-to-triad, power chord, sus
    reduction (no case flip), dim/aug quality strip, 3rd-inv-7-chord-
    to-triad, Aug6 family (Ger6/Fr43/It6 share the defining trio).
    Excludes sus case-flip (Vsus4 → vsus4 changes quality).

    mode='interpretive' (default): same-chord PLUS sus case-flip
    (Vsus4 ↔ vsus4 — quality undetermined). Used downstream alongside
    expand_shared_bass_alternatives + expand_secondary_diatonic_
    equivalence for the full interpretive tier.

    NOTE: the `#vii ↔ vii` strip previously lived here (interpretive
    mode); it has been promoted to the EXACT-tier `normalize` step
    (no-slash forms only), mirroring the engine's Scala normalizer
    (its stripLocalSharpViio step)."""
    seen = {rn}
    current = rn
    while True:
        last_slash = current.rfind('/')
        if last_slash == -1:
            base, target = current, ''
        else:
            base, target = current[:last_slash], current[last_slash:]
        reduced = None
        # Extension pattern: V13 → V11 → V9 → V7 → V; V+9 → V; etc.
        ext_match = re.match(r'^(.*?)(\+?)(13|11|9|7)$', base)
        if ext_match:
            b, plus, ext = ext_match.group(1), ext_match.group(2), ext_match.group(3)
            if plus == '+':
                reduced = b
            elif ext == '13':
                reduced = b + '11'
            elif ext == '11':
                reduced = b + '9'
            elif ext == '9':
                reduced = b + '7'
            elif ext == '7':
                reduced = b
        if reduced is None:
            # Inverted 7th → inverted triad: V65 → V6, V43 → V64
            inv_match = re.match(r'^(.*?)(65|43)$', base)
            if inv_match:
                b, inv = inv_match.group(1), inv_match.group(2)
                if inv == '65':
                    reduced = b + '6'
                elif inv == '43':
                    reduced = b + '64'
        if reduced is None:
            # Power chord: V5 → V (root + 5th only, no 3rd)
            pc_match = re.match(r'^([#b]?[ivIV]+[°øΔ+oM]?)5$', base)
            if pc_match and pc_match.group(1):
                reduced = pc_match.group(1)
        if reduced is None:
            # Sus chord: Vsus4 → V, Vsus264 → V64 (sus has no 3rd)
            sus_match = re.match(r'^([#b]?[ivIV]+)sus[24](|6|64)$', base)
            if sus_match and sus_match.group(1):
                reduced = sus_match.group(1) + sus_match.group(2)
        if reduced is None:
            # Dim triad strip: viio → vii, iio64 → ii64 (MinorOmit5 emit)
            dim_match = re.match(r'^([#b]?[ivIV]+)[oø](|6|64)$', base)
            if dim_match and dim_match.group(1):
                reduced = dim_match.group(1) + dim_match.group(2)
        if reduced is None:
            # Aug triad strip: V+ → V (Augmented triad quality marker)
            aug_match = re.match(r'^([#b]?[ivIV]+)\+(|6|64)$', base)
            if aug_match and aug_match.group(1):
                reduced = aug_match.group(1) + aug_match.group(2)
        if reduced is None:
            # 3rd-inv 7-chord to bare triad: V42 → V (7th in bass, NCT reading)
            inv3_match = re.match(r'^([#b]?[ivIV]+[°øΔ+oM]?)42$', base)
            if inv3_match and inv3_match.group(1):
                reduced = inv3_match.group(1)
        if reduced is None:
            # Aug6 type reduction: Ger6/Fr43 → It6 (all share defining trio)
            if base == 'Ger6':
                reduced = 'It6'
            elif base == 'Fr43':
                reduced = 'It6'
            elif base == 'Ger7':
                # Alternate analyst convention: Ger+6 written as a 7-chord
                # (the aug6 enharmonically equals a m7). Same chord identity
                # as Ger65 / Ger6. Reduce to Ger6 to chain through Ger6 → It6.
                reduced = 'Ger6'
        if reduced is None:
            break
        new = reduced + target
        if new in seen:
            break
        seen.add(new)
        current = new
    # INTERPRETIVE-tier-only rules (skipped in mode='same-chord'):
    if mode == 'interpretive':
        # Sus chord case-flip: Vsus4 ↔ vsus4 (sus has no 3rd → quality
        # undetermined). This CHANGES the chord-quality interpretation.
        # (`#vii ↔ vii` was removed from this tier — it now happens in
        # `normalize` at the exact tier, no-slash forms only, exactly
        # like the Scala side.)
        sus_in_input = re.match(r'^([#b]?[ivIV]+)sus[24](|6|64)(/.+)?$', rn)
        if sus_in_input:
            seen = seen | {flip_numeral_case(s) for s in seen}
    return seen


def flip_numeral_case(rn):
    """Flip the case of leading roman-numeral letters. Preserves
    accidental prefix, quality marker, figure, and tonicization target.
    e.g. V → v, Vsus4 → vsus4, bIII7/V → biii7/v."""
    last_slash = rn.rfind('/')
    if last_slash == -1:
        chord, target = rn, ''
    else:
        chord, target = rn[:last_slash], rn[last_slash:]
    out = []
    i = 0
    while i < len(chord) and chord[i] in ('#', 'b'):
        out.append(chord[i])
        i += 1
    while i < len(chord) and chord[i] in ('I', 'V', 'i', 'v'):
        c = chord[i]
        out.append(c.lower() if c.isupper() else c.upper())
        i += 1
    out.append(chord[i:])
    return ''.join(out) + target


def expand_inversions(rn):
    last_slash = rn.rfind('/')
    if last_slash == -1:
        chord_part, target = rn, ''
    else:
        chord_part, target = rn[:last_slash], rn[last_slash:]
    m = re.match(r'^([#b]?[ivIV]+[°øΔ+oM]?)(7|65|43|42|6|64|)$', chord_part)
    if not m:
        return {rn}
    base, fig = m.group(1), m.group(2)
    if fig in ('', '6', '64'):
        siblings = ['', '6', '64']
    elif fig in ('7', '65', '43', '42'):
        siblings = ['7', '65', '43', '42']
    else:
        siblings = [fig]
    return {f"{base}{s}{target}" for s in siblings}


def expand_cad(rn):
    last_slash = rn.rfind('/')
    if last_slash == -1:
        chord_part, target = rn, ''
    else:
        chord_part, target = rn[:last_slash], rn[last_slash:]
    m = re.match(r'^Cad(\d*)$', chord_part)
    if not m:
        return {rn}
    fig = m.group(1)
    return {f"Cad{fig}{target}", f"I{fig}{target}", f"i{fig}{target}",
            f"V{fig}{target}", f"v{fig}{target}"}


def expand_neapolitan(rn):
    """Synonym set N* ≡ bII* — analyst conventions split on which form
    to write for the same chord (major triad / 7-chord on ♭2)."""
    last_slash = rn.rfind('/')
    if last_slash == -1:
        chord_part, target = rn, ''
    else:
        chord_part, target = rn[:last_slash], rn[last_slash:]
    m = re.match(r'^(N|bII|♭II)(\d*)$', chord_part)
    if not m:
        return {rn}
    fig = m.group(2)
    return {f"N{fig}{target}", f"bII{fig}{target}"}


def strip_minor_flat(rn):
    for pref in ('bVII', 'bVI', 'bIII', 'bvii', 'bvi', 'biii'):
        if rn.startswith(pref):
            return rn[1:]
    return rn


# ── Shared-bass alternatives ──
# Each entry maps a chord to alternative readings that share the same
# bass note (or, for the Cad64 ↔ V case, the same scale-degree-5 bass).
# Mirrors the engine-side majorSharedBass + minorSharedBass tables exactly.

MAJOR_SHARED_BASS = {
    "I":     {"vi6"},
    "I6":    {"iii"},
    "I64":   {"iii6", "V"},
    "ii":    {"viio6"},
    "ii6":   {"IV", "V42"},
    "ii64":  {"IV6"},
    "iii":   {"I6"},
    "iii6":  {"I64", "V"},
    "iii64": {"I"},
    "IV":    {"ii6", "V42"},
    "IV6":   {"vi"},
    "IV64":  {"vi6"},
    "iv":    {"N6"},
    "iv6":   {"N64"},
    "V42":   {"ii6", "IV"},
    "V":     {"iii6", "I64"},
    "V6":    {"viio"},
    "V64":   {"viio6"},
    "vi":    {"IV6"},
    "vi6":   {"I", "IV64"},
    "vi64":  {"I6"},
    "viio":  {"V6"},
    "viio6": {"V64", "ii"},
    "viio64": {"V"},
    "vii":   {"V6"},   # MinorOmit5 emits without ° marker
    "vii6":  {"V64", "ii"},
    "vii64": {"V"},
    "N6":    {"iv"},
    "N64":   {"iv6"},
}

MINOR_SHARED_BASS = {
    "i":      {"VI6"},
    "i6":     {"III"},
    "i64":    {"III6", "V", "v"},
    "iio":    {"iv6"},
    "iio6":   {"iv"},
    "iio64":  {"iv6"},
    "iiø":    {"iv6"},
    "iiø6":   {"iv"},
    "iiø64":  {"iv6"},
    "III":    {"i6"},
    "III6":   {"i64"},
    "iv":     {"iio6", "iiø6", "N6"},
    "iv6":    {"VI", "N64"},
    "iv64":   {"VI6"},
    "v":      {"III6", "i64", "V"},
    "v6":     {"VII", "V6"},
    "v64":    {"VII6", "V64"},
    "v7":     {"V7"},
    "v65":    {"V65"},
    "v43":    {"V43"},
    "v42":    {"V42"},
    "V":      {"iii6", "i64", "v"},
    "V6":     {"viio", "v6"},
    "V64":    {"viio6", "v64"},
    "V7":     {"v7"},
    "V65":    {"v65"},
    "V43":    {"v43"},
    "V42":    {"v42"},
    "VI":     {"iv6"},
    "VI6":    {"i"},
    "VI64":   {"i6"},
    "VII":    {"v6"},
    "VII6":   {"v64"},
    "viio":   {"V6"},
    "viio6":  {"V64"},
    "viio64": {"V"},
    "#viio":  {"V6"},
    "#viio6": {"V64"},
    "#viio64": {"V"},
    "#vii":   {"V6"},
    "#vii6":  {"V64"},
    "N6":     {"iv"},
    "N64":    {"iv6"},
}


def expand_shared_bass_alternatives(rn, is_minor):
    """Port of the engine-side expandSharedBassAlternatives (Scala)."""
    last_slash = rn.rfind('/')
    if last_slash == -1:
        chord, target = rn, ''
    else:
        chord, target = rn[:last_slash], rn[last_slash:]
    table = MINOR_SHARED_BASS if is_minor else MAJOR_SHARED_BASS
    alts = table.get(chord, set())
    if not alts:
        return {rn}
    return {a + target for a in alts} | {rn}


SEC_PATTERN = re.compile(r'^(V|viio|#viio|viiø|#viiø|vii|#vii)(\d*)/(.+)$')
DIAT_PATTERN = re.compile(r'^([#b]?)([ivIV]+)(o|ø|°|)(\d*)$')


def expand_secondary_diatonic_equivalence(rn, is_minor):
    """Port of the engine-side expandSecondaryDiatonicEquivalence (Scala)."""
    alts = set()

    # Secondary → diatonic alternative
    m = SEC_PATTERN.match(rn)
    if m:
        quality, fig, target = m.group(1), m.group(2), m.group(3)
        tlower = target.lower()
        diat_alt = None
        if quality == 'V':
            diat_alt = {
                'v': 'II', 'vi': 'III', 'ii': 'VI',
                'iii': 'VII', 'iv': 'I',
            }.get(tlower)
        elif 'vii' in quality:
            diat_alt = {
                'v': '#ivo', 'vi': '#vo', 'ii': '#io',
                'iii': '#iio', 'iv': 'iiio',
            }.get(tlower)
        if diat_alt:
            alts.add(diat_alt + fig)

    # Diatonic-name → secondary alternative
    m = DIAT_PATTERN.match(rn)
    if m:
        accidental, base, quality, fig = m.group(1), m.group(2), m.group(3), m.group(4)
        if quality == '':
            pairs = {
                'II':  [f"V{fig}/v",  f"V{fig}/V"],
                'III': [f"V{fig}/vi", f"V{fig}/VI"],
                'VI':  [f"V{fig}/ii", f"V{fig}/II"],
                'VII': [f"V{fig}/iii", f"V{fig}/III"],
                'I':   [f"V{fig}/iv", f"V{fig}/IV"],
            }.get(base, [])
            alts.update(pairs)
        # Sharp-prefixed dim chords → viio/X secondaries
        if accidental == '#' and quality in ('o', '°', 'ø'):
            secs = {
                'iv': [f"viio{fig}/v",  f"viio{fig}/V"],
                'v':  [f"viio{fig}/vi", f"viio{fig}/VI"],
                'i':  [f"viio{fig}/ii", f"viio{fig}/II"],
                'ii': [f"viio{fig}/iii", f"viio{fig}/III"],
            }.get(base, [])
            alts.update(secs)

    if not alts:
        return {rn}
    return alts | {rn}


# ── Minimal rntxt parser matching the engine parser's event counting ──

# Note name → pitch class
PC = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}


def parse_key(key_str):
    """Return (tonic_letter, alteration, mode) or None."""
    # e.g., "G" major, "g" minor, "Bb" major, "f#" minor
    m = re.match(r'^([A-Ga-g])([#b]?):?$', key_str.strip())
    if not m:
        return None
    letter, alt = m.group(1), m.group(2)
    mode = 'major' if letter.isupper() else 'minor'
    return (letter.upper(), alt, mode)


def parse_rntxt(path):
    """Parse a When-in-Rome rntxt file into a list of events
    (measure, beat, key_letter_alt_mode, expected_rn, time_sig).

    Expands `mX-Y = mA-B` repeat-equality declarations by cloning events
    from source measures into target measures — mirrors music21's
    RomanText parser and the engine parser's repeat expansion so the
    event counts line up apples-to-apples with the other engines.
    Without expansion, Beethoven Pathétique drops ~93 events (22%) and
    Brahms drops ~61 events.
    """
    events = []
    repeats = []
    current_key = None
    time_sig = '4/4'

    with open(path) as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith('Note:') or line.startswith('Composer:') \
               or line.startswith('Piece:') or line.startswith('Movement:') \
               or line.startswith('Title:') or line.startswith('Analyst:') \
               or line.startswith('Proofreader:') or line.startswith('Form:') \
               or line.startswith('Pedal:') or line.startswith('Tempo:'):
                continue
            if line.startswith('Time Signature:'):
                time_sig = line.split(':', 1)[1].strip()
                continue
            # Variables like "var1: ..."
            if re.match(r'^var\d', line):
                continue
            # Measure-range repeat-equality: `m5-8 = m1-4` (the source's
            # leading `m` is optional in some When-in-Rome files, e.g.
            # `m175-182 = 167-174`).
            rm = re.match(r'^m(\d+)-(\d+)\s*=\s*m?(\d+)-(\d+)\s*$', line)
            if rm:
                repeats.append((
                    int(rm.group(1)), int(rm.group(2)),
                    int(rm.group(3)), int(rm.group(4)),
                ))
                continue
            # Single-measure equality: `m14 = m12` — clone exactly one
            # measure's events into another.
            rs = re.match(r'^m(\d+)\s*=\s*m?(\d+)\s*$', line)
            if rs:
                tgt = int(rs.group(1))
                src = int(rs.group(2))
                repeats.append((tgt, tgt, src, src))
                continue
            # Any other `=`-bearing line (key assertions, etc.)
            if '=' in line:
                continue
            # Section markers / comments
            if line.startswith('!'):
                continue

            # Parse measure line: m<N> ... key tokens, chord tokens
            m = re.match(r'^m(\d+)\s+(.*)$', line)
            if not m:
                continue
            measure = int(m.group(1))
            rest = m.group(2)

            # Tokenize by whitespace
            tokens = rest.split()
            beat = 1.0
            for tok in tokens:
                # Beat marker "b3" or "b3.50"
                bm = re.match(r'^b(\d+(?:\.\d+)?)$', tok)
                if bm:
                    beat = float(bm.group(1))
                    continue
                # Key change "X:" or "x:"
                km = re.match(r'^([A-Ga-g][#b]?):$', tok)
                if km:
                    new_key = parse_key(km.group(1))
                    if new_key:
                        current_key = new_key
                    continue
                # Phrase-boundary markers (`||`, `:||`, `||:`, `:||:`) are
                # structural rntxt syntax, not chord labels. Without this
                # filter, event totals inflate by ~5 per chorale (one per
                # phrase boundary), which throws off the head-to-head
                # event counts vs ours / augnet / analysisgnn. The engine's
                # parser already skips them.
                if tok in ("||", ":||", "||:", ":||:"):
                    continue
                # Otherwise: RN label
                if current_key:
                    events.append((measure, beat, current_key, tok, time_sig))

    # Expand repeats: clone events from source measures into target measures.
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


# ── Find sounding notes at a score time-offset ──

def get_sounding_notes(score_flat, target_offset, epsilon=Fraction(1, 1000)):
    """All Note/Chord pitches sounding (attacked or sustained) at target_offset."""
    pitches = []
    for n in score_flat.notes:
        n_offset = n.offset
        n_end = n_offset + n.duration.quarterLength
        # Note: include attack at target_offset (n_offset == target_offset is fine)
        if n_offset <= target_offset + epsilon and target_offset + epsilon < n_end:
            if isinstance(n, m21note.Note):
                pitches.append(n.pitch)
            elif isinstance(n, chord.Chord):
                pitches.extend(n.pitches)
    return pitches


# ── Per-event labeling via music21 ──

def make_m21_key(tonic_letter, alt, mode):
    """Convert (tonic, alteration, mode) to a music21 Key object."""
    tonic_str = tonic_letter + ('#' if alt == '#' else '-' if alt == 'b' else '')
    if mode == 'minor':
        tonic_str = tonic_str.lower()
    return m21key.Key(tonic_str)


def music21_label(score_flat, event_offset, m21_key):
    """Call music21.romanNumeralFromChord at this offset, with this key."""
    pitches = get_sounding_notes(score_flat, event_offset)
    if not pitches:
        return None
    try:
        c = chord.Chord(pitches)
        rn = roman.romanNumeralFromChord(c, m21_key)
        return rn.figure
    except Exception:
        return None


# ── Score time-offset for an rntxt (measure, beat) ──

def build_measure_spans(score):
    """Ordered per-measure (offset, actual_quarter_length) spans plus
    the score's first measure NUMBER.

    Mirrors the engine-side alignment layer (its eventToTick step):
    the rntxt measure number is mapped via `measure − firstMeasureNumber`
    into the ordered measure list, so anacrusis scores (pickup = m0)
    stay aligned — the previous `measure_offsets[measure - 1]` indexing
    read EVERYTHING one measure early on pickup pieces (Chorale 001:
    music21 scored 4/59 exact purely from this, vs AugNet's 52/59 on
    identical ground truth). Actual per-measure lengths (offset deltas)
    replace the old uniform-measure assumption, so mid-piece time-
    signature changes stay aligned too."""
    parts = list(score.parts)
    stream = parts[0] if parts else score
    measures = list(stream.getElementsByClass('Measure'))
    if not measures:
        measures = list(score.recurse().getElementsByClass('Measure'))
    if not measures:
        return [], 0
    spans = []
    for k, m in enumerate(measures):
        off = float(m.offset)
        if k + 1 < len(measures):
            length = float(measures[k + 1].offset) - off
        else:
            length = float(m.duration.quarterLength)
        spans.append((off, max(length, 1e-9)))
    first_number = measures[0].measureNumber
    if first_number is None:
        first_number = 0
    return spans, first_number


def rntxt_offset(measure, beat, time_sig, measure_spans, first_measure_number):
    """rntxt (measure, beat) → absolute quarter-note offset, or None
    when the measure lies outside the parsed score (the caller counts
    that event as a MISS — same denominator rule as the other engines).

    Mirrors the engine-side `eventToTick`: the beat is scaled PROPORTIONALLY
    into the measure's ACTUAL length using the time signature in effect
    at the event (`(beat-1) × length / beats_per_measure`), then
    clamped into the measure — identical semantics for pickups and
    time-signature changes."""
    idx = measure - first_measure_number
    if idx < 0 or idx >= len(measure_spans):
        return None
    off, length = measure_spans[idx]
    bpm = max(rntxt_beats_per_measure(time_sig), 1)
    raw = (beat - 1.0) * length / bpm
    raw = max(0.0, min(raw, length - 1e-6))
    return off + raw


# ── Per-event classify (mirrors the engine suite's per-event attribution) ──

def classify_per_rule(expected_normalized, is_minor, m21_normalized):
    """Attribute a (expected, m21) pair to the FIRST tier that matches.

    Returns one of: 'exact' | 'same_chord' | 'inversion' | 'convention'
    | 'shared_bass' | 'secondary_diatonic' | None.

    Attribution priority (most innocuous → most radical):
      1. exact              — literal label match
      2. same_chord         — extension/power/sus/Aug6 reductions, Neapolitan
                               synonyms, minor-flat strip (chord identity
                               preserved, same figure)
      3. inversion          — same root + quality, different bass-position
                               figure (V ↔ V6 ↔ V64, V7 ↔ V65 ↔ V43 ↔ V42)
      4. convention         — sus case-flip + #vii↔vii + Cad64↔I64/V64
      5. shared_bass        — iii ↔ I6, ii6 ↔ IV ↔ V42, …
      6. secondary_diatonic — V/V ↔ II, V/vi ↔ III, …

    Mirrors the engine suite's tier classifier after the 2026-05-23
    tier split (inversion + convention/Cad64 broken out of same_chord).
    """
    if m21_normalized is None:
        return None

    if expected_normalized == m21_normalized:
        return 'exact'

    # Pre-expansions that ARE chord-identity-preserving.
    stripped = strip_minor_flat(expected_normalized) if is_minor else expected_normalized
    n_syns = expand_neapolitan(expected_normalized) - {expected_normalized}
    labels = {expected_normalized}
    if is_minor and stripped != expected_normalized:
        labels.add(stripped)
    labels |= n_syns

    engine_strict = {m21_normalized}
    engine_n_syns = set()
    for x in list(engine_strict):
        engine_n_syns |= expand_neapolitan(x)
    engine_labels = engine_strict | engine_n_syns

    # ── SAME-CHORD: chord-identity-preserving reductions only ──
    labels_simpler_sc = set(labels)
    for l in list(labels):
        labels_simpler_sc |= expand_simpler_forms(l, mode='same-chord')
    engine_simpler_sc = set(engine_labels)
    for x in list(engine_labels):
        engine_simpler_sc |= expand_simpler_forms(x, mode='same-chord')
    if (labels & engine_labels) or (labels_simpler_sc & engine_simpler_sc):
        return 'same_chord'

    # ── INVERSION: same root + quality, different bass position ──
    labels_inv_sc = set(labels_simpler_sc)
    for l in list(labels_simpler_sc):
        labels_inv_sc |= expand_inversions(l)
    engine_inv_sc = set(engine_simpler_sc)
    for x in list(engine_simpler_sc):
        engine_inv_sc |= expand_inversions(x)
    if labels_inv_sc & engine_inv_sc:
        return 'inversion'

    # ── CONVENTION: sus case-flip + #vii↔vii + Cad64↔I64/V64 ──
    cad_syns = expand_cad(expected_normalized) - {expected_normalized}
    engine_cad_syns = set()
    for x in list(engine_labels):
        engine_cad_syns |= expand_cad(x)
    labels_with_cad = labels | cad_syns
    engine_with_cad = engine_labels | engine_cad_syns
    labels_simpler_ip = set(labels_with_cad)
    for l in list(labels_with_cad):
        labels_simpler_ip |= expand_simpler_forms(l, mode='interpretive')
    labels_inv_ip = set(labels_simpler_ip)
    for l in list(labels_simpler_ip):
        labels_inv_ip |= expand_inversions(l)
    engine_simpler_ip = set(engine_with_cad)
    for x in list(engine_with_cad):
        engine_simpler_ip |= expand_simpler_forms(x, mode='interpretive')
    engine_inv_ip = set(engine_simpler_ip)
    for x in list(engine_simpler_ip):
        engine_inv_ip |= expand_inversions(x)
    if (labels_with_cad & engine_with_cad) or \
       (labels_simpler_ip & engine_simpler_ip) or \
       (labels_inv_ip & engine_inv_ip):
        return 'convention'

    # SHARED-BASS: iii ↔ I⁶ etc.
    labels_shared_bass = set()
    for l in labels_simpler_ip:
        labels_shared_bass |= expand_shared_bass_alternatives(l, is_minor)
    if labels_shared_bass & engine_inv_ip:
        return 'shared_bass'

    # SECONDARY-DIATONIC: V/V ↔ II etc.
    labels_sec_diatonic = set()
    for l in labels_simpler_ip:
        labels_sec_diatonic |= expand_secondary_diatonic_equivalence(l, is_minor)
    if labels_sec_diatonic & engine_inv_ip:
        return 'secondary_diatonic'

    return None


def classify(expected_normalized, is_minor, m21_normalized, mode='interpretive'):
    """Legacy 3-tier classifier — kept for backward compatibility with
    `*_vs_ours_diff.py` callers. Use `classify_per_rule` for the new
    per-component breakdown.

    Returns 'strict' | 'simpler' | 'inversion' | None.

    mode='exact': pure literal-match.
    mode='same-chord': adds Cad64 + chord-identity-preserving expansions.
    mode='interpretive': adds shared-bass + secondary-diatonic + convention.
    """
    tier = classify_per_rule(expected_normalized, is_minor, m21_normalized)
    if tier is None:
        return None
    if tier == 'exact':
        return 'strict'
    if mode == 'exact':
        return None  # only exact counts at this mode
    # same_chord, convention, shared_bass, secondary_diatonic all collapse
    # to 'inversion' under the legacy 3-tier API. The intermediate tier
    # names ('simpler' vs 'inversion') aren't load-bearing for any caller.
    if mode == 'same-chord':
        return 'inversion' if tier == 'same_chord' else None
    return 'inversion'  # mode='interpretive'


# ── Per-piece eval ──

def evaluate_piece(label, rel_path):
    # Score-source priority order — same as the engine's loader, so every
    # engine analyzes the same notes (see corpus/prep/README.md):
    #   1. corpus/scores-local/<rel>/score_kern.mxl  (Kern via Riemenschneider —
    #      chorales only; the analyst's source matches this, not the cantata-
    #      derived short_score upstream)
    #   2. corpus/When-in-Rome/Corpus/<rel>/score.mxl (submodule default)
    #   3. corpus/scores-local/<rel>/score.mxl (local-fallback for pieces
    #      whose mxl isn't bundled upstream — Brahms Requiem etc.)
    local_kern = f"{SCORES_LOCAL_ROOT}/{rel_path}/score_kern.mxl"
    submodule_score = f"{CORPUS_ROOT}/{rel_path}/score.mxl"
    local_score = f"{SCORES_LOCAL_ROOT}/{rel_path}/score.mxl"
    # Dual-source audit support: set `SKIP_KERN=true` env var to
    # force MarkGotham `score.mxl` instead of Kern. Matches `SKIP_KERN`
    # in run_augnet.sh / run_analysisgnn.sh (and the engine-side
    # equivalent flag).
    skip_kern = os.environ.get("SKIP_KERN", "false").lower() == "true"
    if not skip_kern and os.path.exists(local_kern):
        score_path = local_kern
    elif os.path.exists(submodule_score):
        score_path = submodule_score
    elif os.path.exists(local_score):
        score_path = local_score
    elif os.path.exists(local_kern):
        score_path = local_kern  # fallback if SKIP_KERN but no alt exists
    else:
        return None
    # Analysis path also gets a scores-local fallback (Monteverdi
    # madrigals live ENTIRELY under scores-local — score.mxl AND
    # analysis.txt — because they're not in the When-in-Rome submodule).
    submodule_analysis = f"{CORPUS_ROOT}/{rel_path}/analysis.txt"
    local_analysis = f"{SCORES_LOCAL_ROOT}/{rel_path}/analysis.txt"
    if os.path.exists(submodule_analysis):
        analysis_path = submodule_analysis
    elif os.path.exists(local_analysis):
        analysis_path = local_analysis
    else:
        return None

    print(f"\nLoading {label}...", file=sys.stderr)
    try:
        score = converter.parse(score_path)
    except Exception as e:
        # Beethoven Op.18/2 has `<harmony><function>d.i</function></harmony>`
        # elements (Riemannian function annotations) that music21 fails on.
        # Strip <harmony>...</harmony> blocks and retry.
        print(f"  initial parse failed: {e} — retrying with harmony elements stripped", file=sys.stderr)
        import zipfile, tempfile
        try:
            with zipfile.ZipFile(score_path) as z:
                names = z.namelist()
                xml_name = [n for n in names if n.endswith('.xml') and not n.startswith('META-INF')][0]
                xml_content = z.read(xml_name).decode('utf-8')
            # Strip <harmony>...</harmony> blocks
            xml_stripped = re.sub(r'<harmony[^>]*>.*?</harmony>', '', xml_content, flags=re.DOTALL)
            with tempfile.NamedTemporaryFile(suffix='.xml', delete=False, mode='w', encoding='utf-8') as f:
                f.write(xml_stripped)
                tmp_path = f.name
            score = converter.parse(tmp_path)
            print(f"  retry succeeded after stripping harmony elements", file=sys.stderr)
        except Exception as e2:
            print(f"  retry also failed: {e2}", file=sys.stderr)
            return None

    # Per-measure alignment spans (anacrusis- and TS-change-aware —
    # see build_measure_spans). Mirrors the engine-side eventToTick layer.
    score_flat = score.flatten()
    measure_spans, first_measure_number = build_measure_spans(score)
    if not measure_spans:
        return None

    # Parse our rntxt events (each event carries the time signature in
    # effect at that point in the analysis — the per-event TS feeds the
    # beat-unit computation, matching the engine-side per-event TS handling).
    events = parse_rntxt(analysis_path)
    print(f"  {len(events)} ground-truth events", file=sys.stderr)
    if not events:
        return None

    # Per-rule exclusive counters. Each event lands in the FIRST tier
    # whose rule fires; counts sum to `annotator_defensible`.
    counts = Counter()  # 'exact', 'same_chord', 'convention', 'shared_bass', 'secondary_diatonic'
    total = 0

    for measure, beat, ev_key, ev_rn, ev_ts in events:
        # Denominator rule (uniform across ALL engines): every GT event
        # whose normalized label is non-empty counts; no answer = miss.
        expected = normalize(ev_rn)
        if not expected:
            continue
        total += 1

        ev_offset = rntxt_offset(measure, beat, ev_ts, measure_spans, first_measure_number)
        if ev_offset is None:
            continue  # unalignable (measure outside parsed score) → counted miss

        # Build music21 key
        try:
            m21_k = make_m21_key(*ev_key)
        except Exception:
            continue

        # Get music21's label
        m21_raw = music21_label(score_flat, ev_offset, m21_k)
        if m21_raw is None:
            continue
        m21_norm = normalize(m21_raw)

        # Attribute to the FIRST tier whose rule fires (exclusive counters).
        is_minor = ev_key[2] == 'minor'
        tier = classify_per_rule(expected, is_minor, m21_norm)
        if tier is not None:
            counts[tier] += 1

    matched_exact         = counts['exact']
    matched_same_chord    = counts['same_chord']
    matched_inversion     = counts['inversion']
    matched_convention    = counts['convention']
    matched_shared_bass   = counts['shared_bass']
    matched_sec_diatonic  = counts['secondary_diatonic']
    annotator_defensible  = (matched_exact + matched_same_chord +
                             matched_inversion + matched_convention +
                             matched_shared_bass + matched_sec_diatonic)
    print(f"  music21: exact {matched_exact}/{total}, "
          f"+sChd {matched_same_chord}, +inv {matched_inversion}, "
          f"+conv {matched_convention}, +sBass {matched_shared_bass}, "
          f"+sDia {matched_sec_diatonic}, "
          f"total a-d {annotator_defensible}/{total}",
          file=sys.stderr)
    return (label, total, matched_exact, matched_same_chord, matched_inversion,
            matched_convention, matched_shared_bass, matched_sec_diatonic)


def _pct(n, t):
    return f"{100.0 * n / t:.1f}%" if t > 0 else "  0.0%"


def _group_for_label(label):
    """Map a human-readable piece label to the JSON group-id used by
    the orchestrator. Mirrors augnet_comparison._group_id /
    analysisgnn_comparison so the unified report joins cleanly by
    (group, piece). Phase 2 corpus expansion (2026-05-26): baseline-9
    dissolved; K545/1 + K281/1 fold into mozart-sonatas-dcml; new
    genres bach-wtc, beethoven-op18, schubert-lieder, brahms-lieder.
    """
    if 'Chorale' in label:
        return 'chorales'
    if label.startswith('Monteverdi'):
        return 'monteverdi'
    if label.startswith('Bach WTC I'):
        return 'bach-wtc'
    if label.startswith('Beethoven Op.18/'):
        return 'beethoven-op18'
    if label.startswith('Beethoven Op.10/1') or \
       label.startswith('Beethoven Op.13') or \
       label.startswith('Beethoven Op.31/2') or \
       label.startswith('Beethoven Op.78'):
        return 'beethoven-bps-fh'
    if label.startswith('Haydn Op.20'):
        return 'haydn-op20'
    if label.startswith('Schubert '):
        return 'schubert-lieder'
    if label.startswith('Brahms '):
        return 'brahms-lieder'
    # TAVERN — Mozart Kxxx (with descriptive suffix) or Beethoven WoO
    if 'WoO' in label or ('Mozart K' in label and '/' not in label):
        return 'tavern'
    # MPS-DCML — Mozart Kxxx/N (slash + movement number). K545/1 and
    # K281/1 (originally baseline-9 "test"/"training" pieces) fold in.
    if label.startswith('Mozart K') and '/' in label:
        return 'mozart-sonatas-dcml'
    return 'unknown'


def write_report(engine_name, results, out_path, mode='single-pick'):
    """Write the per-piece counters as a flat JSON report.

    Schema matches the engine suite's report (committed here as
    results/<date>/contrapunctus.report.json), so downstream tooling can
    union the JSON arrays without re-shaping. Each row: `{engine, mode, group, piece, total, exact,
    sameChordGained, conventionGained, sharedBassGained,
    secondaryDiatonicGained}`. Group is derived from the piece label
    to match the augnet/analysisgnn group taxonomy.
    """
    import json
    import datetime
    try:
        import music21
        version = music21.VERSION_STR
    except Exception:
        version = 'unknown'
    rows = []
    for label, t, ex, sc, inv, co, sb, sd in results:
        rows.append({
            'mode': mode,
            'group': _group_for_label(label),
            'piece': label,
            'total': t,
            'exact': ex,
            'sameChordGained': sc,
            'inversionGained': inv,
            'conventionGained': co,
            'sharedBassGained': sb,
            'secondaryDiatonicGained': sd,
        })
    doc = {
        'engine': engine_name,
        'engine_version': version,
        'timestamp': datetime.datetime.utcnow().isoformat() + 'Z',
        'rows': rows,
    }
    os.makedirs(os.path.dirname(out_path), exist_ok=True) if os.path.dirname(out_path) else None
    with open(out_path, 'w') as f:
        json.dump(doc, f, indent=2)
    print(f"[corpus-report] wrote {len(rows)} rows to {out_path}", file=sys.stderr)


if __name__ == '__main__':
    import time
    import json as _json
    # Optional psutil — used for peak-RSS capture in the perf log. If
    # not installed, the perf log just records wall time.
    try:
        import psutil
        _proc = psutil.Process()
    except ImportError:
        _proc = None
    # Optional label-substring filter for audits: set
    # `PIECES_FILTER=Chorale0` to restrict to chorales 001-099.
    # Mirrors the same env var in run_augnet.sh / run_analysisgnn.sh.
    pieces_filter = os.environ.get("PIECES_FILTER", "")
    filtered_pieces = [
        (l, r) for l, r in PIECES
        if not pieces_filter or pieces_filter in l
    ]
    results = []
    perf_rows = []
    for label, rel_path in filtered_pieces:
        t0 = time.perf_counter()
        r = evaluate_piece(label, rel_path)
        t1 = time.perf_counter()
        if r:
            results.append(r)
            wall_s = t1 - t0
            rss_mb = (_proc.memory_info().rss / 1048576.0) if _proc is not None else None
            perf_rows.append({"label": label, "wall_s": round(wall_s, 4),
                              "peak_rss_mb": round(rss_mb, 1) if rss_mb is not None else None})

    # Per-piece wall-time + peak RSS — feeds the upstream page
    # aggregator's "Performance characteristics" section. Same shape as
    # the bash script perf logs at /tmp/{augnet,analysisgnn}-runs/perf.jsonl.
    perf_out = '/tmp/music21-perf.jsonl'
    with open(perf_out, 'w') as f:
        for row in perf_rows:
            f.write(_json.dumps(row) + "\n")
    print(f"[perf] wrote {len(perf_rows)} per-piece rows to {perf_out}", file=sys.stderr)

    print("\n" + "=" * 140)
    print(f"{'Piece':<28} {'Events':<7} {'exact %':<9} {'+ sChd %':<9} "
          f"{'+ inv %':<9} {'+ conv %':<9} {'+ sBass %':<10} {'+ sDia %':<9} {'total %':<9}")
    print("-" * 140)
    tot_t = tot_ex = tot_sc = tot_inv = tot_co = tot_sb = tot_sd = 0
    for label, t, ex, sc, inv, co, sb, sd in results:
        ad = ex + sc + inv + co + sb + sd
        print(f"{label:<28} {t:<7} "
              f"{_pct(ex, t):<9} {_pct(sc, t):<9} {_pct(inv, t):<9} "
              f"{_pct(co, t):<9} {_pct(sb, t):<10} {_pct(sd, t):<9} {_pct(ad, t):<9} "
              f"({ex}+{sc}+{inv}+{co}+{sb}+{sd}={ad}/{t})")
        tot_t += t; tot_ex += ex; tot_sc += sc; tot_inv += inv
        tot_co += co; tot_sb += sb; tot_sd += sd
    print("-" * 140)
    if tot_t > 0:
        tot_ad = tot_ex + tot_sc + tot_inv + tot_co + tot_sb + tot_sd
        print(f"{'AGGREGATE':<28} {tot_t:<7} "
              f"{_pct(tot_ex, tot_t):<9} {_pct(tot_sc, tot_t):<9} "
              f"{_pct(tot_inv, tot_t):<9} {_pct(tot_co, tot_t):<9} "
              f"{_pct(tot_sb, tot_t):<10} {_pct(tot_sd, tot_t):<9} {_pct(tot_ad, tot_t):<9} "
              f"({tot_ex}+{tot_sc}+{tot_inv}+{tot_co}+{tot_sb}+{tot_sd}={tot_ad}/{tot_t})")

    # Write structured JSON output for downstream ingestion.
    # Schema matches the committed results/<date>/*.report.json files.
    write_report('music21', results, '/tmp/music21-report.json')
