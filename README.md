# AGK-Real

An English-like programming language that compiles to real, runnable Python.
Rebuilt from scratch after the AGKOS/AGKCompiler repos turned out to never
have compiled their own examples (0/40 `.agk` files parsed).

**User guide:** [`GUIDE.md`](GUIDE.md) — every program in it is
compile-tested by the suite.

## Quick start

```sh
pip install .                       # installs the `agk` command
agk run hello.agk                    # compile and run
agk check hello.agk                  # compile only
agk build hello.agk                  # emit hello.py
agk repl                             # interactive session
```

(Or without installing: `.venv/bin/python -m agk run hello.agk`.)

```agk
define function main:
    print("hello, agk")
```

## Status

- **M1 DONE** — frozen spec (`SPEC.md`), lexer with real INDENT/DEDENT
  handling, 39/39 lexer tests green.
- **M2 DONE** — recursive-descent parser + AST, 60/60 parser tests green.
  99 tests total.
- **M3 DONE** — semantic analyzer: scope checking, undefined-variable
  errors with line numbers, arity checks, duplicate detection,
  unused/never-assigned/unreachable warnings, automatic
  `self.<field>` rewriting. 32/32 semantic tests green. 131 total.
- **M4 DONE** — Python codegen: precedence-aware expression emission,
  classes/constructors/methods, `main()` entrypoint. 29/29 golden tests
  green (every output validated by `ast.parse`). 160 total.
- **M5 DONE** — pipeline API, 15 runnable corpus programs with exact-stdout
  E2E tests, 500-case mutation fuzz with zero raw tracebacks. 683 total.
- **M6 DONE** — CLI (`run`/`build`/`check`/`repl`), interactive REPL with
  persistent definitions, `.agk` module imports, bundled stdlib
  (`strutils`, `listutils`), `GUIDE.md` with compile-tested examples.
  **725 tests total, all green.**
- **V2 DONE** — exceptions (`try`/`catch`/`finally`, `raise`),
  string interpolation (`"Hello, {name}!"`), richer `for` loops
  (`for x in ...`, `for i from 1 to 10 [step n]`), default parameter
  values, new stdlib modules (`fileutils`, `jsonutils`, `httputils`,
  `dateutils`), pip-installable package (`pip install .` → `agk`
  command), VS Code syntax grammar (`editors/vscode/`), AGK-source
  traceback mapping in `agk run`, and a browser playground
  (Pyodide, compile + run in-page). **789 tests total, all green.**

## Tooling

- `pip install .` — installs the `agk` console script (package
  `agk-real` 0.2.0, Python 3.9+). Stdlib `.agk` modules ship as package
  data.
- `editors/vscode/` — TextMate grammar + language configuration for
  `.agk` files. Copy into `~/.vscode/extensions/agk-0.2.0/`.
- `playground/` — `build.py` embeds the compiler into a single HTML
  page; runs AGK in the browser via Pyodide (no server).

## Layout

```
SPEC.md            v2 language spec (the contract)
GUIDE.md           user guide (every example compile-tested)
agk/               compiler package
  tokens.py        token types
  lexer.py         lexer (INDENT/DEDENT via indent stack)
  parser.py        recursive-descent parser + AST builders
  ast_nodes.py     AST dataclasses
  semantic.py      scope/arity/duplicate checking, self-rewriting
  codegen.py       precedence-aware Python emitter
  pipeline.py      compile_source / run_source, .agk module resolution,
                   AGK-source traceback mapping
  repl.py          interactive REPL
  __main__.py      CLI: run / build / check / repl
  stdlib/          bundled .agk modules (strutils, listutils, fileutils,
                   jsonutils, httputils, dateutils)
  errors.py        file:line:col errors, no tracebacks
editors/vscode/    VS Code syntax highlighting for .agk
playground/        browser playground (Pyodide) sources + build script
tests/
  corpus/          15 runnable .agk programs + expected stdout
```

## Run tests

```
.venv/bin/python -m pytest tests/ -q
```

## Rules (from the post-mortem)

1. No construct ships without a compile-and-run test.
2. Every doc example must compile (CI enforces).
3. Invalid input → `file.agk:line:col: <message>`, never a traceback.
4. One target (Python 3.9+), done right. No fake multi-target wrappers.
