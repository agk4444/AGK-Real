"""Canonical formatter for AGK-Real v1 source.

Re-emits the token stream with canonical layout instead of parsing:
indentation is derived from the lexer's INDENT/DEDENT tokens, so the
formatter never needs a parse tree and always terminates on lexable input.
`format_source` is idempotent: format(format(x)) == format(x).

Formatting rules:
1. Indentation is 4 spaces per INDENT/DEDENT nesting level; any existing
   indentation is normalized.
2. Tokens on a line are separated by single spaces, except:
   - no space before `,` `:` `)` `]` `}` `.`
   - no space after `(` `[` `{` `.`
   - no space between a call/index target and `(`/`[`: `print("hi")`,
     `items[0]`
   - `,` is followed by exactly one space, unless `)` or `]` comes next
   - `:` is followed by exactly one space when more tokens follow on the
     line (a `:` ending the line, e.g. a block header, gets none)
   (`.` binds tight on both sides so `a.b()` and `self.x` stay glued;
   unary `-` / `not` keep plain single spacing, e.g. `set x to - 5`.)
3. Trailing whitespace is stripped.
4. Runs of 2+ blank lines collapse to one; leading and trailing blank
   lines are dropped.
5. The file ends with exactly one newline.
6. STRING contents are preserved exactly (re-quoted with escapes);
   comments (`# ...`, whole-line or trailing) are preserved verbatim and
   re-indented to their context.
"""

from .lexer import Lexer
from .tokens import TokenType

_NO_SPACE_BEFORE = frozenset({
    TokenType.COMMA, TokenType.COLON, TokenType.RPAREN,
    TokenType.RBRACKET, TokenType.RBRACE, TokenType.DOT,
})
_NO_SPACE_AFTER = frozenset({
    TokenType.LPAREN, TokenType.LBRACKET, TokenType.LBRACE, TokenType.DOT,
})
# A `(`/`[` that opens a call/index sticks to its target: `print("hi")`,
# `items[0]`.
_CALL_TARGET_END = frozenset({
    TokenType.IDENTIFIER, TokenType.SELF,
    TokenType.RPAREN, TokenType.RBRACKET,
})
# `,` gets no space after it when a closer follows: `f(a,)` not `f(a, )`.
_COMMA_NO_SPACE_NEXT = frozenset({TokenType.RPAREN, TokenType.RBRACKET})

_ESCAPE_OUT = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\t": "\\t"}


def _quote_string(value):
    """Re-quote a lexed STRING value, preserving its exact contents."""
    return '"' + "".join(_ESCAPE_OUT.get(ch, ch) for ch in value) + '"'


def _token_text(tok):
    if tok.type is TokenType.STRING:
        return _quote_string(tok.value)
    return tok.value


def _scan_source(source):
    """Pre-scan raw lines for things the token stream drops.

    Returns (blank, comment_only, trailing) where:
      blank:        set of 1-based line numbers that are empty/whitespace
      comment_only: {lineno: (indent_width, comment_text)} for `# ...` lines
      trailing:     {lineno: comment_text} for code lines ending in `# ...`
    Comment text is verbatim from `#` to end of line, right-stripped.
    """
    blank = set()
    comment_only = {}
    trailing = {}
    for lineno, raw in enumerate(source.split("\n"), start=1):
        if raw.strip() == "":
            blank.add(lineno)
            continue
        # find a `#` outside any string literal (mirror the lexer: only
        # \", \\, \n, \t escapes exist)
        in_string = False
        i = 0
        hash_at = None
        while i < len(raw):
            ch = raw[i]
            if in_string:
                if ch == "\\":
                    i += 2
                    continue
                if ch == '"':
                    in_string = False
                i += 1
                continue
            if ch == '"':
                in_string = True
            elif ch == "#":
                hash_at = i
                break
            i += 1
        if hash_at is None:
            continue
        text = raw[hash_at:].rstrip()
        if raw[:hash_at].strip() == "":
            indent = len(raw) - len(raw.lstrip(" "))
            comment_only[lineno] = (indent, text)
        else:
            trailing[lineno] = text
    return blank, comment_only, trailing


def _line_depths_and_code(tokens):
    """Group tokens into code lines: [(lineno, depth, [tokens])]."""
    lines = []
    depth = 0
    current = []
    for tok in tokens:
        t = tok.type
        if t is TokenType.INDENT:
            depth += 1
        elif t is TokenType.DEDENT:
            depth -= 1
            assert depth >= 0, "unbalanced DEDENT"
        elif t is TokenType.NEWLINE:
            lines.append((tok.line, depth, current))
            current = []
        elif t is TokenType.EOF:
            break
        else:
            current.append(tok)
    return lines


def _comment_depths(comment_only, code_lines):
    """Depth for each comment-only line.

    The lexer drops comment-only lines, so their context depth is
    unknowable from tokens alone; trust the comment's own indentation,
    clamped to the deepest neighboring code line. (Idempotent: after one
    pass every comment indent is a multiple of 4 at or under that max.)
    """
    depths = {}
    linenos = [ln for ln, _d, _t in code_lines]
    cdepths = [d for _ln, d, _t in code_lines]
    for lineno, (indent, _text) in comment_only.items():
        own = indent // 4
        neighbors = []
        # nearest preceding / following code line depths
        prev_d = next_d = None
        for ln, d in zip(linenos, cdepths):
            if ln < lineno:
                prev_d = d
            elif ln > lineno and next_d is None:
                next_d = d
        if prev_d is not None:
            neighbors.append(prev_d)
        if next_d is not None:
            neighbors.append(next_d)
        cap = max(neighbors) if neighbors else own
        depths[lineno] = min(own, cap)
    return depths


def _format_code_line(tokens):
    """Join one line's tokens per the spacing rules."""
    parts = []
    prev_type = None
    for i, tok in enumerate(tokens):
        text = _token_text(tok)
        t = tok.type
        if i == 0:
            parts.append(text)
        elif t in _NO_SPACE_BEFORE:
            parts.append(text)
        elif prev_type in _NO_SPACE_AFTER:
            parts.append(text)
        elif t is TokenType.LPAREN and prev_type in _CALL_TARGET_END:
            parts.append(text)
        elif t is TokenType.LBRACKET and prev_type in _CALL_TARGET_END:
            parts.append(text)
        elif (prev_type is TokenType.COMMA
                and t in _COMMA_NO_SPACE_NEXT):
            parts.append(text)
        else:
            parts.append(" " + text)
        prev_type = t
    return "".join(parts)


def format_source(source, filename="<input>"):
    """Format AGK source canonically. Raises LexerError on lex failure."""
    tokens = Lexer(source, filename).tokenize()
    blank, comment_only, trailing = _scan_source(source)
    code_lines = _line_depths_and_code(tokens)
    cdepths = _comment_depths(comment_only, code_lines)

    out = []          # finished lines, no trailing whitespace by construction
    last_lineno = 0   # lineno of the last emitted item
    emitted = False   # anything emitted yet (suppresses leading blanks)

    def maybe_blank(lineno):
        nonlocal emitted
        if emitted and any(ln in blank
                           for ln in range(last_lineno + 1, lineno)):
            out.append("")

    def emit(lineno, text):
        nonlocal last_lineno, emitted
        maybe_blank(lineno)
        out.append(text)
        last_lineno = lineno
        emitted = True

    # comment-only lines that precede each code line, in lineno order
    pending_comments = sorted(comment_only)
    ci = 0
    for lineno, depth, toks in code_lines:
        while ci < len(pending_comments) and pending_comments[ci] < lineno:
            cl = pending_comments[ci]
            _indent, text = comment_only[cl]
            emit(cl, "    " * cdepths[cl] + text)
            ci += 1
        line = "    " * depth + _format_code_line(toks)
        if lineno in trailing:
            line += "  " + trailing[lineno]
        emit(lineno, line)
    # trailing comment-only lines after the last code line
    while ci < len(pending_comments):
        cl = pending_comments[ci]
        _indent, text = comment_only[cl]
        emit(cl, "    " * cdepths[cl] + text)
        ci += 1

    return "\n".join(out) + "\n"
