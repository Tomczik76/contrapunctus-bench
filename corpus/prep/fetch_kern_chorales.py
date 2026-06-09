"""Fetch + convert craigsapp/bach-370-chorales Kern transcriptions to
MusicXML, saved as `score_kern.mxl` alongside MarkGotham's
`score.mxl` in each chorale's `scores-local` directory.

The default MarkGotham `short_score.mxl` is auto-extracted from
larger Bach works and for some pieces its note content systematically
diverges from what the When-in-Rome analysts annotated (verified
spot-checks: Chorales 007 & 011 at m11 have entirely different
chord-tones than the analyst's expected reading). The Kern source on
github.com/craigsapp/bach-370-chorales is a direct transcription of
the Riemenschneider edition — the same source Tymoczko + Napoles +
Andrew Jones used to write the rntxt analyses.

The Riemenschneider chorale number is in each
`When-in-Rome/Corpus/.../Chorales/<n>/remote.json` as
`"Riemenschneider": N`. The Kern URL pattern is
`https://raw.githubusercontent.com/craigsapp/bach-370-chorales/master/kern/chor<NNN>.krn`
where `NNN` is `N` zero-padded to 3 digits.

Requires music21 (`pip install music21`); reads kern via
`m21.converter.parse(text, format='humdrum')` and writes MXL via
`Score.write('musicxml', path)`.

The score loaders (runners + engine) prefer `score_kern.mxl` over
`score.mxl` automatically — see corpus/prep/README.md.

Run from anywhere — paths are resolved relative to the script's
parent-parent (the corpus directory).
"""

import json
import os
import sys
import urllib.request

try:
    import music21 as m21
except ImportError:
    print("ERROR: music21 not installed. `pip install music21`")
    sys.exit(1)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CORPUS_DIR = os.path.dirname(SCRIPT_DIR)
WIR_DIR = os.path.join(CORPUS_DIR, "When-in-Rome", "Corpus")
SCORES_LOCAL = os.path.join(CORPUS_DIR, "scores-local")
CHORALES_REL = "Early_Choral/Bach,_Johann_Sebastian/Chorales"

KERN_URL = (
    "https://raw.githubusercontent.com/craigsapp/bach-370-chorales/"
    "master/kern/chor{:03d}.krn"
)


def main():
    # Determine range. Default is all 371; override with first/last positional
    # args for incremental runs (e.g. `python fetch_kern_chorales.py 21 371`
    # to fetch only the expansion beyond the originally-tracked first 20).
    first = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    last = int(sys.argv[2]) if len(sys.argv) > 2 else 371
    chorale_ids = [f"{n:03d}" for n in range(first, last + 1)]
    skipped_existing = 0
    written = 0
    failed = 0
    for cid in chorale_ids:
        out_path = os.path.join(SCORES_LOCAL, CHORALES_REL, cid, "score_kern.mxl")
        if os.path.exists(out_path):
            skipped_existing += 1
            continue
        meta_path = os.path.join(WIR_DIR, CHORALES_REL, cid, "remote.json")
        if not os.path.exists(meta_path):
            print(f"  Chorale {cid}: no remote.json, skipping")
            failed += 1
            continue
        with open(meta_path) as f:
            meta = json.load(f)
        rs = meta.get("Riemenschneider")
        if rs is None:
            print(f"  Chorale {cid}: no Riemenschneider number, skipping")
            failed += 1
            continue
        url = KERN_URL.format(int(rs))
        try:
            kern = urllib.request.urlopen(url).read().decode()
        except Exception as e:
            print(f"  Chorale {cid} (R{rs}): fetch FAILED — {e}")
            failed += 1
            continue
        try:
            s = m21.converter.parse(kern, format="humdrum")
        except Exception as e:
            print(f"  Chorale {cid} (R{rs}): music21 parse FAILED — {e}")
            failed += 1
            continue
        # Dedupe measure-number duplicates within each part.
        # music21's Kern parser preserves the literal volta-2 pickup
        # measure as a SECOND `measureNumber=0` (and sometimes more
        # duplicates) after the repeat-bar. The score loaders use
        # POSITIONAL indexing, so a duplicate measure at position N
        # shifts every subsequent analyst-mapped measure by 1 (chorale
        # 007 m18 events were landing on the wrong physical measure
        # before this fix). The analyst's rntxt doesn't number the
        # volta pickup separately — they treat the second pass as a
        # continuation. Dropping the duplicate gives positional
        # alignment with the analyst's measure numbering at the cost
        # of one volta-pickup beat per repeat.
        from music21.stream import Score, Part
        deduped = Score()
        for p in s.parts:
            new_p = Part()
            seen = set()
            for m in p.getElementsByClass("Measure"):
                if m.measureNumber in seen:
                    continue
                seen.add(m.measureNumber)
                new_p.append(m)
            deduped.insert(0, new_p)
        s = deduped
        out_dir = os.path.join(SCORES_LOCAL, CHORALES_REL, cid)
        os.makedirs(out_dir, exist_ok=True)
        out = os.path.join(out_dir, "score_kern.mxl")
        try:
            s.write("musicxml", out)
        except Exception as e:
            print(f"  Chorale {cid} (R{rs}): MXL write FAILED — {e}")
            failed += 1
            continue
        n_parts = len(list(s.parts))
        n_measures = len(list(list(s.parts)[0].getElementsByClass("Measure")))
        print(f"  Chorale {cid} (R{rs}): wrote {out} — {n_parts} parts, {n_measures} measures")
        written += 1
    print()
    print(f"Summary: {written} written, {skipped_existing} skipped (already present), "
          f"{failed} failed of {len(chorale_ids)} requested ({first}-{last})")


if __name__ == "__main__":
    main()
