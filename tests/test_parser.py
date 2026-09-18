"""Level 2 — Parser unit tests (AGK-Real v1 test plan).

Asserts AST shapes structurally via dataclass equality.
"""

import pytest

from agk.parser import parse
from agk import ast_nodes as A
from agk.errors import ParserError


def p(src):
    return parse(src, filename="test.agk")


def fn_body(src):
    """Parse `define function f:` + src and return the body statements."""
    prog = p("define function f:\n" + src)
    return prog.statements[0].body


def stmt(src):
    body = fn_body("    " + src.replace("\n", "\n    ") + "\n")
    assert len(body) == 1
    return body[0]


# -- top level ------------------------------------------------------------

def test_empty_program():
    assert p("") == A.Program([])
    assert p("# only a comment\n\n") == A.Program([])


def test_import():
    assert p("import math\n") == A.Program([A.Import("math")])


def test_dotted_import():
    assert p("import os.path\n") == A.Program([A.Import("os.path")])


def test_top_level_rejects_bare_statement():
    with pytest.raises(ParserError):
        p("set x to 1\n")


def test_top_level_rejects_garbage_after_define():
    with pytest.raises(ParserError) as exc:
        p("define frobnicate\n")
    assert "test.agk:1:" in str(exc.value)


# -- constants --------------------------------------------------------------

def test_constant_int():
    assert p("define constant MAX as Integer = 100\n") == A.Program(
        [A.ConstantDef("MAX", "Integer", A.IntLit(100))])


def test_constant_float_string_bool():
    prog = p('define constant PI as Float = 3.14\n'
             'define constant NAME as String = "agk"\n'
             'define constant FLAG as Boolean = true\n')
    assert prog.statements[1] == A.ConstantDef("NAME", "String", A.StringLit("agk"))
    assert prog.statements[2] == A.ConstantDef("FLAG", "Boolean", A.BoolLit(True))


def test_constant_rejects_non_literal():
    with pytest.raises(ParserError) as exc:
        p("define constant X as Integer = 1 + 2\n")
    assert "literal" in str(exc.value)


def test_constant_rejects_name_value():
    with pytest.raises(ParserError):
        p("define constant X as Integer = other\n")


# -- functions ----------------------------------------------------------------

def test_bare_function():
    prog = p("define function f:\n    return 1\n")
    assert prog == A.Program([
        A.FunctionDef("f", [], None, [A.ReturnStmt(A.IntLit(1))])])


def test_function_with_params():
    prog = p("define function add that takes a as Integer, b as Integer:\n"
             "    return a\n")
    f = prog.statements[0]
    assert f.name == "add"
    assert f.params == [A.Param("a", "Integer"), A.Param("b", "Integer")]
    assert f.return_type is None


def test_function_with_params_and_returns():
    prog = p("define function add that takes a as Integer and returns Integer:\n"
             "    return a\n")
    f = prog.statements[0]
    assert f.params == [A.Param("a", "Integer")]
    assert f.return_type == "Integer"


def test_function_returns_only():
    prog = p("define function f that returns String:\n    return \"x\"\n")
    f = prog.statements[0]
    assert f.params == [] and f.return_type == "String"


def test_function_missing_colon():
    with pytest.raises(ParserError) as exc:
        p("define function f\n    return 1\n")
    assert "':'" in str(exc.value)


def test_function_missing_name():
    with pytest.raises(ParserError):
        p("define function:\n    return 1\n")


def test_function_empty_body_rejected():
    with pytest.raises(ParserError):
        p("define function f:\n")


# -- create / set ---------------------------------------------------------------

def test_create():
    assert stmt("create x as Integer") == A.CreateStmt("x", "Integer")


def test_set():
    assert stmt("set x to 42") == A.SetStmt("x", A.IntLit(42))


def test_set_expression():
    assert stmt("set x to a + b * 2") == A.SetStmt(
        "x", A.BinOp(A.Name("a"), "+", A.BinOp(A.Name("b"), "*", A.IntLit(2))))


def test_lone_equals_hint():
    with pytest.raises(ParserError) as exc:
        p("define function f:\n    x = 1\n")
    assert "set <name> to <expr>" in str(exc.value)


# -- if / elif / else --------------------------------------------------------------

def test_if_else():
    s = stmt("if x > 5:\n    return 1\nelse:\n    return 2")
    assert s == A.IfStmt(
        A.BinOp(A.Name("x"), ">", A.IntLit(5)),
        [A.ReturnStmt(A.IntLit(1))], [], [A.ReturnStmt(A.IntLit(2))])


def test_if_without_else():
    s = stmt("if x:\n    return 1")
    assert s.else_body is None and s.elifs == []


def test_elif_chain():
    s = stmt("if a:\n    return 1\nelif b:\n    return 2\nelif c:\n    return 3\nelse:\n    return 4")
    assert len(s.elifs) == 2
    assert s.elifs[0][0] == A.Name("b")
    assert s.elifs[1][1] == [A.ReturnStmt(A.IntLit(3))]
    assert s.else_body == [A.ReturnStmt(A.IntLit(4))]


def test_if_missing_colon():
    with pytest.raises(ParserError):
        p("define function f:\n    if x\n        return 1\n")


# -- loops --------------------------------------------------------------------------

def test_while():
    s = stmt("while i > 0:\n    set i to i - 1")
    assert s == A.WhileStmt(
        A.BinOp(A.Name("i"), ">", A.IntLit(0)),
        [A.SetStmt("i", A.BinOp(A.Name("i"), "-", A.IntLit(1)))])


def test_for_each():
    s = stmt("for each item in items:\n    return item")
    assert s == A.ForEachStmt("item", A.Name("items"),
                             [A.ReturnStmt(A.Name("item"))])


def test_for_each_over_call():
    s = stmt("for each k in d.keys():\n    return k")
    assert s.iterable == A.Call(A.Attribute(A.Name("d"), "keys"), [])


def test_for_allows_bare_in_and_each():
    # v2: `for item in items` is the short form; `for each item in` still works.
    s = stmt("for item in items:\n    return item")
    assert isinstance(s, A.ForEachStmt) and s.var == "item"
    s = stmt("for each item in items:\n    return item")
    assert isinstance(s, A.ForEachStmt) and s.var == "item"


# -- return ----------------------------------------------------------------------------

def test_return_bare():
    assert stmt("return") == A.ReturnStmt(None)


def test_return_in_nested_block():
    body = fn_body("    if x:\n        return 1\n")
    assert body[0].then_body == [A.ReturnStmt(A.IntLit(1))]


# -- expression statements ----------------------------------------------------------------

def test_call_as_statement():
    assert stmt('print("hi")') == A.ExprStmt(
        A.Call(A.Name("print"), [A.StringLit("hi")]))


# -- expression precedence ------------------------------------------------------------------

def test_add_mul_precedence():
    assert stmt("set x to 1 + 2 * 3").value == A.BinOp(
        A.IntLit(1), "+", A.BinOp(A.IntLit(2), "*", A.IntLit(3)))


def test_parens_override():
    assert stmt("set x to (1 + 2) * 3").value == A.BinOp(
        A.BinOp(A.IntLit(1), "+", A.IntLit(2)), "*", A.IntLit(3))


def test_sub_div_mod():
    assert stmt("set x to a - b / c % d").value == A.BinOp(
        A.Name("a"), "-",
        A.BinOp(A.BinOp(A.Name("b"), "/", A.Name("c")), "%", A.Name("d")))


def test_comparison_binds_tighter_than_equality():
    assert stmt("set x to a < b == c").value == A.BinOp(
        A.BinOp(A.Name("a"), "<", A.Name("b")), "==", A.Name("c"))


def test_equality_binds_tighter_than_and():
    assert stmt("set x to a == b and c").value == A.BinOp(
        A.BinOp(A.Name("a"), "==", A.Name("b")), "and", A.Name("c"))


def test_and_binds_tighter_than_or():
    assert stmt("set x to a or b and c").value == A.BinOp(
        A.Name("a"), "or", A.BinOp(A.Name("b"), "and", A.Name("c")))


def test_unary_minus_and_not():
    assert stmt("set x to -a").value == A.UnaryOp("-", A.Name("a"))
    assert stmt("set x to not a and b").value == A.BinOp(
        A.UnaryOp("not", A.Name("a")), "and", A.Name("b"))


def test_lte_gte_neq():
    assert stmt("set x to a <= b").value.op == "<="
    assert stmt("set x to a >= b").value.op == ">="
    assert stmt("set x to a != b").value.op == "!="


def test_string_concat_and_bool_lits():
    assert stmt('set x to "a" + "b"').value == A.BinOp(
        A.StringLit("a"), "+", A.StringLit("b"))
    assert stmt("set x to true").value == A.BoolLit(True)
    assert stmt("set x to false").value == A.BoolLit(False)


def test_float_literal():
    assert stmt("set x to 2.5").value == A.FloatLit(2.5)


def test_call_attribute_index_postfix():
    e = stmt("set x to obj.method(a, 1)[0]").value
    assert e == A.Index(
        A.Call(A.Attribute(A.Name("obj"), "method"),
               [A.Name("a"), A.IntLit(1)]),
        A.IntLit(0))


def test_chained_call():
    e = stmt("set x to f(g(1))").value
    assert e == A.Call(A.Name("f"), [A.Call(A.Name("g"), [A.IntLit(1)])])


def test_list_literal():
    assert stmt("set x to [1, 2, 3]").value == A.ListLit(
        [A.IntLit(1), A.IntLit(2), A.IntLit(3)])
    assert stmt("set x to []").value == A.ListLit([])


def test_dict_literal():
    assert stmt('set x to {"a": 1}').value == A.DictLit(
        [(A.StringLit("a"), A.IntLit(1))])
    assert stmt("set x to {}").value == A.DictLit([])


def test_expected_expression_error():
    with pytest.raises(ParserError) as exc:
        p("define function f:\n    set x to \n")
    assert "expected expression" in str(exc.value)


def test_unclosed_paren():
    with pytest.raises(ParserError):
        p("define function f:\n    set x to (1 + 2\n")


def test_unclosed_bracket():
    with pytest.raises(ParserError):
        p("define function f:\n    set x to [1, 2\n")


# -- classes -------------------------------------------------------------------------------

def test_class_fields_only():
    prog = p("define class Person:\n"
             "    variable name as String\n"
             "    variable age as Integer\n")
    c = prog.statements[0]
    assert c == A.ClassDef("Person", None,
                           [A.FieldDecl("name", "String"),
                            A.FieldDecl("age", "Integer")],
                           None, [])


def test_class_extends():
    prog = p("define class Dog extends Animal:\n"
             "    variable name as String\n")
    assert prog.statements[0].base == "Animal"


def test_class_implements_rejected():
    with pytest.raises(ParserError) as exc:
        p("define class C implements I:\n    variable x as Integer\n")
    assert "v1" in str(exc.value)


def test_class_constructor():
    prog = p("define class Person:\n"
             "    variable name as String\n"
             "    define constructor that takes n as String:\n"
             "        set name to n\n")
    c = prog.statements[0]
    assert c.constructor == A.ConstructorDef(
        [A.Param("n", "String")], [A.SetStmt("name", A.Name("n"))])


def test_class_method():
    prog = p("define class Person:\n"
             "    variable name as String\n"
             "    define function greet that returns String:\n"
             '        return "hi"\n')
    c = prog.statements[0]
    assert len(c.methods) == 1
    assert c.methods[0].name == "greet"
    assert c.methods[0].return_type == "String"


def test_class_rejects_bare_statement():
    with pytest.raises(ParserError):
        p("define class C:\n    set x to 1\n")


def test_class_duplicate_constructor():
    with pytest.raises(ParserError):
        p("define class C:\n"
          "    define constructor:\n        return\n"
          "    define constructor:\n        return\n")


# -- nesting ----------------------------------------------------------------------------------

def test_three_level_nesting():
    body = fn_body(
        "    while i > 0:\n"
        "        if done:\n"
        "            return i\n"
        "        set i to i - 1\n")
    w = body[0]
    assert isinstance(w, A.WhileStmt)
    assert isinstance(w.body[0], A.IfStmt)
    assert w.body[0].then_body == [A.ReturnStmt(A.Name("i"))]
    assert w.body[1] == A.SetStmt("i",
                                  A.BinOp(A.Name("i"), "-", A.IntLit(1)))


def test_if_inside_for_inside_function():
    prog = p("define function f that takes items as List:\n"
             "    for each item in items:\n"
             "        if item > 0:\n"
             "            return item\n"
             "    return 0\n")
    f = prog.statements[0]
    loop = f.body[0]
    assert isinstance(loop, A.ForEachStmt)
    assert isinstance(loop.body[0], A.IfStmt)
    assert f.body[1] == A.ReturnStmt(A.IntLit(0))


# -- error positions ----------------------------------------------------------------------------

def test_error_position_in_nested_block():
    with pytest.raises(ParserError) as exc:
        p("define function f:\n    if x:\n        set y to\n")
    assert "test.agk:3:" in str(exc.value)


def test_unexpected_eof_in_block():
    with pytest.raises(ParserError):
        p("define function f:\n    if x:")


def test_define_inside_function_rejected():
    with pytest.raises(ParserError) as exc:
        p("define function f:\n    define function g:\n        return 1\n")
    assert "top level" in str(exc.value)
