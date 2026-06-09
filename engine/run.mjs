#!/usr/bin/env node
// Run the Contrapunctus analysis engine (the closed WASM artifact) on a
// chord progression and print the per-beat Roman-numeral analysis.
//
//   node engine/run.mjs                 # built-in demo progressions
//   node engine/run.mjs request.json    # analyze a custom wire request
//
// This loads the SAME stripped WASM bundle the website serves to every
// browser (engine/main.{wasm,js} + __loader.js — a Scala.js ESModule).
// The learned chord-ID model is baked in and ON by default, so the
// Roman numerals below are the production engine's, model included.
//
// IMPORTANT — this is NOT how the published benchmark numbers are
// reproduced. This artifact carries one model trained on the full
// corpus; pointing it at the benchmark pieces would give an IN-SAMPLE
// score (it has seen them). The published 49.08 / 58.05 are
// OUT-OF-SAMPLE (5-fold CV). To reproduce those, run `make score` on the
// committed reports. See engine/README.md and methodology/protocol.md.

import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { readFileSync } from "node:fs";

const HERE = dirname(fileURLToPath(import.meta.url));
const { analyzeHarmony, warmup } = await import(resolve(HERE, "main.js"));

// ── Wire-format helpers ──────────────────────────────────────────────
// A note is { dp, accidental }: dp = octave*7 + letterIndex
// (C=0 D=1 E=2 F=3 G=4 A=5 B=6); accidental "" = follow the key
// signature, "n"=natural, "#"/"b"/"##"/"bb"=explicit. See CLAUDE-style
// note encoding in methodology/ and the engine's PitchConversions.
const LI = { C: 0, D: 1, E: 2, F: 3, G: 4, A: 5, B: 6 };
const n = (letter, octave, accidental = "") => ({ dp: octave * 7 + LI[letter], accidental });
const beat = (...notes) => ({ notes });
const request = (opts) => ({
  tonic: opts.tonic, scale: opts.scale ?? "major",
  keySig: opts.keySig ?? { count: 0, type: "sharp" },
  tsTop: opts.tsTop ?? 4, tsBottom: opts.tsBottom ?? 4,
  measures: opts.measures,
});

function analyze(req, title) {
  const out = JSON.parse(analyzeHarmony(JSON.stringify(req)));
  if (out.error) { console.log(`\n${title}\n  ERROR: ${out.error}`); return; }
  console.log(`\n${title}  (key: ${req.tonic.letter}${req.tonic.accidental} ${req.scale})`);
  const rn = out.beats.map((b) => (b.romanNumerals?.[0] ?? "·").padEnd(7));
  const ch = out.beats.map((b) => (b.chordNames?.[0] ?? "·").padEnd(7));
  console.log("  Roman:  " + rn.join(" "));
  console.log("  Chord:  " + ch.join(" "));
  if (out.timings) console.log(`  (${out.timings.analyzeMs} ms)`);
}

// ── Custom request from a file, or the built-in demos ────────────────
const arg = process.argv[2];
if (arg) {
  const req = JSON.parse(readFileSync(arg, "utf8"));
  warmup("cli");
  analyze(req, `Custom request: ${arg}`);
} else {
  warmup("demo");
  console.log("Contrapunctus engine — live demo (stripped production WASM)");

  // I–IV–V–I in C major
  analyze(request({
    tonic: n2("C"), measures: [{ beats: [
      beat(n("C", 4), n("E", 4), n("G", 4)),
      beat(n("F", 4), n("A", 4), n("C", 5)),
      beat(n("G", 3), n("B", 3), n("D", 4)),
      beat(n("C", 4), n("E", 4), n("G", 4)),
    ] }],
  }), "I – IV – V – I");

  // ii7 – V7 – I in C major (sevenths)
  analyze(request({
    tonic: n2("C"), measures: [{ beats: [
      beat(n("D", 4), n("F", 4), n("A", 4), n("C", 5)),
      beat(n("G", 3), n("B", 3), n("D", 4), n("F", 4)),
      beat(n("C", 4), n("E", 4), n("G", 4)),
    ] }],
  }), "ii7 – V7 – I");

  // A secondary dominant: I – V/V – V – I  (D major triad = V/V in C)
  analyze(request({
    tonic: n2("C"), measures: [{ beats: [
      beat(n("C", 4), n("E", 4), n("G", 4)),
      beat(n("D", 4), n("F", 4, "#"), n("A", 4)),
      beat(n("G", 3), n("B", 3), n("D", 4)),
      beat(n("C", 4), n("E", 4), n("G", 4)),
    ] }],
  }), "I – V/V – V – I");

  console.log("\nThese are the production engine's labels (learned model on).");
  console.log("To reproduce the PUBLISHED benchmark numbers, run `make score`");
  console.log("— not this (see engine/README.md: in-sample vs out-of-sample).");
}

// tonic helper kept after use above (hoisted)
function n2(letter, accidental = "") { return { letter, accidental }; }
