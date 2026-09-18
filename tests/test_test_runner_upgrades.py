"""Workstream 5 (v0.4.0) — fixtures, mocks, and coverage for the test runner."""

import re
from pathlib import Path

import pytest

from agk.__main__ import main
from agk.mock import Mock, install_helpers, patch
from agk.test_runner import run_tests


def write(path, name, src):
    p = path / name
    p.write_text(src)
    return p


def fx_markers(out):
    """Ordered FX: markers printed by fixture test files."""
    return [l for l in out.splitlines() if l.startswith("FX:")]


def coverage_row(out, path):
    """(pct, covered, total) parsed from the coverage table row for path."""
    name = Path(path).name
    row = next(
        l for l in out.splitlines()
        if name in l and re.search(r"\d+% \(\d+/\d+ lines\)", l)
    )
    m = re.search(r"(\d+)% \((\d+)/(\d+) lines\)", row)
    assert m, f"no coverage row for {path}: {row!r}"
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


# -- fixtures --------------------------------------------------------

FIXTURE_ORDER = """\
define function setup:
    print("FX:setup")

define function teardown:
    print("FX:teardown")

define function test_one:
    print("FX:test_one")

define function test_two:
    print("FX:test_two")
"""


def test_fixtures_run_in_order(tmp_path, capsys):
    f = write(tmp_path, "test_fx.agk", FIXTURE_ORDER)
    assert run_tests(str(f)) == 0
    out = capsys.readouterr().out
    assert fx_markers(out) == [
        "FX:setup", "FX:test_one", "FX:teardown",
        "FX:setup", "FX:test_two", "FX:teardown",
    ]
    assert "2 passed, 0 failed" in out


def test_teardown_runs_on_failure(tmp_path, capsys):
    f = write(tmp_path, "test_fxfail.agk", """\
define function setup:
    print("FX:setup")

define function teardown:
    print("FX:teardown")

define function test_boom:
    print("FX:test_boom")
    raise "kaboom"
""")
    assert run_tests(str(f)) == 1
    out = capsys.readouterr().out
    # teardown ran even though the test raised
    assert fx_markers(out) == ["FX:setup", "FX:test_boom", "FX:teardown"]
    assert f"FAIL {f}::test_boom" in out
    assert "0 passed, 1 failed" in out


def test_teardown_runs_when_setup_fails(tmp_path, capsys):
    f = write(tmp_path, "test_fxsetup.agk", """\
define function setup:
    print("FX:setup")
    raise "setup blew up"

define function teardown:
    print("FX:teardown")

define function test_never_runs:
    print("FX:test_never_runs")
""")
    assert run_tests(str(f)) == 1
    out = capsys.readouterr().out
    markers = fx_markers(out)
    assert markers == ["FX:setup", "FX:teardown"]
    assert f"FAIL {f}::test_never_runs" in out


def test_no_fixtures_still_works(tmp_path, capsys):
    f = write(tmp_path, "test_nofx.agk", """\
define function test_ok:
    create x as Integer
    set x to 1
    if x != 1:
        raise "unreachable"
""")
    assert run_tests(str(f)) == 0
    assert "1 passed, 0 failed" in capsys.readouterr().out


def test_setup_teardown_are_not_tests(tmp_path, capsys):
    f = write(tmp_path, "test_fxnaming.agk", FIXTURE_ORDER)
    assert run_tests(str(f)) == 0
    out = capsys.readouterr().out
    assert "::setup" not in out
    assert "::teardown" not in out


# -- mocks (Python level) --------------------------------------------

def test_patch_records_calls_and_restores():
    ns = {"fetch": lambda uid: uid * 10}
    m = patch(ns, "fetch", return_value=42)
    assert isinstance(m, Mock)
    assert ns["fetch"](7) == 42
    assert ns["fetch"]("x", key=1) == 42
    assert m.call_count() == 2
    assert m.call_arg(0, 0) == 7
    assert m.call_arg(1, 0) == "x"
    assert m.calls[1] == (("x",), {"key": 1})
    m.restore()
    assert ns["fetch"](7) == 70
    assert m.call_count() == 2  # history survives restore


def test_patch_unknown_name_raises():
    with pytest.raises(ValueError, match="no function named 'nope'"):
        patch({}, "nope")


def test_patch_non_callable_raises():
    with pytest.raises(ValueError, match="not callable"):
        patch({"x": 5}, "x")


def test_install_helpers_roundtrip():
    ns = {"f": lambda: "real"}
    helpers = install_helpers(ns)
    ns.update(helpers)
    m = ns["mock_return"]("f", "stubbed")
    assert ns["f"]() == "stubbed"
    assert m.call_count() == 1
    ns["unmock"](m)
    assert ns["f"]() == "real"
    with pytest.raises(ValueError, match="expected a Mock"):
        ns["unmock"]("not-a-mock")


# -- mocks (AGK level) ------------------------------------------------

MOCK_AGK = """\
define function fetch_price that takes sym as String and returns Integer:
    return 999

define function total_for that takes sym as String and returns Integer:
    create p as Integer
    set p to fetch_price(sym)
    return p * 2

define function test_mock_records_and_restores:
    create m as Mock
    set m to mock_return("fetch_price", 42)
    create t as Integer
    set t to total_for("ACME")
    if t != 84:
        raise "stubbed call wrong: {t}"
    if m.call_count() != 1:
        raise "expected 1 call"
    create arg0 as String
    set arg0 to m.call_arg(0, 0)
    if arg0 != "ACME":
        raise "arg wrong: {arg0}"
    unmock(m)
    create t2 as Integer
    set t2 to total_for("ACME")
    if t2 != 1998:
        raise "mock not restored: {t2}"

define function test_mock_void_function:
    create m as Mock
    set m to mock("ping")
    ping("hello")
    ping("world")
    if m.call_count() != 2:
        raise "expected 2 calls"
    create second as String
    set second to m.call_arg(1, 0)
    if second != "world":
        raise "second call arg wrong: {second}"
    unmock(m)

define function ping that takes msg as String:
    print("real ping: {msg}")
"""


def test_mock_in_agk_test(tmp_path, capsys):
    f = write(tmp_path, "test_mock.agk", MOCK_AGK)
    assert run_tests(str(f)) == 0
    out = capsys.readouterr().out
    assert f"PASS {f}::test_mock_records_and_restores" in out
    assert f"PASS {f}::test_mock_void_function" in out
    assert "2 passed, 0 failed" in out


def test_mock_of_imported_helper(tmp_path, capsys):
    write(tmp_path, "helper.agk", """\
define function triple that takes n as Integer and returns Integer:
    return n * 3
""")
    f = write(tmp_path, "test_mockimp.agk", """\
import helper

define function test_mock_imported:
    create m as Mock
    set m to mock_return("triple", 100)
    create r as Integer
    set r to triple(5)
    if r != 100:
        raise "imported mock not hit: {r}"
    if m.call_count() != 1:
        raise "expected 1 call"
    unmock(m)
    if triple(5) != 15:
        raise "restore failed"
""")
    assert run_tests(str(f)) == 0
    assert "1 passed, 0 failed" in capsys.readouterr().out


def test_mock_unknown_name_fails_test(tmp_path, capsys):
    f = write(tmp_path, "test_mockbad.agk", """\
define function test_typo:
    create m as Mock
    set m to mock("does_not_exist")
""")
    assert run_tests(str(f)) == 1
    captured = capsys.readouterr()
    assert f"FAIL {f}::test_typo" in captured.out
    assert "no function named 'does_not_exist'" in captured.err


# -- coverage ----------------------------------------------------------

COVERAGE_PARTIAL = """\
define function used_fn that takes x as Integer and returns Integer:
    return x + 1

define function unused_fn that takes x as Integer and returns Integer:
    return x - 1

define function test_used:
    create r as Integer
    set r to used_fn(1)
    if r != 2:
        raise "bad"
"""


def test_coverage_reports_partial(tmp_path, capsys):
    f = write(tmp_path, "test_cov.agk", COVERAGE_PARTIAL)
    assert run_tests(str(f), coverage=True) == 0
    out = capsys.readouterr().out
    assert "coverage:" in out
    pct, covered, total = coverage_row(out, f)
    assert 0 < pct < 100  # unused_fn never called
    assert covered < total
    assert total > 0


def test_coverage_full_when_everything_runs(tmp_path, capsys):
    f = write(tmp_path, "test_covfull.agk", """\
define function test_trivial:
    print("hello")
""")
    assert run_tests(str(f), coverage=True) == 0
    out = capsys.readouterr().out
    pct, covered, total = coverage_row(out, f)
    assert pct == 100
    assert covered == total


def test_coverage_excludes_bundled_modules(tmp_path, capsys):
    f = write(tmp_path, "test_covstd.agk", """\
import strutils

define function test_shout:
    create s as String
    set s to shout("hey")
    if s != "HEY!":
        raise "bad: {s}"
""")
    assert run_tests(str(f), coverage=True) == 0
    out = capsys.readouterr().out
    assert "coverage:" in out
    rows = [l for l in out.splitlines() if re.search(r"\d+% \(\d+/\d+ lines\)", l)]
    assert rows, "expected at least one coverage row"
    # the bundled stdlib module inlined by the import is excluded
    assert not any("/stdlib/" in r for r in rows), rows
    assert any("test_covstd.agk" in r for r in rows)


def test_no_coverage_table_by_default(tmp_path, capsys):
    f = write(tmp_path, "test_nocov.agk", COVERAGE_PARTIAL)
    assert run_tests(str(f)) == 0
    assert "coverage:" not in capsys.readouterr().out


def test_cli_coverage_flag(tmp_path, capsys):
    f = write(tmp_path, "test_clicov.agk", COVERAGE_PARTIAL)
    assert main(["test", "--coverage", str(f)]) == 0
    out = capsys.readouterr().out
    assert "coverage:" in out
    pct, _covered, _total = coverage_row(out, f)
    assert 0 < pct < 100


def test_cli_coverage_flag_no_path(tmp_path, capsys, monkeypatch):
    write(tmp_path, "test_clicov2.agk", COVERAGE_PARTIAL)
    monkeypatch.chdir(tmp_path)
    assert main(["test", "--coverage"]) == 0
    out = capsys.readouterr().out
    assert "coverage:" in out
    assert "1 passed, 0 failed" in out
