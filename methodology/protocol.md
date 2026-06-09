# Evaluation protocol

How the four engines are run, aligned, scored, and aggregated. The
guiding rule: every choice that could tilt the comparison is made
*against* our engine, or symmetrically, never in its favor.

## Autonomous, single prediction per event

The headline metric is **autonomous single-pick exact match**. Each
engine receives a raw MusicXML score and nothing else — no analyst key,
no modulation boundaries, no metadata — and must emit exactly one Roman
numeral per ground-truth event. This is the only setting that is
apples-to-apples across a rule engine, two neural engines, and ours.

One exception, declared loudly everywhere it appears: **Music21 has no
key detector.** To produce *any* Roman numeral it must be handed a key,
so the harness gives it the analyst's local key. Its column is therefore
an **upper bound** scored under easier conditions than the other three,
and it is labelled "(keys given)" in every table. It still finishes
last by a wide margin.

## Alignment + denominators

- **Ground-truth events** come from parsing each piece's analyst `.rntxt`
  into `(measure, beat) → label` events. No repeat expansion; one pass.
- Each engine's prediction stream is aligned to those events by absolute
  quarter-note position (anacrusis- and time-signature-aware), so a
  pickup-bar numbering difference between an engine's parser and the
  analyst's does not misalign the comparison.
- **Every ground-truth event counts.** If an engine emits no label at a
  position, that event is a miss, not a skip. There is no denominator
  shrinking to an engine's "confident" subset.
- Engines parse marginally different event totals on a few
  repeat-notation pieces (e.g. a Schubert song where one parser reads 51
  events and another 45). Each engine is scored on the events *it* parses
  **within the shared piece set**, which is why the per-engine `events`
  counts in `scores.json` differ by ~0.3% (ours 48,155; the others
  48,301). This does not change which pieces are compared — only the
  within-piece event count — and it is symmetric.

## The common subset + coverage gating

Engines fail on different pieces for structural reasons (a neural
engine's MusicXML writer crashing on a 2048th-note tuplet; a score that
exists only as a remote pointer; a GNN loader tripping on modal meter —
see `corpus/manifest.json` and methodology/corpus.md "Known engine
failures"). To keep the comparison honest:

> **A piece is scored for every engine, or for none.** The evaluated set
> is the **intersection** of pieces where all four engines produce
> output — 505 tonal pieces (48,155 events). No engine is ever credited
> on a piece another engine had to skip.

This intersection is **pinned**. `harness/score.py` writes
`results/<date>/common_subset.json` on first run and **fails** if a later
run's recomputed intersection differs. This is not bureaucracy: a partial
competitor cache silently changing the subset composition has, in this
project's history, flipped an aggregate verdict without any engine
actually changing. The pin makes that impossible to do by accident.

## Two aggregations, both reported

`harness/score.py` computes both, and the README shows both:

1. **All-pieces (micro)** — every chord event is one observation,
   event-weighted across the whole 505-piece subset. Honest, but
   **chorale-tilted**: 370 of 505 pieces (and 21,591 of 48,155 events)
   are Bach chorales, so this mostly reports a chorale number.

2. **Genre-balanced (macro)** — per-genre event-weighted exact%, then the
   unweighted mean over the 9 tonal genres. Each genre is one observation
   regardless of piece count. **This is the meaningful head-to-head**: it
   stops the chorale mass from dominating and asks "across nine distinct
   repertoires, who is more accurate on average?"

We lead on **both**.

## Out-of-sample (ours) vs in-sample (AugmentedNet) — the asymmetry

This is the single most important caveat, and it runs **in our disfavor**,
which is why the comparison is conservative rather than a trick.

**Our number is out-of-sample.** The learned chord-ID re-ranker (the
component that pushed us past AugmentedNet) is evaluated by **5-fold
cross-validation by piece**: the corpus is split into 5 folds, and every
piece is scored by a model trained on the *other four folds* — a model
that never saw that piece. No piece contributes to the model that grades
it. The committed `contrapunctus.report.json` is this out-of-sample
result.

**AugmentedNet's number is largely in-sample.** Its column comes from
running the released pretrained model on these pieces — and those pieces
include much of its own training data. This is **manifest-verified**, not
inferred: AugmentedNet's own dataset manifest
(`harness/augnet_splits.json`, 380 pieces split
260 train / 60 validation / 60 test; derivation documented in
`harness/engines/augmentednet/README.md`) shows that **seven of the nine
benchmark genres substantially overlap its training collections** —
TAVERN, BPS-FH, Haydn Op.20, Beethoven Op.18 (the ABC collection), the
DCML Mozart sonatas, all 24 WTC-I preludes, chorales 1–20, and 39 of our
46 Schubert lieder. Its genuinely out-of-dataset evidence is limited to
chorales 21–371, the two WTC fugues, and a handful of lieder.

So the honest framing is: **we lead, out-of-sample, against an opponent
measured largely in-sample.** A fully in-sample-vs-in-sample or
OOS-vs-OOS comparison would only widen our lead, not narrow it. And the
two genres we *lose* — Beethoven BPS-FH and TAVERN — are both
AugmentedNet training collections, so its edge there cannot be separated
from memorization. We win several genres (Haydn Op.20, Mozart, Op.18,
WTC) that are *also* its training data, which is the stronger result.

> We do not "correct" AugmentedNet's number downward for its in-sample
> advantage. We report its released model's actual output and simply
> disclose the asymmetry. The point is that our lead survives the most
> generous possible reading of the opponent.

AnalysisGNN (2024) is reported as published; its training overlap with
this corpus is not separately audited here (its manifest is not as
cleanly enumerable), so treat its column as "as-released" too.

## What this protocol deliberately excludes

- **No per-engine hyperparameter tuning on this corpus.** Each competitor
  runs its released, pretrained model with documented setup
  (`harness/engines/*/`).
- **No cherry-picked subset.** The piece set is the full intersection,
  pinned.
- **No candidate-set / "any of our N guesses matches" scoring.** Single
  pick only. (The engine *can* emit a candidate set for its tutor UI;
  that recall number is not on this page and is not comparable to
  single-prediction engines.)

See [corpus.md](corpus.md) for the pieces and [match-tiers.md](match-tiers.md)
for the scoring tiers.
