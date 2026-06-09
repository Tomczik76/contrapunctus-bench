#!/usr/bin/env bash
# Run AugmentedNet inference on all corpus pieces.
# Copies each score to /tmp/augnet-runs/<piece>/ first to avoid polluting
# the When-in-Rome submodule.

set -euo pipefail

# __file__-relative paths so the script works from any worktree
# (the previous hardcoded absolute paths fell back to the main
# worktree, missing scores fetched only in feature branches).
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$( cd "$SCRIPT_DIR/../../.." && pwd )"  # standalone bench layout: engines/<x>/ -> root is 3 up

# Venv + model repo live in a PERSISTENT path — NOT /tmp, which the macOS
# reaper purges every ~3 days, silently destroying the toolchain. Override
# with $CONTRAPUNCTUS_ENGINE_HOME. (Run caches stay in /tmp — cheap to redo.)
ENGINE_HOME="${CONTRAPUNCTUS_ENGINE_HOME:-$HOME/.cache/contrapunctus/engines}"

source "$ENGINE_HOME/augnet/bin/activate"
cd "$ENGINE_HOME/AugmentedNet"

CORPUS_ROOT="$REPO_ROOT/corpus/When-in-Rome/Corpus"
SCORES_LOCAL="$REPO_ROOT/corpus/scores-local"
OUT_DIR="/tmp/augnet-runs"
mkdir -p "$OUT_DIR"

# ── KNOWN STRUCTURAL FAILURES (captured 2026-05-26) ──
#
# Some Phase 2 pieces fail AugmentedNet inference for repeatable
# structural reasons (not transient — re-running won't help):
#
#   * Beethoven Op.18 quartets (all 24 movements):
#     music21.harmony.HarmonyException: not a valid pitch specification: F.I
#     The Op.18 score.mxl files contain <harmony><function>X.Y</function></harmony>
#     Riemannian function annotations that music21's chord-symbol
#     parser tries to interpret as romanNumeral pitches and fails on.
#     music21_comparison.py works around this by stripping <harmony>...
#     </harmony> blocks before parsing — porting that workaround into
#     this script would unlock all 24 movements. (TODO for the next
#     instrumented run.)
#
#   * WTC I fugues 19 + 22:
#     Score files not in the When-in-Rome submodule — only `remote.json`
#     pointers to kern.humdrum.org. Fetching + converting (.krn → .mxl
#     via music21) would unlock these. (TODO.)
#
#   * Schubert Die Stadt (Schwanengesang #11):
#     music21.musicxml.xmlObjects.MusicXMLExportException: Cannot convert
#     "2048th" duration to MusicXML (too short).
#     Inference succeeds but the post-inference export crashes on an
#     edge-case tuplet duration. Could probably be fixed by post-
#     processing the score's tuplet rationals before export.
#
# These failures land in the aggregated benchmark as N/A for AugNet's
# row in the corresponding piece. The page's "known failures" footnote
# surfaces them so the reader sees the gap explicitly.

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
  # Tier 1e — TAVERN theme-and-variation sets (Mozart + Beethoven)
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

# All 371 Bach chorales. Chorale 150 is missing in
# craigsapp/bach-370-chorales; the score-lookup loop below logs
# "no score found" and skips it.
for n in $(seq 1 371); do
  num=$(printf "%03d" $n)
  PIECES+=("Chorale${num}|Early_Choral/Bach,_Johann_Sebastian/Chorales/${num}")
done

# 48 Monteverdi madrigals (Books 3 + 4 = 20 each, Book 5 = 8).
for p in $(seq 1 20); do
  num=$(printf "%02d" $p)
  PIECES+=("Monteverdi3_${num}|Madrigals/Monteverdi,_Claudio/Book_3/${num}")
  PIECES+=("Monteverdi4_${num}|Madrigals/Monteverdi,_Claudio/Book_4/${num}")
done
for p in $(seq 1 8); do
  num=$(printf "%02d" $p)
  PIECES+=("Monteverdi5_${num}|Madrigals/Monteverdi,_Claudio/Book_5/${num}")
done

# ── Parallel execution ────────────────────────────────────────────────
# Each piece is fully independent (own work_dir + output files), so the
# roster runs across the performance cores instead of strictly serially.
# The model forward pass + music21 parse are CPU-bound and single-threaded
# per piece, and peak RSS is only ~0.5 GB/process, so the limit on a 16 GB
# machine is the core count, not RAM. TF intra/inter-op threads are pinned
# to 1 below so N worker processes map cleanly onto N cores rather than
# each spawning its own thread pool and oversubscribing. Override the
# worker count with $AUGNET_JOBS.
JOBS="${AUGNET_JOBS:-$(sysctl -n hw.perflevel0.physicalcpu 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)}"
export TF_NUM_INTRAOP_THREADS=1 TF_NUM_INTEROP_THREADS=1 OMP_NUM_THREADS=1

# Process one piece end to end: stage score → strip harmony → infer →
# record per-piece perf. Returns 0 on skips so a missing score never
# aborts the pool. Run once per worker via `xargs`, so module-level
# `label`/`rel_path`/etc. are private to each worker process.
process_piece() {
  local entry="$1"
  local label="${entry%%|*}"
  local rel_path="${entry#*|}"
  cd "$ENGINE_HOME/AugmentedNet"   # `-m AugmentedNet.inference` resolves the package from CWD

  # Optional label-substring filter for audits: set
  # `PIECES_FILTER=Chorale00` to restrict to chorales 001-009, or
  # `PIECES_FILTER=Chorale0` for 001-099, etc. Skips pieces whose
  # label doesn't contain the filter. Used by the dual score-source
  # audit (see corpus/prep/README.md).
  if [[ -n "${PIECES_FILTER:-}" ]]; then
    case "$label" in
      *"$PIECES_FILTER"*) ;;  # match — process
      *) return 0 ;;          # no match — skip
    esac
  fi

  # Find score — mirror the engine's score-loader priority order so the
  # baseline comparison is apples-to-apples with our engine's input. The
  # `score_kern.mxl` override (Riemenschneider-derived, present for
  # all 20 Bach chorales) wins over the MarkGotham `score.mxl`
  # because the analyst rntxt was annotated against the Riemenschneider
  # edition. Without this, AugmentedNet runs on a different score
  # than our engine, and the apples-to-apples diff is meaningless on
  # chorales.
  # Dual-source audit support: set `SKIP_KERN=true` to force loading
  # MarkGotham `score.mxl` instead of the Kern override. Used by the
  # score-source-sensitivity audit (see corpus/prep/README.md for the
  # Kern-vs-MuseScore chorale story).
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

  # Find analysis.txt — same scores-local fallback as score (Monteverdi
  # madrigals have BOTH score AND analysis under scores-local).
  if [[ -f "$CORPUS_ROOT/$rel_path/analysis.txt" ]]; then
    analysis="$CORPUS_ROOT/$rel_path/analysis.txt"
  elif [[ -f "$SCORES_LOCAL/$rel_path/analysis.txt" ]]; then
    analysis="$SCORES_LOCAL/$rel_path/analysis.txt"
  else
    echo "[$label] no analysis.txt found, skipping"
    return 0
  fi

  # Copy to working dir
  work_dir="$OUT_DIR/$label"
  mkdir -p "$work_dir"
  cp "$score" "$work_dir/score.mxl"
  cp "$analysis" "$work_dir/analysis.txt"

  # Strip <harmony>...</harmony> Riemannian function annotations
  # before AugNet inference — music21's chord-symbol parser raises
  # HarmonyException on things like "<harmony><function>F.I</function>
  # </harmony>" (used heavily in Beethoven Op.18 quartet scores).
  # Idempotent: if the score has no <harmony> blocks, this is a copy.
  # Without this, all 24 Op.18 movements (and any other score with
  # function-theory annotations) silently fail AugNet inference.
  python3 "$REPO_ROOT/corpus/prep/strip_harmony.py" "$work_dir/score.mxl" "$work_dir/score_stripped.mxl" 2>&1 | sed 's/^/  /' || true

  echo "[$label] running AugmentedNet inference..."
  # Capture wall-clock + peak RSS per piece via /usr/bin/time -l.
  # Format on macOS: "<seconds> real ... <bytes> maximum resident set size".
  # On Linux: switch to `/usr/bin/time -v` and grep "Maximum resident".
  # Each piece's row gets appended to a JSON-lines perf log; the
  # upstream page aggregator reads it for the live page's
  # "Performance characteristics" section.
  # Run inference on the stripped score (no <harmony> blocks). Falls
  # back to the original if strip failed for some reason (idempotent
  # script always emits the output file, so the fallback path is rare).
  if [[ -f "$work_dir/score_stripped.mxl" ]]; then
    infer_input="$work_dir/score_stripped.mxl"
  else
    infer_input="$work_dir/score.mxl"
  fi
  time_log=$(mktemp)
  /usr/bin/time -l python3 -m AugmentedNet.inference --modelPath AugmentedNet.hdf5 "$infer_input" \
    >/dev/null 2>"$time_log" || true
  # macOS BSD `time -l` writes timing + RSS after stderr from the wrapped
  # command, as `<N> real <N> user <N> sys` on one line — so match the
  # "real" FIELD, not an end-of-line anchor (the old `/real$/` never fired).
  wall_s=$(awk '$2=="real"{print $1}' "$time_log" | tail -1)
  peak_rss_bytes=$(awk '/maximum resident set size/ {print $1}' "$time_log" | tail -1)
  rm -f "$time_log"
  if [[ -n "$wall_s" && -n "$peak_rss_bytes" ]]; then
    peak_rss_mb=$(awk -v b="$peak_rss_bytes" 'BEGIN {printf "%.1f", b/1048576}')
    # Write to the piece's own file; a shared append from parallel workers
    # would interleave. Concatenated into perf.jsonl after the pool drains.
    echo "{\"label\": \"$label\", \"wall_s\": $wall_s, \"peak_rss_mb\": $peak_rss_mb}" > "$work_dir/perf.json"
  fi

  # AugNet writes output as <input-stem>_annotated.<ext>. When the
  # input was the stripped variant, rename outputs to the canonical
  # score_annotated.* names so downstream tools (augnet_comparison.py)
  # don't need to know about the stripping step.
  if [[ "$infer_input" == *_stripped.mxl ]]; then
    for ext in rntxt csv musicxml; do
      if [[ -f "$work_dir/score_stripped_annotated.$ext" ]]; then
        mv "$work_dir/score_stripped_annotated.$ext" "$work_dir/score_annotated.$ext"
      fi
    done
  fi

  if [[ -f "$work_dir/score_annotated.rntxt" ]]; then
    echo "[$label] ✓ produced $(wc -l < $work_dir/score_annotated.rntxt) lines of rntxt output (wall=${wall_s}s, rss=${peak_rss_mb:-?}MB)"
  else
    echo "[$label] ✗ no output produced"
  fi
}
export -f process_piece
export SCRIPT_DIR REPO_ROOT ENGINE_HOME CORPUS_ROOT SCORES_LOCAL OUT_DIR

# Fan out across $JOBS workers. `xargs -I{}` passes one entry per line as a
# single argument; `|| true` keeps a worker failure (already guarded inside
# process_piece) from aborting the whole run under `set -e`.
echo "Running ${#PIECES[@]} pieces across $JOBS parallel workers (override with \$AUGNET_JOBS)..."
printf '%s\n' "${PIECES[@]}" | xargs -P "$JOBS" -I{} bash -c 'process_piece "$@"' _ {} || true

# Gather the per-piece perf lines (written to each work_dir to avoid
# interleaved appends) into the JSON-lines log the upstream aggregator reads.
: > "$OUT_DIR/perf.jsonl"
for pf in "$OUT_DIR"/*/perf.json; do
  [[ -f "$pf" ]] && cat "$pf" >> "$OUT_DIR/perf.jsonl"
done

echo "---"
echo "Outputs in $OUT_DIR"
ls -la $OUT_DIR/*/score_annotated.rntxt 2>/dev/null | head -20
if [[ -f "$OUT_DIR/perf.jsonl" ]]; then
  echo "Perf log: $OUT_DIR/perf.jsonl ($(wc -l < $OUT_DIR/perf.jsonl) pieces)"
fi
