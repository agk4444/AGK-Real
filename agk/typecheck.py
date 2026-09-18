"""AGK-Real static type checker.

Runs after semantic analysis (wired in via pipeline.py). Verifies the
declared annotations on variables, constants, function parameters, and
return types against simply-inferred expression types:

    Integer, Float, String, Boolean, List, Dict, None, Object,
    plus class names as nominal types.

Gradual typing: anything the checker cannot infer is "unknown" and
never produces an error, and ``Object`` accepts any type in either
direction (it is the dynamic escape hatch). Unannotated code — e.g.
functions without a declared return type — is left alone.

Raises TypeCheckError (a compile error, like SemanticError) on the
first mismatch. There are no generics and no union types.
"""

from . import ast_nodes as A
from .errors import TypeCheckError

INTEGER = "Integer"
FLOAT = "Float"
STRING = "String"
BOOLEAN = "Boolean"
LIST = "List"
DICT = "Dict"
OBJECT = "Object"
NONE_TYPE = "None"  # e.g. the result of print(), or a bare `return`

_NUMERIC = {INTEGER, FLOAT}

# builtin name -> fixed result type. Builtins with argument-dependent or
# otherwise dynamic results (abs/min/max/round) are special-cased in
# _call_type; everything else not listed here is "unknown".
_BUILTIN_TYPES = {
    "print": NONE_TYPE,
    "len": INTEGER,
    "str": STRING,
    "int": INTEGER,
    "float": FLOAT,
    "bool": BOOLEAN,
    "input": STRING,
    "list": LIST,
    "dict": DICT,
    "repr": STRING,
    "sorted": LIST,
}


class _Param:
    __slots__ = ("name", "type_name")

    def __init__(self, name, type_name):
        self.name = name
        self.type_name = type_name


class _FuncSig:
    __slots__ = ("params", "return_type")

    def __init__(self, params, return_type):
        self.params = params          # list of _Param
        self.return_type = return_type  # declared type name or None


class _ClassInfo:
    def __init__(self, name, base):
        self.name = name
        self.base = base              # base class name or None
        self.fields = {}              # field name -> declared type name
        self.methods = {}             # method name -> _FuncSig
        self.ctor = None              # _FuncSig or None


class TypeChecker:
    def __init__(self, filename="<input>"):
        self.filename = filename
        self.funcs = {}    # function name -> _FuncSig
        self.classes = {}  # class name -> _ClassInfo
        self._top_scope = {}
        self._scope = None       # current function scope: name -> type|None
        self._func_sig = None    # _FuncSig of the function being checked
        self._func_label = ""    # e.g. "function 'f'" (for messages)
        self._class = None       # _ClassInfo of the class being checked

    # -- helpers ----------------------------------------------------------

    def error(self, message, node):
        raise TypeCheckError(message, self.filename, node.line, node.col)

    def _assignable(self, want, got):
        """Can a value of inferred type `got` be stored where `want` is
        declared? Either side may be None (unknown) — gradual typing:
        unknown is always accepted."""
        if want is None or got is None:
            return True
        if want == OBJECT or got == OBJECT:
            return True  # Object is the dynamic escape hatch
        if want == got:
            return True
        if want == FLOAT and got == INTEGER:
            return True  # numeric widening
        return self._is_subclass(got, want)

    def _is_subclass(self, child, parent):
        """Nominal subclass check over the collected class table."""
        seen = set()
        cur = self.classes.get(child)
        while cur is not None and cur.name not in seen:
            seen.add(cur.name)
            if cur.base is None:
                return False
            if cur.base == parent:
                return True
            cur = self.classes.get(cur.base)
        return False

    def _method_sig(self, class_name, method_name):
        """Look up a method through the inheritance chain."""
        seen = set()
        cur = self.classes.get(class_name)
        while cur is not None and cur.name not in seen:
            seen.add(cur.name)
            if method_name in cur.methods:
                return cur.methods[method_name], cur.name
            cur = self.classes.get(cur.base) if cur.base else None
        return None, None

    # -- entry --------------------------------------------------------------

    def check(self, program, extra_top_levels=()):
        # pass 1: collect signatures (extras first, like semantic analysis)
        for mod in extra_top_levels:
            self._collect_top_level(mod)
        self._collect_top_level(program)
        # pass 2: check bodies
        for mod in extra_top_levels:
            for stmt in mod.statements:
                if isinstance(stmt, A.ConstantDef):
                    self._top_scope[stmt.name] = stmt.type_name
        for stmt in program.statements:
            if isinstance(stmt, A.ConstantDef):
                self._check_constant(stmt)
                self._top_scope[stmt.name] = stmt.type_name
            elif isinstance(stmt, A.FunctionDef):
                self._check_function(stmt, None)
            elif isinstance(stmt, A.ClassDef):
                self._check_class(stmt)

    def _collect_top_level(self, program):
        for stmt in program.statements:
            if isinstance(stmt, A.FunctionDef):
                self.funcs[stmt.name] = _FuncSig(
                    [_Param(p.name, p.type_name) for p in stmt.params],
                    stmt.return_type)
            elif isinstance(stmt, A.ClassDef):
                self._collect_class(stmt)

    def _collect_class(self, cls):
        info = _ClassInfo(cls.name, cls.base)
        self.classes[cls.name] = info  # register first: order-independent
        if cls.base and cls.base in self.classes:
            info.fields.update(self.classes[cls.base].fields)
        for f in cls.fields:
            info.fields[f.name] = f.type_name
        if cls.constructor is not None:
            info.ctor = _FuncSig(
                [_Param(p.name, p.type_name)
                 for p in cls.constructor.params],
                None)
        for m in cls.methods:
            info.methods[m.name] = _FuncSig(
                [_Param(p.name, p.type_name) for p in m.params],
                m.return_type)

    # -- functions / classes --------------------------------------------------

    def _new_scope(self, params):
        scope = dict(self._top_scope)
        for p in params:
            scope[p.name] = p.type_name
        return scope

    def _check_defaults(self, params, label):
        for p in params:
            if p.default is not None:
                got = self._type_of(p.default)
                if not self._assignable(p.type_name, got):
                    self.error(
                        f"type mismatch: default value of parameter "
                        f"'{p.name}' of {label} is {got}, "
                        f"expected {p.type_name}", p.default)

    def _check_function(self, fn, class_info):
        if class_info is None:
            sig = self.funcs[fn.name]
            label = f"function '{fn.name}'"
        else:
            sig = class_info.methods[fn.name]
            label = f"method '{fn.name}' of class '{class_info.name}'"
        self._check_defaults(fn.params, label)
        self._scope = self._new_scope(fn.params)
        self._func_sig = sig
        self._func_label = label
        self._class = class_info
        try:
            self._check_block(fn.body)
        finally:
            self._scope = None
            self._func_sig = None
            self._class = None

    def _check_class(self, cls):
        info = self.classes[cls.name]
        if cls.constructor is not None:
            ctor = cls.constructor
            label = f"constructor of class '{cls.name}'"
            self._check_defaults(ctor.params, label)
            self._scope = self._new_scope(ctor.params)
            self._scope["self"] = cls.name
            self._func_sig = info.ctor
            self._func_label = label
            self._class = info
            try:
                self._check_block(ctor.body)
            finally:
                self._scope = None
                self._func_sig = None
                self._class = None
        for m in cls.methods:
            self._check_function(m, info)

    def _check_constant(self, stmt):
        got = self._type_of(stmt.value)
        if not self._assignable(stmt.type_name, got):
            self.error(
                f"type mismatch: constant '{stmt.name}' declared as "
                f"{stmt.type_name}, but value is {got}", stmt)

    # -- statements ---------------------------------------------------------------

    def _check_block(self, stmts):
        for s in stmts:
            self._check_stmt(s)

    def _check_stmt(self, s):
        if isinstance(s, A.CreateStmt):
            self._scope[s.name] = s.type_name
        elif isinstance(s, A.SetStmt):
            got = self._type_of(s.value)
            want = self._scope.get(s.name)
            if not self._assignable(want, got):
                self.error(
                    f"type mismatch: cannot assign {got} to variable "
                    f"'{s.name}' declared as {want}", s)
        elif isinstance(s, A.SetAttr):
            # field assignment (semantic analysis rewrote bare field
            # names to self.<field>)
            want = self._field_type(s.obj, s.attr)
            if want is not None:
                got = self._type_of(s.value)
                if not self._assignable(want, got):
                    self.error(
                        f"type mismatch: cannot assign {got} to field "
                        f"'{s.attr}' declared as {want}", s)
        elif isinstance(s, A.ReturnStmt):
            want = self._func_sig.return_type if self._func_sig else None
            if want is not None:
                if s.value is None:
                    self.error(
                        f"type mismatch: {self._func_label} declares "
                        f"return type {want}, but 'return' has no value", s)
                else:
                    got = self._type_of(s.value)
                    if not self._assignable(want, got):
                        self.error(
                            f"type mismatch: {self._func_label} declares "
                            f"return type {want}, but returns {got}", s)
        elif isinstance(s, A.IfStmt):
            self._type_of(s.condition)
            self._check_block(s.then_body)
            for cond, body in s.elifs:
                self._type_of(cond)
                self._check_block(body)
            if s.else_body is not None:
                self._check_block(s.else_body)
        elif isinstance(s, A.WhileStmt):
            self._type_of(s.condition)
            self._check_block(s.body)
        elif isinstance(s, A.ForEachStmt):
            self._type_of(s.iterable)
            self._scope.setdefault(s.var, None)  # element type is unknown
            self._check_block(s.body)
        elif isinstance(s, A.ForRangeStmt):
            self._type_of(s.start)
            self._type_of(s.end)
            if s.step is not None:
                self._type_of(s.step)
            self._scope.setdefault(s.var, INTEGER)
            self._check_block(s.body)
        elif isinstance(s, A.TryStmt):
            self._check_block(s.body)
            if s.catch_body is not None:
                if s.catch_name is not None:
                    self._scope.setdefault(s.catch_name, None)
                self._check_block(s.catch_body)
            if s.finally_body is not None:
                self._check_block(s.finally_body)
        elif isinstance(s, A.RaiseStmt):
            if s.value is not None:
                self._type_of(s.value)
        elif isinstance(s, A.ExprStmt):
            self._type_of(s.expr)
        # anything else was already validated by semantic analysis

    def _field_type(self, obj, attr):
        """Declared type of a field store/load, or None if unknown."""
        class_name = None
        if (isinstance(obj, A.Name) and obj.id == "self"
                and self._class is not None):
            class_name = self._class.name
        else:
            class_name = self._type_of(obj)
        info = self.classes.get(class_name) if class_name else None
        if info is not None:
            return info.fields.get(attr)
        return None

    # -- expressions ---------------------------------------------------------------

    def _type_of(self, e):
        """Infer the type of an expression. Returns a type name, or None
        when the type is unknown (gradual typing: never an error)."""
        if isinstance(e, A.IntLit):
            return INTEGER
        if isinstance(e, A.FloatLit):
            return FLOAT
        if isinstance(e, A.StringLit):
            return STRING
        if isinstance(e, A.BoolLit):
            return BOOLEAN
        if isinstance(e, A.ListLit):
            for x in e.elements:
                self._type_of(x)
            return LIST
        if isinstance(e, A.DictLit):
            for k, v in e.pairs:
                self._type_of(k)
                self._type_of(v)
            return DICT
        if isinstance(e, A.Name):
            if self._scope is not None:
                return self._scope.get(e.id)
            return None
        if isinstance(e, A.BinOp):
            lt = self._type_of(e.left)
            rt = self._type_of(e.right)
            return self._binop_type(e.op, lt, rt)
        if isinstance(e, A.UnaryOp):
            t = self._type_of(e.operand)
            if e.op == "not":
                return BOOLEAN
            if e.op == "-" and t in _NUMERIC:
                return t
            return None
        if isinstance(e, A.Call):
            return self._call_type(e)
        if isinstance(e, A.Attribute):
            return self._attr_type(e)
        if isinstance(e, A.Index):
            self._type_of(e.obj)
            self._type_of(e.index)
            return None  # element type is unknown without generics
        return None

    @staticmethod
    def _binop_type(op, lt, rt):
        if op in ("==", "!=", "<", ">", "<=", ">="):
            return BOOLEAN
        if op in ("and", "or"):
            # `x or default` keeps x's type; stay silent rather than
            # claim Boolean and risk false positives.
            return None
        if lt is None or rt is None:
            return None
        if op == "/":
            return FLOAT if lt in _NUMERIC and rt in _NUMERIC else None
        if lt in _NUMERIC and rt in _NUMERIC:
            return FLOAT if FLOAT in (lt, rt) else INTEGER
        if op == "+" and lt == STRING and rt == STRING:
            return STRING
        if op == "+" and lt == LIST and rt == LIST:
            return LIST
        return None

    def _call_type(self, e):
        arg_types = [self._type_of(a) for a in e.args]
        func = e.func
        if isinstance(func, A.Name):
            name = func.id
            if name in _BUILTIN_TYPES:
                return _BUILTIN_TYPES[name]
            if name == "abs" and arg_types:
                t = arg_types[0]
                return t if t in _NUMERIC else None
            if name in ("min", "max") and arg_types:
                known = {t for t in arg_types if t is not None}
                return known.pop() if len(known) == 1 else None
            if name == "round":
                if len(arg_types) == 1:
                    return INTEGER
                if len(arg_types) == 2:
                    return FLOAT
                return None
            if name in self.funcs:
                sig = self.funcs[name]
                self._check_args(f"function '{name}'", sig.params,
                                 e.args, arg_types, e)
                return sig.return_type  # None => unknown
            if name in self.classes:
                info = self.classes[name]
                if info.ctor is not None:
                    self._check_args(f"constructor of class '{name}'",
                                     info.ctor.params, e.args, arg_types, e)
                return name  # constructing yields the class type
            return None
        if isinstance(func, A.Attribute):
            recv = func.obj
            # interpolated strings desugar to "<tmpl>".format(...)
            if isinstance(recv, A.StringLit) and func.attr == "format":
                return STRING
            if (isinstance(recv, A.Name) and recv.id == "self"
                    and self._class is not None):
                recv_type = self._class.name
            else:
                recv_type = self._type_of(recv)
            if recv_type:
                sig, owner = self._method_sig(recv_type, func.attr)
                if sig is not None:
                    self._check_args(
                        f"method '{func.attr}' of class '{owner}'",
                        sig.params, e.args, arg_types, e)
                    return sig.return_type
            return None
        self._type_of(func)
        return None

    def _attr_type(self, e):
        # bare field reads were rewritten to self.<field> by semantic
        # analysis; explicit self.<field> parses this way directly.
        if (isinstance(e.obj, A.Name) and e.obj.id == "self"
                and self._class is not None):
            return self._class.fields.get(e.attr)
        return None

    def _check_args(self, label, params, args, arg_types, node):
        for i, (arg, got) in enumerate(zip(args, arg_types)):
            if i >= len(params):
                break  # arity already enforced by semantic analysis
            p = params[i]
            if not self._assignable(p.type_name, got):
                self.error(
                    f"type mismatch: argument '{p.name}' of {label} "
                    f"expects {p.type_name}, got {got}", arg)


def typecheck(program, filename="<input>", extra_top_levels=()):
    """Run the static type checker over an already-analyzed program.

    Raises TypeCheckError on the first type mismatch. extra_top_levels
    are programs whose top-level functions/classes/constants are visible
    (compiled stdlib modules); their signatures are collected but their
    bodies are not re-checked.
    """
    checker = TypeChecker(filename)
    checker.check(program, extra_top_levels=extra_top_levels)
