# Changelog

What changed in each release. There is no `CHANGELOG.md` in the repo; this page reconstructs the history from the release commits and the project README.

**Contents**

- [[Changelog#v040-current|v0.4.0]]
- [[Changelog#v030|v0.3.0]]
- [[Changelog#v020|v0.2.0]]
- [[Changelog#v010|v0.1.0]]

## v0.4.0 **[current]**

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
