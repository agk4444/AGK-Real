"""M6 — stdlib / module-import tests (AGK-Real v1 test plan)."""

import pytest

from agk.errors import SemanticError
from agk.pipeline import compile_source, run_source


def run(src, **kw):
    return run_source(src, **kw)


def test_strutils(capsys):
    src = ("import strutils\n"
           "define function main:\n"
           '    print(shout("hello"))\n'
           '    print(repeat_string("ab", 3))\n'
           '    print(join_lines(["a", "b"]))\n'
           '    print(slug("Hello World"))\n')
    out, _, warnings = run(src)
    assert warnings == []
    assert out == "HELLO!\nababab\na\nb\n\nhello-world\n"


def test_listutils():
    src = ("import listutils\n"
           "define function main:\n"
           "    print(sum_list([1, 2, 3, 4]))\n"
           "    print(max_in_list([3, 9, 4]))\n"
           "    print(min_in_list([3, 9, 4]))\n"
           "    print(contains_int([3, 9, 4], 9))\n"
           "    print(contains_int([3, 9, 4], 5))\n")
    out, _, warnings = run(src)
    assert warnings == []
    assert out == "10\n9\n3\nTrue\nFalse\n"


def test_sibling_module_import(tmp_path):
    (tmp_path / "helpers.agk").write_text(
        "define function triple that takes n as Integer and returns Integer:\n"
        "    return n * 3\n")
    main = tmp_path / "main.agk"
    main.write_text("import helpers\n"
                    "define function main:\n"
                    "    print(triple(7))\n")
    out, _, _ = run(main.read_text(), filename=str(main))
    assert out == "21\n"


def test_sibling_module_not_found_falls_back_to_python():
    # `os.path` is dotted: never treated as an .agk module.
    out, _, _ = run("import os.path\n"
                    "define function main:\n"
                    "    print(os.path.join(\"a\", \"b\"))\n")
    assert out == "a/b\n"


def test_duplicate_across_main_and_module_errors(tmp_path):
    (tmp_path / "helpers.agk").write_text(
        "define function f:\n    return 1\n")
    main = tmp_path / "main.agk"
    main.write_text("import helpers\n"
                    "define function f:\n    return 2\n")
    with pytest.raises(SemanticError, match="duplicate function 'f'"):
        compile_source(main.read_text(), filename=str(main))


def test_circular_imports_do_not_hang(tmp_path):
    (tmp_path / "a.agk").write_text(
        "import b\n"
        "define function fa:\n    return 1\n")
    (tmp_path / "b.agk").write_text(
        "import a\n"
        "define function fb:\n    return 2\n")
    main = tmp_path / "main.agk"
    main.write_text("import a\n"
                    "define function main:\n"
                    "    print(fa() + fb())\n")
    out, _, _ = run(main.read_text(), filename=str(main))
    assert out == "3\n"


def test_imported_module_constants_and_classes(tmp_path):
    (tmp_path / "shapes.agk").write_text(
        "define constant SIDES as Integer = 4\n"
        "define class Square:\n"
        "    variable w as Integer\n"
        "    define constructor that takes w as Integer:\n"
        "        set w to w\n")
    # NOTE: `set w to w` sets the parameter, not the field — the field
    # keeps its None default; this test only checks the class is usable.
    main = tmp_path / "main.agk"
    main.write_text("import shapes\n"
                    "define function main:\n"
                    "    print(SIDES)\n"
                    "    create s as Object\n"
                    "    set s to Square(5)\n"
                    "    print(\"ok\")\n")
    out, _, _ = run(main.read_text(), filename=str(main))
    assert out == "4\nok\n"
