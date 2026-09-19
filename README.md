# AGK-Real

An English-like programming language that compiles to real, runnable Python.
Rebuilt from scratch after the AGKOS/AGKCompiler repos turned out to never
have compiled their own examples (0/40 `.agk` files parsed).

```agk
to main:
    say "hello, agk"
```

You write `to`, `say`, `name is`, `repeat` — plain English — and the
compiler turns it into readable Python 3 with no runtime dependency.
(The classic `define function` / `create` / `set` / `print` forms still
work too.)

**Docs:** the [GitHub wiki](https://github.com/agk4444/AGK-Real/wiki)
(tutorial, language reference, standard library, cookbook, CLI reference,
changelog) — every example in it is compile-and-run verified.
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

## Status

**v0.6.0** — Simple AGK: `name is ...` declaration with type inference,
`to ... with ...:` functions, `say` / `ask ... giving ...`, `repeat N
times:`, English comparisons (`is greater than`), `otherwise:`,
`increase` / `decrease ... by`. **1259 tests, all green.**

Also in: static type checker, optimizer (constant folding, dead-code and
dead-store elimination), debugger (`agk debug`), test runner
(`agk test`), formatter (`agk fmt`), package manager (`agk pkg`),
LSP server, `.agk` module imports, exceptions, string interpolation,
async/await, generators, decorators, FFI (`extern`), and thirty-three bundled
stdlib modules: `strutils`, `listutils`, `fileutils`, `jsonutils`,
`httputils`, `dateutils`, `csvutils`, `regexutils`, `sqliteutils`,
`crypto`, `graphics`, `agent`, `mathutils`, `randutils`, `timeutils`,
`sysutils`, `pathutils`, `urlutils`, `uuidutils`, `ziputils`, `iniutils`,
`htmlutils`, `xmlutils`, `statutils`, `iterutils`, `colorutils`, `logutils`,
`transformers`, `tokenizer`, `torchutils`, `datasets`, `embeddings`, `finetune`.

See the [changelog](https://github.com/agk4444/AGK-Real/wiki/Changelog)
for the full release history.

## Tooling

- `pip install .` — installs the `agk` console script (package
  `agk-real` 0.6.0, Python 3.9+). Stdlib `.agk` modules ship as package
  data.
- `agk run|build|check|repl|debug|test|fmt|clean` and `agk pkg
  init|install|list` — see `agk --help` or the
  [CLI reference](https://github.com/agk4444/AGK-Real/wiki/CLI-Reference).
- `editors/vscode/` — TextMate grammar + language configuration for
  `.agk` files.
- `playground/` — `build.py` embeds the compiler into a single HTML
  page; runs AGK in the browser via Pyodide (no server).

## Layout

```
SPEC.md            v2 language spec + frozen amendments (the contract)
GUIDE.md           user guide (every example compile-tested)
wiki/              GitHub wiki source (every example compile-and-run verified)
agk/               compiler package
  lexer.py         lexer (INDENT/DEDENT via indent stack)
  parser.py        recursive-descent parser + AST builders (+ Simple AGK desugaring)
  ast_nodes.py     AST dataclasses
  semantic.py      scope/arity/duplicate checking, type inference, self-rewriting
  codegen.py       precedence-aware Python emitter
  pipeline.py      compile_source / run_source, .agk module resolution,
                   AGK-source traceback mapping
  repl.py          interactive REPL
  __main__.py      CLI: run / build / check / repl / debug / test / fmt / clean / pkg
  stdlib/          12 bundled .agk modules (strutils, listutils, fileutils,
                   jsonutils, httputils, dateutils, csvutils, regexutils,
                   sqliteutils, crypto, graphics, agent)
  errors.py        file:line:col errors, no tracebacks
editors/vscode/    VS Code syntax highlighting for .agk
playground/        browser playground (Pyodide) sources + build script
tests/
  corpus/          21 runnable .agk programs + expected stdout
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
