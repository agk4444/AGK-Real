"""Workstream 5 — tests for the AGK test runner (agk/test_runner.py)."""

import pytest

from agk.__main__ import main
from agk.test_runner import collect, run_tests


PASSING = """\
define function add that takes a as Integer, b as Integer and returns Integer:
    return a + b

define function test_add:
    create r as Integer
    set r to add(2, 3)
    if r != 5:
        raise "expected 5, got {r}"

define function test_add_again:
    create r as Integer
    set r to add(0, 0)
    if r != 0:
        raise "expected 0, got {r}"
"""

FAILING = """\
define function test_ok:
    create x as Integer
    set x to 1
    if x != 1:
        raise "should never fire"

define function test_broken:
    create x as Integer
    set x to 7
    if x != 8:
        raise "expected 8, got {x}"
"""

INTERPOLATED = """\
define function test_message:
    create name as String
    set name to "gopi"
    create got as Integer
    set got to 41
    raise "hello {name}, expected 42 but got {got}"
"""


def write(path, name, src):
    p = path / name
    p.write_text(src)
    return p


def test_all_passing(tmp_path, capsys):
    f = write(tmp_path, "test_math.agk", PASSING)
    assert run_tests(str(f)) == 0
    out = capsys.readouterr().out
    assert f"PASS {f}::test_add\n" in out
    assert f"PASS {f}::test_add_again\n" in out
    assert "2 passed, 0 failed" in out


def test_failing(tmp_path, capsys):
    f = write(tmp_path, "test_mixed.agk", FAILING)
    assert run_tests(str(f)) == 1
    out = capsys.readouterr().out
    assert f"PASS {f}::test_ok" in out
    assert f"FAIL {f}::test_broken" in out
    assert "1 passed, 1 failed" in out
    assert f"  {f}::test_broken" in out
    assert "test_ok" not in out.split("failed:")[-1]


def test_interpolated_raise_message_shown(tmp_path, capsys):
    f = write(tmp_path, "test_msg.agk", INTERPOLATED)
    assert run_tests(str(f)) == 1
    captured = capsys.readouterr()
    assert f"FAIL {f}::test_message" in captured.out
    assert "1 passed, 0 failed" not in captured.out
    assert "0 passed, 1 failed" in captured.out
    # The interpolated message and the AGK source line show up.
    assert "hello gopi, expected 42 but got 41" in captured.err
    assert f'File "{f}", line 6' in captured.err


def test_discovery_directory(tmp_path, capsys):
    a = write(tmp_path, "test_alpha.agk", PASSING)
    sub = tmp_path / "nested"
    sub.mkdir()
    b = write(sub, "beta_test.agk", PASSING)
    # Non-matching names must be ignored (even though this one would fail).
    write(tmp_path, "other.agk", FAILING)
    write(tmp_path, "notes.txt", "not agk")
    found = collect(str(tmp_path))
    assert set(found) == {a, b}
    assert found == sorted(found)
    assert run_tests(str(tmp_path)) == 0
    out = capsys.readouterr().out
    assert "other.agk" not in out
    assert "4 passed, 0 failed" in out


def test_collect_missing_path():
    with pytest.raises(FileNotFoundError):
        collect("/no/such/dir/agk-test-runner")


def test_run_tests_missing_path(capsys):
    assert run_tests("/no/such/dir/agk-test-runner") == 2
    assert "no such file or directory" in capsys.readouterr().err


def test_sibling_import(tmp_path, capsys):
    write(tmp_path, "helper.agk", """\
define function triple that takes n as Integer and returns Integer:
    return n * 3
""")
    f = write(tmp_path, "test_uses_helper.agk", """\
import helper

define function test_triple:
    create r as Integer
    set r to triple(7)
    if r != 21:
        raise "expected 21, got {r}"
""")
    assert run_tests(str(f)) == 0
    out = capsys.readouterr().out
    assert f"PASS {f}::test_triple" in out
    assert "1 passed, 0 failed" in out


def test_cli_test_command(tmp_path, capsys):
    a = write(tmp_path, "test_alpha.agk", PASSING)
    b = write(tmp_path, "beta_test.agk", PASSING)
    assert main(["test", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert f"PASS {a}::test_add" in out
    assert f"PASS {b}::test_add_again" in out
    assert "4 passed, 0 failed" in out


def test_cli_test_single_file(tmp_path, capsys):
    f = write(tmp_path, "test_math.agk", PASSING)
    assert main(["test", str(f)]) == 0
    assert "2 passed, 0 failed" in capsys.readouterr().out


def test_cli_test_too_many_args(tmp_path, capsys):
    assert main(["test", "a", "b"]) == 2
    assert "python -m agk test [path]" in capsys.readouterr().err
