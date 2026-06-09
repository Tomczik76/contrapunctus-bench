# AugmentedNet

Nápoles López, Gotham & Fujinaga — *AugmentedNet* (CNN ensemble), ISMIR
2021. The published symbolic-RN baseline on When-in-Rome.

- Upstream: https://github.com/napulen/AugmentedNet — **MIT** licensed
  (© 2021 Néstor Nápoles López), so redistributing model *outputs* (this
  repo's tier-count reports) is permitted.
- Version evaluated: `augnet-v11-rnalt` (the released pretrained model).

## Important: this column is largely in-sample

AugmentedNet's released model was trained on collections that overlap 7 of
the 9 benchmark genres. This is **manifest-verified** here, not assumed:
`augnet_splits_dump.py` reads AugmentedNet's own dataset manifest and
writes [`../../augnet_splits.json`](../../augnet_splits.json) (380 pieces:
260 train / 60 validation / 60 test). Our headline is out-of-sample; this
asymmetry is the central caveat — see
[../../../methodology/protocol.md](../../../methodology/protocol.md).

```bash
# regenerate the splits map (needs the AugmentedNet checkout, see below)
python3 ../../augnet_splits_dump.py
```

## Setup (one-time)

The model needs Python 3.11 + TensorFlow 2.15 (TF 2.16+ uses Keras 3,
which can't deserialize the 2021-vintage architecture). Environments live
in a persistent path (`$CONTRAPUNCTUS_ENGINE_HOME`, default
`~/.cache/contrapunctus/engines`) — **not** `/tmp`, which macOS reaps.

```bash
ENGINE_HOME="${CONTRAPUNCTUS_ENGINE_HOME:-$HOME/.cache/contrapunctus/engines}"
mkdir -p "$ENGINE_HOME"
python3.11 -m venv --copies "$ENGINE_HOME/augnet"
source "$ENGINE_HOME/augnet/bin/activate"
pip install "tensorflow==2.15.*" "music21>=8" mlflow "protobuf>=4,<5" numpy pandas

cd "$ENGINE_HOME" && git clone --depth=1 https://github.com/napulen/AugmentedNet.git
# patch their music21 6.x .flat usage for modern music21:
cd "$ENGINE_HOME/AugmentedNet" && sed -i.bak 's/\.flat\./.flatten()./g' \
  AugmentedNet/annotation_parser.py AugmentedNet/inference.py AugmentedNet/score_parser.py
```

## Run

```bash
# 1. inference on every corpus piece → /tmp/augnet-runs/<piece>/
bash run_augnet.sh
# 2. score the predictions vs ground truth → /tmp/augnet-report.json
python3 ../../augnet_comparison.py
```

`run_augnet.sh` needs the When-in-Rome submodule at `corpus/When-in-Rome`
(`git submodule update --init`) plus the fetched scores under
`corpus/scores-local/` (see `corpus/prep/`). The scorer
(`augnet_comparison.py`) imports the shared `rn_normalize` + the
`music21_comparison` classifier from `harness/`, and reads the splits map
for the in-sample/OOS labelling.

## Known failures (3 pieces)

Documented in `corpus/manifest.json` and
[../../../methodology/corpus.md](../../../methodology/corpus.md): Beethoven
Op.18/1 mvt 2 and Schubert *Die Stadt* (music21 MusicXML-writer crash on a
2048th-note duration), and WTC fugues 19 & 22 (scores present only as
remote pointers). These drop out of the comparison for every engine.
