# Changelog

What changed in each release. There is no `CHANGELOG.md` in the repo; this page reconstructs the history from the release commits and the project README.

**Contents**

- [[v0.7.0|Changelog#v070-current]]
- [[v0.6.0|Changelog#v060]]
- [[v0.5.0|Changelog#v050]]
- [[v0.4.0|Changelog#v040]]
- [[v0.3.0|Changelog#v030]]
- [[v0.2.0|Changelog#v020]]
- [[v0.1.0|Changelog#v010]]

## v0.7.0 **[current]**

- **Simple AGK complete** — every classic construct now has a plain-English spelling, so whole programs can be written without ceremony. New forms, all desugared at parse time to the existing AST (semantics and codegen unchanged, all previously valid programs keep their meaning):
  - `class <Name> [extends <Base>]:` — alias for `define class`; fields are `<name> as <Type>`; the constructor is `constructor [with <params>]:`; methods use the plain `to` form (including `async to`). Classic and simple members may be mixed freely in one class body.
  - `constant <NAME> is <literal>` — alias for `define constant`, with the type inferred from the literal.
  - `each <name> in <expr>:` — alias for `for each`.
  - `repeat with <name> from <a> to <b> [step <s>]:` — the inclusive `for` range loop (the plain `repeat <expr> times:` form is unchanged).
  - `async to <name> [with <params>]:` — alias for `define async function`, at top level and in class bodies.
  - Default parameter values in `to` declarations: `to greet with name as String = "World":` (the type may be omitted).
  - `use <name> [with <params>] [and returns <Type>] from "<lib>"` — the simple `extern` FFI declaration.
- **Still no new reserved words** — `class`, `constructor`, `constant`, `async`, and `each` were already reserved; `use` and `with` stay ordinary identifiers, special only in these statement patterns.
- 8 new verified wiki examples in [[Language Reference|Language-Reference]]; 26 new parser/semantic/runtime tests.
- Version bumped to 0.7.0.

## v0.6.0

- **New stdlib modules (inference)** — `tensor` (NumPy-backed n-dimensional array primitives: creation, matmul, elementwise math, softmax, RMSNorm, SiLU, slicing, seeded sampling, `.npz` weight loading) and `infer` (a real transformer inference engine in AGK: Llama-style decoder with RMSNorm, RoPE and SwiGLU, per-head KV-cache, greedy/temperature sampling, character tokenizer). The cached incremental engine is verified bit-close against an independent full-sequence NumPy reference on identical weights (`tests/test_stdlib7.py`). `examples/tinyshakespeare/` trains a tiny Shakespeare model (`train.py`) and talks to it from AGK (`demo.agk`). Both modules lazy-load NumPy and raise a clear `pip install numpy` error when it is missing. 35 bundled modules total.
- **New stdlib modules (LLM)** — `transformers` (HF pipelines, generation, tokenization, model download), `tokenizer` (token counting, truncation, chunking, tiktoken), `torchutils` (tensor ops), `datasets` (HF datasets), `embeddings` (sentence-transformers + semantic search), `finetune` (peft LoRA training, adapter merge). All six load their Python backends lazily via `importlib` and raise a clear `pip install ...` error when a package is missing; nothing is imported at module-import time. 33 bundled modules total.
- **Project scaffolding** — `agk new <name>` generates a runnable project skeleton (`agk.json`, `README.md`, `.gitignore`, `src/` sources, `tests/` with passing starter tests); `--lib` makes a library project with no entry point. `agk test` now also resolves imports from the project root and `src/` when an `agk.json` project root exists.
- **New stdlib modules** — `mathutils`, `randutils`, `timeutils`, `sysutils`, `pathutils`, `urlutils`, `uuidutils`, `ziputils`, `iniutils`, `htmlutils`, `xmlutils`, `statutils`, `iterutils`, `colorutils`, `logutils` (27 bundled modules total).
- **Optimizer fix** — dead-store elimination no longer drops a store at the end of a loop body that feeds a read at the top of the next iteration (the loop back-edge now counts the body's own reads as live).
- **Simple AGK surface** — a beginner-friendly alias layer over the core statements, desugared at parse time so semantics and codegen are unchanged:
  - `name is <expr>` — declares with an inferred type when the name is new (`Integer`/`Float`/`String`/`Boolean`/`List`/`Dict` for literals, dynamic otherwise), plain assignment when it exists — never a redeclare error. A mismatched reassignment is still a type error, exactly as with `set`.
  - `to <name> [with <params>] [and returns <Type>]:` — alias for `define function`, at top level and in class bodies; omitted parameter types are dynamic.
  - `say <expr>` — `print(<expr>)`.
  - `ask <expr> giving <name>` — `input(<expr>)` into `<name>` (declared `String`, or assigned when it exists).
  - `repeat <expr> times:` — counted loop over `range(<expr>)` with a collision-proof hidden variable.
  - `otherwise:` / `otherwise if <cond>:` — aliases for `else` / `elif`, freely mixable with them.
  - `increase <name> [by <expr>]` / `decrease <name> [by <expr>]` — add/subtract, defaulting to 1.
  - English comparisons in expressions: `is` / `is not` (`==` / `!=`) and `is greater|less than [or equal to]` (`>` / `<` / `>=` / `<=`), at the usual precedence levels.
- **Additive by design** — no new reserved words (`to` was already reserved). `say(x)` still calls a user-defined `say`, every alias word still works as a variable name, and all previously valid programs keep their meaning (1204 pre-existing tests pass unchanged).
- **REPL** — `x is <expr>` assigns in the REPL instead of evaluating `x == <expr>`; `repeat` blocks and the other Simple forms work interactively. Also fixed a crash (`AttributeError`) when the REPL reported a malformed expression.
- 1259 tests, all green.

## v0.5.0

- **`crypto` stdlib module** — SHA-256/512/1 and MD5 hex digests, HMAC-SHA-256, PBKDF2-HMAC-SHA256 key derivation, base64 encode/decode, `secrets`-backed random tokens, and constant-time digest comparison. Hashing and authentication only — no public-key encryption.
- **`graphics` stdlib module** — a pure-stdlib software rasterizer: canvases, pixels, Bresenham lines, filled/outlined rectangles and midpoint circles, with colors as `[r, g, b]` lists or `"#rrggbb"` strings. `save_png` writes a real PNG using only `struct` + `zlib` (hand-rolled IHDR/IDAT/IEND chunks with CRCs). No display, no windowing, no third-party packages; all drawing is clipped to the canvas.
- **`agent` stdlib module** — LLM helpers over any OpenAI-compatible `/chat/completions` endpoint using only `urllib`: `chat()` for single replies and `react()` for a tool-calling ReAct loop (JSON `{"tool", "args"}` / `{"answer"}` protocol, retry on malformed output, capped steps). Requires `AGK_LLM_API_KEY` and network access; nothing here works offline.
- **Expanded library documentation** — every stdlib module now has detailed, compile-and-run-verified examples in the wiki (28 examples across the 12 modules), plus a new [[Library cookbook|Library-Cookbook]] page with three complete programs: a `crypto` password-hashing CLI, a `graphics` generative-art PNG, and an `agent` tool-using assistant (verified offline against a mock LLM server — the wiki's example verifier now also answers POST and serves scripted response sequences).

## v0.4.0

- **Static type checker** — declared annotations on variables, params, and returns are verified; mismatches are compile errors with `file:line`. Unannotated code is untouched (gradual typing; `Object` is the dynamic escape hatch). Wired into `agk check`.
- **AST optimizer** — constant folding, dead-code elimination after `return`/`raise`, and conservative dead-store removal. On by default; `agk run`/`agk build --no-opt` disables it.
- **Fuller LSP** — completions, rename (scope-aware), find-references, and document symbols, alongside the existing diagnostics/hover/go-to-definition.
- **`agk debug`** — pdb-based debugger with breakpoints and stack frames mapped back to AGK source lines.
- **Test framework upgrades** — `setup`/`teardown` fixtures, mocks with call recording, and `agk test --coverage` with per-file AGK-line coverage.
- **async/await** — `define async function`, `await` expressions; async `main` runs via `asyncio.run`.
- **Generators** — `yield` makes a function a generator, consumable by ordinary `for` loops.
- **Decorators** — `@name` / `@name(args)` on functions, resolved through normal scope lookup.
- **`extern` functions** — FFI declarations compiled to `ctypes` calls (e.g. `extern function strlen that takes s as String and returns Integer from "c"`).
- **`agk pkg`** — Go-style package manager: `pkg init`, `pkg install <git-url>`, `pkg list`; `packages/<name>/` resolves in the import system.
- **Incremental compilation** — `.agkcache/` keyed by source hash + compiler version; `agk build` skips unchanged modules, `agk clean` wipes the cache.
- **This documentation wiki** — GitHub-wiki Markdown with verified examples.
- 1159 tests, all green.

## v0.3.0

- `agk fmt` — canonical source formatting, with `--check` mode
- `agk test` — test-file discovery and runner (`test_*.agk` / `*_test.agk`) with AGK-mapped tracebacks
- LSP server (`python -m agk.lsp`) — diagnostics, hover, go-to-definition over stdio JSON-RPC
- "Did you mean?" suggestions for undefined variables, functions, and base classes
- New stdlib modules: `csvutils`, `regexutils`, `sqliteutils`
- CI on Python 3.9–3.12 for every push and PR; PyPI packaging readiness (`RELEASING.md`)
- 890 tests, all green

## v0.2.0
- Exceptions: `try` / `catch` / `finally`, `raise` (string messages and bare re-raise)
- String interpolation (`"Hello, {name}!"`)
- Richer `for` loops: short form `for x in …`, inclusive ranges, negative steps
- Default parameter values (literals)
- New stdlib modules: `fileutils`, `jsonutils`, `httputils`, `dateutils`
- Pip-installable package (`pip install .` → `agk` command)
- VS Code syntax grammar (`editors/vscode/`)
- Browser playground (Pyodide, compile + run in-page)
- AGK-source traceback mapping in `agk run`
- 789 tests, all green

## v0.1.0

The initial build (milestones M1–M6):

- Frozen language spec (`SPEC.md`)
- Lexer with real INDENT/DEDENT handling
- Recursive-descent parser + AST
- Semantic analyzer: scope checking, undefined-variable errors with line numbers, arity checks, duplicate detection, unused/never-assigned/unreachable warnings, automatic `self.<field>` rewriting
- Python codegen: precedence-aware expressions, classes/constructors, `main()` entrypoint
- Pipeline API, 15 runnable corpus programs, 500-case mutation fuzz with zero raw tracebacks
- CLI (`run` / `build` / `check` / `repl`), interactive REPL with persistent definitions, `.agk` module imports, bundled stdlib (`strutils`, `listutils`), `GUIDE.md` with compile-tested examples
- 725 tests, all green
