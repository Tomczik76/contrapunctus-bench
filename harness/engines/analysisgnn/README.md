# AnalysisGNN

Karystinaios — *AnalysisGNN* (multi-task graph neural network for
symbolic-music analysis), 2024. The maintained successor to ChordGNN
(whose pretrained checkpoint was removed from W&B, so AnalysisGNN stands
in as the second neural baseline).

- Upstream: https://github.com/manoskary/analysisgnn — **MIT** licensed
  (© 2025 Emmanouil Karystinaios), so redistributing model *outputs* is
  permitted.
- Version evaluated: `v1.0.0-default-model`.

## Setup (one-time)

Persistent env path (`$CONTRAPUNCTUS_ENGINE_HOME`, default
`~/.cache/contrapunctus/engines`). The venv is named `chordgnnvenv` for
historical continuity.

```bash
ENGINE_HOME="${CONTRAPUNCTUS_ENGINE_HOME:-$HOME/.cache/contrapunctus/engines}"
mkdir -p "$ENGINE_HOME"
python3.11 -m venv "$ENGINE_HOME/chordgnnvenv"
source "$ENGINE_HOME/chordgnnvenv/bin/activate"
pip install torch pytorch-lightning partitura music21 pandas tqdm wandb GitPython rotograd "numpy<2"
pip install torch-scatter torch-sparse torch-cluster torch-geometric \
    -f https://data.pyg.org/whl/torch-2.11.0+cpu.html
cd "$ENGINE_HOME" && git clone https://github.com/manoskary/graphmuse.git && pip install -e graphmuse
cd "$ENGINE_HOME" && git clone https://github.com/manoskary/analysisgnn.git && pip install -e analysisgnn
wandb login    # one-time; the pretrained model is gated behind a free W&B account
```

## Run

```bash
# 1. inference → /tmp/analysisgnn-runs/<label>/<label>_analysis.csv
bash run_analysisgnn.sh
# 2. score vs ground truth → /tmp/analysisgnn-report.json
python3 ../../analysisgnn_comparison.py
```

## Gotcha — reconstruct the RN, don't trust the `romanNumeral` column

AnalysisGNN is multi-task; its single `romanNumeral` head empirically
diverges from the more granular `degree1`/`quality`/`inversion`/`degree2`
heads. `analysisgnn_comparison.py` reconstructs the Roman numeral from
those granular columns instead of trusting `romanNumeral` — without this,
apparent accuracy is ~2-3% (random); with it, the real ~40%. This is a
documented scoring choice, made the same way for every piece. The scorer
imports the shared `rn_normalize` + `music21_comparison` classifier from
`harness/`.

## Known failures (~11 pieces)

The score loader trips on several modal Monteverdi madrigals and 2 TAVERN
sets (logged during inference). These drop out of the comparison for every
engine — see `corpus/manifest.json` and
[../../../methodology/corpus.md](../../../methodology/corpus.md).
