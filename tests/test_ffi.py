"""Workstream 8 — FFI via `extern function` declarations.

Covers parsing, semantic validation, ctypes codegen, and end-to-end
calls against real libc functions. The end-to-end tests need Linux libc
and are skipped elsewhere; the compile-time tests run everywhere.
"""

import os
import sys

import pytest

from agk import ast_nodes as A
from agk.errors import ParserError, SemanticError
from agk.parser import parse
from agk.pipeline import compile_source, run_source

LINUX = sys.platform.startswith("linux")
needs_linux = pytest.mark.skipif(not LINUX, reason="needs Linux libc")


def compile_ok(src):
    code, warnings = compile_source(src, filename="t.agk")
    assert warnings == []
    return code


def compile_err(src, exc):
    with pytest.raises(exc):
        compile_source(src, filename="t.agk")


# --- parsing ---------------------------------------------------------------

def test_extern_parses_full_form():
    prog = parse('extern function strlen that takes s as String '
                 'and returns Integer from "c"\n')
    (decl,) = prog.statements
    assert isinstance(decl, A.ExternDef)
    assert decl.name == "strlen"
    assert [(p.name, p.type_name) for p in decl.params] == [("s", "String")]
    assert decl.return_type == "Integer"
    assert decl.lib == "c"


def test_extern_parses_multiple_params_no_return():
    prog = parse('extern function strcmp that takes a as String, b as String '
                 'from "c"\n')
    (decl,) = prog.statements
    assert decl.name == "strcmp"
    assert [p.name for p in decl.params] == ["a", "b"]
    assert decl.return_type is None


def test_extern_parses_that_returns_without_takes():
    prog = parse('extern function getpid that returns Integer from "c"\n')
    (decl,) = prog.statements
    assert decl.params == []
    assert decl.return_type == "Integer"


def test_extern_requires_from_clause():
    compile_err('extern function strlen that takes s as String '
                'and returns Integer\n',
                ParserError)


def test_extern_requires_quoted_library():
    compile_err('extern function strlen from c\n', ParserError)


def test_extern_rejects_default_value():
    compile_err('extern function f that takes n as Integer = 3 '
                'from "c"\n',
                ParserError)


def test_extern_rejects_missing_name():
    compile_err('extern function that takes n as Integer from "c"\n',
                ParserError)


def test_extern_only_at_top_level():
    compile_err('define function main:\n'
                '    extern function strlen that takes s as String '
                'from "c"\n',
                ParserError)


def test_extern_keyword_lexes():
    from agk.lexer import Lexer
    from agk.tokens import TokenType as T
    toks = Lexer('extern function f from "c"\n', "<t>").tokenize()
    assert toks[0].type == T.EXTERN


# --- semantic validation -----------------------------------------------------

def test_extern_rejects_unsupported_param_type():
    with pytest.raises(SemanticError, match="unsupported parameter type"):
        compile_source('extern function f that takes xs as List '
                       'from "c"\n'
                       'define function main:\n'
                       '    print(1)\n')


def test_extern_rejects_unsupported_return_type():
    with pytest.raises(SemanticError, match="unsupported return type"):
        compile_source('extern function f that returns Object from "c"\n'
                       'define function main:\n'
                       '    print(1)\n')


def test_extern_accepts_all_supported_types():
    compile_ok('extern function f that takes a as String, b as Integer, '
               'c as Float, d as Boolean and returns Boolean from "c"\n'
               'define function main:\n'
               '    print(1)\n')


def test_extern_arity_checked_too_many():
    with pytest.raises(SemanticError, match="takes 1 argument"):
        compile_source('extern function strlen that takes s as String '
                       'and returns Integer from "c"\n'
                       'define function main:\n'
                       '    print(strlen("a", "b"))\n')


def test_extern_arity_checked_too_few():
    with pytest.raises(SemanticError, match="takes 1 argument"):
        compile_source('extern function strlen that takes s as String '
                       'and returns Integer from "c"\n'
                       'define function main:\n'
                       '    print(strlen())\n')


def test_extern_duplicate_declaration():
    with pytest.raises(SemanticError, match="duplicate extern function"):
        compile_source('extern function strlen that takes s as String '
                       'from "c"\n'
                       'extern function strlen that takes s as String '
                       'from "c"\n')


def test_extern_collides_with_defined_function():
    with pytest.raises(SemanticError, match="duplicate"):
        compile_source('define function strlen:\n'
                       '    return 0\n'
                       'extern function strlen that takes s as String '
                       'from "c"\n')


def test_function_collides_with_extern():
    with pytest.raises(SemanticError, match="duplicate"):
        compile_source('extern function strlen that takes s as String '
                       'from "c"\n'
                       'define function strlen:\n'
                       '    return 0\n')


def test_extern_empty_library_rejected():
    with pytest.raises(SemanticError, match="must not be empty"):
        compile_source('extern function f from ""\n'
                       'define function main:\n'
                       '    print(1)\n')


def test_extern_duplicate_params_rejected():
    with pytest.raises(SemanticError, match="duplicate parameter"):
        compile_source('extern function f that takes a as Integer, '
                       'a as Integer from "c"\n'
                       'define function main:\n'
                       '    print(1)\n')


def test_extern_may_shadow_builtin():
    # C libraries export names like `abs`; an extern may deliberately
    # rebind the builtin in the generated module.
    code = compile_ok('extern function abs that takes n as Integer '
                      'and returns Integer from "c"\n'
                      'define function main:\n'
                      '    print(abs(-3))\n')
    assert "def abs(n):" in code


def test_extern_shadowing_builtin_still_arity_checked():
    with pytest.raises(SemanticError, match="takes 1 argument"):
        compile_source('extern function abs that takes n as Integer '
                       'and returns Integer from "c"\n'
                       'define function main:\n'
                       '    print(abs())\n')


def test_extern_suggests_on_typo():
    with pytest.raises(SemanticError, match="did you mean 'strlen'"):
        compile_source('extern function strlen that takes s as String '
                       'and returns Integer from "c"\n'
                       'define function main:\n'
                       '    print(strln("hi"))\n')


# --- codegen -----------------------------------------------------------------

def test_codegen_emits_ctypes_binding():
    code = compile_ok('extern function strlen that takes s as String '
                      'and returns Integer from "c"\n'
                      'define function main:\n'
                      '    print(strlen("hello"))\n')
    assert "import ctypes" in code
    assert "import ctypes.util" in code
    assert "ctypes.util.find_library" in code
    assert "_agk_extern_strlen.argtypes = [ctypes.c_char_p]" in code
    assert "_agk_extern_strlen.restype = ctypes.c_int" in code
    assert 's.encode("utf-8")' in code
    assert "def strlen(s):" in code


def test_codegen_library_loaded_once():
    code = compile_ok('extern function strlen that takes s as String '
                      'and returns Integer from "c"\n'
                      'extern function getpid that returns Integer '
                      'from "c"\n'
                      'define function main:\n'
                      '    print(1)\n')
    assert code.count("def _agk_load_library(name):") == 1
    assert code.count('_agk_load_library("c")') == 1
    assert "_agk_lib0.strlen" in code
    assert "_agk_lib0.getpid" in code


def test_codegen_distinct_libraries():
    code = compile_ok('extern function strlen that takes s as String '
                      'and returns Integer from "c"\n'
                      'extern function sin that takes x as Float '
                      'and returns Float from "m"\n'
                      'define function main:\n'
                      '    print(1)\n')
    assert '_agk_lib0 = _agk_load_library("c")' in code
    assert '_agk_lib1 = _agk_load_library("m")' in code
    assert "_agk_extern_sin.restype = ctypes.c_double" in code
    assert "_agk_extern_sin.argtypes = [ctypes.c_double]" in code


def test_codegen_path_library_used_verbatim():
    code = compile_ok('extern function strlen that takes s as String '
                      'and returns Integer from "/lib/libc.so.6"\n'
                      'define function main:\n'
                      '    print(1)\n')
    assert '_agk_load_library("/lib/libc.so.6")' in code


def test_codegen_string_return_decodes_with_null_guard():
    code = compile_ok('extern function getenv that takes name as String '
                      'and returns String from "c"\n'
                      'define function main:\n'
                      '    print(getenv("PATH"))\n')
    assert "_agk_extern_getenv.restype = ctypes.c_char_p" in code
    assert '_r.decode("utf-8")' in code
    assert "_r is None" in code


def test_codegen_void_extern():
    code = compile_ok('extern function sleep that takes n as Integer '
                      'from "c"\n'
                      'define function main:\n'
                      '    sleep(0)\n')
    assert "_agk_extern_sleep.restype = None" in code
    assert "def sleep(n):" in code


def test_codegen_boolean_mapping():
    code = compile_ok('extern function isatty that takes fd as Integer '
                      'and returns Boolean from "c"\n'
                      'define function main:\n'
                      '    print(isatty(1))\n')
    assert "_agk_extern_isatty.restype = ctypes.c_bool" in code


# --- end to end against real libc --------------------------------------------

@needs_linux
def test_ffi_strlen():
    out, _, warnings = run_source(
        'extern function strlen that takes s as String and returns Integer '
        'from "c"\n'
        'define function main:\n'
        '    print(strlen("hello"))\n')
    assert warnings == []
    assert out == "5\n"


@needs_linux
def test_ffi_getpid():
    out, _, _ = run_source(
        'extern function getpid that returns Integer from "c"\n'
        'define function main:\n'
        '    print(getpid())\n')
    assert out == f"{os.getpid()}\n"


@needs_linux
def test_ffi_toupper():
    out, _, _ = run_source(
        'extern function toupper that takes ch as Integer and returns '
        'Integer from "c"\n'
        'define function main:\n'
        '    print(toupper(97))\n')
    assert out == "65\n"


@needs_linux
def test_ffi_abs_shadowing_builtin():
    out, _, _ = run_source(
        'extern function abs that takes n as Integer and returns Integer '
        'from "c"\n'
        'define function main:\n'
        '    print(abs(-3))\n')
    assert out == "3\n"


@needs_linux
def test_ffi_string_return_decodes():
    out, _, _ = run_source(
        'extern function getenv that takes name as String and returns '
        'String from "c"\n'
        'define function main:\n'
        '    print(len(getenv("PATH")) > 0)\n')
    assert out == "True\n"


@needs_linux
def test_ffi_combined_program():
    src = ('extern function strlen that takes s as String and returns '
           'Integer from "c"\n'
           'extern function getpid that returns Integer from "c"\n'
           'extern function toupper that takes ch as Integer and returns '
           'Integer from "c"\n'
           '\n'
           'define function shout that takes s as String and returns '
           'Integer:\n'
           '    return strlen(s) + toupper(32)\n'
           '\n'
           'define function main:\n'
           '    create n as Integer\n'
           '    set n to shout("hello")\n'
           '    print(n)\n'
           '    print(getpid() > 0)\n')
    out, _, warnings = run_source(src)
    assert warnings == []
    # strlen("hello") == 5, toupper(32) == 32 -> 37
    assert out == "37\nTrue\n"
