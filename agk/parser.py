"""AGK-Real v1 recursive-descent parser.

Consumes the INDENT/DEDENT token stream from the lexer and builds the AST.
Every node records its source line/column (for file:line:col errors).
All failures raise ParserError. The parser never guesses indentation —
it follows the lexer's INDENT/DEDENT tokens exactly.
"""

from .tokens import Token, TokenType as T
from .errors import ParserError
from . import ast_nodes as A


class Parser:
    def __init__(self, tokens, filename="<input>"):
        self.tokens = tokens
        self.filename = filename
        self.pos = 0
        # v0.6.0 (Simple AGK): counter for hidden `repeat` loop variables.
        self._repeat_counter = 0

    # -- token plumbing -------------------------------------------------

    def peek(self):
        return self.tokens[self.pos]

    def advance(self):
        tok = self.tokens[self.pos]
        if tok.type != T.EOF:
            self.pos += 1
        return tok

    def check(self, *types):
        return self.peek().type in types

    def match(self, *types):
        if self.check(*types):
            return self.advance()
        return None

    def expect(self, type_, message):
        tok = self.peek()
        if tok.type != type_:
            raise ParserError(message, self.filename, tok.line, tok.column)
        return self.advance()

    def error(self, message, tok=None):
        tok = tok or self.peek()
        raise ParserError(message, self.filename, tok.line, tok.column)

    def _skip_newlines(self):
        while self.match(T.NEWLINE):
            pass

    # -- entry point ----------------------------------------------------

    def parse(self):
        statements = []
        self._skip_newlines()
        while not self.check(T.EOF):
            if self.match(T.IMPORT):
                statements.append(self.parse_import())
            elif self.check(T.DEFINE, T.AT):
                statements.append(self.parse_top_level_define())
            elif self.check(T.EXTERN):
                statements.append(self.parse_extern_def())
            elif self.check(T.TO):
                # v0.6.0 (Simple AGK): `to <name> ...:` at top level.
                statements.append(self.parse_to_function_def())
            else:
                self.error(f"unexpected {self.peek().value!r} at top level; "
                           f"expected 'import', 'define', or 'extern'")
            self._skip_newlines()
        return A.Program(statements)

    def parse_import(self):
        imp = self.tokens[self.pos - 1]  # the IMPORT token just matched
        parts = [self.expect(T.IDENTIFIER, "expected module name").value]
        while self.match(T.DOT):
            parts.append(self.expect(T.IDENTIFIER, "expected module name").value)
        self.expect(T.NEWLINE, "expected end of line after import")
        return A.Import(".".join(parts), line=imp.line, col=imp.column)

    def parse_top_level_define(self):
        decorators = self.parse_decorators()
        defn = self.expect(T.DEFINE, "expected 'define'")
        is_async = self.match(T.ASYNC) is not None
        tok = self.peek()
        if tok.type == T.FUNCTION:
            return self.parse_function_def(decorators, is_async)
        if tok.type == T.CLASS:
            if is_async:
                self.error("classes cannot be async", defn)
            if decorators:
                self.error("decorators are not supported on classes", defn)
            return self.parse_class_def()
        if tok.type == T.CONSTANT:
            if is_async:
                self.error("constants cannot be async", defn)
            if decorators:
                self.error("decorators are not supported on constants", defn)
            return self.parse_constant_def()
        self.error("expected 'function', 'class', or 'constant' after 'define'")

    def parse_decorators(self):
        """v0.4.0: consume `@name` / `@name(args)` lines; returns a list of
        Name/Call expressions (possibly empty)."""
        decorators = []
        while self.match(T.AT):
            name_tok = self.expect(T.IDENTIFIER,
                                   "expected decorator name after '@'")
            node = A.Name(name_tok.value,
                          line=name_tok.line, col=name_tok.column)
            if self.match(T.LPAREN):
                args = []
                if not self.check(T.RPAREN):
                    args.append(self.parse_expression())
                    while self.match(T.COMMA):
                        args.append(self.parse_expression())
                self.expect(T.RPAREN,
                            "expected ')' after decorator arguments")
                node = A.Call(node, args,
                              line=name_tok.line, col=name_tok.column)
            self.expect(T.NEWLINE, "expected end of line after decorator")
            decorators.append(node)
        return decorators

    # -- definitions ----------------------------------------------------

    def _parse_signature(self, allow_defaults=True):
        """Parse `name [that takes a as T, ...] [and returns T]`, after
        `define function` / `define constructor` / `extern function`.
        Returns (name_tok|None, params, return_type)."""
        name_tok = self.advance() if self.check(T.IDENTIFIER) else None
        params = []
        return_type = None
        if self.match(T.THAT):
            if self.match(T.TAKES):
                params = self._parse_params(allow_defaults)
            if self.match(T.AND):
                self.expect(T.RETURNS, "expected 'returns' after 'and'")
                return_type = self.expect(T.IDENTIFIER,
                                          "expected return type name").value
            elif self.match(T.RETURNS):
                return_type = self.expect(T.IDENTIFIER,
                                          "expected return type name").value
        return name_tok, params, return_type

    def _parse_params(self, allow_defaults=True):
        params = [self._parse_param(allow_defaults)]
        while self.match(T.COMMA):
            params.append(self._parse_param(allow_defaults))
        return params

    def _parse_param(self, allow_defaults=True):
        name = self.expect(T.IDENTIFIER, "expected parameter name")
        self.expect(T.AS, f"expected 'as' after parameter {name.value!r}")
        type_name = self.expect(T.IDENTIFIER,
                                f"expected type for parameter {name.value!r}")
        default = None
        if self.match(T.ASSIGN):
            if not allow_defaults:
                self.error("extern function parameters cannot have default "
                           "values", name)
            default = self._parse_default(name)
        return A.Param(name.value, type_name.value, default,
                       line=name.line, col=name.column)

    def _parse_default(self, name_tok):
        """v2: parse a literal default value (optional leading `-`)."""
        neg_tok = self.match(T.MINUS)
        tok = self.peek()
        node = None
        if tok.type == T.INT:
            node = A.IntLit(int(tok.value), line=tok.line, col=tok.column)
        elif tok.type == T.FLOAT:
            node = A.FloatLit(float(tok.value), line=tok.line, col=tok.column)
        elif tok.type == T.STRING:
            node = self._parse_string(tok)
            if not isinstance(node, A.StringLit):
                self.error(
                    f"default value for parameter {name_tok.value!r} must be "
                    f"a static string (interpolation is not allowed in "
                    f"defaults)", tok)
        elif tok.type in (T.TRUE, T.FALSE):
            node = A.BoolLit(tok.type == T.TRUE,
                             line=tok.line, col=tok.column)
        if node is None:
            self.error(
                f"default value for parameter {name_tok.value!r} must be a "
                f"literal (number, string, or boolean)", tok)
        if neg_tok is not None:
            if not isinstance(node, (A.IntLit, A.FloatLit)):
                self.error(
                    f"cannot negate the default value of parameter "
                    f"{name_tok.value!r}", neg_tok)
            node = A.UnaryOp("-", node, line=neg_tok.line, col=neg_tok.column)
        self.advance()
        return node

    def parse_function_def(self, decorators=(), is_async=False):
        fn = self.expect(T.FUNCTION, "expected 'function'")
        name_tok, params, return_type = self._parse_signature()
        if name_tok is None:
            self.error("expected function name")
        self.expect(T.COLON, "expected ':' after function signature")
        body = self.parse_block()
        return A.FunctionDef(name_tok.value, params, return_type, body,
                             is_async=is_async,
                             decorators=list(decorators),
                             line=fn.line, col=fn.column)

    def parse_extern_def(self):
        """FFI declaration (top level only, no body):
        `extern function <name> [that takes ...] [and returns T] from "<lib>"`."""
        ext = self.expect(T.EXTERN, "expected 'extern'")
        self.expect(T.FUNCTION, "expected 'function' after 'extern'")
        name_tok, params, return_type = self._parse_signature(
            allow_defaults=False)
        if name_tok is None:
            self.error("expected function name after 'extern function'")
        self.expect(T.FROM,
                    "expected 'from \"<library>\"' after extern function "
                    "signature")
        lib_tok = self.expect(T.STRING,
                              "expected library name in quotes after 'from'")
        self.expect(T.NEWLINE, "expected end of line after extern declaration")
        return A.ExternDef(name_tok.value, params, return_type, lib_tok.value,
                           line=ext.line, col=ext.column)

    def parse_constant_def(self):
        cnst = self.expect(T.CONSTANT, "expected 'constant'")
        name = self.expect(T.IDENTIFIER, "expected constant name")
        self.expect(T.AS, f"expected 'as' after constant {name.value!r}")
        type_name = self.expect(T.IDENTIFIER,
                                f"expected type for constant {name.value!r}")
        self.expect(T.ASSIGN, "expected '=' in constant definition")
        value = self.parse_primary()
        if (not isinstance(value, (A.IntLit, A.FloatLit, A.StringLit, A.BoolLit))
                or not self.check(T.NEWLINE)):
            self.error("constant value must be a single literal")
        self.expect(T.NEWLINE, "expected end of line after constant definition")
        return A.ConstantDef(name.value, type_name.value, value,
                             line=cnst.line, col=cnst.column)

    def parse_class_def(self):
        cls = self.expect(T.CLASS, "expected 'class'")
        name = self.expect(T.IDENTIFIER, "expected class name")
        base = None
        if self.match(T.EXTENDS):
            base = self.expect(T.IDENTIFIER, "expected base class name").value
        if self.match(T.IMPLEMENTS):
            self.error("'implements' is not supported in v1")
        self.expect(T.COLON, "expected ':' after class header")
        self.expect(T.NEWLINE, "expected end of line after class header")
        self.expect(T.INDENT, "expected indented class body")

        fields, methods, constructor = [], [], None
        while not self.check(T.DEDENT, T.EOF):
            if self.match(T.NEWLINE):
                continue
            if self.match(T.VARIABLE):
                fields.append(self._parse_field())
            elif self.check(T.DEFINE, T.AT):
                decorators = self.parse_decorators()
                defn = self.expect(T.DEFINE, "expected 'define'")
                is_async = self.match(T.ASYNC) is not None
                if self.match(T.CONSTRUCTOR):
                    if constructor is not None:
                        self.error("duplicate constructor", defn)
                    if decorators:
                        self.error("decorators are not supported on "
                                   "constructors", defn)
                    if is_async:
                        self.error("constructors cannot be async", defn)
                    constructor = self._parse_constructor()
                elif self.check(T.FUNCTION):
                    methods.append(self.parse_function_def(decorators,
                                                           is_async))
                else:
                    self.error("expected 'constructor' or 'function' "
                               "after 'define' in class body", defn)
            elif self.check(T.TO):
                # v0.6.0 (Simple AGK): `to <name> ...:` as a method.
                methods.append(self.parse_to_function_def())
            else:
                self.error("expected 'variable', 'define constructor', "
                           "or 'define function' in class body")
        self.expect(T.DEDENT, "expected end of class body")
        return A.ClassDef(name.value, base, fields, constructor, methods,
                          line=cls.line, col=cls.column)

    def _parse_field(self):
        var = self.tokens[self.pos - 1]  # VARIABLE token just matched
        name = self.expect(T.IDENTIFIER, "expected field name")
        self.expect(T.AS, f"expected 'as' after field {name.value!r}")
        type_name = self.expect(T.IDENTIFIER,
                                f"expected type for field {name.value!r}")
        self.expect(T.NEWLINE, "expected end of line after field declaration")
        return A.FieldDecl(name.value, type_name.value,
                           line=var.line, col=var.column)

    def _parse_constructor(self):
        ctor = self.tokens[self.pos - 1]  # CONSTRUCTOR token just matched
        _, params, _ = self._parse_signature()
        self.expect(T.COLON, "expected ':' after constructor signature")
        body = self.parse_block()
        return A.ConstructorDef(params, body, line=ctor.line, col=ctor.column)

    # -- blocks and statements -------------------------------------------

    def parse_block(self):
        self.expect(T.NEWLINE, "expected end of line")
        self.expect(T.INDENT, "expected indented block")
        stmts = []
        while not self.check(T.DEDENT, T.EOF):
            if self.match(T.NEWLINE):
                continue
            result = self.parse_statement()
            # v0.6.0 (Simple AGK): some forms desugar to several statements.
            if isinstance(result, list):
                stmts.extend(result)
            else:
                stmts.append(result)
        self.expect(T.DEDENT, "expected end of block")
        return stmts

    # -- Simple AGK (v0.6.0): contextual plain-English forms ------------------
    #
    # `to`, `say`, `ask`, `repeat`, `increase`, `decrease` and `otherwise`
    # are NOT new reserved words. Each is only treated specially at
    # statement start (or, for `otherwise`, right after an if/elif block)
    # when the following tokens match the full pattern; every other use —
    # including as a variable or function name — parses exactly as before.
    # `is`, `giving`, `times`, `time`, `by`, `with`, `greater`, `than`,
    # `less`, `equal` stay plain NAME tokens matched by pattern.

    # Tokens that can begin an expression, for `say`/`ask`/`repeat`
    # dispatch. LPAREN is deliberately excluded: `say(x)` stays a call to
    # a user-defined `say`, and NEWLINE/EOF are excluded so a bare `say`
    # still parses as a variable reference.
    _SIMPLE_EXPR_START = (
        T.INT, T.FLOAT, T.STRING, T.TRUE, T.FALSE, T.IDENTIFIER, T.SELF,
        T.LBRACKET, T.LBRACE, T.MINUS, T.NOT, T.AWAIT,
    )

    def _peek_is_word(self, offset, value):
        """True when the token `offset` ahead is a plain NAME `value`."""
        i = self.pos + offset
        return (i < len(self.tokens)
                and self.tokens[i].type == T.IDENTIFIER
                and self.tokens[i].value == value)

    def _next_starts_simple_expr(self):
        i = self.pos + 1
        return (i < len(self.tokens)
                and self.tokens[i].type in self._SIMPLE_EXPR_START)

    def parse_statement(self):
        tok = self.peek()
        if tok.type == T.CREATE:
            return self.parse_create()
        if tok.type == T.SET:
            return self.parse_set()
        if tok.type == T.IF:
            return self.parse_if()
        if tok.type == T.WHILE:
            return self.parse_while()
        if tok.type == T.FOR:
            return self.parse_for()
        if tok.type == T.TRY:
            return self.parse_try()
        if tok.type == T.RAISE:
            return self.parse_raise()
        if tok.type == T.RETURN:
            return self.parse_return()
        if tok.type == T.YIELD:
            return self.parse_yield()
        if tok.type == T.TO:
            self.error("'to' function definitions are only allowed at top "
                       "level or in a class body (like 'define')", tok)
        if tok.type == T.IDENTIFIER and self._peek_is_word(1, "is"):
            # `name is <expr>` — before the say/ask/repeat/increase words
            # below, so `say is 5` declares `say` rather than erroring.
            return self.parse_is_statement()
        if (tok.type == T.IDENTIFIER and tok.value in ("increase", "decrease")
                and self._next_is_identifier()):
            return self.parse_increase_decrease()
        if (tok.type == T.IDENTIFIER and tok.value in ("say", "ask", "repeat")
                and self._next_starts_simple_expr()):
            if tok.value == "say":
                return self.parse_say()
            if tok.value == "ask":
                return self.parse_ask()
            return self.parse_repeat()
        if tok.type == T.DEFINE:
            self.error("'define' is only allowed at top level or in a class body")
        if tok.type == T.EXTERN:
            self.error("'extern' is only allowed at top level")
        if tok.type == T.IDENTIFIER and self._next_is(T.ASSIGN):
            self.error("unexpected '='; AGK uses 'set <name> to <expr>' "
                       "for assignment (or '==' for comparison)", tok)
        expr = self.parse_expression()
        self.expect(T.NEWLINE, "expected end of line")
        return A.ExprStmt(expr, line=expr.line, col=expr.col)

    def _next_is_identifier(self):
        i = self.pos + 1
        return (i < len(self.tokens)
                and self.tokens[i].type == T.IDENTIFIER)

    def _infer_simple_type(self, value):
        """v0.6.0: inferred declared type for `x is <expr>`. Literals get
        their type; anything else is dynamically typed (None)."""
        if isinstance(value, A.IntLit):
            return "Integer"
        if isinstance(value, A.FloatLit):
            return "Float"
        if isinstance(value, A.StringLit):
            return "String"
        if isinstance(value, A.BoolLit):
            return "Boolean"
        if isinstance(value, A.ListLit):
            return "List"
        if isinstance(value, A.DictLit):
            return "Dict"
        return None

    def parse_is_statement(self):
        """`name is <expr>`: declare-with-inference when `name` is new in
        scope, plain assignment when it exists (never a redeclare error).
        Desugars to a soft CreateStmt + SetStmt; semantic analysis decides
        declare vs. assign from scope.

        When the words after `is` read as a comparison (`is not ...`,
        `is greater|less than ...`), the whole line is an expression
        statement instead, matching the expression-level `is` rules."""
        name_tok = self.expect(T.IDENTIFIER, "expected variable name")
        is_tok = self.advance()  # the 'is' NAME
        if self.check(T.NOT) or (
                self._peek_is_word(0, "greater")
                or self._peek_is_word(0, "less")) \
                and self._peek_is_word(1, "than"):
            # comparison tail: rewind and parse as an expression statement
            self.pos -= 2
            expr = self.parse_expression()
            self.expect(T.NEWLINE, "expected end of line")
            return A.ExprStmt(expr, line=expr.line, col=expr.col)
        value = self.parse_expression()
        self.expect(T.NEWLINE, "expected end of line")
        create = A.CreateStmt(name_tok.value, self._infer_simple_type(value),
                              soft=True,
                              line=name_tok.line, col=name_tok.column)
        assign = A.SetStmt(name_tok.value, value,
                           line=is_tok.line, col=is_tok.column)
        return [create, assign]

    def parse_say(self):
        """`say <expr>` — Simple AGK for `print(<expr>)`."""
        kw = self.advance()  # 'say'
        value = self.parse_expression()
        self.expect(T.NEWLINE, "expected end of line")
        return A.ExprStmt(
            A.Call(A.Name("print", line=kw.line, col=kw.column), [value],
                   line=kw.line, col=kw.column),
            line=kw.line, col=kw.column)

    def parse_ask(self):
        """`ask <expr> giving <name>` — read a line with `input(<expr>)`
        into `name` (declared as String, or assigned when it exists)."""
        kw = self.advance()  # 'ask'
        prompt = self.parse_expression()
        g = self.peek()
        if not (g.type == T.IDENTIFIER and g.value == "giving"):
            self.error("expected 'giving <name>' after 'ask <expr>'", g)
        self.advance()
        name = self.expect(T.IDENTIFIER, "expected variable name after "
                                         "'giving'")
        self.expect(T.NEWLINE, "expected end of line")
        create = A.CreateStmt(name.value, "String", soft=True,
                              line=kw.line, col=kw.column)
        assign = A.SetStmt(
            name.value,
            A.Call(A.Name("input", line=kw.line, col=kw.column), [prompt],
                   line=kw.line, col=kw.column),
            line=kw.line, col=kw.column)
        return [create, assign]

    def parse_repeat(self):
        """`repeat <expr> times:` — counted loop. Desugars to
        `for <hidden> in range(<expr>):` with a generated variable name
        that cannot collide with user code."""
        kw = self.advance()  # 'repeat'
        count = self.parse_expression()
        t = self.peek()
        if not (t.type == T.IDENTIFIER and t.value in ("times", "time")):
            self.error("expected 'times' (or 'time') after 'repeat <expr>'",
                       t)
        self.advance()
        self.expect(T.COLON, "expected ':' after 'repeat <expr> times'")
        var = f"__agk_repeat_{self._repeat_counter}"
        self._repeat_counter += 1
        body = self.parse_block()
        return A.ForEachStmt(
            var,
            A.Call(A.Name("range", line=kw.line, col=kw.column), [count],
                   line=kw.line, col=kw.column),
            body, line=kw.line, col=kw.column)

    def parse_increase_decrease(self):
        """`increase <name> [by <expr>]` / `decrease <name> [by <expr>]` —
        `<name> = <name> +/- (<expr>)`, defaulting the amount to 1."""
        kw = self.advance()  # 'increase' or 'decrease'
        name = self.expect(T.IDENTIFIER, "expected variable name")
        g = self.peek()
        if g.type == T.IDENTIFIER and g.value == "by":
            self.advance()
            amount = self.parse_expression()
        else:
            amount = A.IntLit(1, line=kw.line, col=kw.column)
        self.expect(T.NEWLINE, "expected end of line")
        op = "+" if kw.value == "increase" else "-"
        target = A.Name(name.value, line=name.line, col=name.column)
        return A.SetStmt(name.value,
                         A.BinOp(target, op, amount,
                                 line=kw.line, col=kw.column),
                         line=kw.line, col=kw.column)

    def parse_to_function_def(self):
        """`to <name> [with <params>] [and returns <Type>]:` — Simple AGK
        alias for `define function`. Params are comma-separated
        `name [as Type]`; an omitted type is dynamically typed."""
        kw = self.expect(T.TO, "expected 'to'")
        name_tok = self.expect(T.IDENTIFIER, "expected function name "
                                             "after 'to'")
        params = []
        if self._peek_is_word(0, "with"):
            self.advance()
            params = self._parse_simple_params()
        return_type = None
        if self.match(T.AND):
            self.expect(T.RETURNS, "expected 'returns' after 'and'")
            return_type = self.expect(T.IDENTIFIER,
                                      "expected return type name").value
        self.expect(T.COLON, "expected ':' after function signature")
        body = self.parse_block()
        return A.FunctionDef(name_tok.value, params, return_type, body,
                             line=kw.line, col=kw.column)

    def _parse_simple_params(self):
        params = [self._parse_simple_param()]
        while self.match(T.COMMA):
            params.append(self._parse_simple_param())
        return params

    def _parse_simple_param(self):
        name = self.expect(T.IDENTIFIER, "expected parameter name")
        type_name = None
        if self.match(T.AS):
            type_name = self.expect(
                T.IDENTIFIER,
                f"expected type for parameter {name.value!r}").value
        return A.Param(name.value, type_name, None,
                       line=name.line, col=name.column)

    def _next_is(self, type_):
        return (self.pos + 1 < len(self.tokens)
                and self.tokens[self.pos + 1].type == type_)

    def parse_create(self):
        crt = self.expect(T.CREATE, "expected 'create'")
        name = self.expect(T.IDENTIFIER, "expected variable name")
        self.expect(T.AS, f"expected 'as' after variable {name.value!r}")
        type_name = self.expect(T.IDENTIFIER,
                                f"expected type for variable {name.value!r}")
        self.expect(T.NEWLINE, "expected end of line")
        return A.CreateStmt(name.value, type_name.value,
                            line=crt.line, col=crt.column)

    def parse_set(self):
        st = self.expect(T.SET, "expected 'set'")
        name = self.expect(T.IDENTIFIER, "expected variable name")
        self.expect(T.TO, f"expected 'to' after variable {name.value!r}")
        value = self.parse_expression()
        self.expect(T.NEWLINE, "expected end of line")
        return A.SetStmt(name.value, value, line=st.line, col=st.column)

    def _at_otherwise_if(self):
        """`otherwise if` right after an if/elif block (Simple AGK)."""
        t = self.tokens
        p = self.pos
        return (p + 1 < len(t) and t[p].type == T.IDENTIFIER
                and t[p].value == "otherwise" and t[p + 1].type == T.IF)

    def _at_otherwise(self):
        """`otherwise:` right after an if/elif block (Simple AGK)."""
        t = self.tokens
        p = self.pos
        return (p + 1 < len(t) and t[p].type == T.IDENTIFIER
                and t[p].value == "otherwise"
                and t[p + 1].type == T.COLON)

    def parse_if(self):
        kw = self.expect(T.IF, "expected 'if'")
        cond = self.parse_expression()
        self.expect(T.COLON, "expected ':' after 'if' condition")
        then_body = self.parse_block()
        elifs = []
        while True:
            if self.match(T.ELIF):
                pass
            elif self._at_otherwise_if():
                self.advance()  # 'otherwise'
                self.advance()  # 'if'
            else:
                break
            econd = self.parse_expression()
            self.expect(T.COLON, "expected ':' after 'elif' condition")
            elifs.append((econd, self.parse_block()))
        else_body = None
        if self.match(T.ELSE):
            self.expect(T.COLON, "expected ':' after 'else'")
            else_body = self.parse_block()
        elif self._at_otherwise():
            self.advance()  # 'otherwise'
            self.expect(T.COLON, "expected ':' after 'otherwise'")
            else_body = self.parse_block()
        return A.IfStmt(cond, then_body, elifs, else_body,
                        line=kw.line, col=kw.column)

    def parse_while(self):
        kw = self.expect(T.WHILE, "expected 'while'")
        cond = self.parse_expression()
        self.expect(T.COLON, "expected ':' after 'while' condition")
        return A.WhileStmt(cond, self.parse_block(),
                           line=kw.line, col=kw.column)

    def parse_for(self):
        """v2: `for each x in ...`, `for x in ...`, and
        `for i from <start> to <end> [step <step>]:`."""
        kw = self.expect(T.FOR, "expected 'for'")
        if self.match(T.EACH):
            return self._parse_for_each(kw)
        var = self.expect(T.IDENTIFIER, "expected loop variable after 'for'")
        if self.match(T.FROM):
            start = self.parse_expression()
            self.expect(T.TO,
                        "expected 'to' in 'for <var> from <start> to <end>'")
            end = self.parse_expression()
            step = None
            if self.match(T.STEP):
                step = self.parse_expression()
            self.expect(T.COLON, "expected ':' after 'for' header")
            return A.ForRangeStmt(var.value, start, end, step,
                                  self.parse_block(),
                                  line=kw.line, col=kw.column)
        self.expect(T.IN, f"expected 'in' after loop variable {var.value!r}")
        iterable = self.parse_expression()
        self.expect(T.COLON, "expected ':' after 'for' header")
        return A.ForEachStmt(var.value, iterable, self.parse_block(),
                             line=kw.line, col=kw.column)

    def _parse_for_each(self, kw):
        var = self.expect(T.IDENTIFIER, "expected loop variable")
        self.expect(T.IN, f"expected 'in' after loop variable {var.value!r}")
        iterable = self.parse_expression()
        self.expect(T.COLON, "expected ':' after 'for each' header")
        return A.ForEachStmt(var.value, iterable, self.parse_block(),
                             line=kw.line, col=kw.column)

    def parse_try(self):
        """v2: try/catch/finally."""
        kw = self.expect(T.TRY, "expected 'try'")
        self.expect(T.COLON, "expected ':' after 'try'")
        body = self.parse_block()
        catch_name, catch_body, finally_body = None, None, None
        if self.match(T.CATCH):
            if self.check(T.IDENTIFIER):
                catch_name = self.advance().value
            self.expect(T.COLON, "expected ':' after 'catch'")
            catch_body = self.parse_block()
        if self.match(T.FINALLY):
            self.expect(T.COLON, "expected ':' after 'finally'")
            finally_body = self.parse_block()
        if catch_body is None and finally_body is None:
            self.error("expected 'catch' or 'finally' after 'try' block", kw)
        return A.TryStmt(body, catch_name, catch_body, finally_body,
                         line=kw.line, col=kw.column)

    def parse_raise(self):
        """v2: `raise <expr>` or bare `raise` (re-raise inside catch)."""
        kw = self.expect(T.RAISE, "expected 'raise'")
        if self.check(T.NEWLINE):
            self.advance()
            return A.RaiseStmt(None, line=kw.line, col=kw.column)
        value = self.parse_expression()
        self.expect(T.NEWLINE, "expected end of line")
        return A.RaiseStmt(value, line=kw.line, col=kw.column)

    def parse_return(self):
        kw = self.expect(T.RETURN, "expected 'return'")
        if self.check(T.NEWLINE):
            self.advance()
            return A.ReturnStmt(None, line=kw.line, col=kw.column)
        value = self.parse_expression()
        self.expect(T.NEWLINE, "expected end of line")
        return A.ReturnStmt(value, line=kw.line, col=kw.column)

    def parse_yield(self):
        """v0.4.0: `yield <expr>` or bare `yield`."""
        kw = self.expect(T.YIELD, "expected 'yield'")
        if self.check(T.NEWLINE):
            self.advance()
            return A.YieldStmt(None, line=kw.line, col=kw.column)
        value = self.parse_expression()
        self.expect(T.NEWLINE, "expected end of line")
        return A.YieldStmt(value, line=kw.line, col=kw.column)

    # -- expressions (precedence climbing, per SPEC section 5) ------------

    def parse_expression(self):
        return self.parse_or()

    def parse_or(self):
        left = self.parse_and()
        while True:
            op = self.match(T.OR)
            if not op:
                return left
            left = A.BinOp(left, "or", self.parse_and(),
                           line=op.line, col=op.column)

    def parse_and(self):
        left = self.parse_equality()
        while True:
            op = self.match(T.AND)
            if not op:
                return left
            left = A.BinOp(left, "and", self.parse_equality(),
                           line=op.line, col=op.column)

    def parse_equality(self):
        left = self.parse_comparison()
        while True:
            # v0.6.0 (Simple AGK): `a is b` -> `a == b`, `a is not b` -> `a != b`
            if self.check(T.IDENTIFIER) and self.peek().value == "is":
                is_tok = self.advance()
                sym = "!="
                if not self.match(T.NOT):
                    sym = "=="
                left = A.BinOp(left, sym, self.parse_comparison(),
                               line=is_tok.line, col=is_tok.column)
                continue
            op = self.match(T.EQ, T.NEQ)
            if not op:
                return left
            sym = "==" if op.type == T.EQ else "!="
            left = A.BinOp(left, sym, self.parse_comparison(),
                           line=op.line, col=op.column)

    def _match_english_comparison(self):
        """Match `is greater|less than [or equal to]` at the current
        position (v0.6.0 Simple AGK). Returns (symbol, `is` token) and
        consumes the words, or None without consuming anything.

        The words stay plain NAME tokens (`or`/`to` lex as keywords and
        are matched by type); nothing here becomes reserved."""
        t = self.tokens
        p = self.pos

        def at(i, type_, value):
            return (p + i < len(t) and t[p + i].type == type_
                    and t[p + i].value == value)

        if not at(0, T.IDENTIFIER, "is"):
            return None
        if at(1, T.IDENTIFIER, "greater"):
            sym = ">"
        elif at(1, T.IDENTIFIER, "less"):
            sym = "<"
        else:
            return None
        if not at(2, T.IDENTIFIER, "than"):
            return None
        end = 3
        if (at(3, T.OR, "or") and at(4, T.IDENTIFIER, "equal")
                and at(5, T.TO, "to")):
            sym += "="
            end = 6
        is_tok = t[p]
        self.pos = p + end
        return sym, is_tok

    def parse_comparison(self):
        left = self.parse_term()
        while True:
            eng = self._match_english_comparison()
            if eng is not None:
                sym, is_tok = eng
                left = A.BinOp(left, sym, self.parse_term(),
                               line=is_tok.line, col=is_tok.column)
                continue
            op = self.match(T.LT, T.GT, T.LTE, T.GTE)
            if not op:
                return left
            sym = {"<": "<", ">": ">", "<=": "<=", ">=": ">="}[op.value]
            left = A.BinOp(left, sym, self.parse_term(),
                           line=op.line, col=op.column)

    def parse_term(self):
        left = self.parse_factor()
        while True:
            op = self.match(T.PLUS, T.MINUS)
            if not op:
                return left
            left = A.BinOp(left, op.value, self.parse_factor(),
                           line=op.line, col=op.column)

    def parse_factor(self):
        left = self.parse_unary()
        while True:
            op = self.match(T.STAR, T.SLASH, T.PERCENT)
            if not op:
                return left
            left = A.BinOp(left, op.value, self.parse_unary(),
                           line=op.line, col=op.column)

    def parse_unary(self):
        op = self.match(T.MINUS, T.NOT)
        if op:
            sym = "-" if op.type == T.MINUS else "not"
            operand = self.parse_unary()
            return A.UnaryOp(sym, operand, line=op.line, col=op.column)
        aw = self.match(T.AWAIT)
        if aw:
            # v0.4.0: `await <unary>`; binds like Python, so
            # `await f() + 1` is `(await f()) + 1`.
            return A.AwaitExpr(self.parse_unary(),
                              line=aw.line, col=aw.column)
        return self.parse_postfix()

    def parse_postfix(self):
        node = self.parse_primary()
        while True:
            if self.match(T.DOT):
                attr = self.expect(T.IDENTIFIER, "expected attribute name")
                node = A.Attribute(node, attr.value,
                                   line=node.line, col=node.col)
            elif self.match(T.LBRACKET):
                lb = self.tokens[self.pos - 1]
                index = self.parse_expression()
                self.expect(T.RBRACKET, "expected ']'")
                node = A.Index(node, index, line=lb.line, col=lb.column)
            elif self.match(T.LPAREN):
                args = []
                if not self.check(T.RPAREN):
                    args.append(self.parse_expression())
                    while self.match(T.COMMA):
                        args.append(self.parse_expression())
                self.expect(T.RPAREN, "expected ')'")
                node = A.Call(node, args, line=node.line, col=node.col)
            else:
                return node

    def parse_primary(self):
        tok = self.peek()
        if tok.type == T.INT:
            self.advance()
            return A.IntLit(int(tok.value), line=tok.line, col=tok.column)
        if tok.type == T.FLOAT:
            self.advance()
            return A.FloatLit(float(tok.value), line=tok.line, col=tok.column)
        if tok.type == T.STRING:
            return self._parse_string(self.advance())
        if tok.type == T.TRUE:
            self.advance()
            return A.BoolLit(True, line=tok.line, col=tok.column)
        if tok.type == T.FALSE:
            self.advance()
            return A.BoolLit(False, line=tok.line, col=tok.column)
        if tok.type == T.IDENTIFIER or tok.type == T.SELF:
            self.advance()
            return A.Name(tok.value, line=tok.line, col=tok.column)
        if tok.type == T.LPAREN:
            self.advance()
            expr = self.parse_expression()
            self.expect(T.RPAREN, "expected ')'")
            return expr
        if tok.type == T.LBRACKET:
            return self.parse_list_literal()
        if tok.type == T.LBRACE:
            return self.parse_dict_literal()
        self.error(f"expected expression, found {tok.value!r}")

    def _parse_string(self, tok):
        """v2: parse a string literal, desugaring `{expr}` interpolation.

        `"Hello, {name}!"` becomes `"Hello, {}!".format(name)`.
        `{{` and `}}` produce literal braces; a lone `}` is an error.
        Strings without interpolation are plain StringLit nodes (with
        `{{`/`}}` unescaped), so v1 output is unchanged.
        """
        value = tok.value
        template, literal, exprs = [], [], []
        i, n = 0, len(value)
        while i < n:
            ch = value[i]
            if ch == "{":
                if i + 1 < n and value[i + 1] == "{":
                    literal.append("{")
                    template.append("{{")
                    i += 2
                    continue
                brace = i
                inner, i = self._scan_braced(value, i, tok)
                exprs.append(self._parse_braced_expr(inner, tok, brace))
                template.append("{}")
            elif ch == "}":
                if i + 1 < n and value[i + 1] == "}":
                    literal.append("}")
                    template.append("}}")
                    i += 2
                    continue
                self.error("single '}' in string literal "
                           "(use '}}' for a literal brace)", tok)
            else:
                literal.append(ch)
                template.append(ch)
                i += 1
        if not exprs:
            return A.StringLit("".join(literal),
                               line=tok.line, col=tok.column)
        tmpl = A.StringLit("".join(template), line=tok.line, col=tok.column)
        func = A.Attribute(tmpl, "format", line=tok.line, col=tok.column)
        return A.Call(func, exprs, line=tok.line, col=tok.column)

    def _scan_braced(self, value, i, tok):
        """value[i] == '{': return (inner_text, index_past_'}').

        Matches braces respecting nesting and double-quoted strings
        inside the expression."""
        depth = 0
        j, n = i, len(value)
        in_str = False
        while j < n:
            ch = value[j]
            if in_str:
                if ch == "\\":
                    j += 2
                    continue
                if ch == '"':
                    in_str = False
                j += 1
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return value[i + 1:j], j + 1
            j += 1
        self.error("unterminated '{...}' in string literal", tok)

    def _parse_braced_expr(self, inner, tok, brace):
        """Parse the expression inside `{...}` with corrected positions."""
        from .errors import LexerError, ParserError
        from .lexer import Lexer
        if not inner.strip():
            self.error("empty '{...}' in string literal", tok)
        # column of the first inner char (tok.column is the opening quote,
        # `brace` is the value index of the opening `{`)
        base_col = tok.column + brace + 2
        try:
            tokens = Lexer(inner, self.filename).tokenize()
        except LexerError as e:
            raise ParserError(e.message, self.filename, tok.line,
                              base_col + e.column) from None
        for t in tokens:
            t.line = tok.line
            t.column = base_col + t.column
        sub = Parser(tokens, self.filename)
        node = sub.parse_expression()
        rest = sub.peek()
        if rest.type not in (T.NEWLINE, T.EOF):
            raise ParserError(
                f"unexpected {rest.value!r} in '{{...}}' "
                f"(use '{{{{' for a literal brace, e.g. JSON)",
                self.filename, rest.line, rest.column)
        return node

    def parse_list_literal(self):
        lb = self.expect(T.LBRACKET, "expected '['")
        elements = []
        if not self.check(T.RBRACKET):
            elements.append(self.parse_expression())
            while self.match(T.COMMA):
                elements.append(self.parse_expression())
        self.expect(T.RBRACKET, "expected ']'")
        return A.ListLit(elements, line=lb.line, col=lb.column)

    def parse_dict_literal(self):
        lb = self.expect(T.LBRACE, "expected '{'")
        pairs = []
        if not self.check(T.RBRACE):
            pairs.append(self._parse_dict_pair())
            while self.match(T.COMMA):
                pairs.append(self._parse_dict_pair())
        self.expect(T.RBRACE, "expected '}'")
        return A.DictLit(pairs, line=lb.line, col=lb.column)

    def _parse_dict_pair(self):
        key = self.parse_expression()
        self.expect(T.COLON, "expected ':' in dict literal")
        value = self.parse_expression()
        return (key, value)


def parse(source, filename="<input>"):
    """Convenience: lex + parse source text."""
    from .lexer import Lexer
    return Parser(Lexer(source, filename).tokenize(), filename).parse()


def parse_expression_src(source, filename="<input>"):
    """Parse a single expression (for the REPL)."""
    from .lexer import Lexer
    from .tokens import TokenType as T
    parser = Parser(Lexer(source, filename).tokenize(), filename)
    node = parser.parse_expression()
    tok = parser.peek()
    if tok.type not in (T.NEWLINE, T.EOF):
        raise ParserError(f"unexpected {tok.type.name.lower()} after expression",
                          filename, tok.line, tok.column)
    return node


def parse_statement_list(source, filename="<input>"):
    """Parse block-level statements (for the REPL), e.g. ``set x to 5``.

    The source is wrapped in a synthetic function so the normal block
    statement parser can consume it; the function wrapper is discarded.
    """
    if not source.strip():
        return []
    indented = "".join(
        ("    " + line if line.strip() else "") + "\n"
        for line in source.splitlines()
    )
    prog = parse("define function __chunk__:\n" + indented, filename=filename)
    return prog.statements[0].body
