# Tutorial: your first AGK programs

This is a guided walkthrough. Each example is a complete program you can save to a `.agk` file and run with `agk run` — and each one has been compile-and-run verified.

**Contents**

- [[Tutorial#1-hello|1. Hello]]
- [[Tutorial#2-variables|2. Variables]]
- [[Tutorial#3-functions|3. Functions]]
- [[Tutorial#4-branching|4. Branching]]
- [[Tutorial#5-loops|5. Loops]]
- [[Tutorial#6-string-interpolation|6. String interpolation]]
- [[Tutorial#7-classes|7. Classes]]
- [[Tutorial#8-errors-that-help|8. Errors that help]]
- [[Tutorial#9-the-standard-library|9. The standard library]]
- [[Tutorial#10-recursion|10. Recursion]]
- [[Tutorial#next-steps|Next steps]]

## 1. Hello

Save this as `hello.agk` and run `agk run hello.agk`. Execution begins at `define function main:`.

<!-- verify: id=tutorial-hello output="hello, agk\n" -->
```agk
define function main:
    print("hello, agk")
```

## 2. Variables

Declare with `create`, assign with `set`. Types (`Integer`, `String`, …) are documented intent — the compiler records them but does not type-check.

<!-- verify: id=tutorial-vars output="agk\n42\n" -->
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

## 3. Functions

The `that takes …` and `and returns …` clauses are optional documentation. Calling with the wrong number of arguments is a compile error.

<!-- verify: id=tutorial-functions output="42\n" -->
```agk
define function add that takes a as Integer, b as Integer and returns Integer:
    return a + b

define function main:
    print(add(20, 22))
```

Parameters can have default values (literals only), which callers may omit:

<!-- verify: id=tutorial-defaults output="Hello, World!\nHello, Gopi!\nHello, Gopi?\n" -->
```agk
define function greet that takes name as String = "World", punct as String = "!":
    print("Hello, {name}{punct}")

define function main:
    greet()
    greet("Gopi")
    greet("Gopi", "?")
```

## 4. Branching

<!-- verify: id=tutorial-branching output="B\n" -->
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

## 5. Loops

`while` works as you'd expect. The range form of `for` is **inclusive** of the end value, and counts down when the step is negative:

<!-- verify: id=tutorial-loops output="3\n2\n1\nliftoff\n60\n1\n2\n3\n4\n5\n10\n7\n4\n1\n" -->
```agk
define function main:
    create i as Integer
    set i to 3
    while i > 0:
        print(i)
        set i to i - 1
    print("liftoff")
    create total as Integer
    set total to 0
    for each x in [10, 20, 30]:
        set total to total + x
    print(total)
    for i from 1 to 5:
        print(i)
    for i from 10 to 1 step -3:
        print(i)
```

The `each` in `for each x in …` is optional.

## 6. String interpolation

Any `{expression}` inside a string is evaluated and spliced in. Double the braces (`{{`, `}}`) for a literal brace; a lone `{` or `}` is a compile error.

<!-- verify: id=tutorial-interp output="Hello, Gopi!\n1 + 2 = 3\n{braces stay literal}\n" -->
```agk
define function main:
    create name as String
    set name to "Gopi"
    print("Hello, {name}!")
    print("1 + 2 = {1 + 2}")
    print("{{braces stay literal}}")
```

## 7. Classes

Fields are declared with `variable`. Inside methods, just name the field — the compiler rewrites it to `self.<field>` for you. `extends` gives single inheritance.

<!-- verify: id=tutorial-classes output="2\n" -->
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

<!-- verify: id=tutorial-extends output="rex\nwoof\n" -->
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

## 8. Errors that help

A `set` without a `create` is a compile error — this catches typos instead of crashing at runtime. Misspell a name and the compiler suggests the closest known one:

<!-- verify: id=tutorial-error error="cannot set undefined variable 'naem'. did you mean 'name'?" -->
```agk
define function main:
    create name as String
    set naem to "oops"
```

Errors always name the file, line, and column — never a traceback:

```text
hello.agk:2:9: semantic error: cannot set undefined variable 'naem'. did you mean 'name'?
```

## 9. The standard library

Twelve modules ship with the compiler. `import` one by name and its functions are inlined into your program — call them directly.

<!-- verify: id=tutorial-stdlib output="HELLO!\naa\n" -->
```agk
import strutils
import listutils

define function main:
    print(shout("hello"))
    print(repeat_string("a", 2))
```

See the [[Stdlib-Reference|standard library reference]] for all twelve modules.

## 10. Recursion

<!-- verify: id=tutorial-recursion output="55\n" -->
```agk
define function fib that takes n as Integer and returns Integer:
    if n <= 1:
        return n
    else:
        return fib(n - 1) + fib(n - 2)

define function main:
    print(fib(10))
```

## Next steps

- [[Language-Reference|Language reference]] — the full syntax contract, including exceptions, imports, and operator precedence.
- [[CLI-Reference|CLI reference]] — `agk run/build/check/test/fmt/repl` and the LSP server.
- Try `agk repl` for an interactive session, or `agk fmt --check` to see if a file matches canonical style.
