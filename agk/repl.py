"""AGK-Real v1 interactive REPL.

Each input is tried as (1) a full program (definitions, imports), then
(2) a single expression whose value is printed, then (3) a list of
statements. A trailing ':' continues onto more lines until a blank line.
Variables created with `create`, and functions/classes/constants defined
earlier, persist across inputs.
"""

import os

from . import ast_nodes as A
from .errors import AGKError
from .parser import parse, parse_expression_src, parse_statement_list
from .semantic import analyze
from .codegen import CodeGenerator
from .pipeline import compile_program

BANNER = ("AGK-Real v2  |  definitions, statements and expressions  |  "
          "blank line ends a block  |  'exit' quits")

# Warnings that are noise for one REPL input (the name lives on).
_REPL_NOISE = ("is never assigned a value", "unused variable")


def _created_names(stmts):
    """All names introduced by `create` anywhere in a statement list."""
    names = set()

    def walk(node):
        if isinstance(node, A.CreateStmt):
            names.add(node.name)
        if isinstance(node, A.IfStmt):
            for s in node.then_body:
                walk(s)
            for _cond, body in node.elifs:
                for s in body:
                    walk(s)
            if node.else_body:
                for s in node.else_body:
                    walk(s)
        elif isinstance(node, (A.WhileStmt, A.ForEachStmt, A.ForRangeStmt)):
            for s in node.body:
                walk(s)
        elif isinstance(node, A.TryStmt):
            for s in node.body:
                walk(s)
            if node.catch_body:
                for s in node.catch_body:
                    walk(s)
            if node.finally_body:
                for s in node.finally_body:
                    walk(s)

    for s in stmts:
        walk(s)
    return names


class Session:
    def __init__(self):
        self.namespace = {"__name__": "<repl>"}
        self.known = set()       # variable / Python-import names
        self.known_defs = []     # FunctionDef / ClassDef / ConstantDef nodes

    def _extra(self):
        return [A.Program(statements=self.known_defs)] if self.known_defs else []

    def _remember_program(self, program, modules):
        """Record a successfully compiled chunk's definitions so later
        inputs resolve (and may redefine) them."""
        defined = set()
        for stmt in program.statements:
            if isinstance(stmt, (A.FunctionDef, A.ClassDef, A.ConstantDef, A.ExternDef)):
                defined.add((type(stmt).__name__, stmt.name))
            elif isinstance(stmt, A.Import):
                if not any(stmt.module == name for name, _, _ in modules):
                    self.known.add(stmt.module.split(".")[0])
        self.known_defs = [
            d for d in self.known_defs
            if (type(d).__name__, d.name) not in defined
        ]
        for stmt in program.statements:
            if isinstance(stmt, (A.FunctionDef, A.ClassDef, A.ConstantDef, A.ExternDef)):
                self.known_defs.append(stmt)
        for _name, mod_prog, _path in modules:
            for stmt in mod_prog.statements:
                if isinstance(stmt, (A.FunctionDef, A.ClassDef, A.ConstantDef, A.ExternDef)):
                    key = (type(stmt).__name__, stmt.name)
                    self.known_defs = [d for d in self.known_defs
                                       if (type(d).__name__, d.name) != key]
                    self.known_defs.append(stmt)

    # -- the three tiers ----------------------------------------------------

    def run_program(self, chunk):
        program = parse(chunk, filename="<repl>")
        # Drop defs this chunk replaces before compiling, so redefinition
        # works the way it does in other REPLs.
        defined = {(type(s).__name__, s.name) for s in program.statements
                   if isinstance(s, (A.FunctionDef, A.ClassDef, A.ConstantDef, A.ExternDef))}
        kept = [d for d in self.known_defs
                if (type(d).__name__, d.name) not in defined]
        code, warnings, modules = compile_program(
            program, filename="<repl>", search_paths=[os.getcwd()],
            extra_top_levels=[A.Program(statements=kept)] if kept else [])
        for w in warnings:
            print(w)
        exec(compile(code, "<repl>", "exec"), self.namespace)  # noqa: S102
        self.known_defs = kept
        self._remember_program(program, modules)

    def run_statements(self, chunk):
        stmts = parse_statement_list(chunk, filename="<repl>")
        wrapper = A.FunctionDef(name="__repl__", params=[], return_type=None,
                               body=stmts)
        prog = A.Program(statements=[wrapper])
        _, warnings = analyze(prog, filename="<repl>", predeclared=self.known,
                              extra_top_levels=self._extra())
        cg = CodeGenerator()
        for s in wrapper.body:
            cg.gen_stmt(s)
        for w in warnings:
            if not any(noise in w for noise in _REPL_NOISE):
                print(w)
        exec(compile("\n".join(cg.lines), "<repl>", "exec"),  # noqa: S102
             self.namespace)
        self.known.update(_created_names(stmts))

    def run_expression(self, chunk):
        node = parse_expression_src(chunk, filename="<repl>")
        wrapper = A.FunctionDef(name="__repl__", params=[], return_type=None,
                               body=[A.ReturnStmt(value=node)])
        prog = A.Program(statements=[wrapper])
        analyze(prog, filename="<repl>", predeclared=self.known,
                extra_top_levels=self._extra())
        code = CodeGenerator().expr(wrapper.body[0].value)
        result = eval(compile(code, "<repl>", "eval"),  # noqa: S307
                      self.namespace)
        if result is not None:
            print(repr(result))

    # -- dispatch ---------------------------------------------------------------

    def handle(self, chunk):
        stripped = chunk.strip()
        if not stripped:
            return True
        if stripped in ("exit", "quit"):
            return False
        if stripped.split()[0] in ("define", "class", "import"):
            self.run_program(chunk)
            return True
        try:
            self.run_expression(chunk)
        except AGKError:
            try:
                self.run_statements(chunk)
            except AGKError as stmt_err:
                # Expression failed too: the statement error is usually the
                # more informative one (e.g. `set x to`).
                raise stmt_err from None
        return True


def _read_chunk():
    lines = []
    while True:
        try:
            line = input("... " if lines else ">>> ")
        except EOFError:
            print()
            raise
        if not line.strip():
            if lines:
                break
            continue
        lines.append(line)
        if len(lines) == 1 and not line.rstrip().endswith(":"):
            break
    return "\n".join(lines) + "\n"


def repl():
    print(BANNER)
    session = Session()
    while True:
        try:
            chunk = _read_chunk()
        except EOFError:
            break
        try:
            if not session.handle(chunk):
                break
        except AGKError as e:
            print(e)
        except KeyboardInterrupt:
            print()
            continue
