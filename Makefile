# Contrapunctus harmonic-analysis benchmark
#
#   make score   reproduce the headline tables from committed data (~1 min, Python only)
#   make check   score + assert every README number matches scores.json
#   make manifest regenerate corpus/manifest.json from the engine app's page data
#   make bench    full rival re-run (heavy: needs submodule + model envs + engine)
#   make test     run the rn_normalize parity test

PYTHON ?= python3
NODE ?= node
# Default to the newest date-stamped release; override with RESULTS=results/<date>.
RESULTS ?= $(shell ls -d results/*/ 2>/dev/null | sort | tail -1)

.PHONY: score check manifest bench test engine-demo help

help:
	@sed -n 's/^# \{0,1\}//p; /^[a-z].*:/q' Makefile | sed '1,1d'
	@echo "targets: score | check | manifest | bench | test | engine-demo"

## Reproduce the published tables from the committed reports (no engine needed).
score:
	$(PYTHON) harness/score.py $(RESULTS)

## Reproduce AND verify the README numbers against the computed scores.
check:
	$(PYTHON) harness/score.py $(RESULTS) --check

## Rebuild the per-piece provenance manifest from the engine app's benchmarks.json.
## Needs CONTRAPUNCTUS_APP_ROOT to point at the contrapunctus app checkout
## (default ../contrapunctus).
manifest:
	$(PYTHON) corpus/prep/build_manifest.py

## Parity-test the shared Roman-numeral normalizer (40 smoke + committed fixture).
test:
	$(PYTHON) harness/test_rn_normalize_parity.py

## Run the closed engine (stripped WASM) on demo progressions. Needs Node >= 18.
## NOT a benchmark reproduction — see engine/README.md (in-sample vs out-of-sample).
engine-demo:
	$(NODE) engine/run.mjs

## Full regeneration: run every rival model + re-score. This is the heavy path
## and requires (a) the When-in-Rome submodule checked out, (b) the rival model
## environments installed (see harness/engines/*/README.md), and (c) the closed
## Contrapunctus engine. Most users only need `make score`.
bench:
	@echo "make bench regenerates the *.report.json files and is NOT runnable"
	@echo "from committed data alone — it needs the rival model environments and"
	@echo "the closed engine. See CONTRIBUTING.md > 'Regenerating the reports'."
	@echo "To reproduce the published TABLES (the usual goal), run: make score"
	@exit 2
