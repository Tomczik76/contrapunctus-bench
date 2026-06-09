# Contrapunctus

Our engine — the subject of the benchmark. It is **closed**; the compiled
WASM bundle ships under [`../../../engine/`](../../../engine/) (stripped,
evaluation-only), with a Node runner. See that directory for what it is
and how to run it.

## How its report is generated

Unlike the three rivals, Contrapunctus has no runner in this directory:
its column comes from the engine's own Scala test suite
(`WhenInRomeSuite`) in the private engine repo, which writes
`corpus/target/corpus-report.json`. That file (single-pick rows) is the
committed `results/2026-06-09/contrapunctus.report.json`.

The crucial property: it is **out-of-sample**. The learned chord-ID
re-ranker is evaluated by 5-fold cross-validation by piece — every piece
is scored by a model trained only on the other folds. See
[../../../methodology/protocol.md](../../../methodology/protocol.md).

## Reproducing it

You cannot regenerate this report from committed data alone — it requires
the closed engine **and** the cross-validation training harness. The
shipped WASM (`engine/`) can't do it either: it carries one model trained
on the full corpus, whereas this report is the *out-of-sample* CV result
(each piece scored by a fold-model that excluded it), so running the WASM
on the corpus would give an in-sample number instead. To reproduce the
published *tables*, you don't need any of this — the committed reports +
`make score` do it.
