"""AGK-Real v2 command line.

    python -m agk run <file.agk>        compile and run
    python -m agk build <file.agk> [-o out.py]   compile to Python
    python -m agk check <file.agk>       compile only; report errors/warnings
    python -m agk repl                   interactive session
    python -m agk                        interactive session

Exit codes: 0 ok, 1 compile error, 2 runtime or usage error.
"""

import os
import sys

from .errors import AGKError
from .pipeline import compile_source, format_agk_traceback
from .repl import repl

USAGE = __doc__


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        print(f"agk: cannot read '{path}': {e.strerror}", file=sys.stderr)
        raise SystemExit(2)


def _compile(path, annotate=False):
    src = _read(path)
    search = [os.path.dirname(os.path.abspath(path))]
    try:
        return compile_source(src, filename=path, search_paths=search,
                              annotate=annotate)
    except AGKError as e:
        print(e, file=sys.stderr)
        raise SystemExit(1)


def _report_warnings(warnings):
    for w in warnings:
        print(w, file=sys.stderr)


def cmd_run(path):
    code, warnings = _compile(path, annotate=True)
    _report_warnings(warnings)
    try:
        exec(compile(code, path, "exec"), {"__name__": "__main__"})  # noqa: S102
    except Exception:
        # Show AGK file:line (not generated-Python lines) so the user
        # sees their own code. Needs sys.exc_info: the traceback object.
        exc_type, exc_value, tb = sys.exc_info()
        sys.stderr.write(format_agk_traceback(exc_type, exc_value, tb, code))
        raise SystemExit(2)
    return 0


def cmd_build(path, out):
    code, warnings = _compile(path)
    _report_warnings(warnings)
    if out is None:
        out = os.path.splitext(path)[0] + ".py"
    try:
        with open(out, "w", encoding="utf-8") as f:
            f.write(code)
    except OSError as e:
        print(f"agk: cannot write '{out}': {e.strerror}", file=sys.stderr)
        raise SystemExit(2)
    print(f"wrote {out}")
    return 0


def cmd_check(path):
    _code, warnings = _compile(path)
    _report_warnings(warnings)
    print(f"{path}: OK")
    return 0


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if not argv or argv[0] == "repl":
        repl()
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd == "run" and len(rest) == 1:
        return cmd_run(rest[0])
    if cmd == "build" and rest and rest[0].endswith(".agk"):
        out = None
        if len(rest) == 3 and rest[1] == "-o":
            out = rest[2]
        elif len(rest) != 1:
            print(USAGE, file=sys.stderr)
            return 2
        return cmd_build(rest[0], out)
    if cmd == "check" and len(rest) == 1:
        return cmd_check(rest[0])
    print(USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
