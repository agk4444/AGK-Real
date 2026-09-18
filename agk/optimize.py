"""AST-to-AST optimization pass for AGK-Real.

Runs after semantic analysis / type-checking, before codegen. Every
transformation is semantics-preserving: when in doubt the node is left
untouched.

  1. Constant folding: pure literal BinOp/UnaryOp expressions are
     evaluated at compile time (``2 + 3 * 4`` -> ``14``,
     ``"a" + "b"`` -> ``"ab"``). Anything that could raise at fold time
     (``1 / 0``), produce a non-finite float, allocate unbounded memory
     (giant string repetition), or has side effects (calls) is never
     folded.
  2. Dead-code elimination: statements after ``return``/``raise`` in the
     same block are dropped.
  3. Dead-store elimination: ``create``/``set`` of a local that is never
     read afterwards is dropped, but only when the right-hand side is a
     plain literal -- so no side effect and no exception can be lost.
"""

from . import ast_nodes as A

_NO_FOLD = object()
_LITERALS = (A.IntLit, A.FloatLit, A.StringLit, A.BoolLit)

# Cap on folded string length: folding "a" * 10**9 must not turn the
# compiler into a memory bomb. The unoptimized program would attempt the
# same allocation at run time; we simply decline to do it at compile time.
_MAX_FOLDED_STR = 10_000


# -- constant folding ---------------------------------------------------

def _lit_value(node):
    """Python value of a literal node, or _NO_FOLD."""
    if isinstance(node, A.BoolLit):
        return node.value
    if isinstance(node, A.IntLit):
        return node.value
    if isinstance(node, A.FloatLit):
        return node.value
    if isinstance(node, A.StringLit):
        return node.value
    return _NO_FOLD


def _wrap_literal(value, like):
    """Rebuild a literal node for a folded value, or _NO_FOLD.

    Non-finite floats are rejected: repr(inf)/repr(nan) are not valid
    Python literals, so emitting them would be a miscompile.
    """
    kw = {"line": like.line, "col": like.col}
    if isinstance(value, bool):
        return A.BoolLit(value, **kw)
    if isinstance(value, int):
        return A.IntLit(value, **kw)
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            return _NO_FOLD
        return A.FloatLit(value, **kw)
    if isinstance(value, str):
        if len(value) > _MAX_FOLDED_STR:
            return _NO_FOLD
        return A.StringLit(value, **kw)
    return _NO_FOLD


def _fold_binop(op, left, right):
    """Evaluate a binary op on two Python literal values, or _NO_FOLD.

    Any exception (ZeroDivisionError, TypeError, ...) means "leave the
    expression alone" so the error still surfaces at run time.
    """
    try:
        if op == "+":
            return left + right
        if op == "-":
            return left - right
        if op == "*":
            return left * right
        if op == "/":
            return left / right
        if op == "%":
            return left % right
        if op == "==":
            return left == right
        if op == "!=":
            return left != right
        if op == "<":
            return left < right
        if op == ">":
            return left > right
        if op == "<=":
            return left <= right
        if op == ">=":
            return left >= right
        if op == "and":
            return left and right
        if op == "or":
            return left or right
    except Exception:
        return _NO_FOLD
    return _NO_FOLD


def _fold_unary(op, value):
    try:
        if op == "-":
            return -value
        if op == "not":
            return not value
    except Exception:
        return _NO_FOLD
    return _NO_FOLD


def _fold_expr(e):
    """Bottom-up constant folding. Returns the (possibly new) node."""
    if isinstance(e, A.BinOp):
        e.left = _fold_expr(e.left)
        e.right = _fold_expr(e.right)
        left = _lit_value(e.left)
        right = _lit_value(e.right)
        if left is not _NO_FOLD and right is not _NO_FOLD:
            folded = _wrap_literal(_fold_binop(e.op, left, right), e)
            if folded is not _NO_FOLD:
                return folded
        return e
    if isinstance(e, A.UnaryOp):
        e.operand = _fold_expr(e.operand)
        value = _lit_value(e.operand)
        if value is not _NO_FOLD:
            folded = _wrap_literal(_fold_unary(e.op, value), e)
            if folded is not _NO_FOLD:
                return folded
        return e
    if isinstance(e, A.AwaitExpr):
        e.operand = _fold_expr(e.operand)
        return e
    if isinstance(e, A.Call):
        # Calls are never folded (side effects), but their subtrees are.
        e.func = _fold_expr(e.func)
        e.args = [_fold_expr(a) for a in e.args]
        return e
    if isinstance(e, A.Attribute):
        e.obj = _fold_expr(e.obj)
        return e
    if isinstance(e, A.Index):
        e.obj = _fold_expr(e.obj)
        e.index = _fold_expr(e.index)
        return e
    if isinstance(e, A.ListLit):
        e.elements = [_fold_expr(x) for x in e.elements]
        return e
    if isinstance(e, A.DictLit):
        e.pairs = [(_fold_expr(k), _fold_expr(v)) for k, v in e.pairs]
        return e
    return e


# -- read/write sets ----------------------------------------------------

def _reads_expr(e):
    """Names read (in expression position) anywhere inside e."""
    if e is None:
        return set()
    if isinstance(e, A.Name):
        return {e.id}
    if isinstance(e, A.BinOp):
        return _reads_expr(e.left) | _reads_expr(e.right)
    if isinstance(e, A.UnaryOp):
        return _reads_expr(e.operand)
    if isinstance(e, A.AwaitExpr):
        return _reads_expr(e.operand)
    if isinstance(e, A.Call):
        out = _reads_expr(e.func)
        for a in e.args:
            out |= _reads_expr(a)
        return out
    if isinstance(e, A.Attribute):
        return _reads_expr(e.obj)
    if isinstance(e, A.Index):
        return _reads_expr(e.obj) | _reads_expr(e.index)
    if isinstance(e, A.ListLit):
        out = set()
        for x in e.elements:
            out |= _reads_expr(x)
        return out
    if isinstance(e, A.DictLit):
        out = set()
        for k, v in e.pairs:
            out |= _reads_expr(k) | _reads_expr(v)
        return out
    return set()


def _reads_block(stmts):
    out = set()
    for s in stmts or ():
        out |= _reads_stmt(s)
    return out


def _reads_stmt(s):
    """Names read anywhere inside statement s (all nested blocks)."""
    if isinstance(s, A.ExprStmt):
        return _reads_expr(s.expr)
    if isinstance(s, A.SetStmt):
        return _reads_expr(s.value)
    if isinstance(s, A.SetAttr):
        return _reads_expr(s.obj) | _reads_expr(s.value)
    if isinstance(s, (A.ReturnStmt, A.YieldStmt, A.RaiseStmt)):
        return _reads_expr(s.value)
    if isinstance(s, A.IfStmt):
        out = _reads_expr(s.condition)
        out |= _reads_block(s.then_body)
        for cond, body in s.elifs:
            out |= _reads_expr(cond) | _reads_block(body)
        out |= _reads_block(s.else_body)
        return out
    if isinstance(s, A.WhileStmt):
        return _reads_expr(s.condition) | _reads_block(s.body)
    if isinstance(s, A.ForEachStmt):
        return _reads_expr(s.iterable) | _reads_block(s.body)
    if isinstance(s, A.ForRangeStmt):
        out = (_reads_expr(s.start) | _reads_expr(s.end)
               | _reads_expr(s.step) | _reads_block(s.body))
        return out
    if isinstance(s, A.TryStmt):
        return (_reads_block(s.body) | _reads_block(s.catch_body)
                | _reads_block(s.finally_body))
    return set()


def _writes_stmt(s):
    """Local names definitely bound by s itself (not nested blocks)."""
    if isinstance(s, A.SetStmt):
        return {s.name}
    if isinstance(s, A.CreateStmt) and not s.soft:
        # `create` emits no code, but a hard declaration starts the name's
        # live range. A soft (Simple AGK `x is ...`) redeclare is a pure
        # no-op: it must not kill liveness, or an earlier `x = <literal>`
        # would be wrongly dropped as a dead store.
        return {s.name}
    return set()


# -- block optimizer ----------------------------------------------------

def _opt_stmt(s, live_after):
    """Fold s's expressions and optimize nested blocks in place.

    live_after: names live just after s in the enclosing block; nested
    blocks that can observe them get it as their own live-after set.
    """
    if isinstance(s, A.ExprStmt):
        s.expr = _fold_expr(s.expr)
    elif isinstance(s, A.SetStmt):
        s.value = _fold_expr(s.value)
    elif isinstance(s, A.SetAttr):
        s.obj = _fold_expr(s.obj)
        s.value = _fold_expr(s.value)
    elif isinstance(s, (A.ReturnStmt, A.YieldStmt, A.RaiseStmt)):
        s.value = _fold_expr(s.value)
    elif isinstance(s, A.IfStmt):
        s.condition = _fold_expr(s.condition)
        s.then_body = _opt_block(s.then_body, live_after)[0]
        s.elifs = [(_fold_expr(cond), _opt_block(body, live_after)[0])
                   for cond, body in s.elifs]
        if s.else_body is not None:
            s.else_body = _opt_block(s.else_body, live_after)[0]
    elif isinstance(s, A.WhileStmt):
        s.condition = _fold_expr(s.condition)
        # The body loops back to the condition: anything the condition
        # reads is live at the end of the body.
        s.body = _opt_block(s.body,
                            live_after | _reads_expr(s.condition))[0]
    elif isinstance(s, A.ForEachStmt):
        s.iterable = _fold_expr(s.iterable)
        s.body = _opt_block(s.body, live_after)[0]
    elif isinstance(s, A.ForRangeStmt):
        s.start = _fold_expr(s.start)
        s.end = _fold_expr(s.end)
        if s.step is not None:
            s.step = _fold_expr(s.step)
        s.body = _opt_block(s.body, live_after)[0]
    elif isinstance(s, A.TryStmt):
        # The handlers can run after any point of the try body, so
        # anything they read is live throughout it.
        catch_reads = _reads_block(s.catch_body)
        finally_reads = _reads_block(s.finally_body)
        s.body = _opt_block(
            s.body, live_after | catch_reads | finally_reads)[0]
        if s.catch_body is not None:
            s.catch_body = _opt_block(
                s.catch_body, live_after | finally_reads)[0]
        if s.finally_body is not None:
            s.finally_body = _opt_block(s.finally_body, live_after)[0]
    elif isinstance(s, A.FunctionDef):
        s.decorators = [_fold_expr(d) for d in s.decorators]
        s.body = _opt_block(s.body, set())[0]
    elif isinstance(s, A.ClassDef):
        if s.constructor is not None:
            s.constructor.body = _opt_block(s.constructor.body, set())[0]
        for m in s.methods:
            m.decorators = [_fold_expr(d) for d in m.decorators]
            m.body = _opt_block(m.body, set())[0]
    return s


def _opt_block(stmts, live_after):
    """Optimize one statement list.

    Returns (new_statements, live_before). Dead-code elimination runs
    forward (drop everything after return/raise); dead-store elimination
    runs backward with a liveness set.
    """
    # Phase 1 (forward): truncate after return/raise.
    kept = []
    for s in stmts:
        kept.append(s)
        if isinstance(s, (A.ReturnStmt, A.RaiseStmt)):
            break
    # Phase 2 (backward): nested blocks + dead stores.
    live = set(live_after)
    out = []
    for s in reversed(kept):
        s = _opt_stmt(s, live)
        if isinstance(s, A.CreateStmt):
            # `create` emits no code; an unread declaration is dead.
            if s.name not in live:
                continue
        elif isinstance(s, A.SetStmt):
            # Drop only literal stores to unread locals: a literal RHS
            # has no side effects and cannot raise.
            if (s.name not in live
                    and isinstance(s.value, _LITERALS)
                    and s.name not in _reads_expr(s.value)):
                continue
        out.append(s)
        reads = _reads_stmt(s)
        writes = _writes_stmt(s)
        # A write kills liveness, unless the RHS itself reads the name
        # (e.g. `set x to x + 1` keeps x live for earlier statements).
        live = (live - (writes - reads)) | reads
    out.reverse()
    return out, live


def optimize_program(program):
    """Run the optimization pass over a parsed+analyzed Program.

    Mutates the program in place and returns it.
    """
    program.statements = _opt_block(program.statements, set())[0]
    return program
