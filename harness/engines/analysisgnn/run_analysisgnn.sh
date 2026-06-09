#!/usr/bin/env bash
# Run AnalysisGNN (Karystinaios et al., spiritual successor to ChordGNN)
# inference on all corpus pieces. Same 37-piece roster as run_augnet.sh.
#
# Setup (one-time). Venv + repos live in a PERSISTENT path (NOT /tmp, which
# the macOS reaper purges every ~3 days). Override with $CONTRAPUNCTUS_ENGINE_HOME:
#   ENGINE_HOME="${CONTRAPUNCTUS_ENGINE_HOME:-$HOME/.cache/contrapunctus/engines}"; mkdir -p "$ENGINE_HOME"
#   python3.11 -m venv "$ENGINE_HOME/chordgnnvenv"  (named for historical reasons)
#   source "$ENGINE_HOME/chordgnnvenv/bin/activate"
#   pip install torch pytorch-lightning partitura music21 pandas tqdm wandb GitPython rotograd numpy
#   pip install torch-scatter torch-sparse torch-cluster torch-geometric \
#       -f https://data.pyg.org/whl/torch-2.11.0+cpu.html
#   cd "$ENGINE_HOME" && git clone https://github.com/manoskary/graphmuse.git && pip install -e graphmuse
#   cd "$ENGINE_HOME" && git clone https://github.com/manoskary/analysisgnn.git && pip install -e analysisgnn
#   wandb login            # one-time, paste API key from https://wandb.ai/authorize
#
# Outputs land in /tmp/analysisgnn-runs/<label>/<label>_analysis.csv.
# The CSV has one row per 16th-note onset with columns: cadence,
# localkey, tonkey, quality, root, bass, inversion, degree1, degree2,
# romanNumeral, onset, s_measure.

set -euo pipefail

# __file__-relative paths so the script works from any worktree.
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$( cd "$SCRIPT_DIR/../../.." && pwd )"  # standalone bench layout: engines/<x>/ -> root is 3 up

# Persistent venv path (NOT /tmp — reaped every ~3 days). Override via
# $CONTRAPUNCTUS_ENGINE_HOME; must match run_augnet.sh.
ENGINE_HOME="${CONTRAPUNCTUS_ENGINE_HOME:-$HOME/.cache/contrapunctus/engines}"
source "$ENGINE_HOME/chordgnnvenv/bin/activate"

CORPUS_ROOT="$REPO_ROOT/corpus/When-in-Rome/Corpus"
SCORES_LOCAL="$REPO_ROOT/corpus/scores-local"
OUT_DIR="/tmp/analysisgnn-runs"
mkdir -p "$OUT_DIR"

PIECES=(
  # Phase 2 corpus expansion (2026-05-26): baseline-9 dissolved.
  # WTC P01-P03 fold into bach-wtc; K545/K281 fold into mozart-sonatas;
  # Op.18 No.1 mvt 2 folds into beethoven-op18; Schubert Op.59/3 folds
  # into schubert-lieder. Chopin Op.28/20 + Brahms Requiem dropped
  # (no expansion path — only orphans of their would-be genres).

  # Tier 1b — 4 Beethoven Sonatas from BPS-FH
  "BeethovenOp10No1|Piano_Sonatas/Beethoven,_Ludwig_van/Op010_No1/1"
  "BeethovenPathetique|Piano_Sonatas/Beethoven,_Ludwig_van/Op013(Pathetique)/1"
  "BeethovenTempest|Piano_Sonatas/Beethoven,_Ludwig_van/Op031_No2/1"
  "BeethovenOp78|Piano_Sonatas/Beethoven,_Ludwig_van/Op078/1"
  # Tier 1c — 4 Haydn Op. 20 movements
  "HaydnOp20No3mvt4|Quartets/Haydn,_Franz_Joseph/Op20_No3/4"
  "HaydnOp20No4mvt1|Quartets/Haydn,_Franz_Joseph/Op20_No4/1"
  "HaydnOp20No5mvt1|Quartets/Haydn,_Franz_Joseph/Op20_No5/1"
  "HaydnOp20No6mvt4|Quartets/Haydn,_Franz_Joseph/Op20_No6/4"
  # Tier 1d — 7 Mozart Piano Sonatas (DCML contrasting movements +
  # K545/1, K281/1 folded from baseline-9)
  "MozartK545mvt1|Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K545/1"
  "MozartK281mvt1|Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K281/1"
  "MozartK281mvt2|Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K281/2"
  "MozartK283mvt2|Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K283/2"
  "MozartK310mvt1|Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K310/1"
  "MozartK330mvt2|Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K330/2"
  "MozartK284mvt3|Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K284/3"
  "MozartK279mvt2|Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K279/2"
  "MozartK279mvt3|Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K279/3"
  "MozartK280mvt3|Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K280/3"
  "MozartK281mvt3|Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K281/3"
  "MozartK282mvt1|Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K282/1"
  "MozartK282mvt2|Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K282/2"
  "MozartK284mvt2|Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K284/2"
  "MozartK309mvt1|Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K309/1"
  "MozartK309mvt2|Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K309/2"
  "MozartK309mvt3|Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K309/3"
  "MozartK310mvt2|Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K310/2"
  "MozartK311mvt1|Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K311/1"
  "MozartK332mvt1|Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K332/1"
  "MozartK457mvt2|Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K457/2"
  "MozartK533mvt2|Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K533/2"
  "MozartK545mvt3|Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K545/3"
  "MozartK570mvt1|Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K570/1"
  "MozartK576mvt1|Piano_Sonatas/Mozart,_Wolfgang_Amadeus/K576/1"
  # Tier 1e — 11 TAVERN theme-and-variation sets (Mozart + Beethoven)
  "TavernMozartK179|Variations_and_Grounds/Mozart,_Wolfgang_Amadeus/_/K179"
  "TavernMozartK265|Variations_and_Grounds/Mozart,_Wolfgang_Amadeus/_/K265"
  "TavernMozartK354|Variations_and_Grounds/Mozart,_Wolfgang_Amadeus/_/K354"
  "TavernMozartK398|Variations_and_Grounds/Mozart,_Wolfgang_Amadeus/_/K398"
  "TavernMozartK501|Variations_and_Grounds/Mozart,_Wolfgang_Amadeus/_/K501"
  "TavernMozartK573|Variations_and_Grounds/Mozart,_Wolfgang_Amadeus/_/K573"
  "TavernBeethovenWoO64|Variations_and_Grounds/Beethoven,_Ludwig_van/_/WoO_64"
  "TavernBeethovenWoO65|Variations_and_Grounds/Beethoven,_Ludwig_van/_/WoO_65"
  "TavernBeethovenWoO70|Variations_and_Grounds/Beethoven,_Ludwig_van/_/WoO_70"
  "TavernBeethovenWoO75|Variations_and_Grounds/Beethoven,_Ludwig_van/_/WoO_75"
  "TavernBeethovenWoO77|Variations_and_Grounds/Beethoven,_Ludwig_van/_/WoO_77"
)

# Tier 1f — Bach WTC I: all 24 preludes + 2 separately-analyzed fugues.
for n in $(seq 1 24); do
  num=$(printf "%02d" $n)
  PIECES+=("WTC_I_P${num}|Keyboard_Other/Bach,_Johann_Sebastian/The_Well-Tempered_Clavier_I/${num}")
done
PIECES+=("WTC_I_F19|Keyboard_Other/Bach,_Johann_Sebastian/The_Well-Tempered_Clavier_I/19_fugue")
PIECES+=("WTC_I_F22|Keyboard_Other/Bach,_Johann_Sebastian/The_Well-Tempered_Clavier_I/22_fugue")

# Tier 1g — Beethoven Op.18 string quartets (6 × 4 mvts = 24 movements).
for q in $(seq 1 6); do
  for mvt in $(seq 1 4); do
    PIECES+=("BeethovenOp18No${q}mvt${mvt}|Quartets/Beethoven,_Ludwig_van/Op018_No${q}/${mvt}")
  done
done

# Tier 1h — Schubert lieder (46 songs).
PIECES+=("SchubertDieSterne|OpenScore-LiederCorpus/Schubert,_Franz/4_Lieder,_Op.96/1_Die_Sterne,_D.939")
PIECES+=("SchubertDasWandern|OpenScore-LiederCorpus/Schubert,_Franz/Die_schöne_Müllerin,_D.795/01_Das_Wandern")
PIECES+=("SchubertWohin|OpenScore-LiederCorpus/Schubert,_Franz/Die_schöne_Müllerin,_D.795/02_Wohin")
PIECES+=("SchubertPause|OpenScore-LiederCorpus/Schubert,_Franz/Die_schöne_Müllerin,_D.795/12_Pause")
PIECES+=("SchubertTrockneBlumen|OpenScore-LiederCorpus/Schubert,_Franz/Die_schöne_Müllerin,_D.795/18_Trockne_Blumen")
PIECES+=("SchubertAveMaria|OpenScore-LiederCorpus/Schubert,_Franz/Op.52/6_Ellens_Gesang_III,_D.839_(Ave_Maria)")
PIECES+=("SchubertDuBistDieRuh|OpenScore-LiederCorpus/Schubert,_Franz/Op.59/3_Du_bist_die_Ruh")
PIECES+=("SchubertDasRosenband|OpenScore-LiederCorpus/Schubert,_Franz/_/Das_Rosenband,_D.280")
# Schwanengesang (14 songs)
PIECES+=("SchubertLiebesbotschaft|OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/01_Liebesbotschaft")
PIECES+=("SchubertKriegersAhnung|OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/02_Kriegers_Ahnung")
PIECES+=("SchubertFruhlingssehnsucht|OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/03_Frühlingssehnsucht")
PIECES+=("SchubertStandchen|OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/04_Ständchen")
PIECES+=("SchubertAufenthalt|OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/05_Aufenthalt")
PIECES+=("SchubertInDerFerne|OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/06_In_der_Ferne")
PIECES+=("SchubertAbschied|OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/07_Abschied")
PIECES+=("SchubertDerAtlas|OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/08_Der_Atlas")
PIECES+=("SchubertIhrBild|OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/09_Ihr_Bild")
PIECES+=("SchubertDasFischermadchen|OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/10_Das_Fischermädchen")
PIECES+=("SchubertDieStadt|OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/11_Die_Stadt")
PIECES+=("SchubertAmMeer|OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/12_Am_Meer")
PIECES+=("SchubertDerDoppelganger|OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/13_Der_Doppelgänger")
PIECES+=("SchubertDieTaubenpost|OpenScore-LiederCorpus/Schubert,_Franz/Schwanengesang,_D.957/14_Die_Taubenpost")
# Winterreise (24 songs)
PIECES+=("SchubertW01GuteNacht|OpenScore-LiederCorpus/Schubert,_Franz/Winterreise,_D.911/01_Gute_Nacht")
PIECES+=("SchubertW02DieWetterfahne|OpenScore-LiederCorpus/Schubert,_Franz/Winterreise,_D.911/02_Die_Wetterfahne")
PIECES+=("SchubertW03GefrorneThranen|OpenScore-LiederCorpus/Schubert,_Franz/Winterreise,_D.911/03_Gefror’ne_Thränen")
PIECES+=("SchubertW04Erstarrung|OpenScore-LiederCorpus/Schubert,_Franz/Winterreise,_D.911/04_Erstarrung")
PIECES+=("SchubertW05DerLindenbaum|OpenScore-LiederCorpus/Schubert,_Franz/Winterreise,_D.911/05_Der_Lindenbaum")
PIECES+=("SchubertW06Wasserfluth|OpenScore-LiederCorpus/Schubert,_Franz/Winterreise,_D.911/06_Wasserfluth")
PIECES+=("SchubertW07AufDemFlusse|OpenScore-LiederCorpus/Schubert,_Franz/Winterreise,_D.911/07_Auf_dem_Flusse")
PIECES+=("SchubertW08Ruckblick|OpenScore-LiederCorpus/Schubert,_Franz/Winterreise,_D.911/08_Rückblick")
PIECES+=("SchubertW09Irrlicht|OpenScore-LiederCorpus/Schubert,_Franz/Winterreise,_D.911/09_Irrlicht")
PIECES+=("SchubertW10Rast|OpenScore-LiederCorpus/Schubert,_Franz/Winterreise,_D.911/10_Rast_(Spätere_Fassung)")
PIECES+=("SchubertW11Fruhlingstraum|OpenScore-LiederCorpus/Schubert,_Franz/Winterreise,_D.911/11_Frühlingstraum")
PIECES+=("SchubertW12Einsamkeit|OpenScore-LiederCorpus/Schubert,_Franz/Winterreise,_D.911/12_Einsamkeit_(Urspruengliche_Fassung)")
PIECES+=("SchubertW13DiePost|OpenScore-LiederCorpus/Schubert,_Franz/Winterreise,_D.911/13_Die_Post")
PIECES+=("SchubertW14DerGreiseKopf|OpenScore-LiederCorpus/Schubert,_Franz/Winterreise,_D.911/14_Der_greise_Kopf")
PIECES+=("SchubertW15DieKraehe|OpenScore-LiederCorpus/Schubert,_Franz/Winterreise,_D.911/15_Die_Kraehe")
PIECES+=("SchubertW16LetzteHoffnung|OpenScore-LiederCorpus/Schubert,_Franz/Winterreise,_D.911/16_Letzte_Hoffnung")
PIECES+=("SchubertW17ImDorfe|OpenScore-LiederCorpus/Schubert,_Franz/Winterreise,_D.911/17_Im_Dorfe")
PIECES+=("SchubertW18DerStuermischeMorgen|OpenScore-LiederCorpus/Schubert,_Franz/Winterreise,_D.911/18_Der_stuermische_Morgen")
PIECES+=("SchubertW19Tauschung|OpenScore-LiederCorpus/Schubert,_Franz/Winterreise,_D.911/19_Täuschung")
PIECES+=("SchubertW20DerWegweiser|OpenScore-LiederCorpus/Schubert,_Franz/Winterreise,_D.911/20_Der_Wegweiser")
PIECES+=("SchubertW21DasWirthshaus|OpenScore-LiederCorpus/Schubert,_Franz/Winterreise,_D.911/21_Das_Wirthshaus")
PIECES+=("SchubertW22Muth|OpenScore-LiederCorpus/Schubert,_Franz/Winterreise,_D.911/22_Muth")
PIECES+=("SchubertW23DieNebensonnen|OpenScore-LiederCorpus/Schubert,_Franz/Winterreise,_D.911/23_Die_Nebensonnen")
PIECES+=("SchubertW24DerLeiermann|OpenScore-LiederCorpus/Schubert,_Franz/Winterreise,_D.911/24_Der_Leiermann_(Spätere_Fassung)")

# Tier 1i — Brahms lieder (9 songs).
PIECES+=("BrahmsLiebeUndFruhling2|OpenScore-LiederCorpus/Brahms,_Johannes/6_Songs,_Op.3/3_Liebe_und_Frühling_II")
PIECES+=("BrahmsLiebesklage|OpenScore-LiederCorpus/Brahms,_Johannes/7_Lieder,_Op.48/3_Liebesklage_des_Mädchens")
PIECES+=("BrahmsMarien1|OpenScore-LiederCorpus/Brahms,_Johannes/Marienlieder,_Op.22/1_Der_englische_Gruss")
PIECES+=("BrahmsMarien2|OpenScore-LiederCorpus/Brahms,_Johannes/Marienlieder,_Op.22/2_Marias_Kirchgang")
PIECES+=("BrahmsMarien3|OpenScore-LiederCorpus/Brahms,_Johannes/Marienlieder,_Op.22/3_Marias_Wallfahrt")
PIECES+=("BrahmsMarien4|OpenScore-LiederCorpus/Brahms,_Johannes/Marienlieder,_Op.22/4_Der_Jäger")
PIECES+=("BrahmsMarien5|OpenScore-LiederCorpus/Brahms,_Johannes/Marienlieder,_Op.22/5_Ruf_zur_Maria")
PIECES+=("BrahmsMarien6|OpenScore-LiederCorpus/Brahms,_Johannes/Marienlieder,_Op.22/6_Magdalena")
PIECES+=("BrahmsMarien7|OpenScore-LiederCorpus/Brahms,_Johannes/Marienlieder,_Op.22/7_Marias_Lob")

# All 371 Bach chorales. Chorale 150 has no Kern source, so the
# score-lookup loop logs and skips it.
for n in $(seq 1 371); do
  num=$(printf "%03d" $n)
  PIECES+=("Chorale${num}|Early_Choral/Bach,_Johann_Sebastian/Chorales/${num}")
done

# 48 Monteverdi madrigals.
for p in $(seq 1 20); do
  num=$(printf "%02d" $p)
  PIECES+=("Monteverdi3_${num}|Madrigals/Monteverdi,_Claudio/Book_3/${num}")
  PIECES+=("Monteverdi4_${num}|Madrigals/Monteverdi,_Claudio/Book_4/${num}")
done
for p in $(seq 1 8); do
  num=$(printf "%02d" $p)
  PIECES+=("Monteverdi5_${num}|Madrigals/Monteverdi,_Claudio/Book_5/${num}")
done

# ── Parallel execution (see run_augnet.sh for the rationale) ───────────
# AnalysisGNN is heavier than AugNet (torch + a 121 MB checkpoint), so the
# default worker count is lower — override with $ANALYSISGNN_JOBS. Torch is
# pinned to 1 thread/process so workers map onto cores instead of each
# spawning a thread pool. WANDB defaults to offline so parallel workers
# don't each open an online run; the checkpoint is served from the local
# W&B artifact cache (warmed once, serially, before the fan-out below).
JOBS="${ANALYSISGNN_JOBS:-4}"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export WANDB_MODE="${WANDB_MODE:-offline}"
# Checkpoint: fetched once (online) to a persistent local file, then every
# worker loads it via --checkpoint_path so inference never touches W&B — no
# online run per piece, no concurrent-download race. Override with
# $ANALYSISGNN_CKPT.
CKPT="${ANALYSISGNN_CKPT:-$ENGINE_HOME/analysisgnn-model.ckpt}"
# Stable CWD: a CWD-relative ./artifacts dir is created during the one-time
# download; pin it under OUT_DIR (not the repo worktree).
cd "$OUT_DIR"

# Process one piece end to end. Returns 0 on a missing score so the pool
# isn't aborted. Run once per worker via xargs (module-level vars private
# to each worker process).
process_piece() {
  local entry="$1"
  local label="${entry%%|*}"
  local rel_path="${entry#*|}"

  # Optional label-substring filter for audits — see run_augnet.sh
  # for usage. `PIECES_FILTER=Chorale0` restricts to 3-digit chorales.
  if [[ -n "${PIECES_FILTER:-}" ]]; then
    case "$label" in
      *"$PIECES_FILTER"*) ;;
      *) return 0 ;;
    esac
  fi

  # Mirror the engine's score-loader priority: `score_kern.mxl` (Riemenschneider-
  # derived, all 20 Bach chorales) wins over the MarkGotham
  # `score.mxl` so the baseline comparison is on the same input our
  # engine sees. See corpus/prep/fetch_kern_chorales.py.
  #
  # Dual-source audit support: set `SKIP_KERN=true` to force loading
  # MarkGotham `score.mxl` instead. Used by the score-source-
  # sensitivity audit (see corpus/prep/README.md).
  if [[ "${SKIP_KERN:-false}" != "true" ]] && [[ -f "$SCORES_LOCAL/$rel_path/score_kern.mxl" ]]; then
    score="$SCORES_LOCAL/$rel_path/score_kern.mxl"
  elif [[ -f "$CORPUS_ROOT/$rel_path/score.mxl" ]]; then
    score="$CORPUS_ROOT/$rel_path/score.mxl"
  elif [[ -f "$SCORES_LOCAL/$rel_path/score.mxl" ]]; then
    score="$SCORES_LOCAL/$rel_path/score.mxl"
  elif [[ -f "$SCORES_LOCAL/$rel_path/score_kern.mxl" ]]; then
    score="$SCORES_LOCAL/$rel_path/score_kern.mxl"  # fallback if SKIP_KERN set + no alt
  else
    echo "[$label] no score found, skipping"
    return 0
  fi

  work_dir="$OUT_DIR/$label"
  mkdir -p "$work_dir"
  # Copy with a stable filename so the AnalysisGNN output is at a
  # predictable path: <label>/<label>_analysis.csv
  cp "$score" "$work_dir/$label.mxl"

  echo "[$label] running AnalysisGNN inference..."
  # `--export_roman_numerals` triggers a deepcopy-recursion bug in
  # the musicxml writer (analysisgnn 1.0.0). CSV export is all we
  # need for the head-to-head — it has the romanNumeral column at
  # 16th-note resolution.
  #
  # Capture wall-clock + peak RSS per piece via /usr/bin/time -l.
  # See run_augnet.sh for the perf log format. Aggregated by the
  # upstream page aggregator for the live "Performance" section.
  time_log=$(mktemp)
  /usr/bin/time -l analysisgnn-predict \
    --checkpoint_path "$CKPT" \
    --input_score "$work_dir/$label.mxl" \
    --output_dir "$work_dir" \
    --export_csv \
    >/dev/null 2>"$time_log" || true
  # macOS `time -l` emits `<N> real <N> user <N> sys` on one line — match
  # the "real" FIELD (the old `/real$/` anchor never matched on macOS, so
  # this perf log was previously always empty).
  wall_s=$(awk '$2=="real"{print $1}' "$time_log" | tail -1)
  peak_rss_bytes=$(awk '/maximum resident set size/ {print $1}' "$time_log" | tail -1)
  rm -f "$time_log"
  if [[ -n "$wall_s" && -n "$peak_rss_bytes" ]]; then
    peak_rss_mb=$(awk -v b="$peak_rss_bytes" 'BEGIN {printf "%.1f", b/1048576}')
    # Per-piece file (shared append would interleave under parallelism);
    # concatenated into perf.jsonl after the pool drains.
    echo "{\"label\": \"$label\", \"wall_s\": $wall_s, \"peak_rss_mb\": $peak_rss_mb}" > "$work_dir/perf.json"
  fi

  if [[ -f "$work_dir/${label}_analysis.csv" ]]; then
    echo "[$label] ✓ produced $(wc -l < "$work_dir/${label}_analysis.csv") lines of CSV (wall=${wall_s}s, rss=${peak_rss_mb:-?}MB)"
  else
    echo "[$label] ✗ no CSV output"
  fi
}
export -f process_piece
# CKPT MUST be exported: the xargs worker subshells read $CKPT for
# --checkpoint_path. Without it they pass an empty path, fall back to the
# W&B artifact download, and WANDB_MODE=offline then blocks it — so every
# piece fails ~5s in. (ensure_checkpoint above runs in the parent, where
# CKPT is set, which is why the download itself succeeds.)
export SCRIPT_DIR REPO_ROOT ENGINE_HOME CORPUS_ROOT SCORES_LOCAL OUT_DIR CKPT

# One-time: fetch the checkpoint from W&B (online) into $CKPT so the workers
# can run fully offline against it. A single warm inference on any score
# triggers the artifact download (lands at the CWD-relative
# ./artifacts/models/model.ckpt), which we then cache to $CKPT.
ensure_checkpoint() {
  [[ -f "$CKPT" ]] && { echo "Checkpoint present: $CKPT"; return 0; }
  echo "Downloading AnalysisGNN checkpoint (one-time, online)..."
  local warm_dir="$OUT_DIR/_warm"; mkdir -p "$warm_dir"
  local warm_score
  # `… | head -1` makes find SIGPIPE once head closes; under `pipefail`+`set
  # -e` that 141 would abort the script, so swallow it with `|| true`.
  warm_score=$(find "$SCORES_LOCAL" "$CORPUS_ROOT" -name "score*.mxl" 2>/dev/null | head -1 || true)
  if [[ -z "$warm_score" ]]; then
    echo "ERROR: no score found to warm the checkpoint download" >&2; exit 1
  fi
  cp "$warm_score" "$warm_dir/warm.mxl"
  WANDB_MODE=online analysisgnn-predict \
    --input_score "$warm_dir/warm.mxl" --output_dir "$warm_dir" --export_csv \
    >/dev/null 2>&1 || true
  if [[ -f "$OUT_DIR/artifacts/models/model.ckpt" ]]; then
    cp "$OUT_DIR/artifacts/models/model.ckpt" "$CKPT"
  fi
  [[ -f "$CKPT" ]] || { echo "ERROR: failed to obtain checkpoint at $CKPT (W&B login required? run 'wandb login')" >&2; exit 1; }
  echo "Checkpoint cached: $CKPT"
}
ensure_checkpoint

echo "Running ${#PIECES[@]} pieces across $JOBS parallel workers (override with \$ANALYSISGNN_JOBS)..."
printf '%s\n' "${PIECES[@]}" | xargs -P "$JOBS" -I{} bash -c 'process_piece "$@"' _ {} || true

# Gather per-piece perf lines into the JSON-lines log the upstream aggregator reads.
: > "$OUT_DIR/perf.jsonl"
for pf in "$OUT_DIR"/*/perf.json; do
  [[ -f "$pf" ]] && cat "$pf" >> "$OUT_DIR/perf.jsonl"
done

echo "---"
echo "Outputs in $OUT_DIR"
ls -la "$OUT_DIR"/*/*_analysis.csv 2>/dev/null | head -20
if [[ -f "$OUT_DIR/perf.jsonl" ]]; then
  echo "Perf log: $OUT_DIR/perf.jsonl ($(wc -l < $OUT_DIR/perf.jsonl) pieces)"
fi
