# AGK-Real

An English-like programming language that compiles to real, runnable Python. You write `define function`, `create`, `set`, `if`, `while` — the compiler turns it into readable Python 3 with no runtime dependency.

<!-- verify: id=home-hello output="hello, agk\n" -->
```agk
define function main:
    print("hello, agk")
```

> [!NOTE]
> Every AGK example in this wiki is a complete, runnable program. A verification script compiles and runs each one through the real compiler before it ships — see the [[CLI-Reference|CLI reference]] for the tools, or run `scripts/verify_examples.py` in this wiki yourself.

## Get started

```sh
$ pip install .
$ agk run hello.agk        # compile and run
$ agk check hello.agk      # compile only, show errors/warnings
$ agk build hello.agk      # emit hello.py
$ agk repl                 # interactive session
```

(Or without installing: `.venv/bin/python -m agk run hello.agk` from the repo root.)

## Explore

- **[[Tutorial]]** — a guided walkthrough: your first program, variables, functions, loops, classes, errors, and the standard library.
- **[[Language-Reference|Language reference]]** — the full syntax contract — variables, functions, classes, control flow, exceptions, interpolation, imports — plus what's new in 0.4.0.
- **[[Stdlib-Reference|Standard library]]** — nine bundled modules: strings, lists, files, JSON, HTTP, dates, CSV, regex, and SQLite. Import by name, call directly.
- **[[CLI-Reference|CLI reference]]** — every `agk` subcommand with flags and exit codes: run, build, check, test, fmt, repl — plus the LSP server.
- **[[Changelog]]** — what changed in each release, from v0.1.0 to the current v0.4.0.

## Design rules

- No construct ships without a compile-and-run test.
- Every doc example must compile (the test suite enforces it).
- Invalid input gives `file.agk:line:col: <message>` — never a traceback.
- One target (Python 3.9+), done right. No fake multi-target wrappers.

## Project links

- The compiler source lives in the [`agk/`](https://github.com/agk4444/AGK-Real) directory of the AGK-Real repo; this wiki is the `wiki/` directory inside it.

---

*AGK-Real v0.4.0 wiki.*
