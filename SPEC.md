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
```

Type names are ordinary identifiers by convention: `Integer Float String
Boolean List Object`. They carry no runtime meaning (documented intent
only); the compiler records them but does not type-check.

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

## 5. Expressions (precedence, highest to lowest)

1. Literals, names, parenthesised `( <expr> )`
2. Calls: `<expr>(<args>)`, attribute access: `<expr>.<name>`,
   indexing: `<expr>[<expr>]`
3. Unary `-x`, `not x`
4. `*`, `/`, `%`
5. `+`, `-`
6. `<`, `>`, `<=`, `>=`
7. `==`, `!=`
8. `and`
9. `or`

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
- Unused variable, unreachable code after `return` → warnings (non-fatal).

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
compile time. Runtime errors under `agk run` are rendered as AGK-source
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

## 10. Explicitly out of v2

Multi-target codegen (JS/Kotlin/…), ternary `?:`, decorators,
`implements`, slices, comprehensions, operator overloading, lambdas.
Each is a clean parse error if attempted.
