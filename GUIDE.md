# AGK-Real v1 — User Guide

AGK-Real is a small English-like programming language that compiles to
plain Python. You write `define function`, `create`, `set`, `if`, `while`
— the compiler turns it into readable Python 3 with no runtime dependency.

Every program in this guide is a complete, tested example: the test
suite compiles each one.

## Install and run

AGK-Real 0.6.0 is PyPI-ready. From the repo root:

```sh
pip install .            # installs the `agk` command system-wide
```

Write `hello.agk`:

```agk
define function main:
    print("hello, agk")
```

Then, from anywhere:

```sh
agk run hello.agk        # compile and run
agk check hello.agk      # compile only, show errors/warnings
agk build hello.agk      # emit hello.py
agk repl                 # interactive session
```

The standard library (`agk/stdlib/*.agk`) ships inside the installed
package, so `import strutils` and friends work wherever `agk` is
installed — no need to run from the repo directory. For development, a
venv still works: `python -m venv .venv && .venv/bin/pip install -e .`,
then `.venv/bin/python -m agk run hello.agk`.

CI runs the full test suite on Python 3.9–3.12 for every push and pull
request. The release process is documented in `RELEASING.md`; releases
are never published without the maintainer's go-ahead.

`run` prints compiler warnings to stderr but still runs. `check` exits
non-zero on any error. `build` writes a single self-contained `.py` file.

## Variables

Declare with `create`, assign with `set`. A `set` without a `create`
is a compile error — this catches typos instead of crashing at runtime.

```agk
define function main:
    create name as String
    set name to "agk"
    create n as Integer
    set n to 41
    set n to n + 1
    print(name)
    print(n)
```

Types are statically checked — see [Static typing](#static-typing)
below.

## Functions

```agk
define function add that takes a as Integer, b as Integer and returns Integer:
    return a + b

define function main:
    print(add(20, 22))
```

The `that takes ...` / `and returns ...` clauses are optional. Calling a
function with the wrong number of arguments is a compile error.

Parameters can have default values (literals only), which callers may omit:

```agk
define function greet that takes name as String = "World", punct as String = "!":
    print("Hello, {name}{punct}")

define function main:
    greet()
    greet("Gopi")
    greet("Gopi", "?")
```

A parameter without a default may not follow one with a default.

## Static typing

Annotations are checked, not just documented. The compiler infers
simple types for literals (`42` is `Integer`, `"hi"` is `String`,
`true` is `Boolean`, `3.14` is `Float`, `[1, 2]` is `List`), for
arithmetic and comparisons, and for calls to functions with declared
return types — then verifies every `set`, argument, `return`,
constant, default value, and field assignment against the declared
type:

```agk
define function add that takes a as Integer, b as Integer and returns Integer:
    return a + b

define function main:
    create total as Integer
    set total to add(20, 22)
    print(total)
```

A mismatch is a compile error naming the file, line, and column:

```text
hello.agk:5:5: type error: type mismatch: cannot assign String to variable 'total' declared as Integer
```

The rules are deliberately simple — gradual typing, not a proof
system:

- `Object` accepts anything, in either direction. It is the dynamic
  escape hatch: declare something `as Object` when you don't want it
  checked.
- Anything the checker cannot infer (list elements, method calls on
  `Object`s, `for each` loop variables) is "unknown" and never
  produces an error.
- `Integer` widens to `Float`; a subclass instance fits a variable
  declared with its base class.
- Functions without a declared return type are not checked for what
  they return. There are no generics and no union types.

## Branching

```agk
define function main:
    create score as Integer
    set score to 82
    if score >= 90:
        print("A")
    elif score >= 80:
        print("B")
    else:
        print("keep practicing")
```

## Loops

```agk
define function main:
    create i as Integer
    set i to 3
    while i > 0:
        print(i)
        set i to i - 1
    print("liftoff")
```

```agk
define function main:
    create total as Integer
    set total to 0
    for each x in [10, 20, 30]:
        set total to total + x
    print(total)
```

The `each` is optional, and ranges count inclusively in both directions:

```agk
define function main:
    for i from 1 to 5:
        print(i)
    for i from 10 to 1 step -3:
        print(i)
    for w in ["a", "b"]:
        print(w)
```

`for i from 1 to 5` visits 1, 2, 3, 4, 5. The second loop prints
10, 7, 4, 1. The step may be any expression; its sign decides the
direction.

## String interpolation

Any `{expression}` inside a string is evaluated and spliced in:

```agk
define function main:
    create name as String
    set name to "Gopi"
    print("Hello, {name}!")
    print("1 + 2 = {1 + 2}")
    print("{{braces stay literal}}")
```

Double the braces (`{{`, `}}`) for a literal brace. A lone `{` or `}`
is a compile error.

## Exceptions

```agk
define function risky that takes n as Integer:
    if n < 0:
        raise "negative!"
    return 10 / n

define function main:
    try:
        print(risky(-1))
    catch err:
        print("caught: {err}")
    finally:
        print("cleanup runs")
```

`catch err:` binds the exception; a bare `catch:` catches without
binding. `finally:` is optional. A bare `raise` inside a `catch` block
re-raises the current exception. Raising a string message raises
`Exception(message)`.

## Async functions

Mark a function `async` and it compiles to a Python coroutine. Inside
one, `await` pauses until the awaited call finishes — handy for I/O
like network requests or timers:

```agk
import asyncio

define async function fetch_title that takes url as String:
    await asyncio.sleep(0.01)
    return "title of " + url

define async function main:
    create t as String
    set t to await fetch_title("example.com")
    print(t)
```

`await` outside an `async` function is a compile error. If `main`
itself is async, `agk run` drives it with `asyncio.run` automatically
— no boilerplate needed. Async methods work the same way; constructors
can't be async.

## Generators

A function containing `yield` becomes a generator: calling it returns
a lazy sequence, one value per `yield`. Consume it with an ordinary
`for` loop — values are produced on demand, so even an infinite
generator is fine as long as the loop exits:

```agk
define function fibonacci:
    create a as Integer
    create b as Integer
    set a to 0
    set b to 1
    while true:
        yield a
        create next as Integer
        set next to a + b
        set a to b
        set b to next

define function main:
    create count as Integer
    set count to 0
    for each n in fibonacci():
        print(n)
        set count to count + 1
        if count >= 6:
            return
```

A bare `yield` yields `None`. (`yield` inside an `async` function is
rejected — AGK has no async generators.)

## Decorators

Put `@name` (or `@name(args)`) lines directly above a `define
function` to apply a Python decorator — the function is replaced by
`name(function)`. A decorator can be any callable: a plain function,
or a class instance with a `__call__` method:

```agk
define class Doubler:
    variable fn as Object
    define constructor that takes f as Object:
        set fn to f
    define function __call__:
        return self.fn() * 2

@Doubler
define function five:
    return 5

define function main:
    print(five())
```

This prints `10`: `five` was replaced by `Doubler(five)`, whose
`__call__` doubles the result. Decorator names resolve like any other
name (a typo gets a "did you mean?" hint). They work on methods too,
but note the Python rule: wrapping a *method* in a non-descriptor
object breaks method binding, so method decorators should return the
function unchanged (or be descriptors).

## Classes

Fields are declared with `variable`. Inside methods, just name the
field — the compiler rewrites it to `self.<field>` for you.

```agk
define class Counter:
    variable n as Integer
    define constructor:
        set n to 0
    define function bump:
        set n to n + 1
    define function value that returns Integer:
        return n

define function main:
    create c as Object
    set c to Counter()
    c.bump()
    c.bump()
    print(c.value())
```

Inheritance with `extends`. Subclass methods can use inherited fields,
and `extends` on an unknown class is a compile error.

```agk
define class Animal:
    variable name as String
    define constructor that takes n as String:
        set name to n

define class Dog extends Animal:
    define function speak that returns String:
        return "woof"

define function main:
    create d as Object
    set d to Dog("rex")
    print(d.name)
    print(d.speak())
```

## Constants and imports

```agk
define constant LIMIT as Integer = 3

define function main:
    create i as Integer
    set i to 0
    while i < LIMIT:
        print(i)
        set i to i + 1
```

`import x` imports a Python module. `import x.y` works too. If an
`x.agk` file sits next to your program (or in the bundled stdlib), it is
compiled and inlined instead — its functions become directly callable.

```agk
import math
import strutils

define function main:
    print(math.floor(3.7))
    print(shout("done"))
```

A bare `import sys` passes straight through to the generated Python
untouched, so command-line arguments work in compiled programs:

```agk
import sys

define function main:
    print(sys.argv[1])
```

`sys.argv[0]` is the program path, `sys.argv[1:]` the user args — same
as Python.

## Calling C libraries (FFI)

`extern function` declares a C function from a shared library. The
declared name is both the AGK name and the C symbol name; calls look and
type-check exactly like normal function calls (wrong argument count is a
compile error).

```agk
extern function strlen that takes s as String and returns Integer from "c"
extern function getpid that returns Integer from "c"

define function main:
    print(strlen("hello"))
    print(getpid())
```

The `from` string is a library name or a path. A plain name like `"c"`
is resolved with `ctypes.util.find_library` (so it finds `libc.so.6` on
Linux); anything containing `/` is used as a path as-is. Each library is
loaded once, no matter how many functions you declare from it.

Only four AGK types cross the boundary:

| AGK | C | note |
|---|---|---|
| `String` | `char *` | utf-8 encoded on the way in, decoded on the way out (a NULL return becomes `None`) |
| `Integer` | `int` | |
| `Float` | `double` | |
| `Boolean` | `bool` | |

Any other type name is a compile error, and parameters can't have
defaults. Omit the return type for `void` C functions:

```agk
extern function sleep that takes seconds as Integer from "c"

define function main:
    sleep(0)
    print("wide awake")
```

Because real C libraries export names like `abs`, an `extern` name is
allowed to shadow a builtin — the generated wrapper deliberately
replaces it:

```agk
extern function abs that takes n as Integer and returns Integer from "c"

define function main:
    print(abs(-42))
```

FFI is Linux-first in this release: short library names resolve through
the system loader, so on other platforms prefer an explicit path.

## Collections and expressions

```agk
define function main:
    create xs as List
    set xs to [1, 2, 3]
    print(xs[0] + xs[2])
    create user as Object
    set user to {"name": "gopi", "id": 7}
    print(user["name"])
```

Operators follow Python precedence: `*` before `+`, `not` before `and`
before `or`. Parentheses always work.

```agk
define function main:
    print(1 + 2 * 3)
    print((1 + 2) * 3)
    print(not false and true)
```

## Recursion

```agk
define function fib that takes n as Integer and returns Integer:
    if n <= 1:
        return n
    else:
        return fib(n - 1) + fib(n - 2)

define function main:
    print(fib(10))
```

## The standard library

Nine modules ship with the compiler (in `agk/stdlib/`). Import them by
name; their functions are inlined into your program.

**strutils** — `shout(s)`, `repeat_string(s, n)`, `join_lines(lines)`,
`slug(s)`

**listutils** — `sum_list(xs)`, `max_in_list(xs)`, `min_in_list(xs)`,
`contains_int(xs, item)`

**fileutils** — `read_text(path)`, `write_text(path, text)`,
`append_text(path, text)`, `file_exists(path)`, `list_dir(path)`

**jsonutils** — `parse_json(text)`, `to_json(value)`

**httputils** — `http_get(url)` returns the response body as a String

**dateutils** — `today()` (`"YYYY-MM-DD"`), `now()`, `add_days(date, n)`

**csvutils** — `csv_parse(text)` (rows of strings), `csv_to_text(rows)`
(round-trip safe)

**regexutils** — `regex_match(pattern, text)` (Boolean, true if the
pattern is found anywhere), `regex_find_all(pattern, text)`,
`regex_replace(pattern, replacement, text)`, `regex_split(pattern, text)`

**sqliteutils** — `db_execute(db_path, sql)` (runs the statement,
returns `"ok"`), `db_query(db_path, sql)` (returns rows as a List of
lists). Each call opens the database, commits writes, and closes it —
no connection to manage.

**crypto** — `sha256(s)`, `sha512(s)`, `sha1(s)`, `md5(s)` (hex
digests), `hmac_sha256(key, message)`, `pbkdf2_hex(password, salt,
iterations)`, `base64_encode(s)`, `base64_decode(s)`,
`token_hex(nbytes)`, `compare_digest(a, b)` (constant-time). Hashing
and authentication only — no public-key encryption.

**graphics** — `new(w, h, bg)`, `pixel(canvas, x, y, color)`,
`get_pixel(canvas, x, y)`, `line(...)`, `rect(..., fill=true)`,
`circle(..., fill=true)`, `save_png(canvas, path)`. A pure-stdlib
software rasterizer: colors are `[r, g, b]` lists or `"#rrggbb"`
strings, drawing is clipped to the canvas, and `save_png` writes a
real PNG with no third-party packages. No display or windowing.

**agent** — `chat(messages, ...)` and `react(goal, tools, ...)` over
any OpenAI-compatible `/chat/completions` endpoint (standard library
only). Requires the `AGK_LLM_API_KEY` environment variable (or
an explicit key) and network access; nothing here works offline.

```agk
import csvutils

define function main:
    create rows as List
    set rows to csv_parse("name,age\nAmy,30")
    print(csv_to_text(rows))
```

```agk
import regexutils

define function main:
    print(regex_match("\\d+", "abc123"))
    print(regex_find_all("\\d+", "a1b22"))
    print(regex_replace("\\s+", "-", "a b  c"))
```

```agk
import sqliteutils

define function main:
    create p as String
    set p to "/tmp/agk_demo.db"
    db_execute(p, "CREATE TABLE t (name TEXT, n INT)")
    print(db_query(p, "SELECT * FROM t"))
```

Note the doubled backslashes in the regex patterns: `"\\d+"` is the
two-character string `\d+` by the time Python's `re` sees it.

```agk
import jsonutils
import dateutils

define function main:
    create obj as Object
    set obj to parse_json("{{\"a\": 1}}")
    print("json: {to_json(obj)}")
    print("today: {today()}")
    print("next week: {add_days(today(), 7)}")
```

Note the doubled braces: the JSON text lives inside an interpolated
string, so literal braces are written `{{` and `}}`.

You can write your own: put `helpers.agk` next to your program and
`import helpers`.

## Packages

AGK has a minimal, registry-free package manager: packages are plain
git repositories containing `.agk` modules (Go-modules style, minus
the central registry). `agk pkg` keeps a manifest, `agk.json`, in your
project directory:

```text
$ agk pkg init --name myapp
created agk.json (myapp 0.1.0)
$ agk pkg install https://example.com/greeter.git
installed greeter -> /home/you/myapp/packages/greeter @ 3fa1c9d2e4b5
$ agk pkg list
greeter 1.2.0 https://example.com/greeter.git @ 3fa1c9d2e4b5
```

Installs are shallow clones into `packages/<name>/`, and the commit
hash is pinned in `agk.json` next to the URL:

```json
{
  "name": "myapp",
  "version": "0.1.0",
  "dependencies": {
    "greeter": {
      "url": "https://example.com/greeter.git",
      "commit": "3fa1c9d2e4b5...",
      "version": "1.2.0"
    }
  }
}
```

A local directory installs by copy instead of clone (handy for
development and tests), and `--name` overrides the derived package
name. Re-running `install` for an already-installed package is a
no-op.

Once installed, import a package module like any other:

```agk
import greeter

define function main:
    print("greeter installed")
```

Package functions are inlined and called directly, exactly like
stdlib modules. Module lookup order is:

1. the importing file's own directory,
2. the caller's search paths,
3. the bundled stdlib,
4. installed packages (`packages/<name>/`, from the nearest `agk.json`
   walking up from the compiled file).

So a module next to your program — or a stdlib module — always wins
over an installed package with the same name.

## The REPL

```
>>> create x as Integer
>>> set x to 21
>>> x * 2
42
>>> define function double that takes n as Integer and returns Integer:
...     return n * 2
...
>>> double(100)
200
```

Type a line ending in `:` to enter a block; an empty line ends it.
Expressions print their value. Definitions, variables, and imports
persist for the session. `exit` quits.

## Tooling

### `agk fmt` — canonical formatting

`agk fmt` rewrites a `.agk` file with canonical layout: 4-space
indentation derived from block structure, single spaces between tokens,
at most one blank line between statements, no trailing whitespace, and
exactly one newline at the end of the file. Comments and string contents
are preserved verbatim. Formatting is idempotent — running it twice
changes nothing the second time.

```sh
agk fmt game.agk          # rewrite game.agk in place
agk fmt --check game.agk  # exit 0 if canonical, 1 if it would reformat
```

### `agk test` — run your AGK test suite

`agk test [path]` discovers `test_*.agk` / `*_test.agk` files (recursive
for directories, `.` by default), compiles each with the real pipeline,
and runs every `define function test_<name>:` in it. A test passes if it
returns without raising; it fails if it raises — test authors use
`raise "message"` on failure. Failures print an AGK-mapped traceback
pointing at your AGK source line. Output is `PASS`/`FAIL` lines followed
by a `N passed, M failed` summary. Exit codes: 0 all green, 1 failures,
2 usage/IO errors. Sibling helpers work: `import helper` inlines
`helper.agk` next to the test file, and you call its functions by bare
name.

Example test file `test_math.agk`:

```agk
define function add that takes a as Integer, b as Integer and returns Integer:
    return a + b

define function test_add:
    create r as Integer
    set r to add(2, 3)
    if r != 5:
        raise "expected 5, got {r}"
```

**Fixtures.** If a test module defines `setup`, it runs before each
test function; `teardown` runs after each one — even when the test (or
`setup` itself) raised. Neither name is treated as a test:

```agk
define function setup:
    print("seeding test data")

define function teardown:
    print("cleaning up")

define function test_one:
    print("running test one")
```

**Mocks.** Every test module gets three helpers for stubbing
module-level functions (the names `mock`, `mock_return`, `unmock` are
reserved in test files). Because imports are inlined into a single
namespace, mocking intercepts every call — including calls from
imported helper code. A mock records each call's arguments;
`unmock(m)` restores the original:

```
define function fetch_price that takes sym as String and returns Integer:
    return 999  # would hit the network in real life

define function test_total:
    create m as Mock
    set m to mock_return("fetch_price", 42)
    create t as Integer
    set t to fetch_price("ACME") * 2
    if t != 84:
        raise "stubbed total wrong: {t}"
    if m.call_count() != 1:
        raise "expected 1 call"
    create arg0 as String
    set arg0 to m.call_arg(0, 0)  # arg 0 of call 0
    if arg0 != "ACME":
        raise "wrong arg: {arg0}"
    unmock(m)  # fetch_price works normally again
```

`mock("name")` is the same but the stub returns nothing (useful for
void functions you just want to observe). Mocking a name that doesn't
exist fails the test immediately instead of silently mocking nothing,
so typos surface fast.

**Coverage.** `agk test --coverage [path]` traces which AGK lines ran
and prints a per-file table after the summary:

```sh
agk test --coverage
# 2 passed, 0 failed
# coverage:
#   test_math.agk: 81% (22/27 lines)
```

Percentages are covered / total executable AGK lines (lines that
produce code; blank lines and comments don't count). Bundled stdlib
modules pulled in by `import` are excluded from the table.

### `agk debug` — step through AGK code

`agk debug <file.agk>` runs your program under an AGK-aware debugger
(a thin wrapper over Python's `pdb`). Everything speaks AGK lines, not
generated-Python lines:

```agk
define function add that takes a as Integer, b as Integer and returns Integer:
    return a + b

define function main:
    create x as Integer
    set x to add(2, 3)
    print(x)
```

```text
$ agk debug prog.agk
Debugging prog.agk: break/step/list/p use AGK lines; 'help' lists pdb commands.
> "prog.agk"(1)<module>()
-> define function add that takes a as Integer, b as Integer and returns Integer:
(agk) break 8
Breakpoint 1 at prog.agk:8
(agk) continue
> "prog.agk"(8)main()
-> set x to add(2, 3)
(agk) step
> "prog.agk"(1)add()
-> define function add that takes a as Integer, b as Integer and returns Integer:
(agk) continue
5
```

`break <line>` (or `break <file.agk>:<line>`) sets a breakpoint at the
AGK line; stack frames and `where` show `"file.agk"(line)func()` with
the AGK source line; `list` shows AGK source with `->` on the current
line and `B` on breakpoint lines. `p <var>` prints AGK variables —
names are preserved verbatim by codegen, and inside methods a bare
field name (`p n`) resolves to `self.n` automatically. `step`, `next`,
`continue`, `up`/`down` behave as in pdb, and commands can be piped on
stdin for scripted sessions. An unhandled exception prints the same
AGK-mapped traceback as `agk run` (exit code 2).

Known limits: breakpoints need an executable AGK line (blank lines
report `No code at file:line`); frames from non-AGK code (stdlib,
generated `elif`/`else` lines) fall back to showing the real Python
location; post-mortem inspection after a crash is not entered
automatically.

### Editor support (LSP)

`python -m agk.lsp` runs a minimal language server with no dependencies
beyond the standard library. It speaks JSON-RPC over stdio with
`Content-Length` framing: opening or editing a `.agk` file runs it
through the real compile pipeline and publishes the compiler's errors
as LSP diagnostics; hover shows a markdown summary of any defined
function, class, constant, variable, parameter, or field, and
go-to-definition jumps to the defining line. It is deliberately small —
stdio only, full-document sync, first compiler error per change, no
workspace symbols — enough for any generic stdio LSP client extension.
VS Code setup is in `editors/vscode/README.md`.

Capabilities beyond diagnostics/hover/definition:

- **Completion** (`textDocument/completion`): on any identifier prefix it
  suggests in-scope variables and parameters, functions, classes,
  constants, keywords, builtin functions, and standard-library module
  names, each with its kind and signature or type. Typing a dot after a
  module name (e.g. `strutils.`) completes that module's functions.
  Completions are computed from the last successfully parsed document;
  while the file has a syntax error only keywords, builtins, and stdlib
  names are suggested.
- **Rename** (`textDocument/rename`): renames the symbol under the cursor
  everywhere it is used — definition plus all references — via a
  `WorkspaceEdit`. Resolution is scope-aware (it reuses the semantic
  analyzer's scope rules), so renaming a variable called `x` in one
  function never touches a different `x` in another function. Renaming
  with the cursor on empty space or a builtin answers `null`.
- **Find references** (`textDocument/references`): returns every location
  of the symbol under the cursor as line/character ranges. The definition
  site is included by default; pass
  `"context": {"includeDeclaration": false}` to get uses only.
- **Document symbols** (`textDocument/documentSymbol`): a file outline —
  functions with their parameters, classes with fields/constructor/methods,
  constants, and imports — each with its full range and name range.

One honest limitation: method calls on a plain variable (`a.deposit(...)`)
are not tracked by rename/references, because AGK carries no static
receiver type to resolve them to a class. `self`-calls inside methods are
tracked.

## Errors

Errors always name the file, line, and column — never a traceback:

```
hello.agk:2:9: semantic error: cannot set undefined variable 'naem'
hello.agk:1:1: parser error: expected indented block, found 'set'
hello.agk:3:5: lexer error: unexpected character '?'
hello.agk:3:5: type error: type mismatch: cannot assign String to variable 'count' declared as Integer
```

When you misspell a name, the compiler suggests the closest known name
instead of just saying "undefined". Candidates come from variables in
scope, declared functions, classes, and builtins; if nothing is close
enough, the original message is shown unchanged:

```text
hello.agk:3:4: semantic error: cannot set undefined variable 'greting'. did you mean 'greeting'?
hello.agk:2:10: semantic error: undefined function 'fobar'. did you mean 'foobar'?
hello.agk:3:15: semantic error: undefined variable 'zzz'
```

This applies to undefined variables, `set` on undeclared names,
undefined functions, and undefined base classes.

Warnings (unused variables, unreachable code, values never assigned)
go to stderr and never stop a build.

If a program compiles but crashes at runtime, `agk run` rewrites the
traceback to point at your `.agk` source lines instead of generated
Python:

```
Traceback (most recent call last):
  File "boom.agk", line 4, in main
    fail()
  File "boom.agk", line 2, in fail
    print(1 / 0)
ZeroDivisionError: division by zero
```

## What v2 does not do

- No generics, no union types, no keyword arguments.
- `implements` is reserved and rejected.
- One file per program plus `.agk` module imports; no packages.
- Indentation is 4 spaces per level, no tabs.
