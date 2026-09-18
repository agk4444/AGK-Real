"""Token types for the AGK-Real v1 lexer."""

from enum import Enum, auto


class TokenType(Enum):
    # Keywords
    DEFINE = auto()
    FUNCTION = auto()
    THAT = auto()
    TAKES = auto()
    AND = auto()
    RETURNS = auto()
    CREATE = auto()
    SET = auto()
    TO = auto()
    CONSTANT = auto()
    IF = auto()
    ELIF = auto()
    ELSE = auto()
    WHILE = auto()
    FOR = auto()
    EACH = auto()
    IN = auto()
    RETURN = auto()
    CLASS = auto()
    VARIABLE = auto()
    CONSTRUCTOR = auto()
    EXTENDS = auto()
    IMPLEMENTS = auto()
    IMPORT = auto()
    OR = auto()
    NOT = auto()
    TRUE = auto()
    FALSE = auto()
    AS = auto()
    SELF = auto()
    # v2 keywords
    TRY = auto()
    CATCH = auto()
    FINALLY = auto()
    RAISE = auto()
    FROM = auto()
    STEP = auto()
    # FFI keyword
    EXTERN = auto()
    # v0.4.0 keywords
    ASYNC = auto()
    AWAIT = auto()
    YIELD = auto()

    # Literals / names
    IDENTIFIER = auto()
    INT = auto()
    FLOAT = auto()
    STRING = auto()

    # Operators
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    PERCENT = auto()
    EQ = auto()        # ==
    NEQ = auto()       # !=
    ASSIGN = auto()     # = (only valid in `define constant`)
    LT = auto()
    GT = auto()
    LTE = auto()       # <=
    GTE = auto()       # >=

    # Delimiters
    LPAREN = auto()
    RPAREN = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    LBRACE = auto()
    RBRACE = auto()
    COMMA = auto()
    COLON = auto()
    DOT = auto()
    AT = auto()        # @ (decorators)

    # Structural
    NEWLINE = auto()
    INDENT = auto()
    DEDENT = auto()
    EOF = auto()


# Lexer emits LTE/GTE for <= and >=.
KEYWORDS = {
    "define": TokenType.DEFINE,
    "function": TokenType.FUNCTION,
    "that": TokenType.THAT,
    "takes": TokenType.TAKES,
    "and": TokenType.AND,
    "returns": TokenType.RETURNS,
    "create": TokenType.CREATE,
    "set": TokenType.SET,
    "to": TokenType.TO,
    "constant": TokenType.CONSTANT,
    "if": TokenType.IF,
    "elif": TokenType.ELIF,
    "else": TokenType.ELSE,
    "while": TokenType.WHILE,
    "for": TokenType.FOR,
    "each": TokenType.EACH,
    "in": TokenType.IN,
    "return": TokenType.RETURN,
    "class": TokenType.CLASS,
    "variable": TokenType.VARIABLE,
    "constructor": TokenType.CONSTRUCTOR,
    "extends": TokenType.EXTENDS,
    "implements": TokenType.IMPLEMENTS,
    "import": TokenType.IMPORT,
    "or": TokenType.OR,
    "not": TokenType.NOT,
    "true": TokenType.TRUE,
    "false": TokenType.FALSE,
    "as": TokenType.AS,
    "self": TokenType.SELF,
    "try": TokenType.TRY,
    "catch": TokenType.CATCH,
    "finally": TokenType.FINALLY,
    "raise": TokenType.RAISE,
    "from": TokenType.FROM,
    "step": TokenType.STEP,
    "async": TokenType.ASYNC,
    "await": TokenType.AWAIT,
    "yield": TokenType.YIELD,
    "extern": TokenType.EXTERN,
}


class Token:
    __slots__ = ("type", "value", "line", "column")

    def __init__(self, type_, value, line, column):
        self.type = type_
        self.value = value
        self.line = line
        self.column = column

    def __repr__(self):
        return f"Token({self.type.name}, {self.value!r}, {self.line}:{self.column})"

    def __eq__(self, other):
        return (
            isinstance(other, Token)
            and self.type == other.type
            and self.value == other.value
        )
