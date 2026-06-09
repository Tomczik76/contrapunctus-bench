# corpus/prep — deriving the ground truth

This repo does **not** commit scores or analyst Roman-numeral files. The
ground truth is derived at build time from the When-in-Rome git submodule
plus a few fetched score sources. These scripts do that derivation; the
committed `corpus/manifest.json` records what results.

Run order for a full `make bench` regeneration:

```bash
git submodule update --init corpus/When-in-Rome     # the analyst .rntxt + most scores
python3 corpus/prep/fetch_kern_chorales.py          # Riemenschneider **kern chorales
python3 corpus/prep/fetch_tavern_scores.py          # TAVERN variation scores
python3 corpus/prep/fetch_monteverdi_madrigals.py   # Monteverdi (music21 bundled)
python3 corpus/prep/strip_harmony.py <score.mxl>    # used per-piece by the runners
```

| Script | What it does |
|---|---|
| `fetch_kern_chorales.py` | Pulls each Bach chorale from craigsapp/bach-370-chorales, parses with music21, dedupes volta pickups, writes `score_kern.mxl` into `corpus/scores-local/`. Idempotent. The engine prefers these over When-in-Rome's MuseScore exports because the analyst annotated against the Riemenschneider edition (apples-to-apples scores). |
| `fetch_tavern_scores.py` | Fetches TAVERN variation-set scores into `corpus/scores-local/`. |
| `fetch_monteverdi_madrigals.py` | Copies Monteverdi Books 3-5 madrigals (+ `.rntxt`) out of the installed music21 corpus into `corpus/scores-local/`. |
| `strip_harmony.py` | Strips `<harmony>` Riemannian-function blocks from a score.mxl so music21 / AugmentedNet can parse Beethoven Op.18 (whose `<function>X.Y</function>` elements crash their chord-symbol parser). |
| `build_manifest.py` | Regenerates `corpus/manifest.json` from the engine app's `benchmarks.json::per_piece` (piece list + event counts + source URLs) joined with the per-corpus provenance table in the script. Set `CONTRAPUNCTUS_APP_ROOT` to the app checkout (default `../contrapunctus`). |

## The `scores-local` gotcha

The fetch scripts populate `corpus/scores-local/`, which is **machine
state**, not committed here. If it is incomplete, a `make bench` run
silently shrinks to a fraction of the corpus (this bit the project once: a
run dropped to 165 of 545 pieces because a worktree's `scores-local` was
partial). After fetching, sanity-check that a bench run reports the full
**545 pieces incl. 370 chorales** before trusting any number.

These scripts compute paths from their own location
(`corpus/prep/` → repo root via `dirname`), so they run unchanged in this
layout — no path edits were needed (unlike the `harness/` scripts).
