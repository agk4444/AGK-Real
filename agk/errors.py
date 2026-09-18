"""Compiler errors. All user-facing errors carry file:line:column and never
leak Python tracebacks (the CLI catches these and prints them cleanly)."""


class AGKError(Exception):
    def __init__(self, message, filename="<input>", line=0, column=0, phase="error"):
        self.message = message
        self.filename = filename
        self.line = line
        self.column = column
        self.phase = phase
        super().__init__(str(self))

    def __str__(self):
        if self.line:
            return f"{self.filename}:{self.line}:{self.column}: {self.phase}: {self.message}"
        return f"{self.filename}: {self.phase}: {self.message}"


class LexerError(AGKError):
    def __init__(self, message, filename="<input>", line=0, column=0):
        super().__init__(message, filename, line, column, phase="lexer error")


class ParserError(AGKError):
    def __init__(self, message, filename="<input>", line=0, column=0):
        super().__init__(message, filename, line, column, phase="parser error")


class SemanticError(AGKError):
    def __init__(self, message, filename="<input>", line=0, column=0):
        super().__init__(message, filename, line, column, phase="semantic error")
