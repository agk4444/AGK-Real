"""Workstream 4 — stdlib expansion tests (AGK-Real v1 test plan).

Covers csvutils, regexutils, sqliteutils, and the plain-Python-import
passthrough pattern for `sys.argv` (no compiler change needed).
"""

import sys

from agk.pipeline import run_source


def run(src, **kw):
    return run_source(src, **kw)


# --- csvutils --------------------------------------------------------------

def test_csvutils_imports_cleanly():
    out, _, warnings = run("import csvutils\n"
                           "define function main:\n"
                           '    print("ok")\n')
    assert warnings == []
    assert out == "ok\n"


def test_csv_parse():
    src = ("import csvutils\n"
           "define function main:\n"
           '    create rows as List\n'
           '    set rows to csv_parse("name,age\\nAmy,30\\nBob,25\\n")\n'
           "    print(rows)\n"
           "    print(rows[0])\n")
    out, _, warnings = run(src)
    assert warnings == []
    assert out == ("[['name', 'age'], ['Amy', '30'], ['Bob', '25']]\n"
                   "['name', 'age']\n")


def test_csv_parse_quoted_fields():
    # Header row is just row 0; quoted commas stay inside one field.
    src = ("import csvutils\n"
           "define function main:\n"
           '    create rows as List\n'
           '    set rows to csv_parse("a,b\\n\\"x,y\\",2\\n")\n'
           "    print(rows[1])\n")
    out, _, _ = run(src)
    assert out == "['x,y', '2']\n"


def test_csv_round_trip():
    # parse -> serialize -> parse must reproduce the original rows.
    src = ("import csvutils\n"
           "define function main:\n"
           '    create rows as List\n'
           '    set rows to csv_parse("a,b\\n1,2\\n3,4\\n")\n'
           "    create text as String\n"
           "    set text to csv_to_text(rows)\n"
           "    create rows2 as List\n"
           "    set rows2 to csv_parse(text)\n"
           "    print(rows2)\n"
           "    print(rows2 == rows)\n")
    out, _, warnings = run(src)
    assert warnings == []
    assert out == "[['a', 'b'], ['1', '2'], ['3', '4']]\nTrue\n"


# --- regexutils ------------------------------------------------------------

def test_regexutils_imports_cleanly():
    out, _, warnings = run("import regexutils\n"
                           "define function main:\n"
                           '    print("ok")\n')
    assert warnings == []
    assert out == "ok\n"


def test_regex_match():
    src = ("import regexutils\n"
           "define function main:\n"
           '    print(regex_match("\\\\d+", "abc123"))\n'
           '    print(regex_match("^\\\\d+$", "abc123"))\n'
           '    print(regex_match("\\\\d+", "no digits"))\n')
    out, _, warnings = run(src)
    assert warnings == []
    assert out == "True\nFalse\nFalse\n"


def test_regex_find_all():
    src = ("import regexutils\n"
           "define function main:\n"
           '    print(regex_find_all("\\\\d+", "a1b22c333"))\n')
    out, _, warnings = run(src)
    assert warnings == []
    assert out == "['1', '22', '333']\n"


def test_regex_replace():
    src = ("import regexutils\n"
           "define function main:\n"
           '    print(regex_replace("\\\\s+", "-", "a b  c"))\n'
           '    print(regex_replace("o", "0", "foo"))\n')
    out, _, warnings = run(src)
    assert warnings == []
    assert out == "a-b-c\nf00\n"


def test_regex_split():
    src = ("import regexutils\n"
           "define function main:\n"
           '    print(regex_split(",\\\\s*", "a, b,c"))\n')
    out, _, warnings = run(src)
    assert warnings == []
    assert out == "['a', 'b', 'c']\n"


# --- sqliteutils -----------------------------------------------------------

def test_sqliteutils_imports_cleanly():
    out, _, warnings = run("import sqliteutils\n"
                           "define function main:\n"
                           '    print("ok")\n')
    assert warnings == []
    assert out == "ok\n"


def test_sqlite_create_insert_select(tmp_path):
    db = str(tmp_path / "test.db")
    src = ("import sqliteutils\n"
           "define function main:\n"
           '    create p as String\n'
           f'    set p to "{db}"\n'
           '    print(db_execute(p, "CREATE TABLE t (name TEXT, n INT)"))\n'
           "    print(db_execute(p, \"INSERT INTO t VALUES ('amy', 7)\"))\n"
           "    print(db_execute(p, \"INSERT INTO t VALUES ('bob', 3)\"))\n"
           '    print(db_query(p, "SELECT * FROM t ORDER BY n"))\n')
    out, _, warnings = run(src)
    assert warnings == []
    assert out == "ok\nok\nok\n[['bob', 3], ['amy', 7]]\n"


def test_sqlite_empty_result(tmp_path):
    db = str(tmp_path / "empty.db")
    src = ("import sqliteutils\n"
           "define function main:\n"
           '    create p as String\n'
           f'    set p to "{db}"\n'
           '    print(db_execute(p, "CREATE TABLE t (x TEXT)"))\n'
           '    print(db_query(p, "SELECT * FROM t"))\n')
    out, _, warnings = run(src)
    assert warnings == []
    assert out == "ok\n[]\n"


# --- plain-Python-import passthrough: sys.argv -----------------------------

def test_sys_argv_passthrough(monkeypatch):
    # Verified pattern: a bare `import sys` passes straight through to the
    # generated Python, so compiled AGK programs can read sys.argv with no
    # compiler change. (run_source execs in-process, so monkeypatching
    # sys.argv affects the program under test.)
    monkeypatch.setattr(sys, "argv", ["prog", "alpha", "beta"])
    src = ("import sys\n"
           "define function main:\n"
           "    print(sys.argv[0])\n"
           "    print(sys.argv[1])\n"
           "    print(sys.argv[2])\n")
    out, _, warnings = run(src)
    assert warnings == []
    assert out == "prog\nalpha\nbeta\n"


def test_sys_argv_arg_count(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["prog"])
    src = ("import sys\n"
           "define function main:\n"
           "    print(len(sys.argv))\n")
    out, _, _ = run(src)
    assert out == "1\n"
