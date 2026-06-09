# Match tiers — how a prediction is scored against the analyst

Every engine emits one Roman-numeral label per ground-truth event. The
scorer compares that single pick to the analyst's label and assigns the
event to exactly **one** of six tiers. The tiers are cumulative in
permissiveness: `exact ⊂ +sameChord ⊂ +inversion ⊂ +convention ⊂
+sharedBass ⊂ +secondaryDiatonic`. Tier counts per piece are what the
committed `results/<date>/*.report.json` files store; `harness/score.py`
sums them.

**Only the `exact` tier belongs in a head-to-head engine comparison.**
The wider tiers exist to quantify *how* the remaining events miss —
specifically, how many "misses" are actually defensible alternate
readings of an ambiguous chord rather than wrong analyses. They are
reported as the **annotator-defensible (a-d)** total, but a-d is only
meaningful with the per-tier breakdown visible; citing a-d alone is
misleading and we never do.

## Why a single `exact` percentage understates every engine

Roman-numeral analysis is **interpretive**. Trained theorists routinely
disagree on the "correct" label for the same chord, and the published
corpora encode different house styles. A few systematic examples, all of
which describe the *same* sounding chord:

- **Cadential 6-4**: `Cad64` vs `I64` vs `V64` — a functional reading
  (the 6-4 as a dominant embellishment) vs a literal bass-figure reading.
- **Leading-tone vs dominant**: `vii°6` vs `V` over the same bass.
- **Secondary vs diatonic**: `V/V` vs `II`, `V/vi` vs `III` — identical
  pitch-class set, different functional claim.
- **Chromatic leading-tone marker**: `#vii°` (DCML house style) vs
  `vii°` (Gotham / Tymoczko) — purely typographical; same chord.
- **Inversion figures** an analyst may or may not spell out on a passing
  chord.

None of these is an engine *error*. The tier system credits them so the
comparison measures musical agreement, not house-style agreement — and it
does so **identically for all four engines**, so it cannot flatter ours.

## The six tiers

### 0. Normalization (applied before tier 1)

Both labels are canonicalized first, so typography never costs an exact
match: Unicode → ASCII (`♯`→`#`, `♭`→`b`, `°`↔`o`, `Δ`→dropped), the
augmented-sixth family is collapsed to a canonical spelling
(`Ger6.5`/`Ger7` → `Ger6`), and the chromatic leading-tone marker is
stripped on no-slash forms (`#vii°` → `vii°`). This logic lives in one
place — `harness/rn_normalize.py` — and is **parity-tested against the
engine's Scala normalizer** (`harness/test_rn_normalize_parity.py`, 986
committed fixture cases). One normalizer, applied to every engine.

> **Fairness note (2026-06-09).** An audit found the benchmark had been
> scoring *our* engine through the Scala normalizer but the three
> competitors through two independently-drifted Python copies. Three
> drifts all happened to inflate our relative `exact` number (a missing
> `/v`,`/vi`,`/vii` slash keep-set; a missing Ger-family collapse; an
> over-broad `#vii` strip). They were unified into the single
> parity-tested module above and every competitor re-scored. The numbers
> in this repo are post-fix. This is the kind of correction that, by
> construction, can only have *lowered* our reported lead — we report it
> because asymmetric honesty is the point.

### 1. `exact`

The normalized pick literally equals the normalized analyst label.
**This is the only tier used in cross-engine numbers.**

### 2. `+ sameChord`

Chord-identity-preserving reductions: extension collapses
(`V13 → V11 → V9 → V7 → V`), power-chord and sus reductions, the Aug6
family (`Ger6 ≡ It6`), Neapolitan synonyms (`N ≡ bII`), inverted-7th →
triad (drops a chord 7th read as an ornament), minor-mode redundant-flat
strip (`bVI ≡ VI` in minor). Same chord, different spelling depth.

### 3. `+ inversion`

Same root + quality, **different inversion figure**
(`V ↔ V6 ↔ V64`, `V7 ↔ V65 ↔ V43 ↔ V42`). The engine identified the
chord but not the bass position. Split out as its own tier so a reader
can see exactly how much accuracy depends on accepting bass-position
equivalence (≈ 3-6pp for the neural engines and ours alike).

### 4. `+ convention`

Annotator-convention flips that change the *reading* but not the chord:
the cadential-6-4 family (`Cad64 ↔ I64 / V64 / i64 / v64`) and sus
case-flips (`Vsus4 ↔ vsus4`, quality undetermined without the 3rd).

### 5. `+ sharedBass`

Different chord identity sharing a bass note: `iii ↔ I6`,
`ii6 ↔ IV ↔ V42`, `V6 ↔ vii°`. Both are defensible labels for the same
incomplete-chord scenario. **This tier widens reported accuracy by
~6-8pp aggregate — read it with care**, and only ever as part of the
a-d breakdown.

### 6. `+ secondaryDiatonic`

Same pitch-class set, different functional reading: `V/V ↔ II`,
`V/vi ↔ III`, `V/iv ↔ i-in-minor`. The analyst's choice between a
secondary-dominant reading and a diatonic one.

## Derivation

```
exact                          = tier 1
annotator-defensible (a-d)     = tier1 + tier2 + tier3 + tier4 + tier5 + tier6
sameChordAnyInversion          = tier1 + tier2 + tier3
```

`harness/score.py` prints the cumulative ladder per engine
(`scores.json::micro.<engine>.cumulative_tiers_pct`) so you can see where
each engine's a-d total comes from. For example, on the all-pieces micro
aggregate our `exact` 58.05 climbs to 72.30 a-d, of which the single
biggest jump is `+ sharedBass` (65.60 → 71.92) — i.e. a large share of
our non-exact events are genuine bass-sharing ambiguities, not wrong
chords.

## What the tiers do **not** do

- They do not change any engine's *prediction*. Every engine still emits
  one label per event; the tiers only classify the comparison outcome.
- They are not applied asymmetrically. The same `rn_normalize` + the same
  tier classifier scores all four engines.
- `exact` is the published headline. When this repo's README, or
  contrapunctus.app/engine, says "we beat AugmentedNet," it means at
  `exact`.

See [protocol.md](protocol.md) for alignment + denominator rules and
[corpus.md](corpus.md) for the piece set.
