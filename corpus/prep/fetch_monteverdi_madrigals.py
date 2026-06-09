"""Copy music21's bundled Monteverdi madrigal scores + analyses
into corpus/scores-local/ in the standard WiR layout.

music21 ships 48 madrigals from Books 3, 4, and 5 (1592-1605) with
hand-curated rntxt analyses by the music21 team. Monteverdi sits at
the cusp of modal-to-tonal practice — a deliberate "pre-Bach"
test case for our engine's robustness on early-functional harmony.

Layout written:
  corpus/scores-local/Madrigals/Monteverdi,_Claudio/Book_<N>/<MM>/
    score.mxl
    analysis.txt

Same format as When-in-Rome pieces so the score loaders (runners +
engine) handle them without changes.

Requires music21 (`pip install music21`).

Run from anywhere — paths resolve relative to this file's parent.
"""

import os
import re
import shutil
import sys

try:
    import music21 as m21
except ImportError:
    print("ERROR: music21 not installed. `pip install music21`")
    sys.exit(1)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CORPUS_DIR = os.path.dirname(SCRIPT_DIR)
SCORES_LOCAL = os.path.join(CORPUS_DIR, "scores-local")
MADRIGALS_REL = "Madrigals/Monteverdi,_Claudio"

# music21 file naming: madrigal.<book>.<piece>.{mxl,rntxt}
# e.g. madrigal.3.1.mxl, madrigal.5.12.rntxt
NAME_RE = re.compile(r"madrigal\.(\d+)\.(\d+)\.(mxl|rntxt)$")


def main():
    all_works = m21.corpus.getCorePaths()
    monteverdi = sorted(p for p in all_works if "monteverdi" in str(p).lower())

    by_id = {}  # (book, piece) -> {"mxl": path, "rntxt": path}
    for p in monteverdi:
        m = NAME_RE.search(str(p))
        if not m:
            continue
        book, piece, ext = m.group(1), m.group(2), m.group(3)
        key = (book, piece)
        by_id.setdefault(key, {})[ext] = str(p)

    paired = sorted([k for k, v in by_id.items() if "mxl" in v and "rntxt" in v])
    print(f"Found {len(paired)} madrigals with both score + analysis")

    written = 0
    for (book, piece) in paired:
        mxl_src = by_id[(book, piece)]["mxl"]
        rntxt_src = by_id[(book, piece)]["rntxt"]
        # Zero-pad piece number for sortable dir names.
        piece_padded = f"{int(piece):02d}"
        out_dir = os.path.join(
            SCORES_LOCAL, MADRIGALS_REL, f"Book_{book}", piece_padded
        )
        os.makedirs(out_dir, exist_ok=True)
        mxl_dst = os.path.join(out_dir, "score.mxl")
        rntxt_dst = os.path.join(out_dir, "analysis.txt")
        shutil.copyfile(mxl_src, mxl_dst)
        shutil.copyfile(rntxt_src, rntxt_dst)
        written += 1
        print(f"  Book {book} / {piece_padded}: {os.path.basename(mxl_src)}")

    print()
    print(f"Wrote {written} madrigals to {os.path.join(SCORES_LOCAL, MADRIGALS_REL)}")


if __name__ == "__main__":
    main()
