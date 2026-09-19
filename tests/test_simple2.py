"""AGK-Real v0.7.0 — Simple AGK complete-coverage tests.

Every classic construct now has a Simple AGK form. These tests cover the
v0.7.0 additions: simple `class`, `<name> as <Type>` fields, simple
`constructor`, `constant <NAME> is <literal>`, `each <name> in`, `repeat
with <name> from ... to ...`, `async to`, default values in `to` params,
and `use ... from "<lib>"` (FFI). Each form desugars to the existing AST,
so semantic analysis and codegen are exercised through run_source.
"""

import pytest

from agk.parser import parse
from agk import ast_nodes as A
from agk.errors import ParserError
from agk.pipeline import run_source


def p(src):
    return parse(src, filename="test.agk")


def run(src):
    stdout, _ns, warnings = run_source(src, filename="test.agk")
    assert warnings == []
    return stdout


# -- simple `class` ------------------------------------------------------

def test_simple_class_parse_shape():
    prog = p("class Dog:\n"
             "    name as String\n"
             "    constructor with n as String:\n"
             "        set name to n\n"
             "    to bark:\n"
             "        return name\n")
    cls = prog.statements[0]
    assert isinstance(cls, A.ClassDef)
    assert cls.name == "Dog"
    assert cls.base is None
    assert cls.fields == [A.FieldDecl("name", "String")]
    assert isinstance(cls.constructor, A.ConstructorDef)
    assert [par.name for par in cls.constructor.params] == ["n"]
    assert [m.name for m in cls.methods] == ["bark"]


def test_simple_class_extends():
    prog = p("class Puppy extends Dog:\n"
             "    to squeak:\n"
             "        return 1\n")
    cls = prog.statements[0]
    assert cls.base == "Dog"


def test_simple_class_runs():
    out = run(
        "class Counter:\n"
        "    n as Integer\n"
        "    constructor:\n"
        "        set n to 0\n"
        "    to bump:\n"
        "        set n to n + 1\n"
        "    to value:\n"
        "        return n\n"
        "to main:\n"
        "    c is Counter()\n"
        "    c.bump()\n"
        "    c.bump()\n"
        "    say c.value()\n")
    assert out == "2\n"


def test_simple_class_inheritance_runs():
    out = run(
        "class Animal:\n"
        "    name as String\n"
        "    constructor with n as String:\n"
        "        set name to n\n"
        "    to speak:\n"
        "        return \"...\"\n"
        "class Dog extends Animal:\n"
        "    to speak:\n"
        "        return name + \" woof\"\n"
        "to main:\n"
        "    d is Dog(\"rex\")\n"
        "    say d.speak()\n")
    assert out == "rex woof\n"


def test_classic_and_simple_members_mix():
    out = run(
        "define class Mixed:\n"
        "    variable a as Integer\n"
        "    b as String\n"
        "    define constructor that takes x as Integer:\n"
        "        set a to x\n"
        "    to get_a:\n"
        "        return a\n"
        "to main:\n"
        "    m is Mixed(7)\n"
        "    say m.get_a()\n")
    assert out == "7\n"


def test_simple_duplicate_constructor_errors():
    with pytest.raises(ParserError, match="duplicate constructor"):
        p("class C:\n"
          "    constructor:\n"
          "        return\n"
          "    constructor:\n"
          "        return\n")


def test_simple_class_needs_name():
    with pytest.raises(ParserError, match="expected class name"):
        p("class:\n    pass\n")


# -- `constant <NAME> is <literal>` --------------------------------------

def test_simple_constant_parse_shape():
    prog = p("constant Pi is 3.14\n")
    c = prog.statements[0]
    assert isinstance(c, A.ConstantDef)
    assert c.name == "Pi"
    assert c.type_name == "Float"
    assert c.value == A.FloatLit(3.14)


def test_simple_constant_types():
    cases = [("constant A is 1\n", "Integer"),
             ("constant B is 2.5\n", "Float"),
             ("constant C is \"x\"\n", "String"),
             ("constant D is true\n", "Boolean")]
    for src, want in cases:
        assert p(src).statements[0].type_name == want, src


def test_simple_constant_runs():
    out = run("constant Pi is 3.14\n"
              "to main:\n"
              "    say Pi * 2\n")
    assert out == "6.28\n"


def test_simple_constant_rejects_non_literal():
    with pytest.raises(ParserError, match="must be a single literal"):
        p("constant X is 1 + 2\n")


# -- `each <name> in <expr>:` --------------------------------------------

def test_each_parse_shape():
    prog = p("define function f:\n"
             "    each item in cart:\n"
             "        print(item)\n")
    loop = prog.statements[0].body[0]
    assert isinstance(loop, A.ForEachStmt)
    assert loop.var == "item"


def test_each_runs():
    out = run("to main:\n"
              "    total is 0\n"
              "    each n in [1, 2, 3]:\n"
              "        increase total by n\n"
              "    say total\n")
    assert out == "6\n"


# -- `repeat with <name> from ... to ...` --------------------------------

def test_repeat_with_parse_shape():
    prog = p("define function f:\n"
             "    repeat with i from 1 to 5:\n"
             "        print(i)\n")
    loop = prog.statements[0].body[0]
    assert isinstance(loop, A.ForRangeStmt)
    assert loop.var == "i"
    assert loop.start == A.IntLit(1)
    assert loop.end == A.IntLit(5)
    assert loop.step is None


def test_repeat_with_step():
    prog = p("define function f:\n"
             "    repeat with i from 10 to 1 step -2:\n"
             "        print(i)\n")
    loop = prog.statements[0].body[0]
    assert isinstance(loop.step, A.UnaryOp)


def test_repeat_with_runs():
    out = run("to main:\n"
              "    repeat with i from 1 to 3:\n"
              "        say i\n"
              "    repeat with j from 10 to 1 step -3:\n"
              "        say j\n")
    assert out == "1\n2\n3\n10\n7\n4\n1\n"


def test_repeat_counted_form_unchanged():
    # `repeat <expr> times:` still desugars to the hidden-variable loop.
    out = run("to main:\n"
              "    repeat 3 times:\n"
              "        say \"hi\"\n")
    assert out == "hi\nhi\nhi\n"


# -- `async to` ----------------------------------------------------------

def test_async_to_parse_shape():
    prog = p("async to fetch with url as String:\n"
             "    return url\n")
    fn = prog.statements[0]
    assert isinstance(fn, A.FunctionDef)
    assert fn.is_async is True
    assert fn.name == "fetch"


def test_async_to_runs():
    out = run("async to fetch with url as String:\n"
              "    return \"got \" + url\n"
              "async to main:\n"
              "    say await fetch(\"x\")\n")
    assert out == "got x\n"


def test_async_to_method_runs():
    out = run("class Worker:\n"
              "    async to run with x as Integer:\n"
              "        return x * 2\n"
              "async to main:\n"
              "    w is Worker()\n"
              "    say await w.run(21)\n")
    assert out == "42\n"


# -- defaults in `to` params ---------------------------------------------

def test_to_param_defaults():
    prog = p("to greet with name as String = \"World\", n as Integer = 3:\n"
             "    return name\n")
    params = prog.statements[0].params
    assert params[0].default == A.StringLit("World")
    assert params[1].default == A.IntLit(3)


def test_to_param_default_without_type():
    prog = p("to greet with name = \"World\":\n"
             "    return name\n")
    param = prog.statements[0].params[0]
    assert param.type_name is None
    assert param.default == A.StringLit("World")


def test_to_defaults_run():
    out = run("to greet with name = \"World\":\n"
              "    return \"hi \" + name\n"
              "to main:\n"
              "    say greet()\n"
              "    say greet(\"Gopi\")\n")
    assert out == "hi World\nhi Gopi\n"


# -- `use ... from "<lib>"` (FFI) ----------------------------------------

def test_use_parse_shape():
    prog = p("use strlen with s as String and returns Integer from \"c\"\n")
    ext = prog.statements[0]
    assert isinstance(ext, A.ExternDef)
    assert ext.name == "strlen"
    assert ext.lib == "c"
    assert ext.return_type == "Integer"
    assert [(q.name, q.type_name) for q in ext.params] == [("s", "String")]


def test_use_rejects_defaults():
    with pytest.raises(ParserError, match="default"):
        p("use f with x as Integer = 1 from \"c\"\n")


# -- REPL ----------------------------------------------------------------

def _repl_run(chunks):
    from agk.repl import Session
    import io
    from contextlib import redirect_stdout
    s = Session()
    buf = io.StringIO()
    with redirect_stdout(buf):
        for c in chunks:
            s.handle(c)
    return buf.getvalue()


def test_repl_simple_top_level_forms():
    # v0.7.0: `constant`, `use`, and `async to` route to top-level
    # parsing in the REPL, like their classic twins.
    out = _repl_run([
        "constant Tax is 2\n",
        "class Box:\n"
        "    w as Integer\n"
        "    constructor with v as Integer:\n"
        "        set w to v\n"
        "    to area:\n"
        "        return w * w\n",
        "b is Box(5)\n",
        "b.area()\n",
        "each x in [1, 2]:\n    say x\n",
        "use strlen with s as String and returns Integer from \"c\"\n",
        "strlen(\"hey\")\n",
    ])
    assert "25\n" in out
    assert "1\n2\n" in out
    assert "3\n" in out


def test_repl_simple_constant_remembered():
    out = _repl_run(["constant Tax is 2\n", "Tax * 3\n"])
    assert "6" in out


def test_repl_async_to():
    out = _repl_run([
        "async to fetch with u as String:\n    return u\n",
    ])
    assert "error" not in out

def test_everything_simple_end_to_end():
    out = run(
        "constant Pi is 3\n"
        "class Dog:\n"
        "    name as String\n"
        "    constructor with n as String:\n"
        "        set name to n\n"
        "    to bark:\n"
        "        return name + \" woof\"\n"
        "to loud with s as String = \"hi\":\n"
        "    return s + \"!\"\n"
        "to main:\n"
        "    say Pi\n"
        "    d is Dog(\"rex\")\n"
        "    say d.bark()\n"
        "    say loud()\n"
        "    total is 0\n"
        "    each n in [1, 2]:\n"
        "        increase total by n\n"
        "    say total\n"
        "    repeat with i from 1 to 2:\n"
        "        say i\n")
    assert out == "3\nrex woof\nhi!\n3\n1\n2\n"
