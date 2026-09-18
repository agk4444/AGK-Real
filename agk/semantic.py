"""AGK-Real v1 semantic analyzer.

Walks the AST and enforces SPEC section 6:
  - use of an undeclared name -> error naming the variable and line
  - `set` on an undeclared name -> error
  - `create` of a duplicate name in one scope -> error
  - call of an unknown function / wrong arity -> error
  - `return` outside a function -> error
  - unused variables, never-assigned variables, unreachable code -> warnings

Also rewrites bare field references inside methods to `self.<field>`
(SetStmt -> SetAttr, Name -> Attribute) per SPEC 4.7.

Raises SemanticError on the first error; collects warnings in .warnings.
"""

from . import ast_nodes as A
from .errors import SemanticError

import difflib

BUILTINS = {
    "print": -1, "len": 1, "str": 1, "int": 1, "float": 1, "bool": 1,
    "range": -1, "input": -1, "list": -1, "dict": -1, "abs": 1,
    "min": -1, "max": -1, "sum": 1, "sorted": 1, "enumerate": 1,
    "zip": -1, "round": -1, "type": 1, "repr": 1, "open": -1,
}


class _Scope:
    def __init__(self, parent=None):
        self.parent = parent
        # name -> {"assigned": bool, "used": bool, "node": node}
        self.vars = {}

    def declare(self, name, node):
        self.vars[name] = {"assigned": False, "used": False, "node": node}

    def lookup(self, name):
        scope = self
        while scope is not None:
            if name in scope.vars:
                return scope, scope.vars[name]
            scope = scope.parent
        return None, None


class SemanticAnalyzer:
    def __init__(self, filename="<input>"):
        self.filename = filename
        self.warnings = []
        self.functions = {}   # name -> FunctionDef (arity checking)
        self.classes = {}     # name -> ClassDef
        self.constants = set()
        self._scope = None
        self._in_function = 0
        self._class_fields = None  # set of field names while inside a method

    # -- helpers ----------------------------------------------------------

    def error(self, message, node):
        raise SemanticError(message, self.filename, node.line, node.col)

    def warn(self, message, node):
        self.warnings.append(
            f"{self.filename}:{node.line}:{node.col}: warning: {message}")

    def _suggest(self, name):
        """Return a ". did you mean '<match>'?" suffix for an undefined
        name, or '' when nothing is close enough."""
        candidates = set()
        scope = self._scope
        while scope is not None:
            candidates.update(scope.vars)
            scope = scope.parent
        candidates.update(self.functions)
        candidates.update(self.classes)
        candidates.update(BUILTINS)
        candidates.discard(name)
        matches = difflib.get_close_matches(name, sorted(candidates),
                                            n=1, cutoff=0.6)
        if matches:
            return f". did you mean '{matches[0]}'?"
        return ""

    # -- entry --------------------------------------------------------------

    def analyze(self, program, predeclared=(), extra_top_levels=()):
        # pass 1: collect top-level names, detect duplicates
        for mod in extra_top_levels:
            for stmt in mod.statements:
                if isinstance(stmt, A.FunctionDef):
                    self._add_top_level(stmt.name, stmt, self.functions,
                                        "function")
                elif isinstance(stmt, A.ClassDef):
                    self._add_top_level(stmt.name, stmt, self.classes, "class")
                elif isinstance(stmt, A.ConstantDef):
                    if stmt.name in self.constants:
                        self.error(f"duplicate constant '{stmt.name}'", stmt)
                    self.constants.add(stmt.name)
        for stmt in program.statements:
            if isinstance(stmt, A.FunctionDef):
                self._add_top_level(stmt.name, stmt, self.functions,
                                    "function")
            elif isinstance(stmt, A.ClassDef):
                self._add_top_level(stmt.name, stmt, self.classes, "class")
            elif isinstance(stmt, A.ConstantDef):
                if stmt.name in self.constants:
                    self.error(f"duplicate constant '{stmt.name}'", stmt)
                self.constants.add(stmt.name)
            elif isinstance(stmt, A.Import):
                pass  # handled in pass 2 scope setup
            else:
                self.error("unexpected top-level statement", stmt)

        # pass 2: analyze bodies
        self._scope = _Scope()
        for name in predeclared:
            # Names carried over from earlier REPL input: known, assigned,
            # and exempt from unused warnings.
            self._scope.declare(name, None)
            self._scope.vars[name]["assigned"] = True
            self._scope.vars[name]["used"] = True
        for stmt in program.statements:
            if isinstance(stmt, A.Import):
                top = stmt.module.split(".")[0]
                self._scope.declare(top, stmt)
                self._scope.vars[top]["assigned"] = True
            elif isinstance(stmt, A.ConstantDef):
                self._scope.declare(stmt.name, stmt)
                self._scope.vars[stmt.name]["assigned"] = True
        for mod in extra_top_levels:
            for stmt in mod.statements:
                if isinstance(stmt, A.Import):
                    top = stmt.module.split(".")[0]
                    if top not in self._scope.vars:
                        self._scope.declare(top, stmt)
                        self._scope.vars[top]["assigned"] = True
                elif isinstance(stmt, A.ConstantDef):
                    if stmt.name not in self._scope.vars:
                        self._scope.declare(stmt.name, stmt)
                        self._scope.vars[stmt.name]["assigned"] = True
        for stmt in program.statements:
            if isinstance(stmt, (A.FunctionDef,)):
                self._check_function(stmt)
            elif isinstance(stmt, A.ClassDef):
                self._check_class(stmt)
        self._check_unused(self._scope)
        return self.warnings

    def _add_top_level(self, name, node, table, kind):
        if name in table or name in self.functions or name in self.classes:
            self.error(f"duplicate {kind} '{name}'", node)
        if name in BUILTINS:
            self.error(f"{kind} name '{name}' shadows a builtin", node)
        table[name] = node

    # -- functions / classes --------------------------------------------------

    def _check_params(self, params):
        """Declare params; v2: defaults must trail (no plain param after
        a defaulted one)."""
        seen = set()
        seen_default = False
        for p in params:
            if p.name in seen:
                self.error(f"duplicate parameter '{p.name}'", p)
            seen.add(p.name)
            if p.default is not None:
                seen_default = True
            elif seen_default:
                self.error(
                    f"parameter '{p.name}' without a default follows a "
                    f"parameter with a default", p)
            self._scope.declare(p.name, p)
            self._scope.vars[p.name]["assigned"] = True

    def _check_function(self, fn):
        self._scope = _Scope(self._scope)
        self._in_function += 1
        try:
            self._check_params(fn.params)
            self._check_block(fn.body)
            self._check_unused(self._scope)
        finally:
            self._in_function -= 1
            self._scope = self._scope.parent

    def _all_fields(self, cls):
        """Own fields plus inherited fields (transitive, cycle-safe)."""
        fields = [f.name for f in cls.fields]
        seen_classes = {cls.name}
        base_name = cls.base
        while base_name:
            if base_name in seen_classes:
                break
            seen_classes.add(base_name)
            base_def = self.classes.get(base_name)
            if base_def is None:
                break
            for f in base_def.fields:
                if f.name not in fields:
                    fields.append(f.name)
            base_name = base_def.base
        return fields

    def _check_class(self, cls):
        own_fields = [f.name for f in cls.fields]
        if len(set(own_fields)) != len(own_fields):
            self.error(f"duplicate field in class '{cls.name}'", cls)
        if cls.base and cls.base not in self.classes:
            self.error(f"undefined base class '{cls.base}'"
                       f"{self._suggest(cls.base)}", cls)
        fields = self._all_fields(cls)
        method_names = [m.name for m in cls.methods]
        if len(set(method_names)) != len(method_names):
            self.error(f"duplicate method in class '{cls.name}'", cls)
        prev_fields = self._class_fields
        self._class_fields = set(fields)
        try:
            if cls.constructor:
                self._check_method_like(cls.constructor, is_constructor=True)
            for m in cls.methods:
                self._check_method_like(m, is_constructor=False)
        finally:
            self._class_fields = prev_fields

    def _check_method_like(self, fn, is_constructor):
        self._scope = _Scope(self._scope)
        self._in_function += 1
        try:
            self._scope.declare("self", fn)
            self._scope.vars["self"]["assigned"] = True
            seen = {"self"}
            seen_default = False
            for p in fn.params:
                if p.name in seen:
                    self.error(f"duplicate parameter '{p.name}'", p)
                seen.add(p.name)
                if p.default is not None:
                    seen_default = True
                elif seen_default:
                    self.error(
                        f"parameter '{p.name}' without a default follows a "
                        f"parameter with a default", p)
                self._scope.declare(p.name, p)
                self._scope.vars[p.name]["assigned"] = True
            self._check_block(fn.body)
            self._check_unused(self._scope, skip={"self"})
        finally:
            self._in_function -= 1
            self._scope = self._scope.parent

    # -- statements ---------------------------------------------------------------

    def _check_block(self, stmts):
        seen_return = False
        for i, s in enumerate(stmts):
            if seen_return:
                self.warn("unreachable code", s)
            stmts[i] = self._check_stmt(s)
            if isinstance(s, A.ReturnStmt):
                seen_return = True

    def _check_stmt(self, s):
        if isinstance(s, A.CreateStmt):
            if s.name in self._scope.vars:
                self.error(f"variable '{s.name}' is already declared", s)
            self._scope.declare(s.name, s)
        elif isinstance(s, A.SetStmt):
            s.value = self._check_expr(s.value)
            scope, entry = self._scope.lookup(s.name)
            if entry is not None:
                entry["assigned"] = True
            elif (self._class_fields is not None
                    and s.name in self._class_fields):
                # field assignment -> self.<field> = value
                return A.SetAttr(A.Name("self", line=s.line, col=s.col),
                                 s.name, s.value, line=s.line, col=s.col)
            else:
                self.error(f"cannot set undefined variable '{s.name}'"
                           f"{self._suggest(s.name)}", s)
        elif isinstance(s, A.IfStmt):
            s.condition = self._check_expr(s.condition)
            self._check_block(s.then_body)
            new_elifs = []
            for cond, body in s.elifs:
                new_elifs.append((self._check_expr(cond), body))
                self._check_block(body)
            s.elifs = new_elifs
            if s.else_body is not None:
                self._check_block(s.else_body)
        elif isinstance(s, A.WhileStmt):
            s.condition = self._check_expr(s.condition)
            self._check_block(s.body)
        elif isinstance(s, A.ForEachStmt):
            s.iterable = self._check_expr(s.iterable)
            if s.var not in self._scope.vars:
                self._scope.declare(s.var, s)
            self._scope.vars[s.var]["assigned"] = True
            self._check_block(s.body)
        elif isinstance(s, A.ForRangeStmt):
            s.start = self._check_expr(s.start)
            s.end = self._check_expr(s.end)
            if s.step is not None:
                s.step = self._check_expr(s.step)
            if s.var not in self._scope.vars:
                self._scope.declare(s.var, s)
            self._scope.vars[s.var]["assigned"] = True
            self._check_block(s.body)
        elif isinstance(s, A.TryStmt):
            self._check_block(s.body)
            if s.catch_body is not None:
                if s.catch_name is not None:
                    if s.catch_name not in self._scope.vars:
                        self._scope.declare(s.catch_name, s)
                    self._scope.vars[s.catch_name]["assigned"] = True
                self._check_block(s.catch_body)
            if s.finally_body is not None:
                self._check_block(s.finally_body)
        elif isinstance(s, A.RaiseStmt):
            if s.value is not None:
                s.value = self._check_expr(s.value)
        elif isinstance(s, A.ReturnStmt):
            if self._in_function == 0:
                self.error("'return' outside a function", s)
            if s.value is not None:
                s.value = self._check_expr(s.value)
        elif isinstance(s, A.ExprStmt):
            s.expr = self._check_expr(s.expr)
        else:
            self.error("unexpected statement", s)
        return s

    # -- expressions ---------------------------------------------------------------

    def _check_expr(self, e):
        if isinstance(e, (A.IntLit, A.FloatLit, A.StringLit, A.BoolLit)):
            return e
        if isinstance(e, A.Name):
            return self._resolve_name(e)
        if isinstance(e, A.BinOp):
            e.left = self._check_expr(e.left)
            e.right = self._check_expr(e.right)
            return e
        if isinstance(e, A.UnaryOp):
            e.operand = self._check_expr(e.operand)
            return e
        if isinstance(e, A.Call):
            return self._check_call(e)
        if isinstance(e, A.Attribute):
            e.obj = self._check_expr(e.obj)
            return e
        if isinstance(e, A.Index):
            e.obj = self._check_expr(e.obj)
            e.index = self._check_expr(e.index)
            return e
        if isinstance(e, A.ListLit):
            e.elements = [self._check_expr(x) for x in e.elements]
            return e
        if isinstance(e, A.DictLit):
            e.pairs = [(self._check_expr(k), self._check_expr(v))
                       for k, v in e.pairs]
            return e
        self.error("unexpected expression", e)

    def _resolve_name(self, node):
        scope, entry = self._scope.lookup(node.id)
        if entry is not None:
            entry["used"] = True
            return node
        if (self._class_fields is not None
                and node.id in self._class_fields):
            # bare field read -> self.<field>
            self._scope.lookup("self")[1]["used"] = True
            return A.Attribute(A.Name("self", line=node.line, col=node.col),
                               node.id, line=node.line, col=node.col)
        if node.id in BUILTINS or node.id in self.functions \
                or node.id in self.classes:
            return node
        self.error(f"undefined variable '{node.id}'{self._suggest(node.id)}",
                   node)

    def _arity_error(self, kind, name, params, got, node):
        required = sum(1 for p in params if p.default is None)
        total = len(params)
        if required == total:
            self.error(
                f"{kind} '{name}' takes {total} argument(s), got {got}", node)
        elif not required <= got <= total:
            self.error(
                f"{kind} '{name}' takes {required} to {total} arguments, "
                f"got {got}", node)

    def _check_call(self, e):
        e.args = [self._check_expr(a) for a in e.args]
        func = e.func
        if isinstance(func, A.Name):
            name = func.id
            if name in BUILTINS:
                return e
            if name in self.functions:
                params = self.functions[name].params
                required = sum(1 for p in params if p.default is None)
                if not required <= len(e.args) <= len(params):
                    self._arity_error("function", name, params,
                                      len(e.args), e)
                return e
            if name in self.classes:
                ctor = self.classes[name].constructor
                if ctor is not None:
                    params = ctor.params
                    required = sum(1 for p in params if p.default is None)
                    if not required <= len(e.args) <= len(params):
                        self._arity_error("constructor of", name, params,
                                          len(e.args), e)
                return e
            # maybe a local variable holding a callable, or a method via self
            _, entry = self._scope.lookup(name)
            if entry is not None:
                entry["used"] = True
                return e
            self.error(f"undefined function '{name}'{self._suggest(name)}",
                       func)
        # Attribute or other callable: check the object, can't verify arity
        e.func = self._check_expr(func)
        return e

    # -- warnings ---------------------------------------------------------------------

    def _check_unused(self, scope, skip=()):
        for name, entry in scope.vars.items():
            if name in skip:
                continue
            node = entry["node"]
            if isinstance(node, (A.Import, A.Param)):
                continue
            if isinstance(node, A.CreateStmt) and not entry["assigned"]:
                self.warn(f"variable '{name}' is never assigned a value", node)
            elif not entry["used"]:
                self.warn(f"unused variable '{name}'", node)


def analyze(program, filename="<input>", predeclared=(), extra_top_levels=()):
    """Run semantic analysis. Returns (rewritten_program, warnings).
    Raises SemanticError on the first error.

    predeclared: names treated as already-declared (the REPL carries
    variables across inputs). extra_top_levels: programs whose top-level
    functions/classes/constants are visible (compiled stdlib modules).
    """
    analyzer = SemanticAnalyzer(filename)
    warnings = analyzer.analyze(program, predeclared=predeclared,
                                extra_top_levels=extra_top_levels)
    return program, warnings
