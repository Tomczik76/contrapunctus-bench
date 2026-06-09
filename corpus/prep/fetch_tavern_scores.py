"""Fetch + convert TAVERN (Theme-and-Variations Encodings of Roman
Numerals, Devaney et al. 2015) Kern transcriptions to MusicXML, saved
as `score_kern.mxl` in each piece's `scores-local` directory.

TAVERN is theme-and-variations sets by Beethoven and Mozart.  Each
piece is ONE rntxt file with theme + all variations (typically 5-12
variations), compressing many cadences into ~150-500 measures.  The
analysis lives in the When-in-Rome submodule; the scores are remote-
only (kern files on the original TAVERN GitHub).

Usage (any Python with music21 installed):
    python3 corpus/prep/fetch_tavern_scores.py

Run from anywhere — paths are resolved relative to the script's
parent-parent (the corpus directory).

The score loaders (runners + engine) prefer `score_kern.mxl` over
`score.mxl` automatically — see corpus/prep/README.md.
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
TAVERN_REL = "Variations_and_Grounds"


# Pieces to fetch. Picked for variety: covers different keys (major /
# minor / different tonics) and different theme sources (Mozart's
# operatic / chanson / folk material).
TAVERN_PIECES = [
    # Mozart variation sets. K353 fails to parse via music21's
    # humdrum reader (spineType error at spine 18 in the kern file)
    # — skipped here; use K179 / K354 as substitutes covering similar
    # variation counts.
    ("Mozart,_Wolfgang_Amadeus/_/K179", "K179"),  # 12 var on a minuet of Fischer
    ("Mozart,_Wolfgang_Amadeus/_/K265", "K265"),  # "Ah vous dirai-je Maman" (Twinkle Twinkle), 12 var
    ("Mozart,_Wolfgang_Amadeus/_/K354", "K354"),  # 12 var on "Je suis Lindor"
    ("Mozart,_Wolfgang_Amadeus/_/K398", "K398"),  # "Salve tu, Domine" from Paisiello, 6 var
    ("Mozart,_Wolfgang_Amadeus/_/K501", "K501"),  # Andante with Variations (4-hand), 5 var
    ("Mozart,_Wolfgang_Amadeus/_/K573", "K573"),  # Variations on a minuet of Duport, 9 var
    # Beethoven variation sets — kept small (5-8 var each) to balance
    # the corpus weight against Mozart's larger sets.
    ("Beethoven,_Ludwig_van/_/WoO_64", "WoO64"),  # 6 var on a Swiss theme
    ("Beethoven,_Ludwig_van/_/WoO_65", "WoO65"),  # 24 var on "Venni amore"
    ("Beethoven,_Ludwig_van/_/WoO_70", "WoO70"),  # 6 var on "Nel cor più non mi sento"
    ("Beethoven,_Ludwig_van/_/WoO_75", "WoO75"),  # 7 var on "Es kommt die heilige Nacht"
    ("Beethoven,_Ludwig_van/_/WoO_77", "WoO77"),  # 6 easy variations on an original theme
]


def fetch_and_convert(rel_path: str, label: str) -> bool:
    """Fetch the .krn from the URL in remote.json, convert to MXL,
    save at scores-local/{rel_path}/score_kern.mxl.
    Returns True on success.
    """
    meta_path = os.path.join(WIR_DIR, TAVERN_REL, rel_path, "remote.json")
    if not os.path.exists(meta_path):
        print(f"  {label}: no remote.json at {meta_path}, skipping")
        return False
    with open(meta_path) as f:
        meta = json.load(f)
    url = meta.get("remote_score_krn")
    if not url:
        print(f"  {label}: no remote_score_krn in {meta_path}, skipping")
        return False
    out_dir = os.path.join(SCORES_LOCAL, TAVERN_REL, rel_path)
    out_path = os.path.join(out_dir, "score_kern.mxl")
    if os.path.exists(out_path):
        print(f"  {label}: already at {out_path}, skipping fetch")
        return True
    os.makedirs(out_dir, exist_ok=True)
    print(f"  {label}: fetching {url}")
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            raw = resp.read()
    except Exception as e:
        print(f"  {label}: fetch FAILED — {type(e).__name__}: {e}")
        return False
    # TAVERN's Beethoven sub-corpus stores files in `Krn/` but the
    # actual files are MusicXML (UTF-16 with <?xml...?> header), not
    # Humdrum. The Mozart sub-corpus is actually kern. Detect format
    # by sniffing the first bytes.
    is_xml = (
        url.lower().endswith(".xml")
        or raw.lstrip()[:5] == b"<?xml"
        or raw.lstrip()[:1] == b"\xff" and b"<?xml" in raw[:16]
        or raw.lstrip()[:1] == b"\xfe" and b"<?xml" in raw[:16]
    )
    fmt = "musicxml" if is_xml else "humdrum"
    # For UTF-16 XML (BOM-prefixed), decode appropriately; for kern
    # use utf-8 with replacement.
    if is_xml:
        try:
            text = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8", errors="replace")
        except Exception:
            text = raw.decode("utf-8", errors="replace")
    else:
        text = raw.decode("utf-8", errors="replace")
    print(f"  {label}: parsing with music21 (format={fmt}, {len(raw)} bytes)")
    try:
        score = m21.converter.parse(text, format=fmt)
    except Exception as e:
        print(f"  {label}: music21 parse FAILED — {type(e).__name__}: {e}")
        return False
    print(f"  {label}: writing MXL to {out_path}")
    try:
        score.write("mxl", out_path)
    except Exception as e:
        print(f"  {label}: MXL write FAILED — {type(e).__name__}: {e}")
        return False
    return True


def main():
    n_ok = 0
    n_total = len(TAVERN_PIECES)
    for rel_path, label in TAVERN_PIECES:
        ok = fetch_and_convert(rel_path, label)
        if ok:
            n_ok += 1
    print()
    print(f"Done: {n_ok}/{n_total} TAVERN scores fetched + converted.")


if __name__ == "__main__":
    main()
