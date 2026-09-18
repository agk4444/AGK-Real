"""AGK-Real v0.6.0 — Simple AGK surface tests.

Covers parse shapes, desugaring, inference, error cases, backward
compatibility (no previously valid program changes meaning), and a
runnable end-to-end program exercising all eight Simple AGK features.
"""

import pytest

from agk.parser import parse
from agk import ast_nodes as A
from agk.errors import ParserError, SemanticError, TypeCheckError as TypecheckError
from agk.pipeline import run_source, compile_source


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


def stmts(src):
    return fn_body("    " + src.replace("\n", "\n    ") + "\n")


# -- `x is <expr>`: parse shapes -------------------------------------------

def test_is_int_declares_and_assigns():
    create, assign = stmts("x is 5")
    assert create == A.CreateStmt("x", "Integer", soft=True)
    assert assign == A.SetStmt("x", A.IntLit(5))


def test_is_infers_literal_types():
    cases = [
        ("x is 5", "Integer"),
        ("x is 1.5", "Float"),
        ('x is "hi"', "String"),
        ("x is true", "Boolean"),
        ("x is [1, 2]", "List"),
        ('x is {"a": 1}', "Dict"),
    ]
    for src, want in cases:
        create, _assign = stmts(src)
        assert create.type_name == want, src


def test_is_nonliteral_is_dynamic():
    create, _assign = stmts("x is foo()")
    assert create.type_name is None
    create, _assign = stmts("y is a + b")
    assert create.type_name is None


def test_is_redeclare_is_assignment_not_error():
    # two `is` statements: first declares, second assigns
    create1, assign1, create2, assign2 = stmts("x is 5\nx is 6")
    assert create2.soft is True
    assert assign2 == A.SetStmt("x", A.IntLit(6))


def test_is_statement_comparison_carveout():
    # `x is not 5` reads as a comparison, not a declaration
    s = stmt("x is not 5")
    assert isinstance(s, A.ExprStmt)
    assert s.expr == A.BinOp(A.Name("x"), "!=", A.IntLit(5))
    s = stmt("x is greater than 5")
    assert isinstance(s, A.ExprStmt)
    assert s.expr == A.BinOp(A.Name("x"), ">", A.IntLit(5))


# -- `say` ------------------------------------------------------------------

def test_say_desugars_to_print():
    s = stmt('say "hello"')
    assert isinstance(s, A.ExprStmt)
    assert s.expr == A.Call(A.Name("print"), [A.StringLit("hello")])


def test_say_expression():
    s = stmt("say 1 + 2")
    assert s.expr.args[0] == A.BinOp(A.IntLit(1), "+", A.IntLit(2))


# -- `ask ... giving` -------------------------------------------------------

def test_ask_desugars_to_input():
    create, assign = stmts('ask "name? " giving who')
    assert create == A.CreateStmt("who", "String", soft=True)
    assert isinstance(assign, A.SetStmt)
    assert assign.name == "who"
    assert assign.value == A.Call(A.Name("input"),
                                  [A.StringLit("name? ")])


def test_ask_requires_giving_name():
    with pytest.raises(ParserError):
        p("define function f:\n    ask \"name? \"\n")
    with pytest.raises(ParserError):
        p("define function f:\n    ask \"name? \" giving\n")


# -- `repeat` ---------------------------------------------------------------

def test_repeat_times_desugars_to_foreach_range():
    s = stmt("repeat 3 times:\n    say \"hi\"")
    assert isinstance(s, A.ForEachStmt)
    assert s.var.startswith("__agk_repeat_")
    assert s.iterable == A.Call(A.Name("range"), [A.IntLit(3)])
    assert len(s.body) == 1


def test_repeat_time_singular_ok():
    s = stmt("repeat 1 time:\n    say \"hi\"")
    assert isinstance(s, A.ForEachStmt)


def test_repeat_requires_times():
    with pytest.raises(ParserError):
        p("define function f:\n    repeat 3:\n        say \"hi\"\n")


def test_repeat_hidden_vars_are_unique():
    s1, s2 = stmts("repeat 2 times:\n    say 1\nrepeat 2 times:\n    say 2")
    assert s1.var != s2.var


# -- `otherwise` ------------------------------------------------------------

def test_otherwise_becomes_else():
    s = stmt("if a:\n    say 1\notherwise:\n    say 2")
    assert isinstance(s, A.IfStmt)
    assert s.else_body is not None
    assert s.elifs == []


def test_otherwise_if_becomes_elif():
    s = stmt("if a:\n    say 1\notherwise if b:\n    say 2\notherwise:\n    say 3")
    assert isinstance(s, A.IfStmt)
    assert len(s.elifs) == 1
    assert s.else_body is not None


def test_otherwise_mixes_with_elif_else():
    s = stmt("if a:\n    say 1\nelif b:\n    say 2\notherwise:\n    say 3")
    assert isinstance(s, A.IfStmt)
    assert len(s.elifs) == 1
    assert s.else_body is not None


def test_otherwise_outside_if_is_error():
    with pytest.raises(ParserError):
        p("define function f:\n    otherwise:\n        say 1\n")


# -- `increase` / `decrease` -------------------------------------------------

def test_increase_defaults_to_one():
    s = stmt("increase x")
    assert s == A.SetStmt("x", A.BinOp(A.Name("x"), "+", A.IntLit(1)))


def test_increase_by_expr():
    s = stmt("increase x by 2 + 3")
    assert s == A.SetStmt("x", A.BinOp(A.Name("x"), "+",
                                       A.BinOp(A.IntLit(2), "+",
                                               A.IntLit(3))))


def test_decrease_by():
    s = stmt("decrease x by n")
    assert s == A.SetStmt("x", A.BinOp(A.Name("x"), "-", A.Name("n")))


def test_decrease_defaults_to_one():
    s = stmt("decrease x")
    assert s == A.SetStmt("x", A.BinOp(A.Name("x"), "-", A.IntLit(1)))


def test_increase_bare_name_is_variable_reference():
    # `increase` alone is just a variable read (undefined here) —
    # the keyword form needs a name after it
    with pytest.raises(SemanticError, match="undefined variable 'increase'"):
        compile_source("define function f:\n    increase\n")


# -- `to` functions ----------------------------------------------------------

def test_to_simple():
    prog = p("to main:\n    say \"hi\"\n")
    fn = prog.statements[0]
    assert isinstance(fn, A.FunctionDef)
    assert fn.name == "main"
    assert fn.params == []
    assert fn.return_type is None


def test_to_with_untyped_params():
    prog = p("to greet with name:\n    say name\n")
    fn = prog.statements[0]
    assert [q.name for q in fn.params] == ["name"]
    assert fn.params[0].type_name is None


def test_to_with_typed_params_and_returns():
    prog = p("to add with a as Integer, b as Integer and returns Integer:\n"
             "    return a + b\n")
    fn = prog.statements[0]
    assert [(q.name, q.type_name) for q in fn.params] == [
        ("a", "Integer"), ("b", "Integer")]
    assert fn.return_type == "Integer"


def test_to_inside_function_is_error():
    with pytest.raises(ParserError):
        p("define function f:\n    to g:\n        say 1\n")


def test_to_as_method():
    prog = p("define class C:\n    to greet with name:\n        say name\n")
    cls = prog.statements[0]
    assert isinstance(cls, A.ClassDef)
    assert cls.methods[0].name == "greet"


# -- expression-level `is` comparisons ---------------------------------------

def test_is_equality():
    create, assign = stmts("x is 1")
    # statement position: declaration, not comparison
    assert isinstance(create, A.CreateStmt)
    assert assign == A.SetStmt("x", A.IntLit(1))
    _c2, assign2 = stmts("y is (x is 1)")
    assert assign2.value == A.BinOp(A.Name("x"), "==", A.IntLit(1))


def test_is_not():
    expr = fn_body("    y is (x is not 1)\n")[1].value
    assert expr == A.BinOp(A.Name("x"), "!=", A.IntLit(1))


def test_english_ordering_comparisons():
    cases = [
        ("x is greater than y", ">"),
        ("x is less than y", "<"),
        ("x is greater than or equal to y", ">="),
        ("x is less than or equal to y", "<="),
    ]
    for src, want in cases:
        expr = fn_body(f"    y is ({src})\n")[1].value
        assert expr == A.BinOp(A.Name("x"), want, A.Name("y")), src


def test_english_comparison_in_if_condition():
    s = stmt("if x is greater than 3:\n    say 1")
    assert isinstance(s, A.IfStmt)
    assert s.condition == A.BinOp(A.Name("x"), ">", A.IntLit(3))


# -- backward compatibility -------------------------------------------------

def test_say_call_preserved():
    s = stmt('say("hi")')
    assert s == A.ExprStmt(A.Call(A.Name("say"), [A.StringLit("hi")]))


def test_increase_call_preserved():
    s = stmt("increase(x)")
    assert s == A.ExprStmt(A.Call(A.Name("increase"), [A.Name("x")]))


def test_repeat_call_preserved():
    s = stmt("repeat(x)")
    assert s == A.ExprStmt(A.Call(A.Name("repeat"), [A.Name("x")]))


def test_alias_words_still_work_as_variables():
    for word in ("say", "ask", "repeat", "increase", "decrease",
                 "otherwise", "giving", "times", "time", "by",
                 "greater", "than", "less", "equal"):
        create, assign = stmts(f"{word} is 1")
        assert create.name == word
        assert assign.name == word


def test_old_forms_still_parse():
    prog = p("define function main:\n"
             "    create x as Integer\n"
             "    set x to 1\n"
             "    print(x)\n"
             "    while x < 3:\n"
             "        set x to x + 1\n"
             "    if x == 3:\n"
             "        print(\"done\")\n"
             "    elif x == 2:\n"
             "        print(\"two\")\n"
             "    else:\n"
             "        print(\"other\")\n"
             "    for i in [1, 2]:\n"
             "        print(i)\n")
    assert len(prog.statements) == 1


def test_equals_still_rejected():
    with pytest.raises(ParserError, match="unexpected '='"):
        p("define function f:\n    x = 5\n")


# -- semantic analysis -------------------------------------------------------

def test_soft_redeclare_never_errors():
    compile_source("define function f:\n"
                   "    x is 5\n"
                   "    x is 6\n"
                   "    create y as Integer\n"
                   "    set y to 1\n"
                   "    y is 2\n")


def test_hard_redeclare_still_errors():
    with pytest.raises(SemanticError, match="already declared"):
        compile_source("define function f:\n"
                       "    x is 5\n"
                       "    create x as Integer\n")


def test_increase_undeclared_is_error():
    with pytest.raises(SemanticError, match="undefined variable 'x'"):
        compile_source("define function f:\n    increase x\n")


def test_repeat_hidden_var_no_unused_warning():
    _code, warnings = compile_source(
        "define function f:\n    repeat 3 times:\n        print(1)\n")
    assert not [w for w in warnings if "__agk_repeat_" in w]


def test_is_inside_method_assigns_field():
    code, _warnings = compile_source(
        "define class C:\n"
        "    variable count as Integer\n"
        "    define constructor:\n"
        "        set count to 0\n"
        "    to bump:\n"
        "        count is 5\n")
    assert "self.count = 5" in code


# -- type checking -----------------------------------------------------------

def test_soft_redeclare_type_mismatch_still_errors():
    with pytest.raises(TypecheckError):
        compile_source("define function f:\n"
                       "    x is 5\n"
                       "    x is \"hi\"\n")


def test_soft_redeclare_same_type_ok():
    compile_source("define function f:\n"
                   "    x is 5\n"
                   "    x is 6\n")


def test_dynamic_is_accepts_anything():
    # literal inference is checked like `set`: same-type reassignment is fine
    compile_source("define function f:\n"
                   "    x is [1]\n"
                   "    x is [2, 3]\n")
    compile_source("define function getval:\n"
                   "    return 1\n"
                   "define function f:\n"
                   "    x is getval()\n"
                   "    x is \"hi\"\n"
                   "    x is 5\n")


def test_ask_giving_is_string_typed():
    code, _warnings = compile_source(
        "define function f:\n    ask \"n? \" giving name\n")
    assert "name = input(" in code


# -- end to end --------------------------------------------------------------

ALL_EIGHT = """\
to greet with name:
    say "hello, " + name + "!"

define function main:
    ask "what is your name? " giving name
    greet(name)
    count is 0
    repeat 3 times:
        increase count
        say "count is {count}"
    decrease count by 2
    if count is greater than 0:
        say "positive"
    otherwise if count is less than 0:
        say "negative"
    otherwise:
        say "zero"
    if count is not 99:
        say "confirmed"
    if count is greater than or equal to 1:
        say "at least one"
    if count is less than or equal to 1:
        say "at most one"
"""

ALL_EIGHT_EXPECTED = """\
hello, gopi!
count is 1
count is 2
count is 3
positive
confirmed
at least one
at most one
"""


def test_e2e_all_eight_features(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _prompt="": "gopi")
    stdout, _ns, _warnings = run_source(ALL_EIGHT, filename="all_eight.agk")
    assert stdout == ALL_EIGHT_EXPECTED


BEFORE = """\
define function main:
    create i as Integer
    set i to 0
    while i < 3:
        print("hi")
        set i to i + 1
"""

AFTER = """\
to main:
    repeat 3 times:
        say "hi"
"""


def test_before_after_demo_same_output():
    before_out, _ns, _w = run_source(BEFORE, filename="before.agk")
    after_out, _ns2, _w2 = run_source(AFTER, filename="after.agk")
    assert before_out == "hi\nhi\nhi\n"
    assert after_out == before_out


# -- REPL --------------------------------------------------------------------

def test_repl_is_assigns_not_compares(capsys):
    from agk.repl import Session
    s = Session()
    s.handle("x is 5\n")
    s.handle("x\n")
    assert capsys.readouterr().out == "5\n"
    s.handle("x is 10\n")
    s.handle("x\n")
    assert capsys.readouterr().out == "10\n"


def test_repl_is_not_stays_comparison(capsys):
    from agk.repl import Session
    s = Session()
    s.handle("x is 5\n")
    s.handle("x is not 6\n")
    assert capsys.readouterr().out == "True\n"


def test_repl_simple_forms(capsys):
    from agk.repl import Session
    s = Session()
    s.handle('say "hi"\n')
    assert capsys.readouterr().out == "hi\n"
    s.handle("n is 0\n")
    s.handle("increase n\n")
    s.handle("n\n")
    assert capsys.readouterr().out == "1\n"
    s.handle("repeat 2 times:\n    say \"yo\"\n")
    assert capsys.readouterr().out == "yo\nyo\n"
    # expression-first behavior is unchanged for plain expressions
    s.handle("1 + 2\n")
    assert capsys.readouterr().out == "3\n"


def test_optimizer_keeps_literal_store_before_self_read(capsys):
    # Regression: `x is 5` followed by `x is x + 1` must not lose the
    # first store to dead-store elimination (the soft redeclare is a
    # no-op and must not kill liveness).
    stdout, _ns, _w = run_source(
        "define function main:\n"
        "    x is 5\n"
        "    x is x + 1\n"
        "    print(x)\n")
    assert stdout == "6\n"
