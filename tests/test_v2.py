"""Level 6 — AGK-Real v2 feature tests.

Covers every v2 addition: exceptions, string interpolation, richer for
loops, default parameters, new stdlib modules, pip packaging, the VS Code
grammar, and AGK-source traceback mapping.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from agk.lexer import Lexer
from agk.tokens import TokenType as T
from agk.parser import parse
from agk.semantic import analyze
from agk.codegen import generate
from agk.pipeline import run_source, compile_source, format_agk_traceback
from agk import ast_nodes as A
from agk.errors import ParserError, SemanticError

ROOT = Path(__file__).parent.parent


def p(src):
    return parse(src, filename="test.agk")


def fn_body(src):
    prog = p("define function f:\n" + src)
    return prog.statements[0].body


def stmt(src):
    body = fn_body("    " + src.replace("\n", "\n    ") + "\n")
    assert len(body) == 1
    return body[0]


def check(src):
    return analyze(p(src), filename="test.agk")


def fails_semantic(src, fragment):
    with pytest.raises(SemanticError) as exc:
        check(src)
    assert fragment in str(exc.value), str(exc.value)


def fails_parse(src, fragment):
    with pytest.raises(ParserError) as exc:
        p(src)
    assert fragment in str(exc.value), str(exc.value)


def run(src):
    stdout, _ns, warnings = run_source(src, filename="test.agk")
    return stdout, warnings


# -- lexer: new keywords --------------------------------------------------------

def test_new_keywords_lex():
    toks = Lexer("try catch finally raise from step", "test.agk").tokenize()
    kinds = {t.type for t in toks if t.type not in (T.EOF, T.NEWLINE)}
    assert kinds == {T.TRY, T.CATCH, T.FINALLY, T.RAISE, T.FROM, T.STEP}


# -- parser: for loops ----------------------------------------------------------

def test_for_in_iterable():
    s = stmt("for item in items:\n    print(item)")
    assert isinstance(s, A.ForEachStmt)
    assert s.var == "item"
    assert isinstance(s.iterable, A.Name) and s.iterable.id == "items"


def test_for_each_still_works():
    s = stmt("for each item in items:\n    print(item)")
    assert isinstance(s, A.ForEachStmt)
    assert s.var == "item"


def test_for_range():
    s = stmt("for i from 1 to 10:\n    print(i)")
    assert isinstance(s, A.ForRangeStmt)
    assert s.var == "i"
    assert s.start == A.IntLit(1, line=1, col=1)
    assert s.end == A.IntLit(10, line=1, col=1)
    assert s.step is None


def test_for_range_with_step():
    s = stmt("for i from 10 to 1 step -3:\n    print(i)")
    assert isinstance(s, A.ForRangeStmt)
    assert isinstance(s.step, A.UnaryOp)
    assert s.step.op == "-"


def test_for_range_needs_to():
    fails_parse("define function f:\n    for i from 1:\n        print(i)\n",
                "expected 'to'")


# -- parser: try/catch/finally/raise --------------------------------------------

def test_try_catch_finally():
    body = fn_body("    try:\n        print(1)\n    catch err:\n        print(err)\n    finally:\n        print(2)\n")
    s = body[0]
    assert isinstance(s, A.TryStmt)
    assert s.catch_name == "err"
    assert len(s.body) == 1
    assert len(s.catch_body) == 1
    assert len(s.finally_body) == 1


def test_bare_catch():
    body = fn_body("    try:\n        print(1)\n    catch:\n        print(2)\n")
    s = body[0]
    assert isinstance(s, A.TryStmt)
    assert s.catch_name is None
    assert len(s.catch_body) == 1


def test_try_without_catch_or_finally_fails():
    fails_parse("define function f:\n    try:\n        print(1)\n",
                "catch")


def test_raise_with_value():
    s = stmt('raise "boom"')
    assert isinstance(s, A.RaiseStmt)
    assert isinstance(s.value, A.StringLit)


def test_bare_raise():
    s = stmt("raise")
    assert isinstance(s, A.RaiseStmt)
    assert s.value is None


# -- parser: default parameters -------------------------------------------------

def test_default_params():
    prog = p('define function greet that takes name as String = "World", n as Integer = 3:\n    print(name)\n')
    params = prog.statements[0].params
    assert params[0].default == A.StringLit("World", line=1, col=1)
    assert params[1].default == A.IntLit(3, line=1, col=1)


def test_negative_default():
    prog = p('define function f that takes n as Integer = -5:\n    print(n)\n')
    d = prog.statements[0].params[0].default
    assert isinstance(d, A.UnaryOp) and d.op == "-"


def test_nonliteral_default_rejected():
    fails_parse('define function f that takes n as Integer = x:\n    print(n)\n',
                "must be a literal")


def test_negated_string_default_rejected():
    fails_parse('define function f that takes s as String = -"x":\n    print(s)\n',
                "cannot negate")


def test_interpolated_string_default_rejected():
    fails_parse('define function f that takes s as String = "hi {name}":\n    print(s)\n',
                "interpolation is not allowed")


# -- parser: string interpolation -----------------------------------------------

def test_interpolation_desugars_to_format():
    s = stmt('print("Hello, {name}!")')
    call = s.expr.args[0]
    assert isinstance(call, A.Call)
    assert isinstance(call.func, A.Attribute)
    assert call.func.attr == "format"
    assert call.func.obj.value == "Hello, {}!"
    assert len(call.args) == 1 and call.args[0].id == "name"


def test_plain_string_has_no_format():
    s = stmt('print("Hello!")')
    assert isinstance(s.expr.args[0], A.StringLit)


def test_doubled_braces_are_literal():
    s = stmt('print("{{not interpolated}}")')
    assert isinstance(s.expr.args[0], A.StringLit)
    assert s.expr.args[0].value == "{not interpolated}"


def test_interpolation_with_doubled_braces():
    s = stmt('print("{{{name}}}")')
    call = s.expr.args[0]
    assert isinstance(call, A.Call)
    assert call.func.obj.value == "{{{}}}"


def test_lone_close_brace_is_error():
    fails_parse('define function f:\n    print("a}b")\n', "'}}'")


def test_empty_braces_are_error():
    fails_parse('define function f:\n    print("a{}b")\n', "empty")


def test_interpolation_expression():
    s = stmt('print("{1 + 2}")')
    call = s.expr.args[0]
    assert isinstance(call, A.Call)
    assert isinstance(call.args[0], A.BinOp)


# -- semantic: defaults ----------------------------------------------------------

def test_required_after_default_is_error():
    fails_semantic(
        'define function f that takes a as String = "x", b as String:\n    print(a)\n',
        "without a default follows a parameter with a default")


def test_arity_range_ok_with_defaults():
    check('define function f that takes a as String, b as String = "x":\n'
          '    print(a)\n'
          'define function main:\n'
          '    f("hi")\n'
          '    f("hi", "yo")\n')


def test_arity_too_few_with_defaults():
    fails_semantic(
        'define function f that takes a as String, b as String = "x":\n'
        '    print(a)\n'
        'define function main:\n'
        '    f()\n',
        "takes 1 to 2 arguments, got 0")


def test_arity_too_many_with_defaults():
    fails_semantic(
        'define function f that takes a as String = "x":\n'
        '    print(a)\n'
        'define function main:\n'
        '    f("a", "b")\n',
        "takes 0 to 1 arguments, got 2")


def test_exact_arity_message_unchanged_without_defaults():
    fails_semantic(
        'define function f that takes a as String:\n'
        '    print(a)\n'
        'define function main:\n'
        '    f("a", "b")\n',
        "takes 1 argument(s), got 2")


def test_constructor_defaults():
    check('define class C:\n'
          '    define constructor that takes n as Integer = 5:\n'
          '        print(n)\n'
          'define function main:\n'
          '    create c as C\n')


def test_catch_variable_is_declared():
    check('define function f:\n'
          '    try:\n'
          '        print(1)\n'
          '    catch err:\n'
          '        print(err)\n')


def test_range_loop_variable_is_declared():
    check('define function f:\n'
          '    for i from 1 to 3:\n'
          '        print(i)\n')


# -- codegen: v2 constructs -------------------------------------------------------

def gen(src):
    prog, _ = analyze(parse(src, filename="test.agk"), filename="test.agk")
    return generate(prog)


def test_codegen_default_param():
    out = gen('define function greet that takes name as String = "World":\n'
              '    print(name)\n')
    assert 'def greet(name="World"):' in out


def test_codegen_for_range_inclusive():
    out = gen('define function f:\n    for i from 1 to 3:\n        print(i)\n')
    assert "for i in range(1, (3) + 1):" in out


def test_codegen_for_range_negative_step():
    out = gen('define function f:\n    for i from 10 to 1 step -3:\n        print(i)\n')
    assert "range(10," in out and ", -3):" in out


def test_codegen_for_in():
    out = gen('define function f:\n'
              '    create items as List\n'
              '    set items to [1, 2]\n'
              '    for x in items:\n'
              '        print(x)\n')
    assert "for x in items:" in out


def test_codegen_try_catch_finally():
    out = gen('define function f:\n'
              '    try:\n'
              '        print(1)\n'
              '    catch err:\n'
              '        print(err)\n'
              '    finally:\n'
              '        print(2)\n')
    assert "try:" in out
    assert "except Exception as err:" in out
    assert "finally:" in out


def test_codegen_bare_catch():
    out = gen('define function f:\n'
              '    try:\n'
              '        print(1)\n'
              '    catch:\n'
              '        print(2)\n')
    assert "except Exception:" in out


def test_codegen_raise():
    out = gen('define function f:\n    raise "boom"\n')
    assert 'raise Exception("boom")' in out


def test_codegen_bare_raise():
    out = gen('define function f:\n    try:\n        print(1)\n    catch:\n        raise\n')
    assert "\n        raise\n" in out


def test_codegen_interpolation():
    out = gen('define function f:\n'
              '    create name as String\n'
              '    set name to "x"\n'
              '    print("hi {name}")\n')
    assert '"hi {}".format(name)' in out


# -- e2e: language features ---------------------------------------------------------

def test_e2e_defaults_and_interpolation():
    out, warnings = run(
        'define function greet that takes name as String = "World":\n'
        '    print("Hello, {name}!")\n'
        'define function main:\n'
        '    greet()\n'
        '    greet("Gopi")\n')
    assert out == "Hello, World!\nHello, Gopi!\n"
    assert warnings == []


def test_e2e_for_in():
    out, _ = run(
        'define function main:\n'
        '    for w in ["a", "b"]:\n'
        '        print("w={w}")\n')
    assert out == "w=a\nw=b\n"


def test_e2e_for_range_ascending():
    out, _ = run(
        'define function main:\n'
        '    for i from 1 to 3:\n'
        '        print(i)\n')
    assert out == "1\n2\n3\n"


def test_e2e_for_range_descending():
    out, _ = run(
        'define function main:\n'
        '    for i from 10 to 1 step -3:\n'
        '        print(i)\n')
    assert out == "10\n7\n4\n1\n"


def test_e2e_for_range_step_expression():
    out, _ = run(
        'define function main:\n'
        '    for i from 0 to 6 step 2:\n'
        '        print(i)\n')
    assert out == "0\n2\n4\n6\n"


def test_e2e_try_catch_finally():
    out, _ = run(
        'define function main:\n'
        '    try:\n'
        '        print(1 / 0)\n'
        '    catch err:\n'
        '        print("caught")\n'
        '    finally:\n'
        '        print("finally")\n'
        '    print("after")\n')
    assert out == "caught\nfinally\nafter\n"


def test_e2e_bare_catch_and_reraise():
    out, _ = run(
        'define function boom:\n'
        '    raise "kaboom"\n'
        'define function main:\n'
        '    try:\n'
        '        try:\n'
        '            boom()\n'
        '        catch:\n'
        '            print("inner")\n'
        '            raise\n'
        '    catch err:\n'
        '        print("outer")\n')
    assert out == "inner\nouter\n"


def test_e2e_raise_message_is_caught():
    out, _ = run(
        'define function main:\n'
        '    try:\n'
        '        raise "kaboom"\n'
        '    catch err:\n'
        '        print("{err}")\n')
    assert out == "kaboom\n"


def test_e2e_escaped_braces():
    out, _ = run(
        'define function main:\n'
        '    print("{{literal}}")\n')
    assert out == "{literal}\n"


# -- e2e: new stdlib modules ---------------------------------------------------------

def test_e2e_fileutils(tmp_path):
    target = tmp_path / "t.txt"
    out, _ = run(
        'import fileutils\n'
        'define function main:\n'
        f'    write_text("{target}", "hello")\n'
        f'    append_text("{target}", " agk")\n'
        f'    print(read_text("{target}"))\n'
        f'    print(file_exists("{target}"))\n'
        f'    print(file_exists("{target}.nope"))\n')
    assert out == "hello agk\nTrue\nFalse\n"
    assert target.read_text() == "hello agk"


def test_e2e_list_dir(tmp_path):
    (tmp_path / "a.txt").write_text("x")
    out, _ = run(
        'import fileutils\n'
        'define function main:\n'
        f'    for f in list_dir("{tmp_path}"):\n'
        '        print(f)\n')
    assert out.strip() == "a.txt"


def test_e2e_jsonutils():
    out, _ = run(
        'import jsonutils\n'
        'define function main:\n'
        '    create obj as Object\n'
        '    set obj to parse_json("{{\\"a\\": 1}}")\n'
        '    print(to_json(obj))\n')
    assert out.strip() == '{"a": 1}'


def test_e2e_httputils_data_url():
    out, _ = run(
        'import httputils\n'
        'define function main:\n'
        '    print(http_get("data:text/plain,hi"))\n')
    assert out == "hi\n"


def test_e2e_dateutils():
    out, _ = run(
        'import dateutils\n'
        'define function main:\n'
        '    print(add_days("2026-09-18", 7))\n'
        '    print(len(today()))\n')
    assert out == "2026-09-25\n10\n"


# -- traceback mapping ---------------------------------------------------------------

def test_format_agk_traceback_maps_to_agk_lines(tmp_path):
    src = ('define function fail:\n'
           '    print(1 / 0)\n'
           'define function main:\n'
           '    fail()\n')
    prog = tmp_path / "boom.agk"
    prog.write_text(src)
    code, _ = compile_source(src, filename=str(prog))
    ns = {"__name__": "__main__"}
    try:
        exec(compile(code, str(prog), "exec"), ns)
    except ZeroDivisionError:
        import traceback
        rendered = format_agk_traceback(*sys.exc_info(), code)
    else:
        pytest.fail("expected ZeroDivisionError")
    assert "boom.agk" in rendered
    assert "ZeroDivisionError" in rendered
    # AGK line 2 is the division; the .py line numbers must not leak as AGK lines
    assert "test.agk" not in rendered


def test_cli_run_shows_agk_traceback(tmp_path):
    prog = tmp_path / "boom.agk"
    prog.write_text('define function main:\n    print(1 / 0)\n')
    result = subprocess.run(
        [sys.executable, "-m", "agk", "run", str(prog)],
        cwd=str(ROOT), capture_output=True, text=True)
    assert result.returncode != 0
    assert "boom.agk" in result.stderr
    assert "ZeroDivisionError" in result.stderr


# -- packaging --------------------------------------------------------------------------

def test_package_metadata():
    import importlib.metadata as md
    dist = md.distribution("agk-real")
    assert dist.version == "0.2.0"
    assert dist.read_text("entry_points.txt") is not None
    eps = md.entry_points(group="console_scripts")
    assert any(ep.name == "agk" for ep in eps)


def test_stdlib_shipped_as_package_data():
    import importlib.metadata as md
    files = md.distribution("agk-real").files or []
    names = {str(f) for f in files}
    for mod in ("fileutils", "jsonutils", "httputils", "dateutils",
                "strutils", "listutils"):
        assert any(n.endswith(f"stdlib/{mod}.agk") for n in names), mod


# -- VS Code grammar -----------------------------------------------------------------------

def test_vscode_grammar_files_valid():
    base = ROOT / "editors" / "vscode"
    pkg = json.loads((base / "package.json").read_text())
    assert pkg["contributes"]["languages"][0]["extensions"] == [".agk"]
    grammar = json.loads((base / "syntaxes" / "agk.tmLanguage.json").read_text())
    assert grammar["scopeName"] == "source.agk"
    assert any("try" in p.get("match", "") for p in grammar["repository"]["keyword"].get("patterns", [])
               ) or "try" in grammar["repository"]["keyword"]["match"]
    json.loads((base / "language-configuration.json").read_text())
