"""M6 — REPL tests (AGK-Real v1 test plan)."""

import pytest

from agk.errors import AGKError
from agk.repl import Session


def session():
    return Session()


def test_expression_prints_repr(capsys):
    s = session()
    assert s.handle("1 + 2 * 3\n") is True
    assert capsys.readouterr().out == "7\n"


def test_string_repr(capsys):
    s = session()
    s.handle('"hi"\n')
    assert capsys.readouterr().out == "'hi'\n"


def test_create_set_persist(capsys):
    s = session()
    s.handle("create x as Integer\n")
    s.handle("set x to 21\n")
    s.handle("x * 2\n")
    assert capsys.readouterr().out == "42\n"


def test_set_without_create_is_clean_error():
    s = session()
    with pytest.raises(AGKError, match="undefined variable"):
        s.handle("set y to 1\n")


def test_define_then_call(capsys):
    s = session()
    s.handle("define function double that takes n as Integer and returns Integer:\n"
             "    return n * 2\n")
    s.handle("double(21)\n")
    assert capsys.readouterr().out == "42\n"


def test_redefine_function(capsys):
    s = session()
    s.handle("define function f:\n    return 1\n")
    s.handle("define function f:\n    return 2\n")
    s.handle("f()\n")
    assert capsys.readouterr().out == "2\n"


def test_calling_unknown_function_is_clean_error():
    s = session()
    with pytest.raises(AGKError, match="undefined function"):
        s.handle("nope()\n")


def test_broken_input_is_clean_error():
    s = session()
    with pytest.raises(AGKError):
        s.handle("set x to\n")


def test_class_roundtrip(capsys):
    s = session()
    s.handle("define class C:\n"
             "    variable v as Integer\n"
             "    define constructor that takes n as Integer:\n"
             "        set v to n\n")
    s.handle("create c as Object\n")
    s.handle("set c to C(7)\n")
    s.handle("c.v\n")
    assert capsys.readouterr().out == "7\n"


def test_stdlib_import_in_repl(capsys):
    s = session()
    s.handle("import strutils\n")
    s.handle('shout("hey")\n')
    assert capsys.readouterr().out == "'HEY!'\n"


def test_exit_and_quit():
    s = session()
    assert s.handle("exit\n") is False
    assert s.handle("quit\n") is False
    assert s.handle("\n") is True
