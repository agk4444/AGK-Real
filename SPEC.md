# AGK-Real v2 Language Specification

Supersedes the frozen v1 spec (2026-09-18). This document is the contract:
the test suite enforces it, and any construct not in this spec is a compile
error, not a silent miscompile. Changes require a spec amendment + new tests
first.

## 1. Program structure

A program is a sequence of top-level statements: imports, constants, function
definitions, class definitions. Execution begins at a `define function main:`
if present; otherwise the top-level statements run in order.

## 2. Lexical rules

- Comments start with `#` and run to end of line.
- String literals use double quotes: `"hello"`. Escapes: `\"`, `\\`, `\n`, `\t`.
- **String interpolation (v2):** `{expr}` inside a string is evaluated and
  spliced in: `"Hello, {name}!"`. Any expression may appear inside the braces,
  including nested braces and quoted strings. `{{` and `}}` produce literal
  braces; a lone `{` or `}` is a parse error. A string with no interpolation
  is a plain literal (v1 behaviour unchanged).
- Integer literals: `42`. Float literals: `3.14`.
- Boolean literals: `true`, `false`.
- Indentation is significant (4 spaces per level, tabs are an error).
  Blank lines and comment-only lines do not affect indentation.
- Any other character (e.g. `?`, `$`, backtick) is a lexer error with
  `file:line:column`.

## 3. Keywords (v2)

```
define function that takes and returns
create set to constant
if elif else while for each in from step return
class variable constructor extends implements
import try catch finally raise
and or not true false
extern
async await yield
```

Type names are ordinary identifiers by convention: `Integer Float String
Boolean List Object`. They carry no runtime meaning, but the compiler
statically checks them (v0.4.0): assigning a value whose inferred type
does not match a declared annotation is a compile error. `Object`
accepts any type in either direction; anything the checker cannot infer
is left unchecked (gradual typing). There are no generics and no union
types.

## 4. Statements

### 4.1 Function definition
```
define function <name>:
define function <name> that takes <a> as <Type>, <b> as <Type>:
define function <name> that takes <a> as <Type> and returns <Type>:
define function <name> that returns <Type>:
```
Body is an indented block. `and returns <Type>` is optional documentation.

**Default parameter values (v2):** any parameter may declare a default:
```
define function greet that takes name as String = "World", n as Integer = 3:
```
Defaults must be literals (number, string, boolean; numbers may be negated).
Interpolated strings are not allowed as defaults. Parameters with defaults
must come after all parameters without defaults. Calls may omit trailing
defaulted arguments; omitting a required argument or passing too many is a
semantic error. Constructors follow the same rules.

### 4.2 Variable declaration and assignment
```
create <name> as <Type>
set <name> to <expr>
```
`create` introduces the name in the current scope; `set` requires the name
to already exist (semantic error otherwise).

### 4.3 Constant definition (top level only)
```
define constant <NAME> as <Type> = <expr>
```
`<expr>` must be a literal (int, float, string, boolean). Emitted as a
module-level Python assignment.

### 4.4 Conditional
```
if <expr>:
    ...
elif <expr>:
    ...
else:
    ...
```
`elif` may repeat; `else` is optional and last.

### 4.5 Loops
```
while <expr>:
    ...

for each <name> in <expr>:
    ...

for <name> in <expr>:
    ...

for <name> from <start> to <end>:
    ...

for <name> from <start> to <end> step <step>:
    ...
```
- `for each x in ...` and `for x in ...` are equivalent (v2 short form).
- The range form is **inclusive** of `<end>`: `for i from 1 to 3` visits
  1, 2, 3. Default step is 1. A negative step counts down, also inclusive:
  `for i from 10 to 1 step -3` visits 10, 7, 4, 1. `<step>` may be any
  expression; its sign is honoured at runtime.

### 4.6 Return
```
return <expr>
return
```
Outside a function: semantic error.

### 4.7 Class definition
```
define class <Name>:
    variable <field> as <Type>
    define constructor that takes <a> as <Type>:
        ...
    define function <method> that takes <a> as <Type>:
        ...
```
- `extends <Base>` after the class name enables single inheritance.
- `implements` is a parse error (reserved for later).
- Inside methods, fields are accessed as `self.<field>` — the compiler
  rewrites bare field names to `self.<field>` automatically.
- Subclass methods see inherited fields transitively (a subclass
  constructor may `set` a field declared on the base class).
- `extends` on a class not defined in the file is a semantic error.

### 4.8 Import
```
import <module>
```
Imports a Python module (e.g. `import math`). `import a.b` supported.

### 4.10 AGK module imports
```
import <name>
```
If `<name>.agk` is found next to the importing file, in a configured
search path, or in the bundled stdlib, the module is compiled and
inlined: its functions, classes, and constants become directly callable
and the `import` line emits nothing. Otherwise the import falls through
to a plain Python `import <name>`. Dotted names are always Python
imports. Circular `.agk` imports are tolerated (resolved once).

### 4.9 Expression statement
```
<expr>
```
A bare expression as a statement — in practice a call such as
`print("hello")`. The value is discarded.

### 4.11 Exceptions (v2)
```
try:
    ...
catch <name>:
    ...
finally:
    ...

try:
    ...
catch:
    ...
```
- `catch <name>:` binds the caught exception to `<name>` (available only
  inside the catch block). A bare `catch:` catches without binding.
- `finally:` is optional and runs whether or not an exception occurred.
- A `try` requires at least one of `catch` / `finally`.
- `raise <expr>` raises an exception; a bare `raise` re-raises the
  exception currently being handled (valid only inside a `catch` block).
  A string message is raised as `Exception(message)`; any other value is
  raised as-is (so `raise err` re-raises the caught exception object).
- Only `Exception` subclasses are caught (matching Python semantics).

### 4.12 Extern function declarations (FFI)
```
extern function <name> [that takes <a> as <Type>, ...] [and returns <Type>] from "<lib>"
```
- Top level only; no body. Declares a C function from a shared library.
  The declared name is both the AGK name and the C symbol name.
- Supported types are `String`, `Integer`, `Float`, `Boolean` — any other
  type name is a semantic error. Parameters cannot have default values.
- The return type may be omitted, for C functions returning `void`.
- `<lib>`: a string containing `/` (or starting with `.`) is used as a
  path as-is; otherwise it is resolved with `ctypes.util.find_library`,
  falling back to the name itself. So `from "c"` finds `libc.so.6` on
  Linux.
- Each distinct library is loaded once via `ctypes.CDLL`. Every
  declaration sets `argtypes`/`restype` from the table below and is
  wrapped in a plain Python function of the declared name, so calls look
  and arity-check exactly like normal AGK function calls.
- Unlike `define function`, an extern name may deliberately shadow a
  builtin (C libraries export names like `abs`); the generated wrapper
  replaces the builtin in the module namespace.

| AGK | ctypes | argument | result |
|---|---|---|---|
| `String` | `c_char_p` | utf-8 encoded | utf-8 decoded; a NULL return becomes `None` |
| `Integer` | `c_int` | passed as-is | passed as-is |
| `Float` | `c_double` | passed as-is | passed as-is |
| `Boolean` | `c_bool` | passed as-is | passed as-is |

`Integer` maps to C `int`, not `long`: results from APIs returning
`size_t`/`long` are truncated to int range (a documented FFI
limitation). Library resolution is Linux-first: short names like `"c"`
and `"m"` resolve through the system loader; other platforms should
pass an explicit path.

### 4.13 Async functions (v0.4.0)
```
define async function <name> [that takes ...] [and returns <Type>]:
    ...
```
- An `async` function compiles to Python `async def`. `await <expr>`
  inside one suspends until the awaited coroutine completes.
- `await` outside an async function is a semantic error (it is a parse
  error at top level, where only `import`/`define` may appear).
- Async methods are allowed (`define async function` in a class body);
  async constructors are a parse error.
- If `main` is async, `agk run` / `agk build` execute it via
  `asyncio.run(main())` and the generated module imports `asyncio`
  automatically (unless the program already does).
- `yield` inside an async function is a semantic error: AGK has no
  async generators.

### 4.14 Generators (v0.4.0)
```
yield <expr>
yield
```
- `yield` may appear in any (non-async) function body. A function
  containing `yield` becomes a generator: calling it returns a lazy
  iterator, each `yield` producing the next value. A bare `yield`
  produces `None`.
- Generators are consumed with the ordinary `for` loops from §4.5
  (`for each x in gen():`), which pull values lazily — an infinite
  generator is fine as long as the loop exits.
- `yield` outside a function is rejected (a parse error at top level).

### 4.15 Decorators (v0.4.0)
```
@<name>
@<name>(<args>)
define function <name> ...:
    ...
```
- One or more `@` lines directly above a `define function` (top level
  or method) apply Python decorators: the function is replaced by
  `<name>(<func>)`, or `<name>(<args>)(<func>)` for the argument form.
  Multiple decorators apply bottom-up, as in Python.
- Decorator names resolve through normal scope lookup (undefined names
  are a semantic error, with "did you mean?" suggestions); argument
  expressions are checked like any other expression.
- Decorators are not supported on classes, constants, or constructors
  (clean parse errors).
- Note: a decorator that wraps a *method* in a plain (non-descriptor)
  object breaks method binding, exactly as in Python — wrap top-level
  functions, or return the function unchanged for methods.

## 5. Expressions (precedence, highest to lowest)

1. Literals, names, parenthesised `( <expr> )`
2. Calls: `<expr>(<args>)`, attribute access: `<expr>.<name>`,
   indexing: `<expr>[<expr>]`
3. `await <expr>` (async functions only; binds like Python, so
   `await f() + 1` is `(await f()) + 1` and `await -x` is `await (-x)`)
4. Unary `-x`, `not x`
5. `*`, `/`, `%`
6. `+`, `-`
7. `<`, `>`, `<=`, `>=`
8. `==`, `!=`
9. `and`
10. `or`

List literal: `[1, 2, 3]`. Dict literal: `{"a": 1}`.

## 6. Name resolution (semantic rules)

- `set` / use of an undeclared name → error naming the variable and line.
- `create` of an already-declared name in the same scope → error.
- Function called with wrong argument count → error. With defaulted
  parameters the message gives the allowed range, e.g.
  `takes 1 to 2 arguments, got 0`; without defaults it gives the exact
  count as in v1.
- A parameter without a default may not follow one with a default.
- `return` outside a function → error.
- `await` outside an async function → error; `yield` inside an async
  function → error (no async generators).
- Decorator names are resolved like any other name: an undefined
  decorator is an error with a "did you mean?" suggestion.
- Unused variable, unreachable code after `return` → warnings (non-fatal).
- Undefined names get a "did you mean?" suggestion when a close candidate
  exists (searched among variables in scope, declared functions, classes,
  and builtins): the message is `<base message>. did you mean '<name>'?`.
  With no close candidate the base message is unchanged. Applies to
  undefined variables, `set` on undeclared names, undefined function
  calls, and undefined base classes.

## 7. Code generation (Python 3.9+)

| AGK | Python |
|---|---|
| `define function f that takes a as Integer:` | `def f(a):` |
| `define function g that takes n as Integer = 3:` | `def g(n=3):` |
| `create x as Integer` | (declaration only; no output until `set`) |
| `set x to 1` | `x = 1` |
| `define constant PI as Float = 3.14` | `PI = 3.14` |
| `"Hello, {name}!"` | `"Hello, {}!".format(name)` |
| `"{{literal}}"` | `"{literal}"` |
| `if/elif/else`, `while` | direct mapping |
| `for each item in items:` / `for item in items:` | `for item in items:` |
| `for i from 1 to 3:` | `for i in range(1, (3) + 1):` |
| `for i from 10 to 1 step -3:` | `for i in range(10, <end-expr>, -3):` (inclusive both directions) |
| `try:` / `catch e:` / `catch:` / `finally:` | `try:` / `except Exception as e:` / `except Exception:` / `finally:` |
| `raise "boom"` / `raise` | `raise Exception("boom")` / `raise` (bare re-raise) |
| `define async function f:` | `async def f():` |
| `await g()` (inside async) | `await g()` |
| async `define function main:` | `import asyncio` + `asyncio.run(main())` entrypoint |
| `yield x` / `yield` | `yield x` / `yield` (function becomes a generator) |
| `@timer` / `@retry(3)` above `define function` | `@timer` / `@retry(3)` above `def` |
| `extern function strlen that takes s as String and returns Integer from "c"` | `import ctypes`; library loaded once via `ctypes.CDLL`; `def strlen(s):` wrapper with `argtypes=[c_char_p]`, `restype=c_int`, utf-8 encode/decode |
| `true` / `false` | `True` / `False` |
| `and` / `or` / `not` | direct mapping |
| class / constructor / variable | `class`, `__init__`, `self.` fields |

Generated code carries no AGK runtime dependency: plain Python, stdlib only.

`agk run` compiles with per-line AGK source annotations and rewrites
runtime tracebacks to `.agk` file/line form, so a crash points at the AGK
source, never at generated Python internals.

## 8. Error format

Compile errors print as `file.agk:line:column: <phase>: <message>` on
stderr and exit non-zero. No Python tracebacks ever reach the user at
compile time. Where applicable, the message carries a suggestion
(`... did you mean '<name>'?`, see §6); otherwise the message is shown
as-is. Runtime errors under `agk run` are rendered as AGK-source
tracebacks (`file.agk:line` frames) followed by the exception message.

## 9. Standard library (v2)

Bundled `.agk` modules, importable by name with no install step:

| Module | Functions |
|---|---|
| `strutils` | string helpers (v1) |
| `listutils` | list helpers (v1) |
| `fileutils` | `read_text(path)`, `write_text(path, text)`, `append_text(path, text)`, `file_exists(path)`, `list_dir(path)` |
| `jsonutils` | `parse_json(text)`, `to_json(value)` |
| `httputils` | `http_get(url)` → response body as String |
| `dateutils` | `today()` → `"YYYY-MM-DD"`, `now()` → datetime string, `add_days(date, n)` |
| `csvutils` | `csv_parse(text)` → List of rows (each a List of strings); `csv_to_text(rows)` → String (round-trip safe) |
| `regexutils` | `regex_match(pattern, text)` → Boolean (true if pattern found anywhere), `regex_find_all(pattern, text)` → List of matches, `regex_replace(pattern, replacement, text)` → String, `regex_split(pattern, text)` → List |
| `sqliteutils` | `db_execute(db_path, sql)` → `"ok"` (statement executed and committed); `db_query(db_path, sql)` → List of rows (each a List of values). Each call opens, commits writes, and closes the database. |
| `crypto` | `sha256` / `sha512` / `sha1` / `md5` → hex digests; `hmac_sha256(key, message)`; `pbkdf2_hex(password, salt, iterations)`; `base64_encode` / `base64_decode`; `token_hex(nbytes)`; `compare_digest(a, b)` (constant-time). Hashing/auth only. |
| `graphics` | software rasterizer (stdlib only): `new(w, h, bg)`, `pixel`, `get_pixel`, `line`, `rect(..., fill=true)`, `circle(..., fill=true)`, `save_png(canvas, path)` → real PNG. Colors are `[r, g, b]` or `"#rrggbb"`; clipped drawing; no display. |
| `agent` | `chat(messages, ...)` and `react(goal, tools, ...)` over OpenAI-compatible `/chat/completions` via `urllib`. Requires `AGK_LLM_API_KEY` + network; offline it raises a clean error. |

## 10. Explicitly out of v2

Multi-target codegen (JS/Kotlin/…), ternary `?:`,
`implements`, slices, comprehensions, operator overloading, lambdas.
Each is a clean parse error if attempted.

## 11. Simple AGK surface (v0.6.0)

A beginner-friendly alias layer over the statements in §4. Every form
desugars to an existing construct during parsing, so name resolution
(§6) and code generation (§7) are unchanged. No new reserved words are
introduced: `say`, `ask`, `repeat`, `increase`, `decrease`,
`otherwise`, `is`, `giving`, `times`, `time`, `by`, `with`,
`greater`, `than`, `less` and `equal` remain ordinary identifiers and
are only treated specially when the complete statement pattern matches
at statement start (or, for `otherwise`, directly after an if/elif
block). `to` was already reserved (§2). Existing programs keep their
meaning: `say(x)` is still a call to a user-defined `say`, and every
one of these words still works as a variable name.

### 11.1 Inferred declaration: `name is <expr>`

```
<name> is <expr>
```

When `<name>` is new in scope, this declares it with an inferred type
and assigns the value. Literals infer `Integer`, `Float`, `String`,
`Boolean`, `List` or `Dict`; anything else is dynamically typed. When
`<name>` already exists — whether from an earlier `is`, from `create`,
or from `ask ... giving` — it is a plain assignment and never a
redeclare error; the original declared type still governs, so a
mismatched reassignment is a type error exactly as with `set`. The
name must resolve in scope: assigning to an undeclared name is a
semantic error, as with `set`. Inside class methods, `name is <expr>`
assigns a field when `<name>` is a declared field, mirroring `set`.
In the REPL, `x is <expr>` assigns; it does not evaluate `x ==
<expr>`.

When the words after `is` read as a comparison (`is not ...`,
`is greater|less than ...`), the line is an expression statement
instead (§11.5).

### 11.2 `say`, `ask`, `repeat`

```
say <expr>
ask <expr> giving <name>
repeat <expr> times:
repeat <expr> time:
```

`say <expr>` is `print(<expr>)`. `ask <expr> giving <name>` evaluates
`<expr>` as a prompt, reads a line with `input(<expr>)`, and stores it
in `<name>`, which is declared as `String` — or assigned when it
exists — following the `is` rules in §11.1. `repeat <expr> times:` is
`for <hidden> in range(<expr>):`; the loop variable is
compiler-generated and cannot collide with user code.

Each form requires its full pattern. `say(x)` remains a call,
`repeat 3:` is a parse error (the `times`/`time` word is required),
and `ask "prompt"` without `giving <name>` is a parse error.

### 11.3 `otherwise`

```
if <cond>:
    ...
otherwise if <cond>:
    ...
otherwise:
    ...
```

`otherwise if` is `elif`; `otherwise` is `else`. They may be mixed
freely with `elif`/`else`. `otherwise` is only special directly after
an if/elif block; anywhere else it is an ordinary identifier.

### 11.4 `increase` / `decrease`

```
increase <name> [by <expr>]
decrease <name> [by <expr>]
```

`<name> = <name> + (<expr>)` and `<name> = <name> - (<expr>)`; the
amount defaults to `1`. The name must already exist (semantic error
otherwise), as with `set`.

### 11.5 English comparisons

In expressions:

```
<expr> is <expr>                          ==  ==
<expr> is not <expr>                      ==  !=
<expr> is greater than <expr>             ==  >
<expr> is less than <expr>                ==  <
<expr> is greater than or equal to <expr> ==  >=
<expr> is less than or equal to <expr>    ==  <=
```

Precedence is unchanged: `is` / `is not` bind at equality level,
`is greater|less than ...` at comparison level.

### 11.6 `to` functions

```
to <name>:
to <name> with <a>, <b> as <Type>:
to <name> with <a> as <Type> and returns <Type>:
```

Alias for `define function` (§4.1), allowed at top level and in class
bodies. Parameters are comma-separated `<name> [as <Type>]`; an
omitted type is dynamically typed. `to` inside a function body is a
parse error, like `define`.

### 11.7 Example

Before (statements from §4):

```agk
define function main:
    create i as Integer
    set i to 0
    while i < 3:
        print("hi")
        set i to i + 1
```

After (Simple AGK, §11):

```agk
to main:
    repeat 3 times:
        say "hi"
```

Both print:

```text
hi
hi
hi
```
