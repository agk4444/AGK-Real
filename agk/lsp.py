"""Minimal JSON-RPC-over-stdio language server for AGK (.agk) files.

Run it with::

    python -m agk.lsp

It speaks LSP over stdin/stdout with ``Content-Length`` framing. Supported:
- ``initialize`` -> capabilities {textDocumentSync: full, hover,
  definition, completion, rename, references, documentSymbol}
- ``initialized`` (notification)
- ``textDocument/didOpen`` / ``textDocument/didChange`` (full sync) ->
  the document is run through the real compile pipeline and
  ``textDocument/publishDiagnostics`` is emitted
- ``textDocument/hover`` -> markdown summary for defined
  functions/classes/constants/variables/parameters/fields
- ``textDocument/definition`` -> Location of the defining line
- ``textDocument/completion`` -> in-scope variables/parameters, functions,
  classes, constants, keywords, builtins, stdlib modules; after
  ``<module>.`` the module's functions
- ``textDocument/rename`` -> WorkspaceEdit renaming the symbol under the
  cursor (definition + all references, scope-aware)
- ``textDocument/references`` -> all locations of the symbol under the
  cursor; the definition site is included by default (honours
  ``context.includeDeclaration``)
- ``textDocument/documentSymbol`` -> file outline: functions (with params),
  classes (fields, constructor, methods), constants, imports
- ``shutdown`` / ``exit``

No workspace symbols, no incremental sync, no external dependencies.

Rename/references track locals, parameters, functions, classes, constants,
fields, and ``self``-attribute/method uses. Method calls on other objects
(``a.deposit(...)``) are not tracked: AGK carries no static receiver types,
so those call sites cannot be resolved to a class.
"""

import dataclasses
import json
import os
import re
import sys
from urllib.parse import unquote
from urllib.request import url2pathname

from . import ast_nodes as A
from .errors import AGKError
from .parser import parse
from .pipeline import compile_program
from .semantic import BUILTINS, _Scope as _SemScope
from .tokens import KEYWORDS

SERVER_NAME = "agk-lsp"
SERVER_VERSION = "0.2.0"

_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_WARN_RE = re.compile(r"^(.*?):(\d+):(\d+): warning: (.*)$")


# -- framing --------------------------------------------------------------


def read_message(stream):
    """Read one Content-Length framed JSON-RPC message from a binary stream.

    Returns the decoded dict, or None on EOF.
    """
    headers = {}
    while True:
        line = stream.readline()
        if not line:
            return None  # EOF
        line = line.decode("ascii", errors="replace").strip()
        if not line:
            break
        name, _, value = line.partition(":")
        headers[name.strip().lower()] = value.strip()
    try:
        length = int(headers.get("content-length", "0"))
    except ValueError:
        return None
    if length <= 0:
        return None
    body = stream.read(length)
    if not body:
        return None
    return json.loads(body.decode("utf-8"))


def write_message(stream, obj):
    body = json.dumps(obj, separators=(",", ":")).encode("utf-8")
    stream.write(b"Content-Length: %d\r\n\r\n" % len(body))
    stream.write(body)
    stream.flush()


# -- documents and symbol index -------------------------------------------


def uri_to_path(uri):
    if uri.startswith("file://"):
        return url2pathname(unquote(uri[len("file://"):]))
    return None


def word_at(line_text, character):
    for m in _WORD_RE.finditer(line_text):
        if m.start() <= character <= m.end():
            return m.group(0)
    return None


def _extend_to_word(line_text, character):
    """Expand (line, character) to the identifier end for nicer ranges."""
    m = _WORD_RE.search(line_text, character)
    if m and m.start() <= character:
        return m.end()
    return character + 1


class SymbolIndex:
    """name -> list of {kind, name, line (1-based), col (0-based), detail}."""

    def __init__(self):
        self.symbols = {}

    @classmethod
    def from_program(cls, program):
        index = cls()
        try:
            index._walk(program.statements)
        except Exception:
            pass
        return index

    def _add(self, kind, name, node, detail=""):
        self.symbols.setdefault(name, []).append({
            "kind": kind,
            "name": name,
            "line": node.line,
            "col": node.col,
            "detail": detail or "",
        })

    def _sig(self, fn):
        params = ", ".join(
            p.name + (f" as {p.type_name}" if p.type_name else "")
            for p in fn.params)
        ret = f" -> {fn.return_type}" if fn.return_type else ""
        return f"({params}){ret}"

    def _walk(self, stmts):
        for s in stmts or []:
            if isinstance(s, A.FunctionDef):
                self._add("function", s.name, s, self._sig(s))
                for p in s.params:
                    self._add("parameter", p.name, p, p.type_name or "")
                self._walk(s.body)
            elif isinstance(s, A.ClassDef):
                self._add("class", s.name, s,
                          f"extends {s.base}" if s.base else "")
                for f in s.fields:
                    self._add("field", f.name, f, f.type_name or "")
                    self._add("field", f"{s.name}.{f.name}", f,
                              f.type_name or "")
                if s.constructor:
                    for p in s.constructor.params:
                        self._add("parameter", p.name, p, p.type_name or "")
                    self._walk(s.constructor.body)
                for m in s.methods:
                    self._add("method", m.name, m, self._sig(m))
                    self._add("method", f"{s.name}.{m.name}", m,
                              self._sig(m))
                    for p in m.params:
                        self._add("parameter", p.name, p, p.type_name or "")
                    self._walk(m.body)
            elif isinstance(s, A.ConstantDef):
                self._add("constant", s.name, s, s.type_name or "")
            elif isinstance(s, A.ExternDef):
                self._add("extern function", s.name, s, self._sig(s))
            elif isinstance(s, A.CreateStmt):
                self._add("variable", s.name, s, s.type_name or "")
            elif isinstance(s, A.IfStmt):
                self._walk(s.then_body)
                for _cond, body in s.elifs:
                    self._walk(body)
                self._walk(s.else_body)
            elif isinstance(s, (A.WhileStmt, A.ForEachStmt, A.ForRangeStmt)):
                self._walk(s.body)
            elif isinstance(s, A.TryStmt):
                self._walk(s.body)
                self._walk(s.catch_body)
                self._walk(s.finally_body)


# -- scope-aware index ----------------------------------------------------
# Powers completion, rename, find-references, and document symbols.
# Unlike SymbolIndex (name -> entries, used by hover/definition), this
# index tracks lexical scopes the way semantic.py does (module, class,
# function/method -- no block scopes) and resolves every Name/SetStmt
# target to the Def that declares it, so shadowed names in different
# functions never get mixed up. It is best-effort: it never raises, and
# on a document with errors it simply resolves fewer references.


class Def:
    """A single definition site. line is 1-based, col is 0-based."""

    __slots__ = ("kind", "name", "line", "col", "detail", "scope_id")

    def __init__(self, kind, name, line, col, detail, scope_id):
        self.kind = kind
        self.name = name
        self.line = line
        self.col = col
        self.detail = detail
        self.scope_id = scope_id


class Ref:
    """A reference site resolved to a Def key (scope_id, name)."""

    __slots__ = ("def_key", "name", "line", "col")

    def __init__(self, def_key, name, line, col):
        self.def_key = def_key
        self.name = name
        self.line = line
        self.col = col


class _LspScope:
    """A lexical scope. Name lookup reuses semantic._Scope's chain."""

    def __init__(self, sid, parent, kind, name):
        self.id = sid
        self.parent = parent  # _LspScope or None
        self.kind = kind  # module|class|function|method|constructor
        self.name = name
        self.start_line = 0  # 1-based, inclusive
        self.end_line = 0
        self.table = _SemScope()
        self.defs = {}  # name -> Def; first declaration wins
        if parent is not None:
            self.table.parent = parent.table

    def declare(self, kind, name, line, col, detail=""):
        if name in self.defs:
            return self.defs[name]
        d = Def(kind, name, line, col, detail, self.id)
        self.defs[name] = d
        self.table.declare(name, d)
        return d


def _max_line(obj):
    """Greatest 1-based source line in an AST subtree."""
    best = 0
    if isinstance(obj, A.Node):
        best = obj.line or 0
        for f in dataclasses.fields(obj):
            best = max(best, _max_line(getattr(obj, f.name)))
    elif isinstance(obj, (list, tuple)):
        for x in obj:
            best = max(best, _max_line(x))
    return best


def locate_range(lines, line1, col, word):
    """Find the LSP range of `word` on 1-based `line1`, at/after `col`.

    AST node positions usually point at the statement start (e.g. the
    ``define`` keyword), so the identifier itself is located textually.
    Returns (lsp_line, start_char, end_char) or None.
    """
    lsp_line = line1 - 1
    if not (0 <= lsp_line < len(lines)):
        return None
    text = lines[lsp_line]
    fallback = None
    for m in _WORD_RE.finditer(text):
        if m.group(0) != word:
            continue
        if m.start() <= col < m.end():
            return (lsp_line, m.start(), m.end())
        if fallback is None and m.start() >= col:
            fallback = (lsp_line, m.start(), m.end())
    return fallback


def _lsp_range(loc):
    return {"start": {"line": loc[0], "character": loc[1]},
            "end": {"line": loc[0], "character": loc[2]}}


def _contains(loc, lsp_line, character):
    return loc[0] == lsp_line and loc[1] <= character <= loc[2]


class ScopeIndex:
    """Scope-aware definitions + resolved reference sites for one document."""

    def __init__(self):
        self.scopes = []        # _LspScope; [0] is the module scope
        self.refs = []          # [Ref]
        self.class_members = {}  # class name -> {"fields","methods","base"}
        self.top_symbols = []   # outline entries for documentSymbol

    @classmethod
    def from_program(cls, program):
        index = cls()
        try:
            if program is not None:
                index._build(program)
        except Exception:
            pass
        return index

    # -- construction ---------------------------------------------------

    def _new_scope(self, parent, kind, name, start_line, end_line):
        sc = _LspScope(len(self.scopes), parent, kind, name)
        sc.start_line = start_line
        sc.end_line = end_line
        self.scopes.append(sc)
        return sc

    @staticmethod
    def _sig(params, return_type):
        ps = ", ".join(p.name + (f" as {p.type_name}" if p.type_name else "")
                       for p in params or [])
        ret = f" -> {return_type}" if return_type else ""
        return f"({ps}){ret}"

    def _build(self, program):
        module = self._new_scope(None, "module", "<module>", 1, 10 ** 9)
        functions, classes = [], []
        # pass 1: top-level names (mirrors semantic.py's first pass)
        for s in program.statements or []:
            if isinstance(s, A.FunctionDef):
                module.declare("function", s.name, s.line, s.col,
                               self._sig(s.params, s.return_type))
                functions.append(s)
            elif isinstance(s, A.ClassDef):
                module.declare("class", s.name, s.line, s.col,
                               f"extends {s.base}" if s.base else "")
                classes.append(s)
            elif isinstance(s, A.ConstantDef):
                module.declare("constant", s.name, s.line, s.col,
                               s.type_name or "")
            elif isinstance(s, A.Import):
                top = s.module.split(".")[0]
                module.declare("module", top, s.line, s.col, s.module)
        # declare class fields before walking any bodies so that
        # inherited field/method references resolve
        class_scopes = {}
        for c in classes:
            cscope = self._new_scope(module, "class", c.name, c.line,
                                     _max_line(c) or c.line)
            fields, methods = {}, {}
            for f in c.fields or []:
                fields[f.name] = cscope.declare(
                    "field", f.name, f.line, f.col, f.type_name or "")
            self.class_members[c.name] = {
                "fields": fields, "methods": methods, "base": c.base}
            class_scopes[c.name] = cscope
        for c in classes:
            members = self.class_members[c.name]
            cscope = class_scopes[c.name]
            if c.constructor is not None:
                self._walk_function(c.constructor, cscope, "constructor",
                                    c.name, "constructor")
            for m in c.methods or []:
                members["methods"][m.name] = cscope.declare(
                    "method", m.name, m.line, m.col,
                    self._sig(m.params, m.return_type))
                self._walk_function(m, cscope, "method", c.name, m.name)
        for fn in functions:
            self._walk_function(fn, module, "function", None, fn.name)
        self._build_outline(program)

    def _walk_function(self, fn, parent_scope, kind, cls_name, disp_name):
        scope = self._new_scope(parent_scope, kind, disp_name, fn.line,
                                _max_line(fn.body) or fn.line)
        if kind in ("method", "constructor"):
            scope.declare("parameter", "self", fn.line, fn.col, cls_name or "")
        for p in fn.params or []:
            scope.declare("parameter", p.name, p.line, p.col,
                          p.type_name or "")
        self._walk_block(fn.body, scope, cls_name)

    def _walk_block(self, stmts, scope, cls_name):
        for s in stmts or []:
            try:
                self._walk_stmt(s, scope, cls_name)
            except Exception:
                continue  # one odd statement must not kill the index

    def _walk_stmt(self, s, scope, cls_name):
        if isinstance(s, A.CreateStmt):
            scope.declare("variable", s.name, s.line, s.col,
                          s.type_name or "")
        elif isinstance(s, A.SetStmt):
            self._walk_expr(s.value, scope, cls_name)
            self._record_target(s.name, s.line, s.col, scope, cls_name)
        elif isinstance(s, A.SetAttr):
            # produced by the semantic phase for `set <field> ...`
            self._walk_expr(s.obj, scope, cls_name)
            self._record_attr(s.attr, s.line, s.col, s.obj, scope, cls_name)
            self._walk_expr(s.value, scope, cls_name)
        elif isinstance(s, A.IfStmt):
            self._walk_expr(s.condition, scope, cls_name)
            self._walk_block(s.then_body, scope, cls_name)
            for cond, body in s.elifs or []:
                self._walk_expr(cond, scope, cls_name)
                self._walk_block(body, scope, cls_name)
            if s.else_body is not None:
                self._walk_block(s.else_body, scope, cls_name)
        elif isinstance(s, A.WhileStmt):
            self._walk_expr(s.condition, scope, cls_name)
            self._walk_block(s.body, scope, cls_name)
        elif isinstance(s, A.ForEachStmt):
            self._walk_expr(s.iterable, scope, cls_name)
            scope.declare("variable", s.var, s.line, s.col, "")
            self._walk_block(s.body, scope, cls_name)
        elif isinstance(s, A.ForRangeStmt):
            self._walk_expr(s.start, scope, cls_name)
            self._walk_expr(s.end, scope, cls_name)
            if s.step is not None:
                self._walk_expr(s.step, scope, cls_name)
            scope.declare("variable", s.var, s.line, s.col, "")
            self._walk_block(s.body, scope, cls_name)
        elif isinstance(s, A.TryStmt):
            self._walk_block(s.body, scope, cls_name)
            if s.catch_body is not None:
                if s.catch_name:
                    scope.declare("variable", s.catch_name, s.line, s.col, "")
                self._walk_block(s.catch_body, scope, cls_name)
            if s.finally_body is not None:
                self._walk_block(s.finally_body, scope, cls_name)
        elif isinstance(s, A.RaiseStmt):
            if s.value is not None:
                self._walk_expr(s.value, scope, cls_name)
        elif isinstance(s, A.ReturnStmt):
            if s.value is not None:
                self._walk_expr(s.value, scope, cls_name)
        elif isinstance(s, A.ExprStmt):
            self._walk_expr(s.expr, scope, cls_name)
        elif isinstance(s, A.FunctionDef):
            # not valid AGK, but don't crash on it
            self._walk_function(s, scope, "function", cls_name, s.name)
        # top-level-only statements need no walk here

    def _walk_expr(self, e, scope, cls_name):
        if e is None or isinstance(
                e, (A.IntLit, A.FloatLit, A.StringLit, A.BoolLit)):
            return
        if isinstance(e, A.Name):
            self._record_target(e.id, e.line, e.col, scope, cls_name)
        elif isinstance(e, A.Call):
            func = e.func
            if isinstance(func, A.Name):
                # mirrors semantic._check_call: bare names resolve to
                # builtins, functions, classes, or scope variables
                self._record_target(func.id, func.line, func.col,
                                    scope, cls_name)
            else:
                self._walk_expr(func, scope, cls_name)
            for a in e.args or []:
                self._walk_expr(a, scope, cls_name)
        elif isinstance(e, A.Attribute):
            self._walk_expr(e.obj, scope, cls_name)
            self._record_attr(e.attr, e.line, e.col, e.obj, scope, cls_name)
        elif isinstance(e, A.BinOp):
            self._walk_expr(e.left, scope, cls_name)
            self._walk_expr(e.right, scope, cls_name)
        elif isinstance(e, A.UnaryOp):
            self._walk_expr(e.operand, scope, cls_name)
        elif isinstance(e, A.Index):
            self._walk_expr(e.obj, scope, cls_name)
            self._walk_expr(e.index, scope, cls_name)
        elif isinstance(e, A.ListLit):
            for x in e.elements or []:
                self._walk_expr(x, scope, cls_name)
        elif isinstance(e, A.DictLit):
            for k, v in e.pairs or []:
                self._walk_expr(k, scope, cls_name)
                self._walk_expr(v, scope, cls_name)

    def _record_target(self, name, line, col, scope, cls_name):
        _s, entry = scope.table.lookup(name)
        if entry is not None:
            d = entry["node"]
            self.refs.append(Ref((d.scope_id, d.name), name, line, col))
        elif name not in BUILTINS and cls_name:
            # best effort for documents the analyzer didn't finish:
            # a bare name inside a method may be a field
            d = self._member_def(cls_name, name)
            if d is not None:
                self.refs.append(Ref((d.scope_id, d.name), name, line, col))

    def _record_attr(self, attr, line, col, obj, scope, cls_name):
        # `self.<attr>` / `set self.<attr>`: the analyzer rewrites bare
        # field uses to these, so resolve them to the field/method Def
        if cls_name and isinstance(obj, A.Name) and obj.id == "self":
            d = self._member_def(cls_name, attr, kinds=("method", "field"))
            if d is not None:
                self.refs.append(Ref((d.scope_id, d.name), attr, line, col))

    def _member_def(self, cls_name, name, kinds=("field", "method")):
        seen = set()
        cur = cls_name
        while cur and cur not in seen:
            seen.add(cur)
            members = self.class_members.get(cur)
            if not members:
                return None
            for kind in kinds:
                d = members[kind + "s"].get(name)
                if d is not None:
                    return d
            cur = members["base"]
        return None

    # -- outline --------------------------------------------------------

    @staticmethod
    def _param_entry(p):
        return {"kind": "parameter", "name": p.name, "line": p.line,
                "col": p.col, "end_line": p.line, "children": []}

    def _build_outline(self, program):
        for s in program.statements or []:
            if isinstance(s, A.FunctionDef):
                self.top_symbols.append({
                    "kind": "function", "name": s.name,
                    "line": s.line, "col": s.col,
                    "end_line": _max_line(s) or s.line,
                    "children": [self._param_entry(p)
                                  for p in s.params or []],
                })
            elif isinstance(s, A.ClassDef):
                children = [
                    {"kind": "field", "name": f.name, "line": f.line,
                     "col": f.col, "end_line": f.line, "children": []}
                    for f in s.fields or []]
                if s.constructor is not None:
                    c = s.constructor
                    children.append({
                        "kind": "constructor", "name": "constructor",
                        "line": c.line, "col": c.col,
                        "end_line": _max_line(c) or c.line,
                        "children": [self._param_entry(p)
                                      for p in c.params or []],
                    })
                for m in s.methods or []:
                    children.append({
                        "kind": "method", "name": m.name,
                        "line": m.line, "col": m.col,
                        "end_line": _max_line(m) or m.line,
                        "children": [self._param_entry(p)
                                      for p in m.params or []],
                    })
                self.top_symbols.append({
                    "kind": "class", "name": s.name,
                    "line": s.line, "col": s.col,
                    "end_line": _max_line(s) or s.line,
                    "children": children,
                })
            elif isinstance(s, A.ConstantDef):
                self.top_symbols.append({
                    "kind": "constant", "name": s.name,
                    "line": s.line, "col": s.col,
                    "end_line": s.line, "children": [],
                })
            elif isinstance(s, A.Import):
                self.top_symbols.append({
                    "kind": "module", "name": s.module.split(".")[0],
                    "line": s.line, "col": s.col,
                    "end_line": s.line, "children": [],
                })

    # -- queries --------------------------------------------------------

    def def_of(self, def_key):
        sid, name = def_key
        if 0 <= sid < len(self.scopes):
            return self.scopes[sid].defs.get(name)
        return None

    def scope_at(self, line1):
        """Innermost function/method scope containing 1-based line1."""
        best = self.scopes[0] if self.scopes else None
        for sc in self.scopes[1:]:
            if sc.kind in ("function", "method", "constructor") \
                    and sc.start_line <= line1 <= sc.end_line:
                if best is None or best.kind == "module" or (
                        sc.start_line >= best.start_line
                        and sc.end_line <= best.end_line):
                    best = sc
        return best

    def visible_defs(self, scope):
        """All Defs visible from `scope`, nearest scope wins."""
        seen = {}
        t = scope.table
        while t is not None:
            for name, entry in t.vars.items():
                if name not in seen:
                    seen[name] = entry["node"]
            t = t.parent
        return seen

    def resolve_at(self, lines, lsp_line, character):
        """Def under (lsp_line, character): the definition site if the
        cursor is on it, otherwise the Def the reference resolves to.
        None when there is no symbol there."""
        if not (0 <= lsp_line < len(lines)):
            return None
        word = word_at(lines[lsp_line], character)
        if not word:
            return None
        for sc in self.scopes:
            d = sc.defs.get(word)
            if d is not None:
                loc = locate_range(lines, d.line, d.col, d.name)
                if loc is not None and _contains(loc, lsp_line, character):
                    return d
        for ref in self.refs:
            if ref.name != word:
                continue
            loc = locate_range(lines, ref.line, ref.col, ref.name)
            if loc is not None and _contains(loc, lsp_line, character):
                return self.def_of(ref.def_key)
        return None

    def locations_of(self, target):
        """All reference sites resolving to `target` Def."""
        key = (target.scope_id, target.name)
        return [r for r in self.refs if r.def_key == key]


# -- stdlib module functions (for completion) -------------------------------

_STDLIB_FUNCS = None


def stdlib_functions():
    """{module name: [(function name, signature)]} for agk/stdlib/*.agk.

    Parsed once and cached; a broken stdlib file just yields no entries.
    """
    global _STDLIB_FUNCS
    if _STDLIB_FUNCS is None:
        _STDLIB_FUNCS = {}
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stdlib")
        try:
            files = sorted(os.listdir(d))
        except OSError:
            files = []
        for fn in files:
            if not fn.endswith(".agk"):
                continue
            mod = fn[:-4]
            try:
                with open(os.path.join(d, fn), encoding="utf-8") as f:
                    prog = parse(f.read(), filename=fn)
                funcs = []
                for st in prog.statements or []:
                    if isinstance(st, A.FunctionDef):
                        funcs.append((st.name, ScopeIndex._sig(
                            st.params, st.return_type)))
                _STDLIB_FUNCS[mod] = funcs
            except Exception:
                _STDLIB_FUNCS[mod] = []
    return _STDLIB_FUNCS


_COMPLETION_KIND = {  # Def.kind -> LSP CompletionItemKind
    "function": 3, "method": 2, "constructor": 4, "class": 7,
    "constant": 21, "variable": 6, "parameter": 6, "field": 5,
    "module": 9,
}

_SYMBOL_KIND = {  # outline kind -> LSP SymbolKind
    "function": 12, "method": 6, "constructor": 9, "class": 5,
    "field": 8, "constant": 14, "variable": 13, "parameter": 13,
    "module": 2,
}


# -- diagnostics ----------------------------------------------------------


def _range(source_lines, line1, col):
    """AGK is 1-based lines, 0-based cols; LSP is 0-based both."""
    lsp_line = max(line1 - 1, 0)
    char = max(col, 0)
    end = char + 1
    if 0 <= lsp_line < len(source_lines):
        end = _extend_to_word(source_lines[lsp_line], char)
    return {
        "start": {"line": lsp_line, "character": char},
        "end": {"line": lsp_line, "character": end},
    }


def validate(source, filename, search_paths):
    """Run source through the real pipeline.

    Returns (diagnostics, symbol_index, scope_index). The pipeline raises
    on the first error, so diagnostics carry at most one error plus any
    warnings.
    """
    source_lines = source.splitlines()
    diagnostics = []
    program = None
    try:
        program = parse(source, filename=filename)
        # optimize=False: the v0.4.0 optimizer strips dead `create`
        # declarations, which would hide variable definition sites from
        # the scope index. Diagnostics are unaffected (they come from
        # parse/analyze/typecheck, all of which run before optimize),
        # and the generated code is discarded here anyway.
        _code, warnings, _modules = compile_program(
            program, filename=filename, search_paths=search_paths,
            optimize=False)
    except AGKError as e:
        diagnostics.append({
            "range": _range(source_lines, e.line or 1, e.column),
            "severity": 1,  # Error
            "source": SERVER_NAME,
            "message": f"{e.phase}: {e.message}",
        })
    except Exception as e:  # never kill the server on a compiler bug
        diagnostics.append({
            "range": _range(source_lines, 1, 0),
            "severity": 1,
            "source": SERVER_NAME,
            "message": f"internal error: {e}",
        })
    else:
        for w in warnings:
            m = _WARN_RE.match(w)
            if not m:
                continue
            _wfile, wline, wcol, msg = m.groups()
            diagnostics.append({
                "range": _range(source_lines, int(wline), int(wcol)),
                "severity": 2,  # Warning
                "source": SERVER_NAME,
                "message": f"warning: {msg}",
            })
    if program is not None:
        return (diagnostics, SymbolIndex.from_program(program),
                ScopeIndex.from_program(program))
    return diagnostics, SymbolIndex(), ScopeIndex()


# -- server ---------------------------------------------------------------


class LanguageServer:
    def __init__(self, stdin=None, stdout=None):
        self.stdin = stdin or sys.stdin.buffer
        self.stdout = stdout or sys.stdout.buffer
        self.documents = {}   # uri -> {"text", "version", "path"}
        self.indexes = {}     # uri -> SymbolIndex
        self.scope_indexes = {}  # uri -> ScopeIndex
        self._shutdown = False

    # -- io ---------------------------------------------------------------

    def send(self, obj):
        write_message(self.stdout, obj)

    def notify(self, method, params):
        self.send({"jsonrpc": "2.0", "method": method, "params": params})

    def respond(self, msg_id, result):
        self.send({"jsonrpc": "2.0", "id": msg_id, "result": result})

    def error(self, msg_id, code, message):
        self.send({"jsonrpc": "2.0", "id": msg_id,
                   "error": {"code": code, "message": message}})

    # -- documents --------------------------------------------------------

    def _store(self, uri, text, version):
        path = uri_to_path(uri)
        self.documents[uri] = {
            "text": text,
            "version": version,
            "path": path or "<input>",
        }

    def _publish_diagnostics(self, uri):
        doc = self.documents[uri]
        search_paths = []
        if doc["path"] != "<input>":
            d = os.path.dirname(os.path.abspath(doc["path"]))
            if os.path.isdir(d):
                search_paths.append(d)
        diagnostics, index, scope_index = validate(
            doc["text"], doc["path"], search_paths)
        self.indexes[uri] = index
        self.scope_indexes[uri] = scope_index
        self.notify("textDocument/publishDiagnostics",
                    {"uri": uri, "diagnostics": diagnostics})

    # -- handlers ---------------------------------------------------------

    def on_initialize(self, msg_id, _params):
        self.respond(msg_id, {
            "capabilities": {
                "textDocumentSync": 1,  # full document sync
                "hoverProvider": True,
                "definitionProvider": True,
                "completionProvider": {"triggerCharacters": ["."]},
                "renameProvider": True,
                "referencesProvider": True,
                "documentSymbolProvider": True,
            },
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        })

    def on_did_open(self, params):
        doc = params["textDocument"]
        self._store(doc["uri"], doc["text"], doc.get("version"))
        self._publish_diagnostics(doc["uri"])

    def on_did_change(self, params):
        uri = params["textDocument"]["uri"]
        version = params["textDocument"].get("version")
        changes = params.get("contentChanges", [])
        if uri in self.documents and changes:
            # full sync: the last change carries the whole document
            self._store(uri, changes[-1]["text"], version)
            self._publish_diagnostics(uri)

    def _word_and_entries(self, uri, position):
        doc = self.documents.get(uri)
        if doc is None:
            return None, []
        lines = doc["text"].splitlines()
        line_no = position.get("line", 0)
        if not (0 <= line_no < len(lines)):
            return None, []
        word = word_at(lines[line_no], position.get("character", 0))
        if not word:
            return None, []
        entries = self.indexes.get(uri)
        entries = entries.symbols.get(word, []) if entries else []
        return word, entries

    def on_hover(self, msg_id, params):
        _word, entries = self._word_and_entries(
            params["textDocument"]["uri"], params["position"])
        if not entries:
            self.respond(msg_id, None)
            return
        e = entries[0]
        title = {"function": "**function**",
                 "method": "**method**",
                 "class": "**class**",
                 "constant": "**constant**",
                 "variable": "**variable**",
                 "parameter": "**parameter**",
                 "field": "**field**"}.get(e["kind"], f"**{e['kind']}**")
        md = f"{title} `{e['name']}`"
        if e["detail"]:
            md += f"\n\n{e['detail']}"
        md += f"\n\ndefined at line {e['line']}"
        self.respond(msg_id, {
            "contents": {"kind": "markdown", "value": md},
        })

    def on_definition(self, msg_id, params):
        uri = params["textDocument"]["uri"]
        _word, entries = self._word_and_entries(uri, params["position"])
        if not entries:
            self.respond(msg_id, None)
            return
        e = entries[0]
        doc = self.documents[uri]
        lines = doc["text"].splitlines()
        lsp_line = max(e["line"] - 1, 0)
        char = e["col"]
        if 0 <= lsp_line < len(lines):
            found = lines[lsp_line].find(e["name"].split(".")[-1], e["col"])
            if found >= 0:
                char = found
        end = char + len(e["name"].split(".")[-1])
        self.respond(msg_id, {
            "uri": uri,
            "range": {
                "start": {"line": lsp_line, "character": char},
                "end": {"line": lsp_line, "character": end},
            },
        })

    def on_completion(self, msg_id, params):
        uri = params["textDocument"]["uri"]
        doc = self.documents.get(uri)
        if doc is None:
            self.respond(msg_id, {"isIncomplete": False, "items": []})
            return
        lines = doc["text"].splitlines()
        pos = params.get("position", {})
        line_no = pos.get("line", 0)
        character = pos.get("character", 0)
        text = lines[line_no] if 0 <= line_no < len(lines) else ""
        before = text[:max(0, character)]
        items = self._module_attr_items(before)
        if items is None:
            items = self._prefix_items(uri, line_no, before)
        self.respond(msg_id, {"isIncomplete": False, "items": items})

    def _module_attr_items(self, before):
        """Completion right after ``<module>.``: that stdlib module's
        functions. Returns None when the cursor is not after a dot."""
        m = re.search(r"([A-Za-z_][A-Za-z0-9_]*)\.$", before)
        if not m:
            return None
        return [{"label": name, "kind": 2, "detail": sig,
                 "sortText": "0" + name}
                for name, sig in stdlib_functions().get(m.group(1), [])]

    def _prefix_items(self, uri, line_no, before):
        """Completion on an identifier prefix: in-scope symbols first,
        then keywords, builtins, and stdlib module names."""
        pm = re.search(r"[A-Za-z_][A-Za-z0-9_]*$", before)
        prefix = pm.group(0) if pm else ""
        items, seen = [], set()

        def add(label, kind, detail, sort):
            if label in seen or not label.startswith(prefix):
                return
            seen.add(label)
            items.append({"label": label, "kind": kind, "detail": detail,
                          "sortText": sort})

        index = self.scope_indexes.get(uri)
        if index is not None:
            scope = index.scope_at(line_no + 1)
            if scope is not None:
                for name, d in index.visible_defs(scope).items():
                    add(name, _COMPLETION_KIND.get(d.kind, 6), d.detail,
                        ("0" if d.scope_id == scope.id else "1") + name)
        for kw in KEYWORDS:
            add(kw, 14, "keyword", "2" + kw)
        for name in BUILTINS:
            add(name, 3, "builtin function", "3" + name)
        for mod in stdlib_functions():
            add(mod, 9, "standard library module", "4" + mod)
        return items

    def _resolve(self, uri, position):
        doc = self.documents.get(uri)
        index = self.scope_indexes.get(uri)
        if doc is None or index is None:
            return None, None
        lines = doc["text"].splitlines()
        target = index.resolve_at(lines, position.get("line", 0),
                                  position.get("character", 0))
        return target, lines

    def on_rename(self, msg_id, params):
        uri = params["textDocument"]["uri"]
        new_name = params.get("newName", "")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", new_name or ""):
            self.error(msg_id, -32602, f"invalid new name: {new_name!r}")
            return
        target, lines = self._resolve(uri, params.get("position", {}))
        if target is None:
            # no symbol under the cursor: nothing to rename
            self.respond(msg_id, None)
            return
        index = self.scope_indexes[uri]
        edits = []
        loc = locate_range(lines, target.line, target.col, target.name)
        if loc is not None:
            edits.append({"range": _lsp_range(loc), "newText": new_name})
        for ref in index.locations_of(target):
            loc = locate_range(lines, ref.line, ref.col, ref.name)
            if loc is not None:
                edits.append({"range": _lsp_range(loc), "newText": new_name})
        edits.sort(key=lambda e: (e["range"]["start"]["line"],
                                  e["range"]["start"]["character"]))
        self.respond(msg_id, {"changes": {uri: edits}})

    def on_references(self, msg_id, params):
        uri = params["textDocument"]["uri"]
        target, lines = self._resolve(uri, params.get("position", {}))
        if target is None:
            self.respond(msg_id, [])
            return
        include_decl = params.get("context", {}).get("includeDeclaration",
                                                     True)
        index = self.scope_indexes[uri]
        locs = []
        if include_decl:
            loc = locate_range(lines, target.line, target.col, target.name)
            if loc is not None:
                locs.append({"uri": uri, "range": _lsp_range(loc)})
        for ref in index.locations_of(target):
            loc = locate_range(lines, ref.line, ref.col, ref.name)
            if loc is not None:
                locs.append({"uri": uri, "range": _lsp_range(loc)})
        locs.sort(key=lambda l: (l["range"]["start"]["line"],
                                 l["range"]["start"]["character"]))
        self.respond(msg_id, locs)

    def on_document_symbol(self, msg_id, params):
        uri = params["textDocument"]["uri"]
        doc = self.documents.get(uri)
        index = self.scope_indexes.get(uri)
        if doc is None or index is None:
            self.respond(msg_id, [])
            return
        lines = doc["text"].splitlines()
        self.respond(msg_id, [self._document_symbol(e, lines)
                              for e in index.top_symbols])

    def _document_symbol(self, entry, lines):
        loc = locate_range(lines, entry["line"], entry["col"], entry["name"])
        if loc is None:
            loc = (entry["line"] - 1, entry["col"],
                   entry["col"] + len(entry["name"]))
        sel = _lsp_range(loc)
        end_line = max(entry["end_line"], entry["line"]) - 1
        end_char = len(lines[end_line]) if 0 <= end_line < len(lines) else 0
        return {
            "name": entry["name"],
            "kind": _SYMBOL_KIND[entry["kind"]],
            "range": {"start": sel["start"],
                      "end": {"line": end_line, "character": end_char}},
            "selectionRange": sel,
            "children": [self._document_symbol(c, lines)
                         for c in entry["children"]],
        }

    # -- main loop --------------------------------------------------------

    def dispatch(self, msg):
        method = msg.get("method", "")
        msg_id = msg.get("id")
        params = msg.get("params", {}) or {}
        is_request = "id" in msg

        handler = {
            "initialize": lambda: self.on_initialize(msg_id, params),
            "shutdown": lambda: self._do_shutdown(msg_id),
            "textDocument/hover": lambda: self.on_hover(msg_id, params),
            "textDocument/definition":
                lambda: self.on_definition(msg_id, params),
            "textDocument/completion":
                lambda: self.on_completion(msg_id, params),
            "textDocument/rename":
                lambda: self.on_rename(msg_id, params),
            "textDocument/references":
                lambda: self.on_references(msg_id, params),
            "textDocument/documentSymbol":
                lambda: self.on_document_symbol(msg_id, params),
        }.get(method)

        if handler is not None:
            if is_request or method == "shutdown":
                handler()
            return

        # notifications
        if method == "initialized":
            return
        if method == "exit":
            sys.exit(0 if self._shutdown else 1)
        if method == "textDocument/didOpen":
            self.on_did_open(params)
            return
        if method == "textDocument/didChange":
            self.on_did_change(params)
            return
        # unknown: reply MethodNotFound to requests, ignore notifications
        if is_request:
            self.error(msg_id, -32601, f"method not found: {method}")

    def _do_shutdown(self, msg_id):
        self._shutdown = True
        self.respond(msg_id, None)

    def run(self):
        while True:
            msg = read_message(self.stdin)
            if msg is None:
                break
            try:
                self.dispatch(msg)
            except Exception:
                # a bad handler must not take the server down
                if "id" in msg:
                    self.error(msg.get("id"), -32603, "internal error")


def main():
    LanguageServer().run()


if __name__ == "__main__":
    main()
