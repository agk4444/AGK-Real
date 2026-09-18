"""Level 3 — Semantic analysis tests (AGK-Real v1 test plan)."""

import pytest

from agk.parser import parse
from agk.semantic import analyze
from agk import ast_nodes as A
from agk.errors import SemanticError


def check(src):
    """Parse + analyze. Returns (program, warnings). Raises SemanticError."""
    prog = parse(src, filename="test.agk")
    return analyze(prog, filename="test.agk")


def fails_with(src, fragment):
    with pytest.raises(SemanticError) as exc:
        check(src)
    assert fragment in str(exc.value), str(exc.value)
    return str(exc.value)


# -- undefined names ------------------------------------------------------------

def test_undefined_variable_in_expression():
    msg = fails_with(
        "define function f:\n    return x\n", "undefined variable 'x'")
    assert "test.agk:2:" in msg


def test_set_on_undeclared_name():
    fails_with(
        "define function f:\n    set x to 1\n",
        "cannot set undefined variable 'x'")


def test_undefined_in_nested_block_reports_inner_line():
    msg = fails_with(
        "define function f:\n"
        "    create a as Boolean\n"
        "    set a to true\n"
        "    if a:\n"
        "        return nope\n",
        "undefined variable 'nope'")
    assert "test.agk:5:" in msg


def test_create_then_use_is_fine():
    prog, warnings = check(
        "define function f:\n    create x as Integer\n    set x to 1\n    return x\n")
    assert warnings == []


def test_duplicate_create_in_same_scope():
    fails_with(
        "define function f:\n    create x as Integer\n    create x as String\n",
        "already declared")


def test_param_counts_as_declared():
    prog, warnings = check(
        "define function f that takes x as Integer:\n    return x\n")
    assert warnings == []


# -- calls -------------------------------------------------------------------------

def test_call_unknown_function():
    fails_with(
        "define function f:\n    frobnicate(1)\n",
        "undefined function 'frobnicate'")


def test_call_wrong_arity_too_many():
    fails_with(
        "define function g that takes a as Integer:\n    return a\n"
        "define function f:\n    return g(1, 2)\n",
        "takes 1 argument(s), got 2")


def test_call_wrong_arity_too_few():
    fails_with(
        "define function g that takes a as Integer, b as Integer:\n    return a\n"
        "define function f:\n    return g(1)\n",
        "takes 2 argument(s), got 1")


def test_call_correct_arity_ok():
    prog, warnings = check(
        "define function g that takes a as Integer:\n    return a\n"
        "define function f:\n    return g(1)\n")
    assert warnings == []


def test_builtin_calls_ok():
    prog, warnings = check(
        'define function f:\n    print("hi")\n    create n as Integer\n'
        '    set n to len([1, 2])\n    return n\n')
    assert warnings == []


def test_method_call_on_attribute_not_checked():
    # obj.method(...) — can't verify arity, must not error
    prog, warnings = check(
        "define function f that takes obj as Object:\n    return obj.method(1, 2, 3)\n")
    assert warnings == []


# -- top-level duplicates ------------------------------------------------------------------

def test_duplicate_function():
    fails_with(
        "define function f:\n    return 1\ndefine function f:\n    return 2\n",
        "duplicate function 'f'")


def test_duplicate_class():
    fails_with(
        "define class A:\n    variable x as Integer\n"
        "define class A:\n    variable y as Integer\n",
        "duplicate class 'A'")


def test_duplicate_constant():
    fails_with(
        "define constant X as Integer = 1\ndefine constant X as Integer = 2\n",
        "duplicate constant 'X'")


def test_duplicate_param():
    fails_with(
        "define function f that takes a as Integer, a as String:\n    return a\n",
        "duplicate parameter 'a'")


def test_duplicate_field():
    fails_with(
        "define class C:\n    variable x as Integer\n    variable x as String\n",
        "duplicate field")


def test_function_shadowing_builtin():
    fails_with(
        "define function print:\n    return 1\n",
        "shadows a builtin")


# -- warnings ------------------------------------------------------------------------------------

def test_unused_variable_warning():
    prog, warnings = check(
        "define function f:\n    create x as Integer\n    set x to 1\n    return 2\n")
    assert len(warnings) == 1
    assert "unused variable 'x'" in warnings[0]
    assert "test.agk:2:" in warnings[0]


def test_never_assigned_warning():
    prog, warnings = check(
        "define function f:\n    create x as Integer\n    return 1\n")
    assert any("never assigned" in w for w in warnings)


def test_unreachable_code_warning():
    prog, warnings = check(
        "define function f:\n    return 1\n    return 2\n")
    assert any("unreachable code" in w for w in warnings)
    assert any("test.agk:3:" in w for w in warnings)


def test_no_warnings_for_clean_program():
    prog, warnings = check(
        "define function f that takes x as Integer:\n"
        "    create y as Integer\n"
        "    set y to x * 2\n"
        "    return y\n")
    assert warnings == []


# -- classes / field rewriting -------------------------------------------------------------------------

def test_bare_field_read_rewritten_to_self():
    prog, warnings = check(
        "define class Person:\n"
        "    variable name as String\n"
        "    define function greet that returns String:\n"
        "        return name\n")
    method = prog.statements[0].methods[0]
    ret = method.body[0]
    assert ret.value == A.Attribute(A.Name("self"), "name")


def test_set_field_rewritten_to_setattr():
    prog, warnings = check(
        "define class Person:\n"
        "    variable name as String\n"
        "    define constructor that takes n as String:\n"
        "        set name to n\n")
    ctor = prog.statements[0].constructor
    assert ctor.body[0] == A.SetAttr(A.Name("self"), "name", A.Name("n"))


def test_local_shadows_field():
    prog, warnings = check(
        "define class Person:\n"
        "    variable name as String\n"
        "    define function f:\n"
        "        create name as String\n"
        "        set name to \"x\"\n"
        "        return name\n")
    method = prog.statements[0].methods[0]
    # local variable: no self-rewrite
    assert method.body[1] == A.SetStmt("name", A.StringLit("x"))
    assert method.body[2].value == A.Name("name")


def test_constructor_call_arity_checked():
    fails_with(
        "define class Person:\n"
        "    define constructor that takes n as String:\n"
        "        return\n"
        "define function f:\n"
        "    create p as Object\n"
        "    set p to Person()\n"
        "    return p\n",
        "constructor of 'Person' takes 1 argument(s), got 0")


def test_constructor_call_ok():
    prog, warnings = check(
        "define class Person:\n"
        "    define constructor that takes n as String:\n"
        "        return\n"
        "define function f:\n"
        "    return Person(\"x\")\n")
    assert warnings == []


def test_self_usable_directly():
    prog, warnings = check(
        "define class C:\n"
        "    variable x as Integer\n"
        "    define function get that returns Integer:\n"
        "        return self.x\n")
    assert warnings == []


# -- imports / constants / loops ---------------------------------------------------------------------------

def test_import_name_usable():
    prog, warnings = check(
        "import math\n"
        "define function f:\n"
        "    return math.sqrt(4)\n")
    assert warnings == []


def test_constant_usable():
    prog, warnings = check(
        "define constant MAX as Integer = 10\n"
        "define function f:\n"
        "    return MAX\n")
    assert warnings == []


def test_for_each_var_usable_in_body():
    prog, warnings = check(
        "define function f that takes items as List:\n"
        "    for each item in items:\n"
        "        print(item)\n")
    assert warnings == []


def test_while_condition_checked():
    fails_with(
        "define function f:\n    while nope:\n        return 1\n",
        "undefined variable 'nope'")


# -- inheritance -----------------------------------------------------------------

def test_subclass_sets_inherited_field_ok():
    prog = parse(
        "define class Animal:\n"
        "    variable name as String\n"
        "define class Dog extends Animal:\n"
        "    define constructor that takes n as String:\n"
        "        set name to n\n")
    prog, warnings = analyze(prog)
    assert warnings == []


def test_inherited_field_rewritten_to_self():
    prog = parse(
        "define class Animal:\n"
        "    variable name as String\n"
        "define class Dog extends Animal:\n"
        "    define function get that returns String:\n"
        "        return name\n")
    prog, _ = analyze(prog)
    method = prog.statements[1].methods[0]
    assert isinstance(method.body[0].value, A.Attribute)


def test_undefined_base_class_errors():
    with pytest.raises(SemanticError, match="undefined base class 'Ghost'"):
        analyze(parse("define class Dog extends Ghost:\n"
                      "    variable name as String\n"))


def test_transitive_inherited_field():
    prog = parse(
        "define class A:\n"
        "    variable x as Integer\n"
        "define class B extends A:\n"
        "    variable y as Integer\n"
        "define class C extends B:\n"
        "    define function get that returns Integer:\n"
        "        return x\n")
    prog, warnings = analyze(prog)
    assert warnings == []


def test_subclass_may_redeclare_base_field():
    prog = parse(
        "define class A:\n"
        "    variable x as Integer\n"
        "define class B extends A:\n"
        "    variable x as String\n")
    _, warnings = analyze(prog)
    assert warnings == []
