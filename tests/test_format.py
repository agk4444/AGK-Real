"""Tests for the `agk fmt` canonical formatter (agk/format.py)."""

from pathlib import Path

import pytest

from agk.__main__ import main
from agk.errors import LexerError
from agk.format import format_source
from agk.pipeline import run_source

CORPUS = Path(__file__).parent / "corpus"


def write(tmp_path, name, src):
    p = tmp_path / name
    p.write_text(src)
    return str(p)


# -- rule 1: indentation -------------------------------------------------

def test_indentation_normalized_to_4_spaces():
    # valid AGK must grow indentation exactly 4 per level, but the
    # formatter normalizes any *lexable* layout; here the source is
    # already valid and over-indented lines get pulled back.
    src = (
        "define function main:\n"
        "    create x as Int\n"
        "    set x to 1\n"
        "    if x == 1:\n"
        "        print(\"one\")\n"
        "    print(\"done\")\n"
    )
    assert format_source(src) == src  # already canonical


def test_indent_depth_comes_from_indent_dedent_tokens():
    src = (
        "define function outer:\n"
        "    if true:\n"
        "        print(\"deep\")\n"
        "    print(\"mid\")\n"
        "print(\"top\")\n"  # invalid AGK on its own, but lexable
    )
    # `print("top")` at column 0 after a block: lexer dedents fine.
    out = format_source(src)
    assert out == src


def test_nested_blocks_indent():
    src = (
        "define function main:\n"
        "    create x as Int\n"
        "    set x to 0\n"
        "    while x < 3:\n"
        "        if x == 1:\n"
        "            print(\"one\")\n"
        "        set x to x + 1\n"
    )
    assert format_source(src) == src


# -- rule 2: spacing -----------------------------------------------------

def test_space_after_comma():
    src = "define function main:\n    print(max(1,2,3))\n"
    assert format_source(src) == "define function main:\n    print(max(1, 2, 3))\n"


def test_no_space_before_closers_and_after_openers():
    src = "define function main:\n    print( [1 , 2 ] )\n"
    assert format_source(src) == "define function main:\n    print([1, 2])\n"


def test_call_paren_sticks_to_target():
    src = "define function main:\n    print (\"hi\")\n"
    assert format_source(src) == "define function main:\n    print(\"hi\")\n"


def test_index_bracket_sticks_to_target():
    src = (
        "define function main:\n"
        "    create items as List\n"
        "    set items to [1, 2]\n"
        "    print(items [0])\n"
    )
    assert "print(items[0])\n" in format_source(src)


def test_dot_binds_tight_both_sides():
    src = (
        "define function main:\n"
        "    create a as Object\n"
        "    a . deposit (50.0)\n"
    )
    assert "    a.deposit(50.0)\n" in format_source(src)


def test_dict_braces_tight_colon_spaced():
    src = (
        "define function main:\n"
        "    create d as Dict\n"
        "    set d to { \"a\" :1,\"b\": 2 }\n"
    )
    assert '    set d to {"a": 1, "b": 2}\n' in format_source(src)


def test_colon_at_end_of_line_gets_no_trailing_space():
    src = "define function main:\n    if true:\n        print(\"x\")\n"
    out = format_source(src)
    assert "if true:\n" in out
    assert not any(line.endswith(" ") for line in out.split("\n"))


def test_comma_before_closer_gets_no_space():
    # `f(a,)` is degenerate input, but formatting must stay idempotent.
    src = "define function main:\n    print(max(1,))\n"
    assert format_source(src) == src


def test_operators_get_single_spaces():
    src = (
        "define function main:\n"
        "    create x as Int\n"
        "    set x to 1+2*3\n"
        "    if x>=4 and x<=10:\n"
        "        print(x)\n"
    )
    out = format_source(src)
    assert "    set x to 1 + 2 * 3\n" in out
    assert "    if x >= 4 and x <= 10:\n" in out


def test_unary_operators_keep_plain_spacing():
    # Documented: unary minus / not are not special-cased.
    src = (
        "define function main:\n"
        "    create x as Int\n"
        "    set x to -5\n"
        "    if not false:\n"
        "        print(x)\n"
    )
    out = format_source(src)
    assert "    set x to - 5\n" in out
    assert "    if not false:\n" in out


# -- rules 3/4/5: whitespace hygiene -------------------------------------

def test_trailing_whitespace_stripped():
    src = "define function main:   \n    print(\"x\")\t\n"
    assert format_source(src) == "define function main:\n    print(\"x\")\n"


def test_blank_runs_collapse_to_one():
    src = (
        "define function main:\n"
        "    print(\"a\")\n"
        "\n"
        "\n"
        "\n"
        "    print(\"b\")\n"
    )
    assert format_source(src) == (
        "define function main:\n"
        "    print(\"a\")\n"
        "\n"
        "    print(\"b\")\n"
    )


def test_leading_and_trailing_blank_lines_dropped():
    src = "\n\ndefine function main:\n    print(\"x\")\n\n\n"
    assert format_source(src) == "define function main:\n    print(\"x\")\n"


def test_exactly_one_trailing_newline():
    assert format_source("define function main:\n    print(\"x\")") == (
        "define function main:\n    print(\"x\")\n"
    )
    assert format_source("define function main:\n    print(\"x\")\n\n\n") == (
        "define function main:\n    print(\"x\")\n"
    )


# -- rule 6: strings and comments verbatim -------------------------------

def test_string_contents_preserved_with_escapes():
    src = "define function main:\n    print(\"a\\nb\\\"c\\\\d\")\n"
    out = format_source(src)
    assert out == src  # re-quoted identically


def test_string_with_interpolation_untouched():
    src = (
        "define function main:\n"
        "    create name as String\n"
        '    set name to "ada"\n'
        '    print("hi {name}, {{literal}}")\n'
    )
    assert format_source(src) == src


def test_hash_inside_string_is_not_a_comment():
    src = "define function main:\n    print(\"#not a comment\")\n"
    assert format_source(src) == src


def test_whole_line_comments_preserved_and_indented():
    src = (
        "# top comment\n"
        "define function main:\n"
        "    # inner comment\n"
        "    print(\"x\")\n"
        "    # trailing comment\n"
    )
    assert format_source(src) == src


def test_trailing_comment_kept_with_two_space_gap():
    src = "define function main:\n    print(\"x\")# c\n    print(\"y\")   # d  \n"
    out = format_source(src)
    assert out == (
        "define function main:\n"
        "    print(\"x\")  # c\n"
        "    print(\"y\")  # d\n"
    )


def test_comment_between_dedented_blocks():
    src = (
        "define function main:\n"
        "    if true:\n"
        "        print(\"a\")\n"
        "    # between blocks\n"
        "    print(\"b\")\n"
    )
    assert format_source(src) == src


def test_empty_and_comment_only_sources():
    assert format_source("") == "\n"
    assert format_source("# just a comment\n") == "# just a comment\n"


# -- idempotency ----------------------------------------------------------

IDEMPOTENCY_CASES = [
    "define function main:\n    print(\"x\")\n",
    "define function main:\n    print( \"x\" )  # c\n\n\n    if true:\n        print([1,2,{\"a\":3}])\n",
    "# c1\n\n\ndefine function main:\n    create x as Int\n    set x to 1+2\n    while x<5:\n        set x to x+1   \n# tail\n",
    "define class A:\n    variable v as Int\n    define function f that takes x as Int and returns Int:\n        return x*2\n",
    "define function main:\n    create s as String\n    set s to \"tab\\there\"\n    print(s)\n",
]


@pytest.mark.parametrize("src", IDEMPOTENCY_CASES)
def test_idempotent(src):
    once = format_source(src)
    assert format_source(once) == once


def test_lex_error_propagates():
    with pytest.raises(LexerError):
        format_source("define function main:\n        print(\"x\")\n")  # 8-space jump


# -- corpus round-trip ----------------------------------------------------

def corpus_programs():
    return sorted(CORPUS.glob("*.agk"))


@pytest.mark.parametrize("prog", corpus_programs(), ids=lambda p: p.stem)
def test_corpus_round_trip(prog):
    src = prog.read_text()
    expected = prog.with_suffix(".expected").read_text()
    out = format_source(src, filename=prog.name)
    # formatted output must be a fixed point...
    assert format_source(out, filename=prog.name) == out
    # ...and must still compile and produce the same stdout.
    stdout, _ns, _warnings = run_source(out, filename=prog.name)
    assert stdout == expected
    if out == src:
        pass  # canonical already
    else:
        # non-canonical corpus file: at least it must not lose behavior
        orig_stdout, _ns2, _w2 = run_source(src, filename=prog.name)
        assert stdout == orig_stdout == expected


# -- CLI ------------------------------------------------------------------

def test_fmt_rewrites_file_in_place(tmp_path):
    p = write(tmp_path, "m.agk", "define function main:\n    print( \"x\" )  \n")
    assert main(["fmt", p]) == 0
    assert Path(p).read_text() == "define function main:\n    print(\"x\")\n"


def test_fmt_canonical_file_unchanged(tmp_path):
    src = "define function main:\n    print(\"x\")\n"
    p = write(tmp_path, "m.agk", src)
    assert main(["fmt", p]) == 0
    assert Path(p).read_text() == src


def test_fmt_check_clean(tmp_path, capsys):
    p = write(tmp_path, "m.agk", "define function main:\n    print(\"x\")\n")
    assert main(["fmt", "--check", p]) == 0
    assert "ok" in capsys.readouterr().out


def test_fmt_check_dirty(tmp_path, capsys):
    p = write(tmp_path, "m.agk", "define function main:\n    print( \"x\" )\n")
    assert main(["fmt", "--check", p]) == 1
    out = capsys.readouterr().out
    assert "would reformat" in out and p in out
    # --check must not touch the file
    assert Path(p).read_text() == "define function main:\n    print( \"x\" )\n"


def test_fmt_lex_error_reports_and_returns_1(tmp_path, capsys):
    p = write(tmp_path, "m.agk", "define function main:\n        print(\"x\")\n")
    assert main(["fmt", p]) == 1
    err = capsys.readouterr().err
    assert f"agk: cannot format '{p}':" in err


def test_fmt_check_lex_error_returns_1(tmp_path, capsys):
    p = write(tmp_path, "m.agk", "define function main:\n        print(\"x\")\n")
    assert main(["fmt", "--check", p]) == 1
    assert "cannot format" in capsys.readouterr().err


def test_fmt_missing_file_raises_systemexit_2(capsys):
    with pytest.raises(SystemExit) as e:
        main(["fmt", "nope.agk"])
    assert e.value.code == 2


def test_fmt_usage_errors_return_2(capsys):
    assert main(["fmt"]) == 2
    assert main(["fmt", "a.agk", "b.agk"]) == 2
