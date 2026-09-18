"""M6 — CLI tests (AGK-Real v1 test plan)."""

import ast as py_ast

import pytest

from agk.__main__ import main

HELLO = "define function main:\n    print(\"hello, agk\")\n"
BAD = "define function main:\n    set x to 1\n"
BOOM = "define function main:\n    print(1 / 0)\n"


def write(tmp_path, name, src):
    p = tmp_path / name
    p.write_text(src)
    return str(p)


def test_run_ok(tmp_path, capsys):
    assert main(["run", write(tmp_path, "h.agk", HELLO)]) == 0
    assert capsys.readouterr().out == "hello, agk\n"


def test_run_compile_error(tmp_path, capsys):
    with pytest.raises(SystemExit) as e:
        main(["run", write(tmp_path, "b.agk", BAD)])
    assert e.value.code == 1
    assert "error" in capsys.readouterr().err


def test_run_runtime_error(tmp_path, capsys):
    with pytest.raises(SystemExit) as e:
        main(["run", write(tmp_path, "r.agk", BOOM)])
    assert e.value.code == 2


def test_run_missing_file(capsys):
    with pytest.raises(SystemExit) as e:
        main(["run", "nope.agk"])
    assert e.value.code == 2


def test_build_default_name(tmp_path):
    src = write(tmp_path, "h.agk", HELLO)
    assert main(["build", src]) == 0
    out = tmp_path / "h.py"
    py_ast.parse(out.read_text())  # valid Python


def test_build_explicit_out(tmp_path, capsys):
    src = write(tmp_path, "h.agk", HELLO)
    out = str(tmp_path / "custom.py")
    assert main(["build", src, "-o", out]) == 0
    assert "wrote" in capsys.readouterr().out
    py_ast.parse(open(out).read())


def test_check_ok(tmp_path, capsys):
    assert main(["check", write(tmp_path, "h.agk", HELLO)]) == 0
    assert "OK" in capsys.readouterr().out


def test_check_bad(tmp_path):
    with pytest.raises(SystemExit) as e:
        main(["check", write(tmp_path, "b.agk", BAD)])
    assert e.value.code == 1


def test_unknown_command(capsys):
    assert main(["frobnicate"]) == 2


def test_run_reports_warnings_not_errors(tmp_path, capsys):
    src = write(tmp_path, "w.agk",
                "define function main:\n"
                "    create x as Integer\n"
                "    print(\"hi\")\n")
    assert main(["run", src]) == 0
    err = capsys.readouterr().err
    assert "never assigned" in err
