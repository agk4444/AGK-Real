"""AGK-aware debugging: `agk debug <file.agk>`.

Compiles the AGK file with ``annotate=True`` (every generated line
carries an ``# AGK file:line`` comment), builds an AGK<->Python line
map, and runs the program under a small :class:`pdb.Pdb` subclass that
translates the debugging experience back to AGK terms:

- ``break <agk-line>`` (or ``break <file.agk>:<line>``) sets a
  breakpoint at the corresponding generated-Python line.
- Stack frames (on stop, ``where``) show ``"<agk file>"(<line>)func()``
  with the AGK source line, not generated-Python locations.
- ``list`` shows AGK source around the current AGK line, marking the
  current line with ``->`` and breakpoint lines with ``B``.
- ``p <var>`` evaluates AGK variable names. Codegen preserves names
  verbatim, except bare field references inside methods, which the
  semantic analyzer rewrites to ``self.<field>`` — so a bare name that
  raises ``NameError`` is retried as ``self.<name>`` when the current
  frame has a ``self``.

``step``, ``next``, ``continue``, ``up``/``down`` and the rest of pdb
work unchanged. Interactive use reads commands from stdin; scripted
use works by piping commands on stdin.
"""

import os
import pdb
import re
import sys
import tempfile
import bdb as _bdb

from .errors import AGKError
from .pipeline import agk_line_map, compile_source, format_agk_traceback

_IDENT = re.compile(r"[A-Za-z_]\w*\Z")
# Matches pdb's "at <file>:<line>" fragments (breakpoint confirmations,
# the `break` listing, "Deleted ..." messages) so they can be rewritten
# in AGK terms.
_AT_RE = re.compile(r"at (\S+):(\d+)")


# Frames belonging to the debugger machinery itself (this module, pdb,
# bdb) are noise in an AGK traceback, the same way `agk run` skips its
# own exec frame.
_DEBUGGER_NOISE = {os.path.realpath(p)
                   for p in (__file__, pdb.__file__, _bdb.__file__)}


def _skip_debugger_frames(tb):
    """Drop leading traceback frames from the debugger machinery."""
    while tb is not None:
        try:
            name = os.path.realpath(tb.tb_frame.f_code.co_filename)
        except OSError:
            break
        if name in _DEBUGGER_NOISE:
            tb = tb.tb_next
        else:
            break
    return tb


class AGKDebugger(pdb.Pdb):
    """A pdb that speaks AGK line numbers and shows AGK source."""

    def __init__(self, agk_path, tmp_py, py_to_agk, agk_to_py):
        super().__init__()
        self.prompt = "(agk) "
        self._agk_path = agk_path  # path as given on the command line
        self._tmp_py = tmp_py  # generated-Python file pdb actually runs
        self._canonic_tmp = self.canonic(tmp_py)
        # {py_lineno: (agk_file, agk_line)}
        self._py_to_agk = py_to_agk
        # {(agk_file, agk_line): first py_lineno}
        self._agk_to_py = agk_to_py
        self._source_cache = {}
        self._agk_list_lineno = None

    # -- line-map helpers -------------------------------------------------

    def _agk_lines(self, path):
        if path not in self._source_cache:
            try:
                with open(path, encoding="utf-8") as f:
                    self._source_cache[path] = f.read().splitlines()
            except OSError:
                self._source_cache[path] = []
        return self._source_cache[path]

    def _matches_agk_file(self, filename):
        if filename == self._agk_path:
            return True
        try:
            if os.path.abspath(filename) == os.path.abspath(self._agk_path):
                return True
        except OSError:
            pass
        return os.path.basename(filename) == os.path.basename(self._agk_path)

    # -- break ------------------------------------------------------------

    def _translate_break_arg(self, arg):
        """Rewrite an AGK ``break`` location to generated-Python terms.

        Returns ``(new_arg, agk_file, agk_line)``; ``new_arg`` is None
        when translation failed (the error is already reported), and
        ``agk_line`` is None when the argument was passed through to
        pdb unchanged (function names, other files, empty args).
        """
        if not arg or not arg.strip():
            return arg, None, None
        cond = ""
        rest = arg
        comma = rest.find(",")
        if comma > 0:
            cond, rest = rest[comma:], rest[:comma]
        loc = rest.strip()
        filename = None
        lineno_text = loc
        if ":" in loc:
            filename, _, lineno_text = loc.rpartition(":")
            filename = filename.strip()
            lineno_text = lineno_text.strip()
        if not lineno_text.isdigit():
            return arg, None, None  # function name etc.: let pdb handle it
        agk_line = int(lineno_text)
        agk_file = self._agk_path
        if filename and not self._matches_agk_file(filename):
            return arg, None, None  # some other file: pass through
        py_line = self._agk_to_py.get((agk_file, agk_line))
        if py_line is None:
            self.error(f"No code at {agk_file}:{agk_line}")
            return None, None, None
        return f"{self._tmp_py}:{py_line}{cond}", agk_file, agk_line

    def do_break(self, arg, temporary=0):
        """b(reak) [ ([filename:]lineno | function) [, condition] ]

        Line numbers are AGK lines in the file under debug; they are
        translated to the generated-Python lines before pdb sees them.
        """
        new_arg, _agk_file, _agk_line = self._translate_break_arg(arg)
        if new_arg is None:
            return  # translation error already reported
        super().do_break(new_arg, temporary=temporary)

    do_b = do_break

    def message(self, msg):
        """Rewrite pdb's "at <tmpfile>:<pyline>" fragments to AGK."""
        def _agk_loc(m):
            fname, lineno = m.group(1), int(m.group(2))
            if self.canonic(fname) == self._canonic_tmp:
                loc = self._py_to_agk.get(lineno)
                if loc is not None:
                    return f"at {loc[0]}:{loc[1]}"
            return m.group(0)

        super().message(_AT_RE.sub(_agk_loc, msg))

    # -- frame display ------------------------------------------------------

    def format_stack_entry(self, frame_lineno, lprefix=": "):
        frame, lineno = frame_lineno
        loc = self._py_to_agk.get(lineno) if lineno is not None else None
        if loc is None:
            # Not AGK-generated code (stdlib, unannotated line): show the
            # real Python location rather than a wrong AGK one.
            return super().format_stack_entry(frame_lineno, lprefix)
        agk_file, agk_line = loc
        name = frame.f_code.co_name or "<lambda>"
        s = f'"{agk_file}"({agk_line}){name}()'
        lines = self._agk_lines(agk_file)
        if 1 <= agk_line <= len(lines):
            s += lprefix + lines[agk_line - 1].strip()
        return s

    # -- source listing -----------------------------------------------------

    def _agk_break_lines(self, agk_file):
        """AGK lines in *agk_file* that currently hold breakpoints."""
        found = set()
        for py_line in self.get_file_breaks(self._tmp_py):
            loc = self._py_to_agk.get(py_line)
            if loc is not None and loc[0] == agk_file:
                found.add(loc[1])
        return found

    def do_list(self, arg):
        """l(ist) [first[, last] | .]

        List AGK source around the current line. Arguments are AGK line
        numbers in the current file. The current line is marked ``->``,
        lines holding breakpoints with ``B``.
        """
        self.lastcmd = "list"
        frame = self.curframe
        loc = self._py_to_agk.get(frame.f_lineno)
        lines = self._agk_lines(loc[0]) if loc is not None else []
        if not lines:
            return super().do_list(arg)
        agk_file, agk_line = loc
        last = None
        if arg and arg != ".":
            try:
                if "," in arg:
                    first_s, last_s = arg.split(",", 1)
                    first = int(first_s.strip())
                    last = int(last_s.strip())
                    if last < first:
                        last = first + last  # a count, like pdb
                else:
                    first = max(1, int(arg.strip()) - 5)
            except ValueError:
                self.error("Error in argument: %r" % arg)
                return
        elif self._agk_list_lineno is None or arg == ".":
            first = max(1, agk_line - 5)
        else:
            first = self._agk_list_lineno + 1
        if last is None:
            last = first + 10
        first = max(1, first)
        last = min(last, len(lines))
        bp_lines = self._agk_break_lines(agk_file)
        for i in range(first, last + 1):
            marker = "->" if i == agk_line else "  "
            bmark = "B" if i in bp_lines else " "
            self.message(f"{marker}{bmark} {i:4d}  {lines[i - 1]}")
        self._agk_list_lineno = last
        if last >= len(lines):
            self.message("[EOF]")

    do_l = do_list

    def do_longlist(self, arg):
        """ll | longlist

        List the AGK source lines spanned by the current function.
        """
        frame = self.curframe
        agk_file = lo = hi = None
        try:
            py_lines = [ln for _, _, ln in frame.f_code.co_lines()
                        if ln is not None]
        except Exception:
            py_lines = []
        for py_line in py_lines:
            loc = self._py_to_agk.get(py_line)
            if loc is None:
                continue
            if agk_file is None:
                agk_file = loc[0]
            if loc[0] != agk_file:
                continue
            lo = loc[1] if lo is None else min(lo, loc[1])
            hi = loc[1] if hi is None else max(hi, loc[1])
        if agk_file is None:
            return super().do_longlist(arg)
        self.do_list(f"{lo},{hi}")

    do_ll = do_longlist

    # -- expression evaluation ----------------------------------------------

    def _getval(self, arg):
        frame = self.curframe
        try:
            return eval(arg, frame.f_globals, self.curframe_locals)  # noqa: S307
        except NameError:
            # Bare field references inside methods compile to
            # `self.<field>`; let `p field` find them.
            name = arg.strip()
            if _IDENT.fullmatch(name) and "self" in self.curframe_locals:
                try:
                    return eval("self." + name, frame.f_globals,  # noqa: S307
                                self.curframe_locals)
                except NameError:
                    pass
            self._error_exc()
            raise
        except BaseException:
            self._error_exc()
            raise

    def default(self, line):
        # Like _getval: a bare field name typed as an expression inside a
        # method resolves to self.<name>.
        if (line[:1] != "!" and self.curframe is not None
                and _IDENT.fullmatch(line.strip())
                and "self" in self.curframe_locals):
            try:
                val = eval("self." + line.strip(),  # noqa: S307
                           self.curframe.f_globals, self.curframe_locals)
            except Exception:
                pass
            else:
                print(repr(val), file=self.stdout)
                return
        return super().default(line)


def debug_file(path):
    """Compile *path* and run it under the AGK-aware debugger.

    Returns the process exit code: 0 when the session ends, 1 on
    compile error, 2 when the debugged program dies with an unhandled
    exception (an AGK-mapped traceback is printed, like `agk run`).
    """
    try:
        with open(path, encoding="utf-8") as f:
            src = f.read()
    except OSError as e:
        print(f"agk: cannot read '{path}': {e.strerror}", file=sys.stderr)
        raise SystemExit(2)
    search = [os.path.dirname(os.path.abspath(path))]
    try:
        code, warnings = compile_source(src, filename=path,
                                        search_paths=search, annotate=True)
    except AGKError as e:
        print(e, file=sys.stderr)
        raise SystemExit(1)
    for w in warnings:
        print(w, file=sys.stderr)
    fd, tmp_py = tempfile.mkstemp(prefix="agk_debug_", suffix=".py")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(code)
        py_to_agk = agk_line_map(code)
        agk_to_py = {}
        for py_line, (agk_file, agk_line) in py_to_agk.items():
            key = (agk_file, agk_line)
            if key not in agk_to_py or py_line < agk_to_py[key]:
                agk_to_py[key] = py_line
        dbg = AGKDebugger(path, tmp_py, py_to_agk, agk_to_py)
        dbg.message(f"Debugging {path}: break/step/list/p use AGK lines; "
                    f"'help' lists pdb commands.")
        try:
            dbg.run(compile(code, tmp_py, "exec"),
                    {"__name__": "__main__", "__file__": tmp_py})
        except SystemExit:
            raise  # the program called sys.exit(): keep its exit code
        except BaseException:
            # Unhandled exception under the debugger: show AGK file:line
            # like `agk run` does, without the debugger's own frames.
            exc_type, exc_value, tb = sys.exc_info()
            sys.stderr.write(format_agk_traceback(
                exc_type, exc_value, _skip_debugger_frames(tb), code))
            return 2
    finally:
        try:
            os.unlink(tmp_py)
        except OSError:
            pass
    return 0
