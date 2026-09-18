"""Level 3 — "did you mean?" suggestions on undefined-name errors."""

import pytest

from agk.parser import parse
from agk.semantic import analyze
from agk.pipeline import compile_source
from agk.errors import SemanticError


def check(src):
    prog = parse(src, filename="test.agk")
    return analyze(prog, filename="test.agk")


def fails_with(src, fragment):
    with pytest.raises(SemanticError) as exc:
        check(src)
    msg = str(exc.value)
    assert fragment in msg, msg
    return msg


def test_typo_variable_suggests_name():
    fails_with(
        "define function f:\n"
        "    create greeting as String\n"
        "    set greeting to \"hi\"\n"
        "    print(greting)\n",
        "undefined variable 'greting'. did you mean 'greeting'?")


def test_typo_set_variable_suggests_name():
    fails_with(
        "define function f:\n"
        "    create greeting as String\n"
        "    set greting to \"hi\"\n",
        "cannot set undefined variable 'greting'. did you mean 'greeting'?")


def test_typo_function_call_suggests_name():
    fails_with(
        "define function greet that takes name as String:\n"
        "    print(name)\n"
        "define function f:\n"
        "    gret(\"bob\")\n",
        "undefined function 'gret'. did you mean 'greet'?")


def test_typo_base_class_suggests_name():
    fails_with(
        "define class Animal:\n"
        "    variable name as String\n"
        "define class Dog extends Animl:\n"
        "    variable bark as String\n",
        "undefined base class 'Animl'. did you mean 'Animal'?")


def test_no_suggestion_when_nothing_close():
    msg = fails_with(
        "define function f:\n"
        "    return xyzqqq\n",
        "undefined variable 'xyzqqq'")
    assert "did you mean" not in msg, msg
    assert msg.rstrip().endswith("undefined variable 'xyzqqq'"), msg


def test_suggestion_through_pipeline():
    with pytest.raises(SemanticError) as exc:
        compile_source(
            "define function f:\n"
            "    create greeting as String\n"
            "    set greeting to \"hi\"\n"
            "    print(greting)\n",
            filename="test.agk")
    assert "undefined variable 'greting'. did you mean 'greeting'?" in str(
        exc.value), str(exc.value)
