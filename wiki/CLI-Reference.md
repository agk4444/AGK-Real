# CLI reference

The `agk` command (installed by `pip install .`). Without installing, prefix everything with `.venv/bin/python -m` from the repo root, e.g. `.venv/bin/python -m agk run hello.agk`.

**Contents**

- [[`agk run`|CLI-Reference#agk-run-fileagk]]
- [[`agk build`|CLI-Reference#agk-build-fileagk--o-outpy]]
- [[`agk check`|CLI-Reference#agk-check-fileagk]]
- [[`agk test`|CLI-Reference#agk-test-path]]
- [[`agk fmt`|CLI-Reference#agk-fmt---check-fileagk]]
- [[`agk repl`|CLI-Reference#agk-repl-or-bare-agk]]
- [[LSP server|CLI-Reference#lsp-server]]
- [[Exit codes|CLI-Reference#exit-codes]]

## `agk run <file.agk>`

Compile and run. Compiler warnings print to stderr but don't stop the run. Runtime tracebacks are rewritten to `.agk` file/line form, so a crash points at your AGK source, never at generated Python.

```sh
$ agk run hello.agk
hello, agk
```

## `agk build <file.agk> [-o out.py]`

Compile to Python and write the file. Default output is the input name with a `.py` extension (`hello.agk` → `hello.py`); `-o` picks the path. The emitted file is self-contained plain Python — run it with any Python 3.9+ interpreter, no AGK needed.

```sh
$ agk build hello.agk
wrote hello.py
$ agk build hello.agk -o dist/hello.py
wrote dist/hello.py
```

## `agk check <file.agk>`

Compile only. Reports errors and warnings without running anything; exits non-zero on any error.

```sh
$ agk check hello.agk
hello.agk: OK
```

## `agk test [path]`

Discover and run `test_*.agk` / `*_test.agk` files (recursive for directories; `.` by default). Each file is compiled with the real pipeline, then every `define function test_<name>:` in it runs. A test passes if it returns without raising; it fails if it raises — test authors use `raise "message"` on failure. Failures print an AGK-mapped traceback pointing at your AGK source line. Output is `PASS`/`FAIL` lines followed by a `N passed, M failed` summary. Sibling helpers work: `import helper` inlines `helper.agk` next to the test file, and you call its functions by bare name.

Example test file `test_math.agk` (verified: it compiles and runs as a program too):

<!-- verify: id=cli-test-file compile-only -->
```agk
define function add that takes a as Integer, b as Integer and returns Integer:
    return a + b

define function test_add:
    create r as Integer
    set r to add(2, 3)
    if r != 5:
        raise "expected 5, got {r}"
```

```sh
$ agk test .
PASS test_math.agk::test_add
1 passed, 0 failed
```

## `agk fmt [--check] <file.agk>`

Canonical formatting. Rewrites the file in place with: 4-space indentation derived from block structure, single spaces between tokens, at most one blank line between statements, no trailing whitespace, exactly one newline at end of file. Comments and string contents are preserved verbatim. Formatting is idempotent — running it twice changes nothing the second time. With `--check`, exits 0 and prints `ok` if the file is already canonical, 1 and prints `would reformat …` otherwise.

```sh
$ agk fmt game.agk            # rewrite game.agk in place
$ agk fmt --check game.agk    # exit 0 if canonical, 1 if it would reformat
ok
```

## `agk repl` (or bare `agk`)

Interactive session. Type a line ending in `:` to enter a block; an empty line ends it. Expressions print their value. Definitions, variables, and imports persist for the session. `exit` quits.

```text
>>> create x as Integer
>>> set x to 21
>>> x * 2
42
>>> define function double that takes n as Integer and returns Integer:
...     return n * 2
...
>>> double(100)
200
>>> exit
```

## LSP server

`python -m agk.lsp` runs a minimal language server with no dependencies beyond the standard library. It speaks JSON-RPC over stdio with `Content-Length` framing: opening or editing a `.agk` file runs it through the real compile pipeline and publishes the compiler's errors as LSP diagnostics; hover shows a markdown summary of any defined function, class, constant, variable, parameter, or field; go-to-definition jumps to the defining line. Deliberately small — stdio only, full-document sync, first compiler error per change, no workspace symbols — enough for any generic stdio LSP client extension. VS Code setup is in `editors/vscode/README.md` in the repo.

```sh
$ python -m agk.lsp    # speak JSON-RPC over stdio
```

## Exit codes

| Command | 0 | 1 | 2 |
|---|---|---|---|
| `run`, `build`, `check` | ok | compile error | runtime or usage error |
| `test` | all tests passed | some test failed, or a file could not be collected | usage / IO error |
| `fmt` | ok (or clean under `--check`) | would reformat / lexer error | usage / IO error |
