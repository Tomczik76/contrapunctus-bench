# Engine evaluation-only license

This license covers the **Contrapunctus analysis engine** — the compiled
engine artifact distributed under [`engine/`](engine/)
(`main.wasm` + its `main.js` / `__loader.js` glue). It does **not** cover
the rest of this repository, which is Apache-2.0 ([LICENSE](LICENSE)), nor
the small `engine/run.mjs` runner (Apache-2.0, like the other harness
code).

The engine source is not published. The engine is provided here, if at
all, solely so that these benchmark results can be independently
reproduced and so the engine can be evaluated for research.

## You may

- Run the artifact to **reproduce the benchmark results** in this
  repository.
- Run the artifact for **research and evaluation** — measuring its
  accuracy, comparing it against other engines, studying its behavior.
- Quote and discuss its outputs and measured performance.

## You may not, without separate written permission

- Use the artifact in **production** or in any product or service.
- **Redistribute** the artifact, in whole or in part, outside this
  repository, or host it elsewhere.
- Use the artifact, or any output derived from it, to **train, fine-tune,
  or distill** another model.
- Reverse-engineer, decompile, or attempt to reconstruct the engine
  source from the artifact.

## No warranty

The artifact is provided "AS IS", without warranty of any kind. The
copyright holder is not liable for any claim or damages arising from its
use.

## Contact

For production use, redistribution, or any other permission, contact the
maintainer (see the repository owner on GitHub /
[contrapunctus.app](https://contrapunctus.app)).

Copyright © 2026 Contrapunctus. All rights reserved except as granted above.
