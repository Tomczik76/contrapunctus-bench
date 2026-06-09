# Contributing — add your engine to the comparison

This benchmark is meant to be a fair, reproducible head-to-head. New
Roman-numeral-analysis engines are welcome. The bar is **fairness**, not
allegiance — a PR that beats Contrapunctus is exactly as welcome as one
that doesn't, and the README shows losses as prominently as wins.

## The interchange format

Everything in this repo communicates through one JSON shape. An engine's
result is a per-piece, per-tier **count** report:

```json
{
  "engine": "yourengine",
  "engine_version": "1.2.3",
  "timestamp": "2026-06-09T16:37:27Z",
  "mode": "single-pick",
  "rows": [
    {"mode": "single-pick", "group": "bach-wtc", "piece": "Bach WTC I Prelude 01",
     "total": 35, "exact": 19,
     "sameChordGained": 2, "inversionGained": 1, "conventionGained": 0,
     "sharedBassGained": 0, "secondaryDiatonicGained": 0}
  ]
}
```

- `total` = ground-truth events in that piece.
- `exact` + the five `*Gained` counters partition the **matched** events
  by tier ([methodology/match-tiers.md](methodology/match-tiers.md)).
  They are mutually exclusive, so
  `total ≥ exact + sameChordGained + … + secondaryDiatonicGained`.
- `group` must be one of the 9 tonal genres (or `monteverdi`); `piece`
  must match the ids in `corpus/manifest.json`.

Drop your report at `results/<date>/yourengine.report.json`, add your
engine to the `ENGINES` list in [`harness/score.py`](harness/score.py),
and `make score` will include you in every table.

## The rules that keep it fair

1. **Autonomous.** Your engine gets the raw MusicXML and nothing else —
   no analyst key, no modulation hints. (The sole documented exception is
   Music21, which has no key detector and is explicitly labelled "keys
   given." If your engine also cannot detect keys, say so loudly and
   expect the same asterisk.)
2. **Score through the shared normalizer.** Use
   [`harness/rn_normalize.py`](harness/rn_normalize.py) — the single,
   parity-tested Roman-numeral canonicalizer — and the shared tier
   classifier. Do **not** define your own normalization; divergent
   normalizers are how a benchmark silently flatters one engine (it
   happened here once — see the fairness note in match-tiers.md).
3. **Every ground-truth event counts.** No answer for a position is a
   miss, not a skipped event. Denominators are the analyst's events.
4. **The piece set is the pinned intersection.** If your engine fails on
   some pieces for structural reasons, document them (like the existing
   `known_failures`); those pieces drop out for *every* engine, never just
   yours. `harness/score.py` enforces the pinned common subset and will
   fail if the intersection changes — update the pin deliberately and note
   it in `PROVENANCE.md`.
5. **Out-of-sample if you can.** If your engine learns, evaluate by
   cross-validation by piece (or hold the corpus out entirely) and say
   which. In-sample numbers are accepted but must be disclosed as such, so
   readers can weigh them (this is exactly how AugmentedNet's column is
   treated).

## Regenerating the reports (`make bench`)

The committed reports were produced by the private engine repo's Scala
suite (ours) and the runners under `harness/engines/` (the rivals). A full
regeneration needs:

- the **When-in-Rome submodule** checked out (`git submodule update
  --init`) plus the fetched score sources (`corpus/prep/`);
- each rival's **model environment** — see
  `harness/engines/{augmentednet,analysisgnn,music21}/README.md`. These
  pin specific Python / TensorFlow / PyTorch versions and download
  pretrained checkpoints;
- for the Contrapunctus column, the **closed engine** plus its
  cross-validation training harness. (The stripped WASM under `engine/` is
  the shipped engine, but it carries one full-corpus model and so produces
  in-sample numbers on the corpus — it cannot regenerate the out-of-sample
  report. See `engine/README.md`.)

`make score` — reproducing the *tables* from committed reports — needs
none of that, only Python. That is the path 99% of readers want.

## A note on the scorer

`harness/score.py` is intentionally tiny and dependency-free (stdlib
only) so it is easy to audit. If you find a scoring bug, a PR that fixes
it *and moves a number against Contrapunctus* is the most valuable kind of
contribution here.
