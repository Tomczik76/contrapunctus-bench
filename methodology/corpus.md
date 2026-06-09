# The corpus

The benchmark evaluates on **563 movements** drawn from public
Roman-numeral-analysis corpora: **515 tonal** pieces across 9 genres,
plus **48 Monteverdi madrigals** reported separately as a pre-tonal
exploration. The 4-engine head-to-head runs on the **505-piece tonal
common subset** (48,155 ground-truth events).

This repo does **not** redistribute the scores or the analyst `.rntxt`
files. They are derived at build time from the When-in-Rome git submodule
and a few fetched score sources (see [`../corpus/prep/`](../corpus/prep/)).
What is committed is the **manifest** (`corpus/manifest.json` — every
piece's id, genre, event count, source URL, and per-corpus license) and
each engine's **scored tier-counts** (`results/`). Per-piece provenance
and licensing live in the manifest; this file describes the shape of the
set.

## The nine tonal genres

| Genre | Pieces (subset) | Period | Texture | Score source |
|---|--:|---|---|---|
| Bach chorales | 370 | Late Baroque ~1730 | homophonic SATB | Riemenschneider **kern (craigsapp) |
| Bach WTC I | 24 | Late Baroque 1722 | figural / fugal | When-in-Rome |
| Beethoven Op.18 quartets | 24 | Classical ~1799 | string quartet | When-in-Rome |
| Mozart sonatas (DCMLab) | 24 | Classical 1773–88 | figural keyboard | DCMLab |
| Schubert lieder | 39 | Early Romantic 1815–28 | voice + piano | OpenScore (CC0) |
| Brahms lieder | 9 | Late Romantic 1853–68 | voice + piano | OpenScore (CC0) |
| TAVERN variations | 7 | Classical/E.Romantic | variation form | TAVERN |
| Beethoven BPS-FH | 4 | Classical/E.Romantic | dense keyboard | Chen & Su 2018 |
| Haydn Op.20 quartets | 4 | Classical 1772 | string quartet | HaydnSun |

(Piece counts are the common-subset counts used in the head-to-head; the
full iterated set is slightly larger before the coverage intersection.
See `corpus/manifest.json::counts`.)

Four genres have ≤9 pieces. This is a real limitation, surfaced rather
than hidden: it is *why* the genre-balanced macro is the honest aggregate
(each genre = one observation) **and** why those small genres carry
outsized variance. Expanding them (more Annotated Beethoven Sonatas, the
remaining DCML Mozart sonatas) is the top item in this benchmark's future
work.

## Why genre balancing matters

The all-pieces micro aggregate is **chorale-tilted**: 370 of 505 pieces
and 21,591 of 48,155 events are Bach chorales. A single event-weighted
percentage over the whole set therefore mostly reports a chorale number
and lets one homogeneous, relatively-easy repertoire dominate. The
genre-balanced macro-average treats each of the 9 genres as one
observation, so chorales count once, not 370 times. Both aggregates are
reported; we lead on both. See [protocol.md](protocol.md).

## Pre-tonal: Monteverdi madrigals (reported, not aggregated)

48 madrigals from Monteverdi Books 3–5 (1592–1605), from music21's
bundled corpus. This is **modal pre-tonal polyphony** — Roman-numeral
analysis of it is a different and ill-posed task, and the numbers are
exploratory. Monteverdi is **excluded from every tonal aggregate** and
shown in its own section. (Note: `harness/score.py` reports it on the
4-engine common subset for internal consistency; contrapunctus.app/engine
reports it per-engine-own-coverage, so the two are not meant to match
piece-for-piece.)

## Known engine failures (the coverage gate in practice)

Engines fail on different pieces for repeatable structural reasons. Each
such piece is dropped from the comparison for **every** engine (the
intersection rule, [protocol.md](protocol.md)). The documented cases:

- **AugmentedNet** — cannot export 3 pieces (Beethoven Op.18/1 mvt 2,
  Schubert *Die Stadt*: a music21 MusicXML-writer crash on a 2048th-note
  duration; WTC fugues 19 & 22: scores present only as remote pointers in
  the submodule, not fetched).
- **AnalysisGNN** — its score loader trips on ~11 pieces (several modal
  Monteverdi madrigals; 2 TAVERN sets), logged silently during inference.

These are surfaced here and in `corpus/manifest.json` so the reader sees
the gap explicitly, rather than an engine being quietly credited on
pieces it skipped.

## Frozen held-out set (overfitting discipline)

Separate from the cross-validation that makes our headline out-of-sample
(see [protocol.md](protocol.md)), the engine's own development used a
**frozen 9-piece held-out set** — Brahms Requiem mvt 1, three chorales,
Beethoven Op.10/1 mvt 1, two Haydn quartets, Mozart K330/2, Mozart K398 —
that was **never iterated against**: its outputs were not read between
commits, and no engine, picker, or scorer rule was ever tuned in response
to a held-out miss. It is an additional guard against the iterated corpus
silently becoming a training set through repeated tuning. The held-out
diagnostic is published on contrapunctus.app/engine; it is not duplicated
in this repo's `results/`.

## Sources

Full citations are in `corpus/manifest.json::corpora` and on
contrapunctus.app/engine. The primary analyst-label source is the
**When-in-Rome** corpus (Gotham et al.; new content CC BY-SA 4.0); scores
come from When-in-Rome, the OpenScore Lieder Corpus (CC0), Craig Sapp's
Riemenschneider **kern chorales, and the original BPS-FH / TAVERN / DCML /
HaydnSun datasets re-bundled into When-in-Rome. Monteverdi scores +
analyses are from music21 (BSD-3-Clause). External score licenses vary —
the manifest records each per corpus and links the canonical source.
