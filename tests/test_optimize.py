"""Tests for the AST optimizer (agk/optimize.py).

Covers constant folding (including must-not-fold edge cases), dead-code
elimination after return/raise, dead-store elimination with side-effect
safety, the --no-opt CLI flag, and end-to-end output equivalence between
optimized and unoptimized compilation.
"""

from pathlib import Path

import pytest

from agk import ast_nodes as A
from agk.parser import parse
from agk.semantic import analyze
from agk.optimize import optimize_program
from agk.pipeline import compile_source, run_source
from agk.__main__ import main as cli_main

CORPUS = Path(__file__).parent / "corpus"


def opt_main_body(src):
    """Parse, analyze, optimize; return the optimized `main` body."""
    prog = parse(src)
    prog, _ = analyze(prog)
    optimize_program(prog)
    fn = next(s for s in prog.statements
              if isinstance(s, A.FunctionDef) and s.name == "main")
    return fn.body


def compiled(src, optimize):
    code, _ = compile_source(src, filename="t.agk", optimize=optimize)
    return code


def main_src(*lines):
    return "define function main:\n" + "".join("    " + ln + "\n"
                                              for ln in lines)


# -- constant folding ---------------------------------------------------

def test_fold_arithmetic_precedence():
    code = compiled(main_src("print(2 + 3 * 4)"), True)
    assert "print(14)" in code
    assert "2 + 3 * 4" in compiled(main_src("print(2 + 3 * 4)"), False)


def test_fold_parenthesized():
    assert "print(20)" in compiled(main_src("print((2 + 3) * 4)"), True)


def test_fold_string_concat():
    assert 'print("ab")' in compiled(main_src('print("a" + "b")'), True)


def test_fold_string_repeat():
    assert 'print("ababab")' in compiled(main_src('print("ab" * 3)'), True)


def test_fold_comparisons():
    code = compiled(main_src("print(3 > 2)", "print(1 == 2)",
                             "print(2 < 2.5)", 'print("a" != "b")'), True)
    assert "print(True)" in code
    assert "print(False)" in code


def test_fold_boolean_ops():
    code = compiled(main_src("print(true and false)", "print(true or false)",
                             "print(not true)"), True)
    assert code.count("print(True)") == 1
    assert code.count("print(False)") == 2


def test_fold_unary_minus_ast():
    body = opt_main_body(main_src("print(-5)"))
    arg = body[0].expr.args[0]
    assert isinstance(arg, A.IntLit) and arg.value == -5


def test_fold_division_is_float():
    body = opt_main_body(main_src("print(7 / 2)"))
    arg = body[0].expr.args[0]
    assert isinstance(arg, A.FloatLit) and arg.value == 3.5


def test_fold_nested():
    assert "print(10)" in compiled(main_src("print(1 + 2 + 3 + 4)"), True)


def test_fold_inside_condition():
    src = ('define function main:\n'
           '    if 1 + 1 == 2:\n'
           '        print("yes")\n')
    assert "if True:" in compiled(src, True)


def test_no_fold_division_by_zero():
    # 1/0 must stay a BinOp: folding it would turn a *runtime*
    # ZeroDivisionError into a *compile-time* crash.
    body = opt_main_body(main_src("print(1 / 0)"))
    assert isinstance(body[0].expr.args[0], A.BinOp)
    with pytest.raises(ZeroDivisionError):
        run_source(main_src("print(1 / 0)"), filename="t.agk", optimize=True)


def test_no_fold_modulo_by_zero():
    body = opt_main_body(main_src("print(10 % 0)"))
    assert isinstance(body[0].expr.args[0], A.BinOp)


def test_no_fold_float_division_by_zero():
    body = opt_main_body(main_src("print(1.0 / 0.0)"))
    assert isinstance(body[0].expr.args[0], A.BinOp)


def test_no_fold_type_mismatch():
    # "a" - "b" raises TypeError at run time; the compiler must not.
    body = opt_main_body(main_src('print("a" - "b")'))
    assert isinstance(body[0].expr.args[0], A.BinOp)
    code = compiled(main_src('print("a" - "b")'), True)  # must not raise
    assert "-" in code


def test_no_fold_call():
    src = ("define function f that returns Integer:\n"
           "    return 1\n"
           + main_src("print(f() + 1)"))
    prog = parse(src)
    prog, _ = analyze(prog)
    optimize_program(prog)
    fn = next(s for s in prog.statements
              if isinstance(s, A.FunctionDef) and s.name == "main")
    assert isinstance(fn.body[0].expr.args[0], A.BinOp)


def test_fold_stops_at_call_boundary():
    # 2 * 3 folds to 6, but f() + 6 must stay a BinOp (call: side effects).
    src = ("define function f that returns Integer:\n"
           "    return 1\n"
           + main_src("print(f() + 2 * 3)"))
    prog = parse(src)
    prog, _ = analyze(prog)
    optimize_program(prog)
    fn = next(s for s in prog.statements
              if isinstance(s, A.FunctionDef) and s.name == "main")
    outer = fn.body[0].expr.args[0]
    assert isinstance(outer, A.BinOp)
    assert isinstance(outer.left, A.Call)
    assert isinstance(outer.right, A.IntLit) and outer.right.value == 6


def test_no_fold_giant_string():
    # Folding "a" * 100000 must not allocate 100KB at compile time.
    body = opt_main_body(main_src('print("a" * 100000)'))
    assert isinstance(body[0].expr.args[0], A.BinOp)


def test_fold_does_not_produce_inf():
    # 1e308 * 10 overflows to inf; repr(inf) is not valid Python, so the
    # node must be left unfolded. (The lexer has no scientific notation;
    # build the AST directly.)
    from agk.optimize import _fold_expr
    node = A.BinOp(A.FloatLit(1e308), "*", A.FloatLit(10.0),
                   line=1, col=1)
    assert _fold_expr(node) is node


# -- dead-code elimination ----------------------------------------------

def test_dead_code_after_return():
    body = opt_main_body(main_src("print(1)", "return", 'print("gone")'))
    assert len(body) == 2
    assert isinstance(body[-1], A.ReturnStmt)


def test_dead_code_after_raise():
    body = opt_main_body(main_src('raise "boom"', "print(1)"))
    assert len(body) == 1
    assert isinstance(body[0], A.RaiseStmt)


def test_dead_code_in_branch():
    body = opt_main_body(main_src("if true:", "    return", '    print("gone")',
                                  'print("kept")'))
    then_body = body[0].then_body
    assert len(then_body) == 1
    assert len(body) == 2  # the if and the print after it survive


def test_code_before_return_kept():
    body = opt_main_body(main_src("print(1)", "print(2)", "return"))
    assert len(body) == 3


# -- dead-store elimination ---------------------------------------------

def test_unused_create_and_set_removed():
    code = compiled(main_src("create dead as Integer", "set dead to 99",
                             'print("hi")'), True)
    assert "dead" not in code
    assert 'print("hi")' in code


def test_used_variable_kept():
    code = compiled(main_src("create x as Integer", "set x to 41 + 1",
                             "print(x)"), True)
    assert "x = 42" in code
    assert "print(x)" in code


def test_unread_call_result_kept():
    # The call may have side effects: never drop it.
    src = ("define function f that returns Integer:\n"
           "    return 1\n"
           + main_src("create y as Integer", "set y to f()",
                      'print("hi")'))
    code = compiled(src, True)
    assert "y = f()" in code


def test_overwritten_store_first_removed():
    code = compiled(main_src("create x as Integer", "set x to 1",
                             "set x to 2", "print(x)"), True)
    assert "x = 2" in code
    assert "x = 1" not in code


def test_self_reading_store_kept():
    # set x to x + 1 reads x; dropping it could hide a NameError.
    body = opt_main_body(main_src("create x as Integer", "set x to x + 1"))
    assert len(body) == 2


def test_variable_read_in_later_branch_kept():
    body = opt_main_body(main_src("create x as Integer", "set x to 1",
                                  "if true:", "    print(x)"))
    assert any(isinstance(s, A.SetStmt) for s in body)


def test_store_used_by_while_condition_kept():
    body = opt_main_body(main_src(
        "create x as Integer", "set x to 0",
        "while x < 3:", "    print(x)", "    set x to x + 1"))
    assert any(isinstance(s, A.SetStmt) and s.name == "x" for s in body)
    loop = next(s for s in body if isinstance(s, A.WhileStmt))
    assert any(isinstance(s, A.SetStmt) for s in loop.body)


def test_try_except_liveness():
    body = opt_main_body(main_src(
        "create x as Integer",
        "try:", "    set x to 1",
        "catch:", "    print(x)"))
    try_stmt = next(s for s in body if isinstance(s, A.TryStmt))
    assert any(isinstance(s, A.SetStmt) for s in try_stmt.body)


def test_field_assignment_not_removed():
    # `set name to ...` on a class field becomes SetAttr: observable
    # object state, never a dead store.
    src = ("define class C:\n"
           "    variable name as String\n"
           "    define function set_name that takes v as String:\n"
           "        set name to v\n"
           + main_src('print("hi")'))
    code = compiled(src, True)
    assert "self.name = v" in code


# -- end-to-end equivalence ---------------------------------------------

def test_optimized_program_output():
    src = main_src(
        "create x as Integer",
        "set x to 2 + 3 * 4",
        "create unused as Integer",
        "set unused to 10 + 10",
        'print(x)',
        'print("a" + "b")',
        "if x > 10:",
        '    print("big")',
        "return",
        'print("never")')
    out_opt, _, _ = run_source(src, filename="t.agk", optimize=True)
    out_noopt, _, _ = run_source(src, filename="t.agk", optimize=False)
    assert out_opt == out_noopt == "14\nab\nbig\n"


@pytest.mark.parametrize("prog", sorted(CORPUS.glob("*.agk")),
                         ids=lambda p: p.stem)
def test_corpus_optimized_matches_unoptimized(prog):
    src = prog.read_text()
    expected = prog.with_suffix(".expected").read_text()
    out_opt, _, _ = run_source(src, filename=prog.name, optimize=True)
    out_noopt, _, _ = run_source(src, filename=prog.name, optimize=False)
    assert out_opt == out_noopt == expected


# -- CLI --no-opt --------------------------------------------------------

def _write(tmp_path, name, src):
    p = tmp_path / name
    p.write_text(src)
    return str(p)


def test_cli_run_no_opt(tmp_path, capsys):
    src = _write(tmp_path, "h.agk", main_src("print(2 + 3 * 4)"))
    assert cli_main(["run", "--no-opt", src]) == 0
    assert capsys.readouterr().out == "14\n"


def test_cli_build_no_opt(tmp_path):
    src = _write(tmp_path, "h.agk", main_src("print(2 + 3 * 4)"))
    out_opt = tmp_path / "opt.py"
    out_noopt = tmp_path / "noopt.py"
    assert cli_main(["build", src, "-o", str(out_opt)]) == 0
    assert cli_main(["build", "--no-opt", src, "-o", str(out_noopt)]) == 0
    assert "print(14)" in out_opt.read_text()
    assert "2 + 3 * 4" in out_noopt.read_text()


def test_cli_build_no_opt_cache_separation(tmp_path):
    # Builds with and without --no-opt must not share cache entries.
    src = _write(tmp_path, "h.agk", main_src("print(2 + 3 * 4)"))
    out1 = tmp_path / "a.py"
    out2 = tmp_path / "b.py"
    out3 = tmp_path / "c.py"
    assert cli_main(["build", "--no-opt", src, "-o", str(out1)]) == 0
    assert cli_main(["build", src, "-o", str(out2)]) == 0
    assert cli_main(["build", src, "-o", str(out3)]) == 0  # cache hit path
    assert "2 + 3 * 4" in out1.read_text()
    assert "print(14)" in out2.read_text()
    assert "print(14)" in out3.read_text()
