# Music21

Cuthbert et al. — *music21*, the reference rule-based baseline. We invoke
`roman.romanNumeralFromChord` per beat on `chordify()`-flattened parts.

- Upstream: https://github.com/cuthbertLab/music21 — **BSD-3-Clause**, so
  redistributing outputs is permitted.
- Version evaluated: `10.1.0`.

## NOT autonomous — keys given

This is the one engine the harness does **not** run autonomously.
music21 has no key detector, so to produce any Roman numeral it must be
handed a key; the harness gives it the **analyst's local key**. Its column
is therefore an upper bound measured under easier conditions than the
other three engines, and is labelled "(keys given)" everywhere it appears.
It still finishes last by a wide margin.

## Run

```bash
python3 -m venv /tmp/m21env && source /tmp/m21env/bin/activate
pip install music21
python3 ../../music21_comparison.py     # → /tmp/music21-report.json
```

`music21_comparison.py` lives in `harness/` (flat) because it also hosts
the shared tier classifier (`classify_per_rule`) and the PIECES roster
that the AugmentedNet and AnalysisGNN scorers import. It reads scores +
analyses from the When-in-Rome submodule at `corpus/When-in-Rome` and
scores through the shared `rn_normalize`.

## Caveats

- music21 10.1.0 can't parse Beethoven Op.18's `<harmony><function>…`
  Riemannian elements; the script strips `<harmony>` blocks first (see
  `corpus/prep/strip_harmony.py`).
- The Python rntxt parser treats Schubert's `m12-15 = m8-11` repeat
  notation slightly differently than the engine's Scala parser — a
  handful of events on a few pieces (symmetric, doesn't change the
  bottom line; see [../../../methodology/protocol.md](../../../methodology/protocol.md)).
