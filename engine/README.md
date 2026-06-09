# The Contrapunctus engine (runnable artifact)

The engine is **closed** — its source is not published. But the compiled
WebAssembly bundle **is** here, because it already ships to every browser
that visits [contrapunctus.app](https://contrapunctus.app) (the engine
runs browser-local in a Web Worker), so committing it adds no exposure.
It is provided under an **evaluation-only** license
([../LICENSE-ENGINE.md](../LICENSE-ENGINE.md)).

```
main.wasm      the engine bytecode (stripped Scala.js → WebAssembly)
main.js        the Scala.js ESModule wrapper (the @JSExportTopLevel API)
__loader.js    instantiates the WASM (browser + Node compatible)
run.mjs        a tiny CLI that analyzes a chord progression
```

## What it is

A hybrid Roman-numeral analysis engine: rule-based key detection +
rule-based chord-candidate generation, with a small **learned model**
(logistic regression over tonic-rotated windowed pitch-class features)
that picks the final Roman numeral. The trained weights are baked into
the bytecode and the model is **on by default** — the Roman numerals this
artifact emits are the production engine's, model included.

## Run it

```bash
node engine/run.mjs                 # built-in demo progressions
node engine/run.mjs request.json    # analyze a custom wire request
```

Example output:

```
I – IV – V – I        Roman:  I    IV   V    I
ii7 – V7 – I          Roman:  ii⁷  V⁷   I
I – V/V – V – I       Roman:  I    V/V  V    I      ← reads the D-major triad
                                                       as a secondary dominant
```

The engine's input is a **wire format** (JSON: per-beat notes as
`{dp, accidental}`, a tonic, scale, key signature, time signature — see
the header of `run.mjs`), not raw MusicXML. MusicXML parsing lives in the
app, not in this artifact. Only `@JSExportTopLevel` entrypoints survive
the WASM backend: `analyzeHarmony`, `identifyChord`, `warmup`,
`checkFirstSpecies`/`Second`/`Third`.

## ⚠ This does NOT reproduce the published benchmark numbers

Read this before pointing it at the corpus. This artifact carries **one
model trained on the full corpus**. The published genre-balanced **49.08**
and all-pieces **58.05** are **out-of-sample** — 5-fold cross-validation,
each piece scored by a model that never trained on it. Run *this* artifact
on the benchmark pieces and you get an **in-sample** score (it has seen
them), which will be **higher** and is **not** the published number.

- To **reproduce the published numbers**: `make score` over the committed
  `results/` reports (no engine needed). That is the canonical path.
- To **run the live engine on your own scores**: this artifact. It's the
  same one users interact with on the site.

This is the same in-sample-vs-out-of-sample distinction the methodology
applies to the other engines ([../methodology/protocol.md](../methodology/protocol.md)),
applied honestly to our own shipped model.

## Provenance + verification

- **Engine build:** Scala.js `fullLinkJS` (full optimization, source maps
  off), the same production build the site deploys. Built from engine code
  at git `328bcf8b`; the analysis + model code is **unchanged** from the
  report-generation SHA `6ac09c91` (the intervening commits touched only
  Python tooling and docs, not `core/` or `engine-wasm/`). Recorded for the
  maintainer's traceability; the source commit is in a private repo and is
  intentionally not linked to a public URL.
- **Stripped:** verified — the `.wasm` has **no `name`/debug custom
  section** and **zero** `io.github.tomczik76` / `.scala` / sourcemap
  strings. The only surviving string constants are Scala.js framework
  boilerplate (`__scalaJSHelpers*`) and music-theory labels (`V7`,
  `Cad64`, …) — nothing engine-source-revealing.
- **Size:** ~1.75 MB raw (the older site build was 1.56 MB; the delta is
  the baked model weights). Brotli-compresses to ~250 KB.
- **Runs:** loads + executes in Node ≥ 18 and in browsers (Web Worker).

### Re-verify it yourself

```bash
# no name/debug section, no engine symbols:
python3 - engine/main.wasm <<'PY'
import sys
b=open(sys.argv[1],'rb').read(); assert b[:4]==b'\x00asm'
def leb(b,i):
    r=s=0
    while True:
        x=b[i];i+=1;r|=(x&0x7f)<<s
        if not x&0x80: break
        s+=7
    return r,i
i=8;cs=[]
while i<len(b):
    sid=b[i];i+=1;sz,i=leb(b,i)
    if sid==0:
        nl,j=leb(b,i);cs.append(b[j:j+nl].decode('utf-8','replace'))
    i+=sz
print("custom sections:", cs or "NONE (stripped)")
PY
strings engine/main.wasm | grep -c 'io.github.tomczik76'   # → 0
```
