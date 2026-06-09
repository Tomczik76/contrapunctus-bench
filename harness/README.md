# harness/

The evaluation code. Two layers:

- **`score.py`** — the aggregator. Reads the committed
  `results/<date>/*.report.json` tier-count reports and reprints the
  headline tables (`make score`). Self-contained, stdlib only, no engine.
  **This is the path 99% of readers want.**
- **everything else** — the *generation* path: the shared Roman-numeral
  normalizer and the per-rival runners/scorers that produced the reports
  in the first place. These need the model environments + the When-in-Rome
  submodule and are documented per engine under `engines/`.

## Layout note

The interdependent Python modules (`rn_normalize.py`,
`music21_comparison.py`, `augnet_comparison.py`,
`analysisgnn_comparison.py`, `augnet_vs_ours_diff.py`,
`augnet_splits_dump.py`, …) live **flat in this directory**. They were
lifted from the engine repo's `corpus/scripts/`, where they
cross-import each other (`from music21_comparison import …`,
`from rn_normalize import …`) and assume co-location. Keeping them
co-located means those imports work unchanged — the only edit was
`_REPO_ROOT` (now one level up, since `harness/` sits directly under the
repo root). `engines/<engine>/` therefore holds each rival's **shell
runner + setup notes**, and points back here for the Python scorer.

## The shared normalizer

`rn_normalize.py` is the single Roman-numeral canonicalizer **every**
engine is scored through (ours via its Scala twin; the three competitors
via this module). It is parity-tested against the engine's Scala
normalizer:

```bash
make test            # python3 harness/test_rn_normalize_parity.py
```

40 hand-written smoke cases + 986 committed fixture cases
(`rn_normalize_fixture.json`, dumped from the engine). Using one
normalizer for all engines is a fairness requirement, not a convenience —
see the fairness note in [../methodology/match-tiers.md](../methodology/match-tiers.md).

## Provenance

All Python here except `score.py` was lifted from the private engine
repo's harness directory (2026-06-09), with two classes of edit: the
`_REPO_ROOT` path constant adjusted for this layout, and comments that
referenced private-repo files/paths reworded to self-contained or
"engine-side" phrasing (no logic changes — the parity test and `make
check` verify behavior is unchanged). `score.py` is new to this repo:
the engine repo aggregates via its own page-data builder; `score.py` is
the standalone, app-independent equivalent for the cross-engine tables.
