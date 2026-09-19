"""Tests for agk/to_simple.py — the classic -> Simple AGK transpiler.

Every playground sample must convert to Simple AGK, re-parse, be
idempotent, and (verified by playground/build.py) run to its .expected
output. These tests pin the conversion rules on focused snippets.
"""

import pytest

from agk.lexer import Lexer
from agk.parser import Parser
from agk.to_simple import to_simple


def convert(src):
    return to_simple(src)


def test_create_set_merges_to_is():
    out = convert("define function main:\n"
                  "    create total as Integer\n"
                  "    set total to 0\n")
    assert out == "to main:\n    total is 0\n"


def test_function_signature():
    out = convert("define function check that takes pw as String, salt as String "
                  "and returns Boolean:\n"
                  "    return true\n")
    assert out == ("to check with pw as String, salt as String "
                   "and returns Boolean:\n"
                   "    return true\n")


def test_say_each_repeat_with():
    out = convert("define function main:\n"
                  "    for w in [\"a\"]:\n"
                  "        print(w)\n"
                  "    for i from 1 to 3:\n"
                  "        print(i)\n")
    assert out == ("to main:\n"
                   "    each w in [\"a\"]:\n"
                   "        say w\n"
                   "    repeat with i from 1 to 3:\n"
                   "        say i\n")


def test_otherwise_forms():
    out = convert("define function main:\n"
                  "    create s as Integer\n"
                  "    set s to 5\n"
                  "    if s == 1:\n"
                  "        print(1)\n"
                  "    elif s != 2:\n"
                  "        print(2)\n"
                  "    else:\n"
                  "        print(3)\n")
    assert out == ("to main:\n"
                   "    s is 5\n"
                   "    if s is 1:\n"
                   "        say 1\n"
                   "    otherwise if s is not 2:\n"
                   "        say 2\n"
                   "    otherwise:\n"
                   "        say 3\n")


def test_class_forms():
    out = convert("define class Counter:\n"
                  "    variable n as Integer\n"
                  "    define constructor:\n"
                  "        set n to 0\n"
                  "    define function bump:\n"
                  "        set n to n + 1\n")
    assert out == ("class Counter:\n"
                   "    n as Integer\n"
                   "    constructor:\n"
                   "        set n to 0\n"
                   "    to bump:\n"
                   "        increase n\n")


def test_constant_and_use():
    out = convert('define constant K as Integer = 41\n'
                  'extern function puts that takes s as String '
                  'from "libc"\n')
    assert out == ('constant K is 41\n'
                   '\n'
                   'use puts with s as String from "libc"\n')


def test_increase_decrease():
    out = convert("define function main:\n"
                  "    create i as Integer\n"
                  "    set i to 10\n"
                  "    set i to i - 1\n"
                  "    set i to i + 3\n")
    assert out == ("to main:\n"
                   "    i is 10\n"
                   "    decrease i\n"
                   "    increase i by 3\n")


def test_interpolation_round_trip():
    src = ('define function main:\n'
           '    create name as String\n'
           '    set name to "gopi"\n'
           '    print("hi {name}, {1 + 2}")\n')
    out = convert(src)
    assert out == ('to main:\n'
                   '    name is "gopi"\n'
                   '    say "hi {name}, {1 + 2}"\n')


def test_literal_braces_survive():
    src = ('define function main:\n'
           '    print("{{\\"a\\": 1}}")\n')
    out = convert(src)
    # re-parsing the output must give the same string value back
    assert convert(out) == out
    assert out == 'to main:\n    say "{{\\"a\\": 1}}"\n'


def test_say_paren_falls_back_to_print():
    # `say (x)` would parse as a call to `say`; keep `print(...)`.
    out = convert("define function main:\n"
                  "    print((1 + 2) * 3)\n")
    assert out == "to main:\n    print((1 + 2) * 3)\n"


def test_bare_comparison_statement_parenthesized():
    # Bare `a is b` would re-parse as a declaration.
    out = convert("define function main:\n"
                  "    1 + 2\n")
    assert "1 + 2" in out
    prog = Parser(Lexer(out).tokenize()).parse()
    assert prog is not None


def test_repeat_times_round_trip():
    out = convert("to main:\n    repeat 3 times:\n        say 1\n")
    assert convert(out) == out  # already simple: stable


def test_comments_preserved():
    src = ("# header\n"
           "define function main:\n"
           "    # inside\n"
           "    create n as Integer  # trailing\n"
           "    set n to 1\n")
    out = convert(src)
    assert out == ("# header\n"
                   "to main:\n"
                   "    # inside\n"
                   "    n is 1  # trailing\n")


def test_output_is_simple_only():
    """No classic-only spellings may remain in converted output.

    `while` has no simple form and stays; `print(` remains only in the
    `say (` fallback (which would otherwise parse as a call to `say`).
    """
    import re
    from pathlib import Path
    classic = re.compile(
        r"(?m)^\s*(define\s|create\s|variable\s|extern\s|for\s)"
        r"|\bprint\((?!\()|==|!=")
    bad = []
    for f in sorted(Path("playground/samples").glob("*.agk")):
        out = convert(f.read_text())
        # string literals may legally contain anything; strip them first
        stripped = re.sub(r'"(?:[^"\\]|\\.)*"', '""', out)
        if classic.search(stripped):
            bad.append(f.name)
    assert not bad, f"classic forms remain in: {bad}"
