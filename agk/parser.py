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
            elif self.check(T.DEFINE):
                statements.append(self.parse_top_level_define())
            else:
                self.error(f"unexpected {self.peek().value!r} at top level; "
                           f"expected 'import' or 'define'")
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
        defn = self.expect(T.DEFINE, "expected 'define'")
        tok = self.peek()
        if tok.type == T.FUNCTION:
            return self.parse_function_def()
        if tok.type == T.CLASS:
            return self.parse_class_def()
        if tok.type == T.CONSTANT:
            return self.parse_constant_def()
        self.error("expected 'function', 'class', or 'constant' after 'define'")

    # -- definitions ----------------------------------------------------

    def _parse_signature(self):
        """Parse `name [that takes a as T, ...] [and returns T]`, after
        `define function` / `define constructor`.
        Returns (name_tok|None, params, return_type)."""
        name_tok = self.advance() if self.check(T.IDENTIFIER) else None
        params = []
        return_type = None
        if self.match(T.THAT):
            if self.match(T.TAKES):
                params = self._parse_params()
            if self.match(T.AND):
                self.expect(T.RETURNS, "expected 'returns' after 'and'")
                return_type = self.expect(T.IDENTIFIER,
                                          "expected return type name").value
            elif self.match(T.RETURNS):
                return_type = self.expect(T.IDENTIFIER,
                                          "expected return type name").value
        return name_tok, params, return_type

    def _parse_params(self):
        params = [self._parse_param()]
        while self.match(T.COMMA):
            params.append(self._parse_param())
        return params

    def _parse_param(self):
        name = self.expect(T.IDENTIFIER, "expected parameter name")
        self.expect(T.AS, f"expected 'as' after parameter {name.value!r}")
        type_name = self.expect(T.IDENTIFIER,
                                f"expected type for parameter {name.value!r}")
        default = None
        if self.match(T.ASSIGN):
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

    def parse_function_def(self):
        fn = self.expect(T.FUNCTION, "expected 'function'")
        name_tok, params, return_type = self._parse_signature()
        if name_tok is None:
            self.error("expected function name")
        self.expect(T.COLON, "expected ':' after function signature")
        body = self.parse_block()
        return A.FunctionDef(name_tok.value, params, return_type, body,
                             line=fn.line, col=fn.column)

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
            elif self.check(T.DEFINE):
                defn = self.advance()
                if self.match(T.CONSTRUCTOR):
                    if constructor is not None:
                        self.error("duplicate constructor", defn)
                    constructor = self._parse_constructor()
                elif self.check(T.FUNCTION):
                    methods.append(self.parse_function_def())
                else:
                    self.error("expected 'constructor' or 'function' "
                               "after 'define' in class body", defn)
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
            stmts.append(self.parse_statement())
        self.expect(T.DEDENT, "expected end of block")
        return stmts

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
        if tok.type == T.DEFINE:
            self.error("'define' is only allowed at top level or in a class body")
        if tok.type == T.IDENTIFIER and self._next_is(T.ASSIGN):
            self.error("unexpected '='; AGK uses 'set <name> to <expr>' "
                       "for assignment (or '==' for comparison)", tok)
        expr = self.parse_expression()
        self.expect(T.NEWLINE, "expected end of line")
        return A.ExprStmt(expr, line=expr.line, col=expr.col)

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

    def parse_if(self):
        kw = self.expect(T.IF, "expected 'if'")
        cond = self.parse_expression()
        self.expect(T.COLON, "expected ':' after 'if' condition")
        then_body = self.parse_block()
        elifs = []
        while self.match(T.ELIF):
            econd = self.parse_expression()
            self.expect(T.COLON, "expected ':' after 'elif' condition")
            elifs.append((econd, self.parse_block()))
        else_body = None
        if self.match(T.ELSE):
            self.expect(T.COLON, "expected ':' after 'else'")
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
            op = self.match(T.EQ, T.NEQ)
            if not op:
                return left
            sym = "==" if op.type == T.EQ else "!="
            left = A.BinOp(left, sym, self.parse_comparison(),
                           line=op.line, col=op.column)

    def parse_comparison(self):
        left = self.parse_term()
        while True:
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
                          filename, tok.line, tok.col)
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
