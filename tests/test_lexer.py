"""Level 1 — Lexer unit tests (AGK-Real v1 test plan)."""

import pytest

from agk.lexer import Lexer
from agk.tokens import TokenType as T
from agk.errors import LexerError


def lex(src, filename="test.agk"):
    return Lexer(src, filename).tokenize()


def types(src, **kw):
    """Token-type sequence, dropping NEWLINE/INDENT/DEDENT/EOF noise unless asked."""
    toks = lex(src, **kw)
    return [t.type for t in toks
            if t.type not in (T.NEWLINE, T.INDENT, T.DEDENT, T.EOF)]


def structural(src, **kw):
    """Full structural sequence including INDENT/DEDENT/NEWLINE."""
    return [(t.type, t.value) for t in lex(src, **kw)
            if t.type != T.EOF]


# -- keywords -----------------------------------------------------------

def test_all_keywords_tokenize():
    words = ("define function that takes and returns create set to constant "
             "if elif else while for each in return class variable "
             "constructor extends implements import or not true false as self")
    toks = lex(words)
    got = [t.type for t in toks if t.type not in (T.EOF, T.NEWLINE)]
    assert got == [T.DEFINE, T.FUNCTION, T.THAT, T.TAKES, T.AND, T.RETURNS,
                   T.CREATE, T.SET, T.TO, T.CONSTANT, T.IF, T.ELIF, T.ELSE,
                   T.WHILE, T.FOR, T.EACH, T.IN, T.RETURN, T.CLASS,
                   T.VARIABLE, T.CONSTRUCTOR, T.EXTENDS, T.IMPLEMENTS,
                   T.IMPORT, T.OR, T.NOT, T.TRUE, T.FALSE, T.AS, T.SELF]


def test_keyword_prefix_is_identifier():
    # `iffy`, `format`, `constantine` are identifiers, not keywords
    assert types("iffy format constantine") == [T.IDENTIFIER] * 3


def test_identifier_with_underscores_and_digits():
    assert types("my_var _x var2") == [T.IDENTIFIER] * 3


# -- literals ------------------------------------------------------------

def test_int_literal():
    toks = [t for t in lex("42") if t.type == T.INT]
    assert len(toks) == 1 and toks[0].value == "42"


def test_float_literal():
    toks = [t for t in lex("3.14") if t.type == T.FLOAT]
    assert len(toks) == 1 and toks[0].value == "3.14"


def test_float_requires_digits_after_dot():
    # `3.` is INT(3) then DOT — the parser will reject it, lexer stays simple
    assert types("3.") == [T.INT, T.DOT]


def test_string_literal():
    toks = [t for t in lex('"hello"') if t.type == T.STRING]
    assert len(toks) == 1 and toks[0].value == "hello"


def test_string_escapes():
    toks = [t for t in lex(r'"a\"b\\c\nd\te"') if t.type == T.STRING]
    assert toks[0].value == 'a"b\\c\nd\te'


def test_true_false_keywords():
    assert types("true false") == [T.TRUE, T.FALSE]


# -- operators -----------------------------------------------------------

def test_all_operators():
    src = "+ - * / % == != < > <= >="
    assert types(src) == [T.PLUS, T.MINUS, T.STAR, T.SLASH, T.PERCENT,
                          T.EQ, T.NEQ, T.LT, T.GT, T.LTE, T.GTE]


def test_delimiters():
    assert types("( ) [ ] { } , : .") == [
        T.LPAREN, T.RPAREN, T.LBRACKET, T.RBRACKET,
        T.LBRACE, T.RBRACE, T.COMMA, T.COLON, T.DOT]


# -- indentation ----------------------------------------------------------

def test_single_indent_dedent():
    seq = structural("define function f:\n    return 1\n")
    kinds = [k for k, _ in seq]
    assert kinds == [T.DEFINE, T.FUNCTION, T.IDENTIFIER, T.COLON, T.NEWLINE,
                     T.INDENT, T.RETURN, T.INT, T.NEWLINE, T.DEDENT]


def test_nested_indent_three_levels():
    src = ("if a:\n"
           "    if b:\n"
           "        if c:\n"
           "            return 1\n")
    kinds = [k for k, _ in structural(src)]
    assert kinds.count(T.INDENT) == 3
    assert kinds.count(T.DEDENT) == 3


def test_dedent_multiple_levels_at_once():
    src = ("if a:\n"
           "    if b:\n"
           "        return 1\n"
           "return 2\n")
    kinds = [k for k, _ in structural(src)]
    # one INDENT per level in, two DEDENTs when jumping back out
    assert kinds.count(T.INDENT) == 2
    assert kinds.count(T.DEDENT) == 2


def test_blank_lines_ignored_for_indent():
    src = "define function f:\n\n    return 1\n\n"
    kinds = [k for k, _ in structural(src)]
    assert kinds.count(T.INDENT) == 1
    assert kinds.count(T.DEDENT) == 1


def test_comment_only_lines_ignored_for_indent():
    src = ("define function f:\n"
           "    # a comment\n"
           "    return 1\n")
    kinds = [k for k, _ in structural(src)]
    assert kinds.count(T.INDENT) == 1


def test_inline_comment():
    assert types("set x to 1 # done") == [T.SET, T.IDENTIFIER, T.TO, T.INT]


def test_full_comment_line_between_code():
    src = "set x to 1\n# comment\nset y to 2\n"
    assert types(src) == [T.SET, T.IDENTIFIER, T.TO, T.INT,
                          T.SET, T.IDENTIFIER, T.TO, T.INT]


def test_eof_unwinds_indentation():
    src = "if a:\n    return 1"  # no trailing newline
    kinds = [k for k, _ in structural(src)]
    assert kinds.count(T.DEDENT) == 1
    assert kinds[-1] == T.DEDENT


# -- realistic snippets ----------------------------------------------------

def test_function_header():
    src = "define function greet that takes name as String and returns String:\n"
    assert types(src) == [T.DEFINE, T.FUNCTION, T.IDENTIFIER, T.THAT, T.TAKES,
                          T.IDENTIFIER, T.AS, T.IDENTIFIER, T.AND,
                          T.RETURNS, T.IDENTIFIER, T.COLON]


def test_constant_definition():
    src = 'define constant PI as Float = 3.14\n'
    assert types(src) == [T.DEFINE, T.CONSTANT, T.IDENTIFIER, T.AS,
                          T.IDENTIFIER, T.ASSIGN, T.FLOAT]


def test_for_each_header():
    src = "for each item in items:\n"
    assert types(src) == [T.FOR, T.EACH, T.IDENTIFIER, T.IN,
                          T.IDENTIFIER, T.COLON]


def test_expression_operators():
    src = "set x to (a + b) * c - d / e % f\n"
    assert types(src) == [T.SET, T.IDENTIFIER, T.TO, T.LPAREN, T.IDENTIFIER,
                          T.PLUS, T.IDENTIFIER, T.RPAREN, T.STAR,
                          T.IDENTIFIER, T.MINUS, T.IDENTIFIER, T.SLASH,
                          T.IDENTIFIER, T.PERCENT, T.IDENTIFIER]


def test_comparison_chain():
    src = "if a <= b and c != d or not e:\n"
    assert types(src) == [T.IF, T.IDENTIFIER, T.LTE, T.IDENTIFIER, T.AND,
                          T.IDENTIFIER, T.NEQ, T.IDENTIFIER, T.OR, T.NOT,
                          T.IDENTIFIER, T.COLON]


def test_list_and_dict_literals():
    assert types("[1, 2]") == [T.LBRACKET, T.INT, T.COMMA, T.INT, T.RBRACKET]
    assert types('{"a": 1}') == [T.LBRACE, T.STRING, T.COLON, T.INT, T.RBRACE]


def test_call_and_attribute_and_index():
    assert types("foo.bar(1, x[0])") == [
        T.IDENTIFIER, T.DOT, T.IDENTIFIER, T.LPAREN, T.INT, T.COMMA,
        T.IDENTIFIER, T.LBRACKET, T.INT, T.RBRACKET, T.RPAREN]


def test_class_header():
    src = "define class Person extends Animal:\n"
    assert types(src) == [T.DEFINE, T.CLASS, T.IDENTIFIER, T.EXTENDS,
                          T.IDENTIFIER, T.COLON]


def test_token_positions():
    toks = [t for t in lex("set xy to 1\n") if t.type == T.IDENTIFIER]
    assert (toks[0].line, toks[0].column) == (1, 4)


# -- errors -----------------------------------------------------------------

def test_illegal_character_question_mark():
    # the exact character that killed mobile_os.agk in the old toolchain
    with pytest.raises(LexerError) as exc:
        lex('set x to a ? b : c\n')
    assert "test.agk:1:11" in str(exc.value)


def test_illegal_character_dollar():
    with pytest.raises(LexerError):
        lex("set x to $5\n")


def test_tab_indentation_rejected():
    with pytest.raises(LexerError) as exc:
        lex("define function f:\n\treturn 1\n")
    assert "tabs" in str(exc.value)


def test_indent_must_be_four_spaces():
    with pytest.raises(LexerError):
        lex("define function f:\n  return 1\n")


def test_indent_eight_spaces_at_once_rejected():
    with pytest.raises(LexerError):
        lex("define function f:\n        return 1\n")


def test_inconsistent_dedent_rejected():
    src = ("if a:\n"
           "    if b:\n"
           "        return 1\n"
           "  return 2\n")
    with pytest.raises(LexerError):
        lex(src)


def test_unterminated_string():
    with pytest.raises(LexerError) as exc:
        lex('set x to "abc\n')
    assert "unterminated" in str(exc.value)


def test_bad_escape():
    with pytest.raises(LexerError):
        lex(r'set x to "a\qb"' + "\n")


def test_assign_token_emitted():
    # `=` lexes as ASSIGN; the parser (M2) rejects `x = 1` with a hint
    # since AGK assignment is `set x to ...`
    assert types("x = 1\n") == [T.IDENTIFIER, T.ASSIGN, T.INT]


def test_error_carries_filename():
    with pytest.raises(LexerError) as exc:
        lex("set x to ?\n", filename="prog.agk")
    assert str(exc.value).startswith("prog.agk:1:")


def test_error_format_is_file_line_col():
    with pytest.raises(LexerError) as exc:
        lex("ab ?\n", filename="f.agk")
    s = str(exc.value)
    assert s.startswith("f.agk:1:3: lexer error:")
