# AGK-Real v1 — User Guide

AGK-Real is a small English-like programming language that compiles to
plain Python. You write `define function`, `create`, `set`, `if`, `while`
— the compiler turns it into readable Python 3 with no runtime dependency.

Every program in this guide is a complete, tested example: the test
suite compiles each one.

## Install and run

AGK-Real 0.3.0 is PyPI-ready. From the repo root:

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

Types (`Integer`, `Float`, `String`, `Boolean`, `List`, `Object`) are
documented intent in v1 — the compiler records them but does not
type-check.

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

## Errors

Errors always name the file, line, and column — never a traceback:

```
hello.agk:2:9: semantic error: cannot set undefined variable 'naem'
hello.agk:1:1: parser error: expected indented block, found 'set'
hello.agk:3:5: lexer error: unexpected character '?'
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

- No type checking: annotations are documentation.
- No generics, no keyword arguments.
- `implements` is reserved and rejected.
- One file per program plus `.agk` module imports; no packages.
- Indentation is 4 spaces per level, no tabs.
