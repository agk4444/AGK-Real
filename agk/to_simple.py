"""Classic AGK -> Simple AGK transpiler (v0.7.0).

Parses (classic or mixed) AGK source and re-emits it in Simple AGK form::

    create total as Integer      ->      total is 0
    set total to 0
    define function f that takes      to f with n as Integer
        n as Integer:                     and returns Integer:
    print(x)                    ->      say x
    for x in xs:                ->      each x in xs:
    for i from 1 to 10:         ->      repeat with i from 1 to 10:
    if a:                       ->      if a:
    elif b:                     ->      otherwise if b:
    else:                       ->      otherwise:
    a == b                      ->      a is b
    a != b                      ->      a is not b
    define class C:             ->      class C:
    variable n as Integer       ->      n as Integer
    define constructor:         ->      constructor:
    define constant K as Integer = 1    ->  constant K is 1
    extern function f ... from "lib"    ->  use f ... from "lib"
    set i to i + 1              ->      increase i

Statements with no simple equivalent (`import`, `while`, `try`/`catch`,
`raise`, `return`, `yield`, `await`, `set`) are emitted unchanged — the
two forms share one parser, so the output always parses.

Comments (whole-line and trailing) are preserved verbatim at their original
indentation. Blank lines are normalized: one blank line between top-level
definitions, none inside blocks.

``to_simple`` guarantees its output re-parses; semantic equivalence is
verified by running the result (the playground build compile-and-run
verifies every converted sample against its ``.expected`` file).
"""

from . import ast_nodes as A
from .format import _scan_source
from .lexer import Lexer
from .parser import Parser

# Precedence levels, low to high (mirrors parser.parse_or .. parse_postfix).
# `is` / `is not` live at the equality level, like `==` / `!=`.
_PREC = {
    "or": 0,
    "and": 1,
    "==": 2, "!=": 2,
    "<": 3, ">": 3, "<=": 3, ">=": 3,
    "+": 4, "-": 4,
    "*": 5, "/": 5, "%": 5,
}
_UNARY_PREC = 6
_PRIMARY_PREC = 7

_SIMPLE_BINOP = {"==": "is", "!=": "is not"}

_REPEAT_VAR_PREFIX = "__agk_repeat_"


def _quote_plain(value):
    """Quote a string value for AGK source.

    Like format._quote_string, but also doubles `{`/`}`: after the parser's
    interpolation desugar a lone `{` in a value can only mean a literal
    brace (written `{{` in source).
    """
    out = []
    for ch in value:
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\t":
            out.append("\\t")
        elif ch == "{":
            out.append("{{")
        elif ch == "}":
            out.append("}}")
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def _quote_template(value):
    """Quote an interpolation template: braces are already source-correct
    (`{}` placeholders and `{{`/`}}` escapes), so only backslash, quote,
    and control characters are escaped."""
    out = []
    for ch in value:
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\t":
            out.append("\\t")
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def _node_prec(node):
    if isinstance(node, A.BinOp):
        return _PREC[node.op]
    if isinstance(node, (A.UnaryOp, A.AwaitExpr)):
        return _UNARY_PREC
    return _PRIMARY_PREC


def _leading_not(node):
    """True when the emitted expression's first token is `not`.

    `x is not y` would re-parse as a comparison-statement, so an `is`
    declaration whose value starts with `not` needs parentheses.
    """
    if isinstance(node, A.UnaryOp) and node.op == "not":
        return True
    if isinstance(node, A.BinOp):
        return _leading_not(node.left)
    return False


class SimpleEmitter:
    def __init__(self, comments, trailing):
        self._lines = []
        self._comments = comments      # {lineno: (indent, text)}
        self._trailing = trailing      # {lineno: text}
        self._cursor = 1               # next unconsumed source line

    # -- output helpers -------------------------------------------------

    def _write(self, indent, text):
        self._lines.append("    " * indent + text)

    def _flush_comments(self, upto_line):
        """Emit verbatim whole-line comments before `upto_line`."""
        for ln in range(self._cursor, upto_line):
            if ln in self._comments:
                indent, text = self._comments[ln]
                self._lines.append(" " * indent + text)
        self._cursor = max(self._cursor, upto_line)

    def _stmt_head(self, indent, node, start_line=None):
        """Flush comments, then return the trailing comment for this stmt."""
        first = start_line if start_line is not None else node.line
        self._flush_comments(first)
        trail = self._trailing.get(first, "")
        if trail:
            trail = "  " + trail
        self._cursor = max(self._cursor, first + 1)
        return trail

    # -- expressions ----------------------------------------------------

    def _interp_call(self, node):
        """Rebuild `"...{expr}..."` source for a desugared interpolation.

        The parser turns `"caught: {err}"` into
        `"caught: {}".format(err)`; emitting that call verbatim would not
        re-parse (`{}` is an error), so the `{expr}` source form is rebuilt.
        Returns None when `node` is not an interpolation call.
        """
        func = node.func
        if not (isinstance(func, A.Attribute) and func.attr == "format"
                and isinstance(func.obj, A.StringLit)
                and len(node.args) > 0):
            return None
        template = func.obj.value
        parts = template.split("{}")
        if len(parts) - 1 != len(node.args):
            raise ValueError("to_simple: format placeholder/arg mismatch")
        out = [parts[0]]
        for arg, part in zip(node.args, parts[1:]):
            out.append("{" + self.expr(arg) + "}")
            out.append(part)
        return _quote_template("".join(out))

    def expr(self, node, prec=0):
        text = self._expr(node)
        if _node_prec(node) < prec:
            text = "(" + text + ")"
        return text

    def _expr(self, node):
        if isinstance(node, A.IntLit):
            return str(node.value)
        if isinstance(node, A.FloatLit):
            return repr(node.value)
        if isinstance(node, A.StringLit):
            return _quote_plain(node.value)
        if isinstance(node, A.BoolLit):
            return "true" if node.value else "false"
        if isinstance(node, A.Name):
            return node.id
        if isinstance(node, A.BinOp):
            p = _PREC[node.op]
            op = _SIMPLE_BINOP.get(node.op, node.op)
            left = self.expr(node.left, p)
            right = self.expr(node.right, p + 1)
            return f"{left} {op} {right}"
        if isinstance(node, A.UnaryOp):
            return f"{node.op} {self.expr(node.operand, _UNARY_PREC)}"
        if isinstance(node, A.AwaitExpr):
            return f"await {self.expr(node.operand, _UNARY_PREC)}"
        if isinstance(node, A.Call):
            if self._interp_call(node) is not None:
                return self._interp_call(node)
            func = self.expr(node.func, _PRIMARY_PREC)
            args = ", ".join(self.expr(a) for a in node.args)
            return f"{func}({args})"
        if isinstance(node, A.Attribute):
            return f"{self.expr(node.obj, _PRIMARY_PREC)}.{node.attr}"
        if isinstance(node, A.Index):
            return f"{self.expr(node.obj, _PRIMARY_PREC)}[{self.expr(node.index)}]"
        if isinstance(node, A.ListLit):
            return "[" + ", ".join(self.expr(e) for e in node.elements) + "]"
        if isinstance(node, A.DictLit):
            pairs = ", ".join(
                f"{self.expr(k)}: {self.expr(v)}" for k, v in node.pairs)
            return "{" + pairs + "}"
        raise ValueError(f"to_simple: unsupported expression {type(node).__name__}")

    # -- statements -----------------------------------------------------

    def _params(self, params):
        out = []
        for p in params:
            s = p.name
            if p.type_name:
                s += f" as {p.type_name}"
            if p.default is not None:
                s += f" = {self.expr(p.default)}"
            out.append(s)
        return ", ".join(out)

    def _function(self, fn, indent, start_line=None):
        for dec in fn.decorators:
            self._flush_comments(dec.line)
            self._write(indent, "@" + self.expr(dec))
            self._cursor = max(self._cursor, dec.line + 1)
        trail = self._stmt_head(indent, fn, start_line)
        head = "to " + fn.name
        if fn.params:
            head += " with " + self._params(fn.params)
        if fn.return_type:
            head += " and returns " + fn.return_type
        if fn.is_async:
            head = "async " + head
        self._write(indent, head + ":" + trail)
        self._block(fn.body, indent + 1)

    def _emit_stmt(self, stmt, indent):
        if isinstance(stmt, A.Import):
            trail = self._stmt_head(indent, stmt)
            self._write(indent, f"import {stmt.module}" + trail)
        elif isinstance(stmt, A.ConstantDef):
            trail = self._stmt_head(indent, stmt)
            self._write(indent,
                        f"constant {stmt.name} is {self.expr(stmt.value)}" + trail)
        elif isinstance(stmt, A.FunctionDef):
            self._function(stmt, indent)
        elif isinstance(stmt, A.ClassDef):
            self._class(stmt, indent)
        elif isinstance(stmt, A.ExternDef):
            trail = self._stmt_head(indent, stmt)
            head = "use " + stmt.name
            if stmt.params:
                head += " with " + self._params(stmt.params)
            if stmt.return_type:
                head += " and returns " + stmt.return_type
            self._write(indent, head + f' from "{stmt.lib}"' + trail)
        elif isinstance(stmt, A.CreateStmt):
            # Unmerged declaration (no immediate `set` follows): no simple
            # form exists, keep the classic statement — it still parses.
            trail = self._stmt_head(indent, stmt)
            self._write(indent, f"create {stmt.name} as {stmt.type_name}" + trail)
        elif isinstance(stmt, A.SetStmt):
            self._set(stmt, indent)
        elif isinstance(stmt, A.IfStmt):
            trail = self._stmt_head(indent, stmt)
            self._write(indent, f"if {self.expr(stmt.condition)}:" + trail)
            self._block(stmt.then_body, indent + 1)
            for cond, body in stmt.elifs:
                self._flush_comments(cond.line)
                trail = self._trailing.get(cond.line, "")
                trail = "  " + trail if trail else ""
                self._cursor = max(self._cursor, cond.line + 1)
                self._write(indent, f"otherwise if {self.expr(cond)}:" + trail)
                self._block(body, indent + 1)
            if stmt.else_body is not None:
                self._flush_comments(stmt.else_body[0].line
                                    if stmt.else_body else stmt.line + 1)
                self._write(indent, "otherwise:")
                self._block(stmt.else_body, indent + 1)
        elif isinstance(stmt, A.WhileStmt):
            trail = self._stmt_head(indent, stmt)
            self._write(indent, f"while {self.expr(stmt.condition)}:" + trail)
            self._block(stmt.body, indent + 1)
        elif isinstance(stmt, A.ForEachStmt):
            self._foreach(stmt, indent)
        elif isinstance(stmt, A.ForRangeStmt):
            trail = self._stmt_head(indent, stmt)
            head = (f"repeat with {stmt.var} from {self.expr(stmt.start)}"
                    f" to {self.expr(stmt.end)}")
            if stmt.step is not None:
                head += f" step {self.expr(stmt.step)}"
            self._write(indent, head + ":" + trail)
            self._block(stmt.body, indent + 1)
        elif isinstance(stmt, A.TryStmt):
            trail = self._stmt_head(indent, stmt)
            self._write(indent, "try:" + trail)
            self._block(stmt.body, indent + 1)
            if stmt.catch_body is not None:
                first = stmt.catch_body[0] if stmt.catch_body else None
                self._flush_comments(first.line if first else stmt.line + 1)
                head = "catch"
                if stmt.catch_name:
                    head += " " + stmt.catch_name
                self._write(indent, head + ":")
                self._block(stmt.catch_body, indent + 1)
            if stmt.finally_body is not None:
                first = stmt.finally_body[0] if stmt.finally_body else None
                self._flush_comments(first.line if first else stmt.line + 1)
                self._write(indent, "finally:")
                self._block(stmt.finally_body, indent + 1)
        elif isinstance(stmt, A.RaiseStmt):
            trail = self._stmt_head(indent, stmt)
            text = "raise" if stmt.value is None else f"raise {self.expr(stmt.value)}"
            self._write(indent, text + trail)
        elif isinstance(stmt, A.ReturnStmt):
            trail = self._stmt_head(indent, stmt)
            text = "return" if stmt.value is None else f"return {self.expr(stmt.value)}"
            self._write(indent, text + trail)
        elif isinstance(stmt, A.YieldStmt):
            trail = self._stmt_head(indent, stmt)
            text = "yield" if stmt.value is None else f"yield {self.expr(stmt.value)}"
            self._write(indent, text + trail)
        elif isinstance(stmt, A.ExprStmt):
            self._expr_stmt(stmt, indent)
        else:
            raise ValueError(f"to_simple: unsupported statement {type(stmt).__name__}")

    def _set(self, stmt, indent):
        trail = self._stmt_head(indent, stmt)
        v = stmt.value
        if (isinstance(v, A.BinOp) and v.op in ("+", "-")
                and isinstance(v.left, A.Name) and v.left.id == stmt.name):
            word = "increase" if v.op == "+" else "decrease"
            if isinstance(v.right, A.IntLit) and v.right.value == 1:
                self._write(indent, f"{word} {stmt.name}" + trail)
            else:
                self._write(indent,
                            f"{word} {stmt.name} by {self.expr(v.right)}" + trail)
            return
        self._write(indent, f"set {stmt.name} to {self.expr(v)}" + trail)

    def _is_decl(self, create, assign, indent):
        """`create x as T` + `set x to v` -> `x is v` (or `ask`)."""
        trail = self._trailing.get(create.line, "") or self._trailing.get(assign.line, "")
        trail = "  " + trail if trail else ""
        self._flush_comments(create.line)
        self._cursor = max(self._cursor, assign.line + 1)
        v = assign.value
        prompt = None
        if (create.soft and create.type_name == "String"
                and isinstance(v, A.Call)
                and isinstance(v.func, A.Name) and v.func.id == "input"
                and len(v.args) == 1):
            prompt = self.expr(v.args[0])
        if prompt is not None and not prompt.startswith("("):
            # `ask (` would parse as a call to `ask`, not the statement.
            self._write(indent, f"ask {prompt} giving {create.name}" + trail)
            return
        value = self.expr(v)
        if _leading_not(v):
            # `x is not ...` would re-parse as a comparison statement.
            value = f"({value})"
        self._write(indent, f"{create.name} is {value}" + trail)

    def _foreach(self, stmt, indent):
        trail = self._stmt_head(indent, stmt)
        it = stmt.iterable
        if (stmt.var.startswith(_REPEAT_VAR_PREFIX)
                and isinstance(it, A.Call)
                and isinstance(it.func, A.Name) and it.func.id == "range"
                and len(it.args) == 1):
            count = it.args[0]
            word = "time" if isinstance(count, A.IntLit) and count.value == 1 else "times"
            self._write(indent, f"repeat {self.expr(count)} {word}:" + trail)
        else:
            self._write(indent, f"each {stmt.var} in {self.expr(it)}:" + trail)
        self._block(stmt.body, indent + 1)

    def _expr_stmt(self, stmt, indent):
        trail = self._stmt_head(indent, stmt)
        e = stmt.expr
        if (isinstance(e, A.Call) and isinstance(e.func, A.Name)
                and e.func.id == "print" and len(e.args) == 1):
            arg = self.expr(e.args[0])
            if arg.startswith("("):
                # `say (` parses as a call to `say`, not the statement.
                self._write(indent, f"print({arg})" + trail)
            else:
                self._write(indent, f"say {arg}" + trail)
            return
        text = self.expr(e)
        if (isinstance(e, A.BinOp) and e.op in ("==", "!=")
                and isinstance(e.left, A.Name)):
            # Bare `a is b` would re-parse as a declaration; parenthesize.
            text = f"({text})"
        self._write(indent, text + trail)

    def _class(self, cls, indent):
        trail = self._stmt_head(indent, cls)
        head = "class " + cls.name
        if cls.base:
            head += " extends " + cls.base
        self._write(indent, head + ":" + trail)
        for f in cls.fields:
            self._flush_comments(f.line)
            trail = self._trailing.get(f.line, "")
            trail = "  " + trail if trail else ""
            self._cursor = max(self._cursor, f.line + 1)
            self._write(indent + 1, f"{f.name} as {f.type_name}" + trail)
        if cls.constructor is not None:
            c = cls.constructor
            trail = self._stmt_head(indent + 1, c)
            head = "constructor"
            if c.params:
                head += " with " + self._params(c.params)
            self._write(indent + 1, head + ":" + trail)
            self._block(c.body, indent + 2)
        for m in cls.methods:
            self._function(m, indent + 1)

    def _block(self, stmts, indent):
        i = 0
        while i < len(stmts):
            s = stmts[i]
            nxt = stmts[i + 1] if i + 1 < len(stmts) else None
            if (isinstance(s, A.CreateStmt) and isinstance(nxt, A.SetStmt)
                    and nxt.name == s.name):
                self._is_decl(s, nxt, indent)
                i += 2
                continue
            self._emit_stmt(s, indent)
            i += 1

    def program(self, prog):
        first = True
        for s in prog.statements:
            if not first:
                self._lines.append("")
            first = False
            if isinstance(s, A.CreateStmt):
                # Top-level stray declaration; keep classic (still parses).
                self._emit_stmt(s, 0)
            else:
                self._emit_stmt(s, 0)
        self._flush_comments(max(self._comments.keys() | self._trailing.keys(),
                                   default=0) + 1)
        return "\n".join(self._lines).rstrip("\n") + "\n"


def to_simple(source):
    """Transpile (classic or mixed) AGK `source` to Simple AGK form."""
    _blank, comment_only, trailing = _scan_source(source)
    prog = Parser(Lexer(source).tokenize()).parse()
    return SimpleEmitter(comment_only, trailing).program(prog)


def main(argv):
    import sys
    for path in argv[1:]:
        src = open(path).read()
        sys.stdout.write(to_simple(src))


if __name__ == "__main__":
    main(__import__("sys").argv)
