# AGK-Real v1 — User Guide

AGK-Real is a small English-like programming language that compiles to
plain Python. You write `define function`, `create`, `set`, `if`, `while`
— the compiler turns it into readable Python 3 with no runtime dependency.

Every program in this guide is a complete, tested example: the test
suite compiles each one.

## Install and run

```sh
cd agk-real
python -m venv .venv && .venv/bin/pip install -e .   # or just use .venv/bin/python
```

Write `hello.agk`:

```agk
define function main:
    print("hello, agk")
```

```sh
.venv/bin/python -m agk run hello.agk     # compile and run
.venv/bin/python -m agk check hello.agk   # compile only, show errors/warnings
.venv/bin/python -m agk build hello.agk   # emit hello.py
.venv/bin/python -m agk repl              # interactive session
```

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

Six modules ship with the compiler (in `agk/stdlib/`). Import them by
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

## Errors

Errors always name the file, line, and column — never a traceback:

```
hello.agk:2:9: semantic error: cannot set undefined variable 'naem'
hello.agk:1:1: parser error: expected indented block, found 'set'
hello.agk:3:5: lexer error: unexpected character '?'
```

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
