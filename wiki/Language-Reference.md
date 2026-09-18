# Language reference

The full syntax contract for AGK-Real v0.4.0, derived from `SPEC.md` (the v2 spec). Anything not in this reference is a compile error, not a silent miscompile. Every runnable example below is compile-and-run verified.

**Contents**

- [[Language-Reference#program-structure|Program structure]]
- [[Language-Reference#lexical-rules|Lexical rules]]
- [[Language-Reference#keywords|Keywords]]
- [[Language-Reference#functions|Functions]]
- [[Language-Reference#variables|Variables]]
- [[Language-Reference#constants|Constants]]
- [[Language-Reference#conditionals|Conditionals]]
- [[Language-Reference#loops|Loops]]
- [[Language-Reference#return|Return]]
- [[Language-Reference#classes|Classes]]
- [[Language-Reference#imports|Imports]]
- [[Language-Reference#expression-statements|Expression statements]]
- [[Language-Reference#exceptions|Exceptions]]
- [[Language-Reference#expressions--precedence|Expressions & precedence]]
- [[Language-Reference#name-resolution|Name resolution]]
- [[Language-Reference#code-generation|Code generation]]
- [[Language-Reference#error-format|Error format]]
- [[Language-Reference#new-in-040|New in 0.4.0]]
- [[Language-Reference#explicitly-out-of-scope|Explicitly out of scope]]

## Program structure

A program is a sequence of top-level statements: imports, constants, function definitions, class definitions. Execution begins at a `define function main:` if present; otherwise the top-level statements (imports, constants, definitions) are processed in order.

<!-- verify: id=ref-toplevel compile-only -->
```agk
define constant PI as Float = 3.14
```

## Lexical rules

- Comments start with `#` and run to end of line.
- String literals use double quotes: `"hello"`. Escapes: `\"`, `\\`, `\n`, `\t`.
- **String interpolation:** `{expr}` inside a string is evaluated and spliced in. Any expression may appear inside the braces, including quoted strings. `{{` and `}}` produce literal braces; a lone `{` or `}` is a parse error. A string with no interpolation is a plain literal.
- Integer literals: `42`. Float literals: `3.14`.
- Boolean literals: `true`, `false`.
- Indentation is significant: **4 spaces per level, tabs are an error**. Blank lines and comment-only lines do not affect indentation.
- Any other character (e.g. `?`, `$`, backtick) is a lexer error with `file:line:column`.

<!-- verify: id=ref-comments output="42\n" -->
```agk
# a comment runs to end of line
define function main:
    # comments can live inside blocks too
    create n as Integer  # and trail a statement
    set n to 40 + 2
    print(n)
```

<!-- verify: id=ref-interp output="Gopi has 4 letters\n{literal} and 3\n{Gopi}\n" -->
```agk
define function main:
    create name as String
    set name to "Gopi"
    print("{name} has {len(name)} letters")
    print("{{literal}} and {1 + 2}")
    print("{{{name}}}")
```

> [!NOTE]
> Nested braces (e.g. dict or set literals) and quoted strings inside an interpolation are a parse error in the current implementation — only `{{`/`}}` doubling and the `{{{name}}}` mixed form are supported.

## Keywords

```text
define function that takes and returns
create set to constant
if elif else while for each in from step return
class variable constructor extends implements
import try catch finally raise
and or not true false
```

Type names are ordinary identifiers by convention: `Integer Float String Boolean List Object`. They carry no runtime meaning (documented intent only); the compiler records them but does not type-check.

## Functions

```text
define function <name>:
define function <name> that takes <a> as <Type>, <b> as <Type>:
define function <name> that takes <a> as <Type> and returns <Type>:
define function <name> that returns <Type>:
```

The body is an indented block. `and returns <Type>` is optional documentation.

<!-- verify: id=ref-func output="42\n" -->
```agk
define function add that takes a as Integer, b as Integer and returns Integer:
    return a + b

define function main:
    print(add(20, 22))
```

### Default parameter values

Any parameter may declare a default. Defaults must be literals (number, string, boolean; numbers may be negated). Interpolated strings are not allowed as defaults. Parameters with defaults must come after all parameters without defaults. Calls may omit trailing defaulted arguments; omitting a required argument or passing too many is a semantic error. Constructors follow the same rules.

<!-- verify: id=ref-defaults output="Hello, World!\nHello, Gopi!\nHello, Gopi?\n" -->
```agk
define function greet that takes name as String = "World", punct as String = "!":
    print("Hello, {name}{punct}")

define function main:
    greet()
    greet("Gopi")
    greet("Gopi", "?")
```

<!-- verify: id=ref-defaults-error error="parameter 'b' without a default follows a parameter with a default" -->
```agk
define function bad that takes a as Integer = 1, b as Integer:
    return a
```

## Variables

```text
create <name> as <Type>
set <name> to <expr>
```

`create` introduces the name in the current scope; `set` requires the name to already exist (semantic error otherwise). Re-declaring a name in the same scope is an error.

<!-- verify: id=ref-vars output="agk\n42\n" -->
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

<!-- verify: id=ref-set-error error="cannot set undefined variable 'naem'" -->
```agk
define function main:
    create name as String
    set naem to "oops"
```

## Constants

Top level only. The value must be a literal (int, float, string, boolean). Emitted as a module-level Python assignment.

```text
define constant <NAME> as <Type> = <expr>
```

<!-- verify: id=ref-const output="3.14\n" -->
```agk
define constant PI as Float = 3.14

define function main:
    print(PI)
```

## Conditionals

<!-- verify: id=ref-if output="B\n" -->
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

`elif` may repeat; `else` is optional and last.

## Loops

<!-- verify: id=ref-while output="3\n2\n1\nliftoff\n" -->
```agk
define function main:
    create i as Integer
    set i to 3
    while i > 0:
        print(i)
        set i to i - 1
    print("liftoff")
```

<!-- verify: id=ref-for-each output="60\n" -->
```agk
define function main:
    create total as Integer
    set total to 0
    for each x in [10, 20, 30]:
        set total to total + x
    print(total)
```

`for each x in …` and `for x in …` are equivalent (short form).

<!-- verify: id=ref-for-short output="a\nb\n" -->
```agk
define function main:
    for w in ["a", "b"]:
        print(w)
```

The range form is **inclusive** of the end value. Default step is 1. A negative step counts down, also inclusive. The step may be any expression; its sign is honoured at runtime.

<!-- verify: id=ref-for-range output="1\n2\n3\n" -->
```agk
define function main:
    for i from 1 to 3:
        print(i)
```

<!-- verify: id=ref-for-step output="10\n7\n4\n1\n" -->
```agk
define function main:
    for i from 10 to 1 step -3:
        print(i)
```

## Return

```text
return <expr>
return
```

Outside a function, `return` is an error:

<!-- verify: id=ref-return-error error="unexpected 'return' at top level" -->
```agk
return 1
```

## Classes

```text
define class <Name>:
    variable <field> as <Type>
    define constructor that takes <a> as <Type>:
        ...
    define function <method> that takes <a> as <Type>:
        ...
```

- `extends <Base>` after the class name enables single inheritance.
- `implements` is a parse error (reserved for later).
- Inside methods, fields are accessed as `self.<field>` — the compiler rewrites bare field names to `self.<field>` automatically.
- Subclass methods see inherited fields transitively (a subclass constructor may `set` a field declared on the base class).
- `extends` on a class not defined in the file is a semantic error.

<!-- verify: id=ref-class output="2\n" -->
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

<!-- verify: id=ref-extends output="rex\nwoof\n" -->
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

<!-- verify: id=ref-extends-error error="undefined base class 'Nope'" -->
```agk
define class A extends Nope:
    variable x as Integer
```

<!-- verify: id=ref-implements-error error="'implements' is not supported" -->
```agk
define class A implements B:
    variable x as Integer
```

## Imports

`import <module>` imports a Python module. `import a.b` (dotted names) is supported and always means a Python import.

<!-- verify: id=ref-import-py output="3\n" -->
```agk
import math

define function main:
    print(math.floor(3.7))
```

<!-- verify: id=ref-import-dotted output="a/b\n" -->
```agk
import os.path

define function main:
    print(os.path.join("a", "b"))
```

### AGK module imports

If `<name>.agk` is found next to the importing file, in a configured search path, or in the bundled stdlib, the module is compiled and inlined: its functions, classes, and constants become directly callable and the `import` line emits nothing. Otherwise the import falls through to a plain Python `import <name>`. Circular `.agk` imports are tolerated (resolved once).

<!-- verify: id=ref-import-agk output="DONE!\n" -->
```agk
import strutils

define function main:
    print(shout("done"))
```

A bare `import sys` passes straight through to the generated Python untouched, so command-line arguments work in compiled programs (`sys.argv[0]` is the program path, `sys.argv[1:]` the user args — same as Python):

<!-- verify: id=ref-argv args="one two" output="one\ntwo\n" -->
```agk
import sys

define function main:
    create i as Integer
    set i to 1
    while i < len(sys.argv):
        print(sys.argv[i])
        set i to i + 1
```

## Expression statements

A bare expression as a statement — in practice a call such as `print("hello")`. The value is discarded.

<!-- verify: id=ref-expr-stmt output="side effect\n3\n" -->
```agk
define function main:
    print("side effect")
    1 + 2
    print(1 + 2)
```

## Exceptions

<!-- verify: id=ref-try output="caught: negative!\ncleanup runs\n" -->
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

- `catch <name>:` binds the caught exception to `<name>` (available only inside the catch block). A bare `catch:` catches without binding.
- `finally:` is optional and runs whether or not an exception occurred.
- A `try` requires at least one of `catch` / `finally`.
- `raise <expr>` raises an exception; a bare `raise` re-raises the exception currently being handled (valid only inside a `catch` block). A string message is raised as `Exception(message)`; any other value is raised as-is (so `raise err` re-raises the caught exception object).
- Only `Exception` subclasses are caught (matching Python semantics).

<!-- verify: id=ref-reraise output="re-raised: boom\n" -->
```agk
define function main:
    try:
        try:
            raise "boom"
        catch:
            raise
    catch err:
        print("re-raised: {err}")
```

<!-- verify: id=ref-try-error error="expected 'catch' or 'finally' after 'try' block" -->
```agk
define function main:
    try:
        print("x")
```

## Expressions & precedence

Precedence, highest to lowest:

1. Literals, names, parenthesised `( <expr> )`
2. Calls `<expr>(<args>)`, attribute access `<expr>.<name>`, indexing `<expr>[<expr>]`
3. Unary `-x`, `not x`
4. `*`, `/`, `%`
5. `+`, `-`
6. `<`, `>`, `<=`, `>=`
7. `==`, `!=`
8. `and`
9. `or`

List literal: `[1, 2, 3]`. Dict literal: `{"a": 1}`.

<!-- verify: id=ref-precedence output="7\n9\nTrue\n" -->
```agk
define function main:
    print(1 + 2 * 3)
    print((1 + 2) * 3)
    print(not false and true)
```

<!-- verify: id=ref-collections output="4\ngopi\n" -->
```agk
define function main:
    create xs as List
    set xs to [1, 2, 3]
    print(xs[0] + xs[2])
    create user as Object
    set user to {"name": "gopi", "id": 7}
    print(user["name"])
```

## Name resolution

- `set` / use of an undeclared name → error naming the variable and line.
- `create` of an already-declared name in the same scope → error.
- Function called with wrong argument count → error. With defaulted parameters the message gives the allowed range (e.g. `takes 1 to 2 arguments, got 0`); without defaults it gives the exact count.
- A parameter without a default may not follow one with a default.
- `return` outside a function → error.
- Unused variable, unreachable code after `return` → warnings (non-fatal, printed to stderr).
- Undefined names get a **"did you mean?"** suggestion when a close candidate exists (searched among variables in scope, declared functions, classes, and builtins). With no close candidate the base message is unchanged. Applies to undefined variables, `set` on undeclared names, undefined function calls, and undefined base classes.

```text
hello.agk:3:4: semantic error: cannot set undefined variable 'greting'. did you mean 'greeting'?
hello.agk:2:10: semantic error: undefined function 'fobar'. did you mean 'foobar'?
hello.agk:3:15: semantic error: undefined variable 'zzz'
```

## Code generation

AGK compiles to plain Python 3.9+ with no AGK runtime dependency. Key mappings:

| AGK | Python |
|---|---|
| `define function f that takes a as Integer:` | `def f(a):` |
| `define function g that takes n as Integer = 3:` | `def g(n=3):` |
| `create x as Integer` | (declaration only; no output until `set`) |
| `set x to 1` | `x = 1` |
| `define constant PI as Float = 3.14` | `PI = 3.14` |
| `"Hello, {name}!"` | `"Hello, {}!".format(name)` |
| `"{{literal}}"` | `"{literal}"` |
| `for i from 1 to 3:` | `for i in range(1, (3) + 1):` |
| `for i from 10 to 1 step -3:` | `for i in range(10, <end>, -3):` (inclusive both directions) |
| `try:` / `catch e:` / `catch:` / `finally:` | `try:` / `except Exception as e:` / `except Exception:` / `finally:` |
| `raise "boom"` / `raise` | `raise Exception("boom")` / `raise` (bare re-raise) |
| `true` / `false`, `and` / `or` / `not` | `True` / `False`, direct mapping |
| class / constructor / variable | `class`, `__init__`, `self.` fields |

`agk run` compiles with per-line AGK source annotations and rewrites runtime tracebacks to `.agk` file/line form, so a crash points at the AGK source, never at generated Python internals.

## Error format

Compile errors print as `file.agk:line:column: <phase>: <message>` on stderr and exit non-zero. No Python tracebacks ever reach the user at compile time. Runtime errors under `agk run` are rendered as AGK-source tracebacks (`file.agk:line` frames) followed by the exception message:

```text
Traceback (most recent call last):
  File "boom.agk", line 4, in main
    fail()
  File "boom.agk", line 2, in fail
    print(1 / 0)
ZeroDivisionError: division by zero
```

## New in 0.4.0

> These features shipped in 0.4.0 and are fully compilable. Every example below is verified.

### async / await

Asynchronous functions and awaiting asynchronous calls. An async `main` runs via `asyncio.run`.

```agk
define async function fetch that takes url as String and returns String:
    create body as String
    set body to await http_get(url)
    return body
```

`await` outside an async function is a compile error.

### Generators

`yield` inside a function makes it a generator; ordinary `for` loops consume it lazily.

```agk
define function countdown that takes n as Integer:
    while n > 0:
        yield n
        set n to n - 1
```

### Decorators

`@name` / `@name(args)` lines above a function definition apply a Python decorator, resolved through normal scope lookup.

```agk
@timer
define function slow:
    print("working")
```

### extern

Foreign-function declarations binding C functions from shared libraries, compiled to `ctypes` calls.

```agk
extern function strlen that takes s as String and returns Integer from "c"
```

Type mapping: String→c_char_p (utf-8), Integer→c_int, Float→c_double, Boolean→c_bool.

### Static typing

Declared annotations are now checked: the compiler rejects provable type misuses as compile errors with `file:line`. Unannotated code is unaffected; `Object` accepts anything.

```agk
define function add that takes a as Integer, b as Integer and returns Integer:
    return a + b
```

## Explicitly out of scope

Each of these is a clean parse error if attempted:

- Multi-target codegen (JS/Kotlin/…)
- Ternary `?:`
- Slices, comprehensions, operator overloading, lambdas
- `implements` (reserved for later)
