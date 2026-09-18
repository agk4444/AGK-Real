"""Tests for `agk debug` — the AGK-aware pdb wrapper.

The debugger is driven with scripted stdin (break, continue, print,
step, ...) via a subprocess so each run gets a fresh pdb/bdb state.
Assertions check that line numbers shown are AGK lines (not generated
Python lines) and that variable values are right.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from agk.__main__ import main
from agk.pipeline import agk_line_map, compile_source

ROOT = Path(__file__).parent.parent

# AGK lines: 1 def add, 3 set result, 4 return, 6 def main, 8 set x,
# 9 print(x).
PROG = (
    "define function add that takes a as Integer, b as Integer:\n"
    "    create result as Integer\n"
    "    set result to a + b\n"
    "    return result\n"
    "\n"
    "define function main:\n"
    "    create x as Integer\n"
    "    set x to add(2, 3)\n"
    "    print(x)\n"
)

# AGK lines: 1 class, 4 set n (constructor), 6 set n (bump),
# 8 return (get), 9 def main, 13 print(c.get()).
COUNTER = (
    "define class Counter:\n"
    "    variable n as Integer\n"
    "    define constructor that takes start as Integer:\n"
    "        set n to start\n"
    "    define function bump:\n"
    "        set n to n + 1\n"
    "    define function get that returns Integer:\n"
    "        return n\n"
    "define function main:\n"
    "    create c as Object\n"
    "    set c to Counter(0)\n"
    "    c.bump()\n"
    "    print(c.get())\n"
)

BOOM = "define function main:\n    print(1 / 0)\n"
BAD = "define function main:\n    set x to 1\n"


def write(tmp_path, name, src):
    p = tmp_path / name
    p.write_text(src)
    return str(p)


def run_debug(prog, script):
    return subprocess.run(
        [sys.executable, "-m", "agk", "debug", str(prog)],
        input=script, capture_output=True, text=True,
        cwd=str(ROOT), timeout=60)


def test_debug_break_continue_print(tmp_path):
    prog = write(tmp_path, "prog.agk", PROG)
    result = run_debug(prog, "break 9\ncontinue\np x\ncontinue\n")
    assert result.returncode == 0
    out = result.stdout
    # Breakpoint confirmation uses the AGK file:line ...
    assert f"Breakpoint 1 at {prog}:9" in out
    # ... and the stop shows the AGK location, not generated Python.
    assert f'"{prog}"(9)main()' in out
    assert "-> print(x)" in out
    assert "(agk) 5" in out.splitlines()  # p x


def test_debug_break_in_function_where(tmp_path):
    prog = write(tmp_path, "prog.agk", PROG)
    result = run_debug(prog, "break 3\ncontinue\nwhere\np a\np b\ncontinue\n")
    assert result.returncode == 0
    out = result.stdout
    assert f"Breakpoint 1 at {prog}:3" in out
    # Frames show AGK lines inside the right functions.
    assert f'"{prog}"(3)add()' in out
    assert f'"{prog}"(8)main()' in out
    assert "(agk) 2" in out.splitlines()  # p a
    assert "(agk) 3" in out.splitlines()  # p b


def test_debug_break_filename_colon_line(tmp_path):
    prog = write(tmp_path, "prog.agk", PROG)
    name = Path(prog).name
    result = run_debug(prog, f"break {name}:3\ncontinue\np a\ncontinue\n")
    assert result.returncode == 0
    assert f"Breakpoint 1 at {prog}:3" in result.stdout
    assert "(agk) 2" in result.stdout.splitlines()


def test_debug_step_into_function(tmp_path):
    prog = write(tmp_path, "prog.agk", PROG)
    result = run_debug(prog, "break 8\ncontinue\nstep\nstep\ncontinue\n")
    assert result.returncode == 0
    out = result.stdout
    # step stops at the call (AGK def line), then on the first real line.
    assert f'"{prog}"(1)add()' in out
    assert f'"{prog}"(3)add()' in out


def test_debug_list_shows_agk_source(tmp_path):
    prog = write(tmp_path, "prog.agk", PROG)
    result = run_debug(prog, "break 9\ncontinue\nlist\ncontinue\n")
    assert result.returncode == 0
    out = result.stdout
    assert "set x to add(2, 3)" in out
    assert "->B    9      print(x)" in out  # current line + bp marker


def test_debug_break_no_code_line(tmp_path):
    prog = write(tmp_path, "prog.agk", PROG)
    result = run_debug(prog, "break 5\ncontinue\n")
    assert result.returncode == 0
    assert f"*** No code at {prog}:5" in result.stdout  # line 5 is blank


def test_debug_class_field_self_mapping(tmp_path):
    # Bare field reads compile to self.<field>; `p n` must still work.
    prog = write(tmp_path, "counter.agk", COUNTER)
    result = run_debug(prog, "break 6\ncontinue\np n\nnext\np n\ncontinue\n")
    assert result.returncode == 0
    out = result.stdout
    assert f'"{prog}"(6)bump()' in out
    assert "*** NameError" not in out
    assert "(agk) 0" in out.splitlines()  # p n before the increment
    assert "(agk) 1" in out.splitlines()  # p n after `next`


def test_debug_unhandled_exception_agk_traceback(tmp_path):
    prog = write(tmp_path, "boom.agk", BOOM)
    result = run_debug(prog, "continue\n")
    assert result.returncode == 2
    assert "boom.agk" in result.stderr
    assert "line 2" in result.stderr
    assert "ZeroDivisionError" in result.stderr
    # No debugger-machinery frames leak into the traceback.
    assert "debugger.py" not in result.stderr
    assert "bdb.py" not in result.stderr


def test_debug_missing_file():
    with pytest.raises(SystemExit) as e:
        main(["debug", "nope.agk"])
    assert e.value.code == 2


def test_debug_compile_error(tmp_path, capsys):
    with pytest.raises(SystemExit) as e:
        main(["debug", write(tmp_path, "b.agk", BAD)])
    assert e.value.code == 1
    assert "error" in capsys.readouterr().err


def test_debug_usage():
    assert main(["debug"]) == 2


def test_agk_line_map_public():
    code, _warnings = compile_source(PROG, filename="p.agk", annotate=True)
    line_map = agk_line_map(code)
    pairs = {(agk_line, py_line) for py_line, (_f, agk_line)
             in line_map.items()}
    agk_lines = {a for a, _p in pairs}
    # Every executable AGK line is mapped (blank lines are not).
    assert agk_lines == {1, 3, 4, 6, 8, 9}
