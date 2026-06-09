"""Strip <harmony>...</harmony> blocks from a MusicXML score.

Some scores in the When-in-Rome corpus (notably all 24 Beethoven Op.18
string quartet movements) contain Riemannian function annotations like

    <harmony><function>F.I</function></harmony>

inside the MusicXML. music21's chord-symbol parser tries to interpret
`F.I` as a romanNumeral pitch and raises HarmonyException, which
crashes any downstream tool that uses music21 to load the score —
including AugmentedNet's inference path.

This script reads an .mxl (zipped MusicXML), strips every
<harmony>...</harmony> block (including any nested children — they're
chord-symbol annotations, not actual notes), and writes a clean copy.
If the score contains no <harmony> blocks, the input is just copied as-is.

Usage:
    python3 corpus/prep/strip_harmony.py <input.mxl> <output.mxl>

Idempotent. Safe to apply to every score in a batch pipeline — the
overhead is one zip read + regex scan + zip write per piece (~10 ms).
"""

import re
import shutil
import sys
import tempfile
import zipfile


def strip_harmony(input_mxl: str, output_mxl: str) -> int:
    """Strip <harmony>...</harmony> from input_mxl, write to output_mxl.

    Returns the number of <harmony> blocks removed. Zero means the file
    was clean and was copied verbatim.
    """
    with zipfile.ZipFile(input_mxl) as z:
        names = z.namelist()
        # The score XML lives at a path like "*.xml" (not in META-INF).
        # MuseScore writes it as score.xml; some converters use the piece
        # name. Pick the first non-META-INF .xml.
        xml_names = [n for n in names if n.endswith(".xml") and not n.startswith("META-INF")]
        if not xml_names:
            # Not a standard .mxl — just copy.
            shutil.copy(input_mxl, output_mxl)
            return 0
        xml_name = xml_names[0]
        xml_content = z.read(xml_name).decode("utf-8")
        other_files = [(n, z.read(n)) for n in names if n != xml_name]

    # Match <harmony ... > ... </harmony> (allow attrs, multi-line content)
    pattern = re.compile(r"<harmony[^>]*>.*?</harmony>", re.DOTALL)
    matches = pattern.findall(xml_content)
    n_stripped = len(matches)
    if n_stripped == 0:
        # No work needed — preserve original byte-for-byte.
        shutil.copy(input_mxl, output_mxl)
        return 0

    stripped = pattern.sub("", xml_content)

    # Write a new .mxl with the stripped XML + every other file
    # preserved (container.xml, mimetype, etc).
    with zipfile.ZipFile(output_mxl, "w", zipfile.ZIP_DEFLATED) as zout:
        zout.writestr(xml_name, stripped)
        for name, payload in other_files:
            zout.writestr(name, payload)
    return n_stripped


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(f"usage: {sys.argv[0]} <input.mxl> <output.mxl>")
    in_path = sys.argv[1]
    out_path = sys.argv[2]
    n = strip_harmony(in_path, out_path)
    if n > 0:
        print(f"stripped {n} <harmony> blocks from {in_path} → {out_path}", file=sys.stderr)
