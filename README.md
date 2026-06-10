# Contrapunctus harmonic-analysis benchmark

Open evaluation of automatic **Roman-numeral analysis** engines: given a
raw MusicXML score and nothing else, label every beat with a Roman
numeral. This repo holds the methodology, the scoring code, the
rival-engine harnesses, the corpus manifest, and every engine's scored
results — enough to **reproduce the headline table on a clean machine in
about a minute**.

It is the public, verifiable record behind Contrapunctus's claim that its
engine **out-performs AugmentedNet out-of-sample**. The same data drives
the [contrapunctus.app/engine](https://contrapunctus.app/engine) page,
which is regenerated from it — a site deploy can lag a `results/` release,
so this repo is the canonical, dated source of truth. The engine itself is
closed; the evaluation is open. ("Closed model, open evals.")

The numbers below are computed by [`harness/score.py`](harness/score.py)
from the committed `results/2026-06-10/*.report.json` files. Run
`make score` to regenerate them yourself.

---

## Headline — genre-balanced, out-of-sample

Each of 9 tonal genres counts as **one observation** (macro-average), so
the 370 Bach chorales don't drown out the other eight repertoires. All
four engines run **fully autonomously** from raw MusicXML. Match is
**exact** Roman-numeral agreement with the analyst (see
[methodology/match-tiers.md](methodology/match-tiers.md)); the
annotator-defensible (**a-d**) column credits defensible alternate
readings of ambiguous chords and is shown only alongside exact.

<!-- BEGIN GENERATED: genre-balanced -->
| Engine | Type | Exact % | a-d % | Genres won |
|---|---|--:|--:|--:|
| **Contrapunctus** | hybrid: rules + learned re-ranker | **50.17** | 69.49 | **6 / 9** |
| AugmentedNet 11+ (RNalt), ISMIR 2021 | neural (CNN) | 47.89 | 68.04 | 3 / 9 |
| AnalysisGNN v1.0, 2024 | neural (GNN) | 38.72 | 59.23 | 0 / 9 |
| Music21 10.1.0 *(keys given — not autonomous)* | rule-based | 23.33 | 41.12 | 0 / 9 |
<!-- END GENERATED: genre-balanced -->

**Contrapunctus 50.17 vs AugmentedNet 47.89 — a +2.28pp lead**, and the
first release where the genre-balanced headline is above 50%. It is also
the *stronger* kind of lead: **our number is out-of-sample** (5-fold
cross-validation by piece — every piece is scored by a model that never
trained on it), whereas AugmentedNet's released model is evaluated on
pieces that include much of its own training data
([why this is conservative, not a trick](methodology/protocol.md)).
Music21 has no key detector, so it is handed the analyst's key — its
column is an easier-conditions upper bound and still finishes last.

### Where we win, where we lose — per genre

Sorted by our margin over AugmentedNet, so the three genres we **don't**
win are as visible as the six we do. (`exact %`, event-weighted within
each genre.)

<!-- BEGIN GENERATED: per-genre -->
| Genre | Pieces | Contrapunctus | AugmentedNet | AnalysisGNN | Music21 | Winner | Δ vs AugNet |
|---|--:|--:|--:|--:|--:|---|--:|
| Bach chorales | 370 | **68.15** | 55.23 | 52.89 | 25.62 | Contrapunctus | **+12.92** |
| Haydn Op.20 | 4 | **54.61** | 46.57 | 39.90 | 35.69 | Contrapunctus | +8.04 |
| Mozart sonatas (DCML) | 24 | **63.30** | 55.78 | 53.36 | 19.60 | Contrapunctus | +7.52 |
| Beethoven Op.18 | 24 | **49.28** | 44.08 | 38.78 | 22.91 | Contrapunctus | +5.20 |
| Schubert lieder | 39 | **56.68** | 54.34 | 43.73 | 35.67 | Contrapunctus | +2.34 |
| Bach WTC I | 24 | **37.03** | 34.76 | 29.10 | 27.61 | Contrapunctus | +2.27 |
| Brahms lieder | 9 | 38.36 | **39.43** | 28.57 | 11.31 | AugmentedNet | −1.07 |
| TAVERN variations | 7 | 42.26 | **49.27** | 43.96 | 21.24 | AugmentedNet | −7.01 |
| Beethoven BPS-FH | 4 | 41.85 | **51.53** | 18.20 | 10.31 | AugmentedNet | −9.68 |
<!-- END GENERATED: per-genre -->

We lose **TAVERN**, **Beethoven BPS-FH**, and — narrowly — **Brahms
lieder**, all three to AugmentedNet. (AnalysisGNN, which won Brahms on
the 2026-06-09 release at 43.09, dropped to 28.57 there and now wins no
genre.) TAVERN and BPS-FH are *both* AugmentedNet training collections
(4 BPS-FH pieces, all in-sample), so its lead there cannot be cleanly
separated from memorization — whereas several genres we **win** (Haydn
Op.20, Mozart, Op.18, WTC) are *also* its training data. Brahms is
different: 7 of the 9 Brahms songs are absent from AugmentedNet's
dataset entirely (one sits in its training split, one in validation —
per its published splits), so its −1.07pp edge there is mostly *not* a
memorization artifact; it is simply slightly ahead on that repertoire
today. The two big losses are figural/variation textures where a chord
is spread across an arpeggio; closing them is active engine work, not a
benchmark artifact.

### All pieces (micro) — reported too, but chorale-tilted

Event-weighted over all 505 pieces. 370 of them are chorales, so this
mostly reports a chorale number — which is why genre-balanced above is the
headline. We lead here as well:

<!-- BEGIN GENERATED: all-pieces -->
| Engine | Exact % | a-d % |
|---|--:|--:|
| **Contrapunctus** | **58.93** | 72.77 |
| AugmentedNet 11+ | 51.46 | 69.67 |
| AnalysisGNN v1.0 | 46.63 | 62.82 |
| Music21 10.1.0 *(keys given)* | 24.68 | 40.17 |
<!-- END GENERATED: all-pieces -->

Common subset: **505 tonal pieces, 48,237 events** — the intersection of
pieces all four engines successfully analyze (no engine is credited on a
piece another skipped). 48 Monteverdi madrigals (39 of them analyzed by
all four engines) are evaluated separately as a pre-tonal exploration,
outside every aggregate above.

---

## Why exact-match understates everyone

Roman-numeral analysis is **interpretive** — theorists disagree on the
"right" label for the same chord (Cad⁶₄ vs I⁶₄, `vii°6` vs `V`, `V/V` vs
`II`, applied-chord and inversion-figure conventions). A flat exact-match
score penalizes every engine for these defensible disagreements. The
**annotator-defensible** tiers credit them — identically for all four
engines, so they cannot flatter ours — and the per-tier ladder is in
`scores.json`. The full tier system, and the convention examples it
covers, are in [methodology/match-tiers.md](methodology/match-tiers.md).

## Methodology in one paragraph

Autonomous single prediction per beat from raw MusicXML; one
parity-tested normalizer scores all four engines; every ground-truth
event counts (no answer = miss); the evaluated set is the pinned 505-piece
4-engine intersection. Our headline is **out-of-sample** (5-fold CV by
piece); AugmentedNet's is **largely in-sample** (manifest-verified: 7 of
9 genres overlap its training collections). That asymmetry runs in our
disfavor, which is the point — the lead survives the most generous reading
of the opponent. Full detail: [methodology/protocol.md](methodology/protocol.md),
[methodology/corpus.md](methodology/corpus.md).

## What didn't work (negative results)

Asymmetric honesty: the failures are what make the wins credible.

- **Learned *key* detectors lose, every time.** LR / MLP / random-forest
  key detectors beat the hand-tuned heuristic on *per-beat key accuracy*
  yet **regressed chord-ID exact by 5–9pp** — because chord-ID depends on
  the *structure* of the keychain (long, phrase-aligned key runs) more
  than on per-beat correctness, and a learned detector's many short
  spurious segments each cost several wrong-key chord beats. The shipped
  engine keeps rule-based key detection. The complementary lesson — a
  learned model *does* win for **chord-label selection** (it's what put us
  ahead here) — is the one place learning helped. Rule: never learn keys;
  do learn the chord label.
- **Bigger models overfit.** A higher-capacity neural variant of the
  chord-ID re-ranker scored *below* the plain logistic-regression one.
  Capacity was not the lever; the feature representation was. Simpler
  generalized better.
- **Scoring-side strictness probes were rejected on the merits.** E.g.
  forcing the cadential-6-4 family to count only at `exact` (instead of
  crediting the I⁶₄/V⁶₄ readings as a convention) was measured and
  reverted — it penalizes a documented annotator convention for every
  engine without making any engine ordering more informative. The tier
  system ([methodology/match-tiers.md](methodology/match-tiers.md)) is
  the result of probes like this, run symmetrically.

These are summarized from the engine's iteration history; the benchmark
records them so a reader can see the search was adversarial, not a
victory lap.

## Reproduce it

```bash
# 1-minute reproduction from committed data — no engine, no models, just Python:
make score        # aggregates results/2026-06-10/*.report.json → the tables above
make check        # additionally asserts every README number matches scores.json
```

`make score` needs only Python 3.9+ (stdlib). It reads the four committed
per-piece tier-count reports and reprints the genre-balanced, all-pieces,
and per-genre tables, writing `results/2026-06-10/scores.json`.

Regenerating the reports themselves (the heavy path — runs each rival
model and re-scores) is `make bench`; it needs the When-in-Rome submodule,
the rival model environments, and the closed engine. See
[CONTRIBUTING.md](CONTRIBUTING.md) and [`harness/engines/`](harness/engines/)
for per-engine setup. Most users only ever need `make score`.

### Run the engine on your own chords

The closed engine ships here as a stripped WebAssembly bundle (the exact
build the website serves to browsers), under an evaluation-only license:

```bash
make engine-demo          # or: node engine/run.mjs
```

It analyzes a few progressions and prints the production engine's Roman
numerals (learned model on). **This does not reproduce the benchmark
numbers** — the artifact carries one full-corpus model, so running it on
the corpus is *in-sample*, whereas the published 50.17 / 58.93 are
*out-of-sample*. The headline is reproduced by `make score`; the engine is
for analyzing new music. See [`engine/README.md`](engine/README.md).

## What's in here

```
README.md                      headline + methodology summary (this file)
methodology/                   match-tiers · corpus · protocol
corpus/manifest.json           every piece: id, genre, events, source, license
corpus/prep/                   scripts that derive ground truth from the submodule
harness/score.py               the aggregator make score runs
harness/rn_normalize.py        the one normalizer (+ parity test) all engines share
harness/engines/               per-rival runners + setup notes
results/<date>/                dated releases: four scored reports + scores.json (+ pinned subset)
engine/                        the closed engine as a stripped WASM bundle + a runner
```

The corpus itself is a git **submodule** (When-in-Rome), never vendored;
its sub-corpora carry varying licenses recorded per-piece in the manifest.

## Versioning

Results are **date-stamped releases** (`results/2026-06-10/`), each pinned
to the engine build that produced them (git SHA in
`results/<date>/PROVENANCE.md`). This repo is the canonical record;
the `contrapunctus.app/engine` page is regenerated from the same
`benchmarks.json` and may briefly lag a release between deploys. When in
sync they describe the same engine build by construction.

## Add your engine

PRs that add another RNA engine to the comparison are welcome — see
[CONTRIBUTING.md](CONTRIBUTING.md) for the report schema and the one rule
that matters (score through the shared normalizer, on the full piece set).

## License

- Harness, scoring, methodology, and the `engine/run.mjs` runner:
  **Apache-2.0** ([LICENSE](LICENSE)).
- The compiled Contrapunctus engine artifact (`engine/main.wasm` + glue):
  **evaluation-only** ([LICENSE-ENGINE.md](LICENSE-ENGINE.md)).
- Rival engine outputs in `results/` are derived from MIT-licensed models
  (AugmentedNet, AnalysisGNN) and music21 (BSD-3-Clause). Scores and
  analyst labels are **not** redistributed here; their licenses are
  recorded per-corpus in `corpus/manifest.json`.

---

Maintained by [Contrapunctus](https://contrapunctus.app) · live numbers at
[contrapunctus.app/engine](https://contrapunctus.app/engine).
