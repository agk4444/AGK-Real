"""AGK-Real v1 lexer.

Produces INDENT/DEDENT tokens from significant leading whitespace
(4 spaces per level; tabs are an error). Blank lines and comment-only
lines never affect indentation. All failures raise LexerError with
file:line:column.
"""

from .tokens import Token, TokenType, KEYWORDS
from .errors import LexerError

_TWO_CHAR_OPS = {
    "==": TokenType.EQ,
    "!=": TokenType.NEQ,
    "<=": TokenType.LTE,
    ">=": TokenType.GTE,
}

_ONE_CHAR_OPS = {
    "+": TokenType.PLUS,
    "-": TokenType.MINUS,
    "*": TokenType.STAR,
    "/": TokenType.SLASH,
    "%": TokenType.PERCENT,
    "<": TokenType.LT,
    ">": TokenType.GT,
    "(": TokenType.LPAREN,
    ")": TokenType.RPAREN,
    "[": TokenType.LBRACKET,
    "]": TokenType.RBRACKET,
    "{": TokenType.LBRACE,
    "}": TokenType.RBRACE,
    ",": TokenType.COMMA,
    ":": TokenType.COLON,
    ".": TokenType.DOT,
}

_ESCAPES = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}


class Lexer:
    def __init__(self, source, filename="<input>"):
        self.source = source
        self.filename = filename
        self.tokens = []
        # indent stack holds column counts; index == nesting depth
        self._indents = [0]

    def error(self, message, line, column):
        raise LexerError(message, self.filename, line, column)

    def tokenize(self):
        lines = self.source.split("\n")
        for lineno, raw in enumerate(lines, start=1):
            self._lex_line(raw, lineno)
        # unwind any remaining indentation at EOF
        while len(self._indents) > 1:
            self._indents.pop()
            self.tokens.append(Token(TokenType.DEDENT, "", lineno, 0))
        self.tokens.append(Token(TokenType.EOF, "", lineno, 0))
        return self.tokens

    # -- line handling -------------------------------------------------

    def _lex_line(self, raw, lineno):
        # measure leading whitespace
        pos = 0
        while pos < len(raw) and raw[pos] in " \t":
            if raw[pos] == "\t":
                self.error("tabs are not allowed for indentation (use 4 spaces)",
                           lineno, pos)
            pos += 1
        indent = pos
        rest = raw[pos:]

        # blank or comment-only lines: emit nothing, ignore indentation
        stripped = rest.lstrip()
        if stripped == "" or stripped.startswith("#"):
            return

        # indentation change -> INDENT / DEDENTs
        if indent > self._indents[-1]:
            if indent - self._indents[-1] != 4:
                self.error(
                    f"indentation must increase by exactly 4 spaces "
                    f"(got {indent - self._indents[-1]})",
                    lineno, 0)
            self._indents.append(indent)
            self.tokens.append(Token(TokenType.INDENT, "", lineno, 0))
        elif indent < self._indents[-1]:
            while len(self._indents) > 1 and indent < self._indents[-1]:
                self._indents.pop()
                self.tokens.append(Token(TokenType.DEDENT, "", lineno, 0))
            if indent != self._indents[-1]:
                self.error("dedent does not match any outer indentation level",
                           lineno, 0)

        self._lex_code(rest, lineno, pos)
        self.tokens.append(Token(TokenType.NEWLINE, "\n", lineno, len(raw)))

    # -- code handling -------------------------------------------------

    def _lex_code(self, text, lineno, base_col):
        i = 0
        n = len(text)
        while i < n:
            ch = text[i]
            col = base_col + i
            if ch == "#":
                break  # comment to end of line
            if ch in " \t":
                i += 1
                continue
            two = text[i:i + 2]
            if two in _TWO_CHAR_OPS:
                self.tokens.append(Token(_TWO_CHAR_OPS[two], two, lineno, col))
                i += 2
                continue
            if ch in _ONE_CHAR_OPS:
                self.tokens.append(Token(_ONE_CHAR_OPS[ch], ch, lineno, col))
                i += 1
                continue
            if ch == "=":
                # `=` is only valid in `define constant X as T = <lit>`;
                # anything else is a parser error (M2 gives the hint there)
                self.tokens.append(Token(TokenType.ASSIGN, ch, lineno, col))
                i += 1
                continue
            if ch == '"':
                value, i = self._lex_string(text, i, lineno, base_col)
                self.tokens.append(Token(TokenType.STRING, value, lineno, col))
                continue
            if ch.isdigit():
                value, i = self._lex_number(text, i)
                ttype = TokenType.FLOAT if "." in value else TokenType.INT
                self.tokens.append(Token(ttype, value, lineno, col))
                continue
            if ch.isalpha() or ch == "_":
                j = i
                while j < n and (text[j].isalnum() or text[j] == "_"):
                    j += 1
                word = text[i:j]
                ttype = KEYWORDS.get(word, TokenType.IDENTIFIER)
                self.tokens.append(Token(ttype, word, lineno, col))
                i = j
                continue
            self.error(f"unexpected character {ch!r}", lineno, col)

    def _lex_string(self, text, i, lineno, base_col):
        # text[i] == '"'
        i += 1
        out = []
        n = len(text)
        while i < n:
            ch = text[i]
            if ch == '"':
                return "".join(out), i + 1
            if ch == "\\":
                if i + 1 >= n or text[i + 1] not in _ESCAPES:
                    self.error(f"bad escape '\\{text[i + 1] if i + 1 < n else ''}'",
                               lineno, base_col + i)
                out.append(_ESCAPES[text[i + 1]])
                i += 2
                continue
            out.append(ch)
            i += 1
        self.error("unterminated string literal", lineno, base_col + i)

    def _lex_number(self, text, i):
        j = i
        n = len(text)
        while j < n and text[j].isdigit():
            j += 1
        if j < n and text[j] == "." and j + 1 < n and text[j + 1].isdigit():
            j += 1
            while j < n and text[j].isdigit():
                j += 1
        return text[i:j], j
