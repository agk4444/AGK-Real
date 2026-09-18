"""Workstream 6 — new language features: async/await, generators, decorators.

Covers all four stages (lexer, parser, semantic, codegen) plus end-to-end
programs that actually run: an async program doing real awaits, a
generator consumed by a for loop, and decorators modifying behavior.
"""

import pytest

from agk.lexer import Lexer
from agk.tokens import TokenType as T
from agk.parser import parse
from agk.semantic import analyze
from agk.codegen import generate
from agk.pipeline import run_source, compile_source
from agk import ast_nodes as A
from agk.errors import ParserError, SemanticError


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


# -- lexer ----------------------------------------------------------------

def test_new_keywords_lex():
    toks = Lexer("async await yield", "test.agk").tokenize()
    kinds = [t.type for t in toks if t.type not in (T.EOF, T.NEWLINE)]
    assert kinds == [T.ASYNC, T.AWAIT, T.YIELD]


def test_at_sign_lex():
    toks = Lexer("@timer", "test.agk").tokenize()
    kinds = [t.type for t in toks if t.type not in (T.EOF, T.NEWLINE)]
    assert kinds == [T.AT, T.IDENTIFIER]


# -- parser: async ----------------------------------------------------------

def test_async_function_def_parses():
    prog = p("define async function f:\n    return 1\n")
    fn = prog.statements[0]
    assert isinstance(fn, A.FunctionDef)
    assert fn.is_async is True


def test_sync_function_def_defaults():
    prog = p("define function f:\n    return 1\n")
    fn = prog.statements[0]
    assert fn.is_async is False
    assert fn.decorators == []


def test_async_with_params_and_return_type():
    prog = p("define async function f that takes x as Integer "
             "and returns Integer:\n    return x\n")
    fn = prog.statements[0]
    assert fn.is_async is True
    assert fn.return_type == "Integer"
    assert [q.name for q in fn.params] == ["x"]


def test_async_method_parses():
    prog = p("define class C:\n"
             "    define async function m:\n"
             "        return 1\n")
    m = prog.statements[0].methods[0]
    assert m.is_async is True


def test_async_constructor_is_parse_error():
    fails_parse(
        "define class C:\n"
        "    define async constructor:\n"
        "        return\n",
        "constructors cannot be async")


def test_async_class_is_parse_error():
    fails_parse("define async class C:\n    variable x as Integer\n",
                "classes cannot be async")


def test_async_constant_is_parse_error():
    fails_parse("define async constant X as Integer = 1\n",
                "constants cannot be async")


# -- parser: await ----------------------------------------------------------

def test_await_expr_parses():
    s = stmt("set x to await fetch()")
    assert isinstance(s, A.SetStmt)
    assert isinstance(s.value, A.AwaitExpr)
    assert isinstance(s.value.operand, A.Call)


def test_await_binds_like_python():
    # `await f() + 1` is `(await f()) + 1`, matching Python.
    s = stmt("set x to await f() + 1")
    assert isinstance(s.value, A.BinOp)
    assert s.value.op == "+"
    assert isinstance(s.value.left, A.AwaitExpr)


def test_await_unary_operand():
    s = stmt("set x to await -y")
    assert isinstance(s.value, A.AwaitExpr)
    assert isinstance(s.value.operand, A.UnaryOp)


def test_await_in_args_and_conditions():
    s = stmt("print(await fetch(url))")
    call = s.expr
    assert isinstance(call.args[0], A.AwaitExpr)
    s2 = stmt("if await ready():\n    print(1)")
    assert isinstance(s2.condition, A.AwaitExpr)


# -- parser: yield ----------------------------------------------------------

def test_yield_parses():
    s = stmt("yield 42")
    assert isinstance(s, A.YieldStmt)
    assert s.value == A.IntLit(42, line=1, col=1)


def test_bare_yield_parses():
    s = stmt("yield")
    assert isinstance(s, A.YieldStmt)
    assert s.value is None


# -- parser: decorators -----------------------------------------------------

def test_decorator_plain_parses():
    prog = p("@timer\ndefine function f:\n    return 1\n")
    fn = prog.statements[0]
    assert len(fn.decorators) == 1
    assert fn.decorators[0] == A.Name("timer", line=1, col=1)


def test_decorator_with_args_parses():
    prog = p("@retry(3)\ndefine function f:\n    return 1\n")
    fn = prog.statements[0]
    (deco,) = fn.decorators
    assert isinstance(deco, A.Call)
    assert deco.func == A.Name("retry", line=1, col=1)
    assert deco.args == [A.IntLit(3, line=1, col=1)]


def test_multiple_decorators_keep_order():
    prog = p("@a\n@b(1, 2)\ndefine function f:\n    return 1\n")
    (d1, d2) = prog.statements[0].decorators
    assert isinstance(d1, A.Name) and d1.id == "a"
    assert isinstance(d2, A.Call) and d2.func.id == "b"


def test_decorator_on_method_parses():
    prog = p("define class C:\n"
             "    @timer\n"
             "    define function m:\n"
             "        return 1\n")
    (deco,) = prog.statements[0].methods[0].decorators
    assert isinstance(deco, A.Name) and deco.id == "timer"


def test_decorator_on_async_function():
    prog = p("@timer\ndefine async function f:\n    return 1\n")
    fn = prog.statements[0]
    assert fn.is_async is True
    assert len(fn.decorators) == 1


def test_decorator_on_class_is_parse_error():
    fails_parse("@timer\ndefine class C:\n    variable x as Integer\n",
                "decorators are not supported on classes")


def test_decorator_on_constant_is_parse_error():
    fails_parse("@timer\ndefine constant X as Integer = 1\n",
                "decorators are not supported on constants")


def test_decorator_on_constructor_is_parse_error():
    fails_parse("define class C:\n"
                "    @timer\n"
                "    define constructor:\n"
                "        return\n",
                "decorators are not supported on constructors")


def test_stray_at_sign_is_parse_error():
    with pytest.raises(ParserError):
        p("define function f:\n    @timer\n    return 1\n")


# -- semantic ---------------------------------------------------------------

def test_await_outside_async_is_error():
    fails_semantic(
        "define function f:\n"
        "    create x as Integer\n"
        "    set x to await g()\n",
        "'await' outside an async function")


def test_await_at_top_level_expr_is_error():
    prog = p("define async function g:\n    return 1\n"
             "define function f:\n    return await g()\n")
    with pytest.raises(SemanticError) as exc:
        analyze(prog, filename="test.agk")
    assert "'await' outside an async function" in str(exc.value)


def test_await_inside_async_ok():
    check("define async function g:\n    return 1\n"
          "define async function f:\n"
          "    create x as Integer\n"
          "    set x to await g()\n"
          "    return x\n")


def test_await_inside_async_method_ok():
    check("define class C:\n"
          "    define async function m:\n"
          "        create x as Integer\n"
          "        set x to await self.n()\n"
          "        return x\n"
          "    define async function n:\n"
          "        return 1\n")


def test_yield_outside_function_is_error():
    # The parser already rejects a top-level `yield`, so this gate is
    # defense-in-depth; drive the statement checker directly.
    fails_parse("yield 1\n", "unexpected 'yield' at top level")
    from agk.semantic import SemanticAnalyzer
    an = SemanticAnalyzer("test.agk")
    with pytest.raises(SemanticError) as exc:
        an._check_stmt(A.YieldStmt(A.IntLit(1), line=1, col=1))
    assert "'yield' outside a function" in str(exc.value)


def test_yield_inside_async_is_error():
    fails_semantic(
        "define async function f:\n"
        "    yield 1\n",
        "'yield' is not allowed in an async function")


def test_undefined_decorator_name_is_error():
    fails_semantic("@nope\ndefine function f:\n    return 1\n",
                   "undefined variable 'nope'")


def test_decorator_name_gets_did_you_mean():
    fails_semantic(
        "define function timer:\n    return 1\n"
        "@timre\n"
        "define function f:\n    return 1\n",
        "did you mean 'timer'?")


def test_decorator_with_args_resolves_names():
    check("define function retry that takes n as Integer:\n"
          "    return 1\n"
          "@retry(3)\n"
          "define function f:\n"
          "    return 1\n")


def test_decorator_marks_name_used():
    # a decorator-only use must not warn "unused variable"
    _prog, warnings = check(
        "define function timer that takes fn as Object:\n"
        "    return fn\n"
        "@timer\n"
        "define function f:\n"
        "    return 1\n")
    assert warnings == []


# -- codegen ----------------------------------------------------------------

def test_codegen_async_def():
    code = generate(analyze(p(
        "define async function f:\n    return 1\n"),
        filename="test.agk")[0])
    assert "async def f():" in code
    assert "import asyncio" in code


def test_codegen_sync_def_unchanged():
    code = generate(analyze(p(
        "define function f:\n    return 1\n"),
        filename="test.agk")[0])
    assert "\ndef f():" in code
    assert "asyncio" not in code


def test_codegen_async_main_runs_on_event_loop():
    code = generate(analyze(p(
        "define async function main:\n    return\n"),
        filename="test.agk")[0])
    assert "asyncio.run(main())" in code


def test_codegen_sync_main_unchanged():
    code = generate(analyze(p(
        "define function main:\n    return\n"),
        filename="test.agk")[0])
    assert "\n    main()\n" in code
    assert "asyncio" not in code


def test_codegen_no_duplicate_asyncio_import():
    code = generate(analyze(p(
        "import asyncio\n"
        "define async function main:\n    return\n"),
        filename="test.agk")[0])
    assert code.count("import asyncio") == 1


def test_codegen_await():
    code = generate(analyze(p(
        "define function g:\n"
        "    return 1\n"
        "define async function f:\n"
        "    create x as Integer\n"
        "    set x to await g() + 1\n"),
        filename="test.agk")[0])
    assert "x = await g() + 1" in code


def test_codegen_await_parens():
    code = generate(analyze(p(
        "define async function f that takes y as Integer:\n"
        "    create x as Integer\n"
        "    set x to await -y\n"),
        filename="test.agk")[0])
    assert "x = await (-y)" in code


def test_codegen_yield():
    code = generate(analyze(p(
        "define function f:\n"
        "    yield 1\n"
        "    yield\n"),
        filename="test.agk")[0])
    assert "\n    yield 1\n" in code
    assert "\n    yield\n" in code


def test_codegen_decorators():
    code = generate(analyze(p(
        "@timer\n"
        "@retry(3)\n"
        "define function f:\n    return 1\n"
        "define function timer that takes fn as Object:\n    return fn\n"
        "define function retry that takes n as Integer:\n    return timer\n"),
        filename="test.agk")[0])
    assert "@timer\n@retry(3)\ndef f():" in code


# -- end to end: async ------------------------------------------------------

ASYNC_PROG = """import asyncio

define async function sleep_then that takes ms as Integer, tag as String:
    await asyncio.sleep(ms / 1000.0)
    return tag + "!"

define async function main:
    create first as String
    create second as String
    set first to await sleep_then(20, "one")
    set second to await sleep_then(10, "two")
    print(first)
    print(second)
"""


def test_e2e_async_real_awaits():
    out, warnings = run(ASYNC_PROG)
    assert out == "one!\ntwo!\n"
    assert warnings == []


def test_e2e_async_method():
    out, _ = run(
        "import asyncio\n"
        "define class Sleeper:\n"
        "    define async function nap that takes n as Integer:\n"
        "        await asyncio.sleep(0.001)\n"
        "        return n * 2\n"
        "define async function main:\n"
        "    create s as Object\n"
        "    set s to Sleeper()\n"
        "    create r as Integer\n"
        "    set r to await s.nap(21)\n"
        "    print(r)\n")
    assert out == "42\n"


def test_e2e_async_for_loop_over_results():
    out, _ = run(
        "import asyncio\n"
        "define async function double that takes n as Integer:\n"
        "    await asyncio.sleep(0.001)\n"
        "    return n * 2\n"
        "define async function main:\n"
        "    create total as Integer\n"
        "    set total to 0\n"
        "    for i from 1 to 5:\n"
        "        set total to total + await double(i)\n"
        "    print(total)\n")
    assert out == "30\n"


# -- end to end: generators ---------------------------------------------------

GEN_PROG = """define function counter that takes n as Integer:
    create i as Integer
    set i to 1
    while i <= n:
        yield i * 10
        set i to i + 1

define function main:
    create total as Integer
    set total to 0
    for each v in counter(4):
        set total to total + v
    print(total)
"""


def test_e2e_generator_for_loop():
    out, warnings = run(GEN_PROG)
    assert out == "100\n"
    assert warnings == []


def test_e2e_generator_is_lazy():
    # an infinite generator consumed only as far as needed
    out, _ = run(
        "define function naturals:\n"
        "    create n as Integer\n"
        "    set n to 1\n"
        "    while true:\n"
        "        yield n\n"
        "        set n to n + 1\n"
        "define function main:\n"
        "    create count as Integer\n"
        "    set count to 0\n"
        "    for each n in naturals():\n"
        "        print(n)\n"
        "        set count to count + 1\n"
        "        if count >= 3:\n"
        "            return\n")
    assert out == "1\n2\n3\n"


def test_e2e_generator_bare_yield():
    out, _ = run(
        "define function marks:\n"
        "    yield 1\n"
        "    yield\n"
        "    yield 3\n"
        "define function main:\n"
        "    for each m in marks():\n"
        "        print(m)\n")
    assert out == "1\nNone\n3\n"


def test_e2e_generator_pipeline():
    # generator feeding another generator
    out, _ = run(
        "define function evens that takes n as Integer:\n"
        "    for i from 1 to n:\n"
        "        if i % 2 == 0:\n"
        "            yield i\n"
        "define function squares that takes gen as Object:\n"
        "    for each x in gen:\n"
        "        yield x * x\n"
        "define function main:\n"
        "    for each s in squares(evens(6)):\n"
        "        print(s)\n")
    assert out == "4\n16\n36\n"


# -- end to end: decorators ---------------------------------------------------

DECO_PROG = """define class Doubler:
    variable fn as Object
    define constructor that takes f as Object:
        set fn to f
    define function __call__:
        return self.fn() * 2

define class Repeater:
    variable n as Integer
    define constructor that takes k as Integer:
        set n to k
    define function __call__ that takes fn as Object:
        return Wrap(fn, self.n)

define class Wrap:
    variable fn as Object
    variable n as Integer
    define constructor that takes f as Object, k as Integer:
        set fn to f
        set n to k
    define function __call__:
        create r as Integer
        set r to 0
        create k as Integer
        set k to 0
        while k < self.n:
            set r to r + self.fn()
            set k to k + 1
        return r

define function repeat that takes n as Integer:
    return Repeater(n)

@Doubler
define function five:
    return 5

@repeat(3)
define function seven:
    return 7

define function main:
    print(five())
    print(seven())
"""


def test_e2e_decorators_modify_behavior():
    out, warnings = run(DECO_PROG)
    assert out == "10\n21\n"
    assert warnings == []


def test_e2e_decorator_on_method():
    # A decorator that returns the function unchanged preserves binding.
    out, warnings = run(
        "define function plain that takes fn as Object:\n"
        "    return fn\n"
        "define class Calc:\n"
        "    @plain\n"
        "    define function three:\n"
        "        return 3\n"
        "define function main:\n"
        "    create c as Object\n"
        "    set c to Calc()\n"
        "    print(c.three())\n")
    assert out == "3\n"
    assert warnings == []


# -- CLI: agk run with an async main ------------------------------------------

def test_cli_run_async_main(tmp_path, capsys):
    from agk.__main__ import main
    src = ("import asyncio\n"
           "define async function main:\n"
           "    await asyncio.sleep(0.001)\n"
           "    print(\"async ok\")\n")
    path = tmp_path / "a.agk"
    path.write_text(src)
    assert main(["run", str(path)]) == 0
    assert capsys.readouterr().out == "async ok\n"


def test_cli_build_async_main(tmp_path):
    import ast as py_ast
    from agk.__main__ import main
    path = tmp_path / "a.agk"
    path.write_text("define async function main:\n    return\n")
    out = str(tmp_path / "a.py")
    assert main(["build", str(path), "-o", out]) == 0
    text = open(out).read()
    py_ast.parse(text)
    assert "asyncio.run(main())" in text
