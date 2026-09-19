# Tutorial: your first AGK programs

This is a guided walkthrough. Each example is a complete program you can save to a `.agk` file and run with `agk run` — and each one has been compile-and-run verified.

**Contents**

- [[1. Hello|Tutorial#1-hello]]
- [[2. Simple AGK: the plain-English way|Tutorial#2-simple-agk-the-plain-english-way]]
- [[3. Variables|Tutorial#3-variables]]
- [[4. Functions|Tutorial#4-functions]]
- [[5. Branching|Tutorial#5-branching]]
- [[6. Loops|Tutorial#6-loops]]
- [[7. String interpolation|Tutorial#7-string-interpolation]]
- [[8. Classes|Tutorial#8-classes]]
- [[9. Errors that help|Tutorial#9-errors-that-help]]
- [[10. The standard library|Tutorial#10-the-standard-library]]
- [[11. Recursion|Tutorial#11-recursion]]
- [[Next steps|Tutorial#next-steps]]

## 1. Hello

Save this as `hello.agk` and run `agk run hello.agk`. Execution begins at `define function main:`.

<!-- verify: id=tutorial-hello output="hello, agk\n" -->
```agk
define function main:
    print("hello, agk")
```

## 2. Simple AGK: the plain-English way

Everything in this tutorial has a shorter spelling. Simple AGK is an
alias layer for beginners — each form below means exactly the same as
the longer form, and you can mix both styles freely.

<!-- verify: id=tutorial-simple output="hi\nhi\nhi\n" -->
```agk
to main:
    repeat 3 times:
        say "hi"
```

That is the whole program. Here is the same program in the long form
from §1:

<!-- verify: id=tutorial-simple-long output="hi\nhi\nhi\n" -->
```agk
define function main:
    create i as Integer
    set i to 0
    while i < 3:
        print("hi")
        set i to i + 1
```

Both print the same thing. The pieces:

- `to main:` instead of `define function main:`. With parameters:
  `to greet with name:` — add `as String` after a parameter when you
  want a type, and `and returns String` at the end for a return type.
- `name is value` instead of `create` + `set`: the first `is` declares
  the variable (the compiler infers the type), later ones just assign.
- `say` instead of `print`.
- `repeat 3 times:` instead of a `while` counter loop.
- `otherwise:` instead of `else`, `otherwise if` instead of `elif`.
- `increase score` / `decrease lives by 1` instead of
  `set score to score + 1`.
- Comparisons read as English: `is`, `is not`,
  `is greater than`, `is less than`, `is greater than or equal to`,
  `is less than or equal to`.

<!-- verify: id=tutorial-simple-guess output="too small\n" -->
```agk
to main:
    secret is 7
    guess is 5
    if guess is less than secret:
        say "too small"
    otherwise if guess is greater than secret:
        say "too big"
    otherwise:
        say "just right"
```

<!-- verify: id=tutorial-simple-score output="score is 5\n" -->
```agk
to main:
    score is 0
    repeat 3 times:
        increase score by 2
    decrease score
    say "score is {score}"
```

Almost nothing here is a reserved word: `say`, `repeat`, `increase`,
`otherwise` and friends still work as ordinary variable names, and
`say("hi")` still calls a function named `say`. (Only `to` was already
reserved.) When you outgrow the short forms, the long forms are always
there — both compile to the same code.

## 3. Variables

Declare with `create`, assign with `set`. (In a hurry? `name is value`
from §2 declares and assigns in one step.) Declared types are
statically checked: assigning a value of the wrong type is a compile
error.

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

## 4. Functions

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

## 5. Branching

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

## 6. Loops

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

## 7. String interpolation

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

## 8. Classes

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

## 9. Errors that help

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

## 10. The standard library

Twelve modules ship with the compiler. `import` one by name and its functions are inlined into your program — call them directly.

<!-- verify: id=tutorial-stdlib output="HELLO!\naa\n" -->
```agk
import strutils
import listutils

define function main:
    print(shout("hello"))
    print(repeat_string("a", 2))
```

See the [[standard library reference|Stdlib-Reference]] for all twenty-seven modules.

## 11. Recursion

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

- [[Language reference|Language-Reference]] — the full syntax contract, including exceptions, imports, and operator precedence.
- [[CLI reference|CLI-Reference]] — `agk run/build/check/test/fmt/repl` and the LSP server.
- Try `agk repl` for an interactive session, or `agk fmt --check` to see if a file matches canonical style.
