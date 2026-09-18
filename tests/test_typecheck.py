"""Static type checker tests (AGK-Real v0.4.0 workstream 1).

Covers agk/typecheck.py: declared annotations on variables, constants,
function parameters, and return types are verified against inferred
types; mismatches are compile errors (TypeCheckError) with file:line
locations. Gradual typing: unknown types and `Object` never error.
"""

import subprocess
import sys

import pytest

from agk.errors import TypeCheckError
from agk.pipeline import compile_source, run_source


def check_ok(src):
    """Compiles cleanly (no type error)."""
    compile_source(src, filename="t.agk")


def check_fails(src, fragment):
    """Raises TypeCheckError whose message contains fragment."""
    with pytest.raises(TypeCheckError) as exc_info:
        compile_source(src, filename="t.agk")
    msg = str(exc_info.value)
    assert "type error" in msg
    assert "t.agk:" in msg  # file:line:col location
    assert fragment in msg
    return msg


# -- correct programs pass ---------------------------------------------------

def test_assign_matching_literal_types():
    check_ok(
        "define function main:\n"
        "    create count as Integer\n"
        "    set count to 42\n"
        "    create name as String\n"
        "    set name to \"hi\"\n"
        "    create ratio as Float\n"
        "    set ratio to 3.14\n"
        "    create flag as Boolean\n"
        "    set flag to true\n"
        "    create items as List\n"
        "    set items to [1, 2, 3]\n"
    )


def test_int_widens_to_float():
    check_ok(
        "define function main:\n"
        "    create ratio as Float\n"
        "    set ratio to 3\n"
    )


def test_object_accepts_anything():
    check_ok(
        "define function main:\n"
        "    create x as Object\n"
        "    set x to 5\n"
        "    set x to \"hi\"\n"
        "    set x to [1, 2]\n"
        "    set x to {\"a\": 1}\n"
    )


def test_object_value_flows_anywhere():
    check_ok(
        "define function take_int that takes n as Integer:\n"
        "    print(n)\n"
        "define function main:\n"
        "    create x as Object\n"
        "    set x to 5\n"
        "    take_int(x)\n"
        "    create i as Integer\n"
        "    set i to x\n"
    )


def test_correct_arg_and_return_types():
    check_ok(
        "define function add that takes a as Integer, b as Integer and returns Integer:\n"
        "    return a + b\n"
        "define function main:\n"
        "    create total as Integer\n"
        "    set total to add(1, 2)\n"
        "    print(total)\n"
    )


def test_string_concat_and_comparison_inference():
    check_ok(
        "define function main:\n"
        "    create greeting as String\n"
        "    set greeting to \"hello, \" + \"world\"\n"
        "    create same as Boolean\n"
        "    set same to greeting == \"hello, world\"\n"
    )


def test_unknown_types_never_error():
    # indexing a List has unknown element type; attribute calls on
    # Objects are unknown; for-each variables are unknown.
    check_ok(
        "define function main:\n"
        "    create items as List\n"
        "    set items to [1, 2, 3]\n"
        "    create first as Integer\n"
        "    set first to items[0]\n"
        "    create anything as Object\n"
        "    set anything to items\n"
        "    print(anything.pop())\n"
        "    for each x in items:\n"
        "        print(x)\n"
    )


def test_unannotated_return_type_is_untouched():
    check_ok(
        "define function maybe:\n"
        "    return 42\n"
        "define function main:\n"
        "    maybe()\n"
    )


def test_unannotated_code_passes():
    check_ok(
        "define function main:\n"
        "    create x as Integer\n"
        "    set x to 1\n"
        "    while x < 10:\n"
        "        set x to x + 1\n"
        "    print(x)\n"
    )


def test_builtin_result_types():
    check_ok(
        "define function main:\n"
        "    create n as Integer\n"
        "    set n to len(\"hello\")\n"
        "    create s as String\n"
        "    set s to str(42)\n"
        "    create f as Float\n"
        "    set f to float(2)\n"
        "    create b as Boolean\n"
        "    set b to bool(1)\n"
        "    create xs as List\n"
        "    set xs to sorted([3, 1])\n"
        "    create r as String\n"
        "    set r to \"n={n}\"\n"
    )


def test_field_assignment_matching_type():
    check_ok(
        "define class Account:\n"
        "    variable balance as Float\n"
        "    define constructor that takes initial as Float:\n"
        "        set balance to initial\n"
        "    define function get_balance that returns Float:\n"
        "        return balance\n"
        "define function main:\n"
        "    create a as Object\n"
        "    set a to Account(100.0)\n"
        "    print(a.get_balance())\n"
    )


def test_subclass_instance_assignable_to_base():
    check_ok(
        "define class Animal:\n"
        "    variable name as String\n"
        "    define constructor that takes n as String:\n"
        "        set name to n\n"
        "define class Dog extends Animal:\n"
        "    define constructor that takes n as String:\n"
        "        set name to n\n"
        "define function main:\n"
        "    create pet as Animal\n"
        "    set pet to Dog(\"rex\")\n"
    )


def test_method_call_arg_and_return_types():
    check_ok(
        "define class Counter:\n"
        "    variable n as Integer\n"
        "    define constructor:\n"
        "        set n to 0\n"
        "    define function bump that takes delta as Integer and returns Integer:\n"
        "        set n to n + delta\n"
        "        return n\n"
        "define function main:\n"
        "    create c as Counter\n"
        "    set c to Counter()\n"
        "    create v as Integer\n"
        "    set v to c.bump(2)\n"
    )


def test_correct_program_still_runs():
    out, _, _ = run_source(
        "define function add that takes a as Integer, b as Integer and returns Integer:\n"
        "    return a + b\n"
        "define function main:\n"
        "    print(add(20, 22))\n",
        filename="t.agk",
    )
    assert out.strip() == "42"


# -- mismatches fail ----------------------------------------------------------

def test_assign_string_to_integer():
    msg = check_fails(
        "define function main:\n"
        "    create count as Integer\n"
        "    set count to \"oops\"\n",
        "cannot assign String to variable 'count' declared as Integer",
    )
    assert msg.startswith("t.agk:3:")


def test_assign_float_to_integer():
    check_fails(
        "define function main:\n"
        "    create count as Integer\n"
        "    set count to 3.14\n",
        "cannot assign Float to variable 'count' declared as Integer",
    )


def test_assign_integer_to_boolean():
    check_fails(
        "define function main:\n"
        "    create flag as Boolean\n"
        "    set flag to 1\n",
        "cannot assign Integer to variable 'flag' declared as Boolean",
    )


def test_assign_dict_to_list():
    check_fails(
        "define function main:\n"
        "    create items as List\n"
        "    set items to {\"a\": 1}\n",
        "cannot assign Dict to variable 'items' declared as List",
    )


def test_wrong_argument_type():
    check_fails(
        "define function greet that takes name as String:\n"
        "    print(name)\n"
        "define function main:\n"
        "    greet(42)\n",
        "argument 'name' of function 'greet' expects String, got Integer",
    )


def test_wrong_argument_type_in_expression():
    check_fails(
        "define function double that takes n as Integer and returns Integer:\n"
        "    return n * 2\n"
        "define function main:\n"
        "    create x as Integer\n"
        "    set x to double(\"hi\") + 1\n",
        "argument 'n' of function 'double' expects Integer, got String",
    )


def test_wrong_return_type():
    check_fails(
        "define function greet that takes name as String and returns String:\n"
        "    return 42\n",
        "function 'greet' declares return type String, but returns Integer",
    )


def test_bare_return_with_declared_return_type():
    check_fails(
        "define function f that returns Integer:\n"
        "    return\n",
        "function 'f' declares return type Integer, but 'return' has no value",
    )


def test_returning_none_from_print():
    check_fails(
        "define function main:\n"
        "    create x as Integer\n"
        "    set x to print(\"hi\")\n",
        "cannot assign None to variable 'x' declared as Integer",
    )


def test_constant_type_mismatch():
    check_fails(
        "define constant LIMIT as Integer = \"ten\"\n",
        "constant 'LIMIT' declared as Integer, but value is String",
    )


def test_param_default_type_mismatch():
    check_fails(
        "define function greet that takes name as String = 42:\n"
        "    print(name)\n",
        "default value of parameter 'name' of function 'greet' is Integer, "
        "expected String",
    )


def test_field_assignment_mismatch():
    check_fails(
        "define class Account:\n"
        "    variable balance as Float\n"
        "    define constructor that takes initial as Float:\n"
        "        set balance to \"broke\"\n",
        "cannot assign String to field 'balance' declared as Float",
    )


def test_method_argument_mismatch():
    check_fails(
        "define class Counter:\n"
        "    define function bump that takes delta as Integer:\n"
        "        print(delta)\n"
        "define function main:\n"
        "    create c as Counter\n"
        "    set c to Counter()\n"
        "    c.bump(\"two\")\n",
        "argument 'delta' of method 'bump' of class 'Counter' expects "
        "Integer, got String",
    )


def test_method_return_mismatch():
    check_fails(
        "define class Box:\n"
        "    define function label that returns String:\n"
        "        return 7\n",
        "method 'label' of class 'Box' declares return type String, "
        "but returns Integer",
    )


def test_constructor_argument_mismatch():
    check_fails(
        "define class Point:\n"
        "    define constructor that takes x as Integer, y as Integer:\n"
        "        print(x)\n"
        "define function main:\n"
        "    create p as Object\n"
        "    set p to Point(1, \"two\")\n",
        "argument 'y' of constructor of class 'Point' expects Integer, "
        "got String",
    )


def test_class_mismatch_not_subclass():
    check_fails(
        "define class Cat:\n"
        "    define constructor:\n"
        "        print(\"meow\")\n"
        "define class Dog:\n"
        "    define constructor:\n"
        "        print(\"woof\")\n"
        "define function main:\n"
        "    create pet as Cat\n"
        "    set pet to Dog()\n",
        "cannot assign Dog to variable 'pet' declared as Cat",
    )


def test_binop_result_mismatch():
    check_fails(
        "define function main:\n"
        "    create s as String\n"
        "    set s to 1 + 2\n",
        "cannot assign Integer to variable 's' declared as String",
    )


def test_error_reports_file_line_col():
    with pytest.raises(TypeCheckError) as exc_info:
        compile_source(
            "define function main:\n"
            "    create count as Integer\n"
            "    set count to \"oops\"\n",
            filename="hello.agk",
        )
    err = exc_info.value
    assert (err.filename, err.line, err.column) == ("hello.agk", 3, 4)
    assert str(err) == (
        "hello.agk:3:4: type error: type mismatch: cannot assign String "
        "to variable 'count' declared as Integer"
    )


# -- end to end via the CLI ---------------------------------------------------

def _agk_check(path):
    return subprocess.run(
        [sys.executable, "-m", "agk", "check", str(path)],
        cwd="/home/hatch/workspace/agk-real",
        capture_output=True, text=True, timeout=60,
    )


def test_cli_check_rejects_type_error(tmp_path):
    bad = tmp_path / "bad.agk"
    bad.write_text(
        "define function add that takes a as Integer, b as Integer "
        "and returns Integer:\n"
        "    return a + b\n"
        "define function main:\n"
        "    create total as String\n"
        "    set total to add(1, 2)\n"
    )
    proc = _agk_check(bad)
    assert proc.returncode == 1
    assert "type error" in proc.stderr
    assert "bad.agk:5:" in proc.stderr


def test_cli_check_accepts_clean_program(tmp_path):
    good = tmp_path / "good.agk"
    good.write_text(
        "define function add that takes a as Integer, b as Integer "
        "and returns Integer:\n"
        "    return a + b\n"
        "define function main:\n"
        "    create total as Integer\n"
        "    set total to add(1, 2)\n"
        "    print(total)\n"
    )
    proc = _agk_check(good)
    assert proc.returncode == 0, proc.stderr
    assert "OK" in proc.stdout
