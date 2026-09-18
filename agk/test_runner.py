"""AGK-Real v2 test runner.

Discovers ``test_*.agk`` / ``*_test.agk`` files, compiles each with the
real pipeline (``compile_source`` with ``annotate=True`` and the file's
own directory on the search path so sibling ``import``s work), executes
it, and runs every namespace callable named ``test_*``. A test passes
if it returns without raising; anything raised (test authors use
``raise "message"``) fails it, and the failure is reported with an
AGK-mapped traceback so it points at AGK source lines, not generated
Python.

Fixtures: if the module defines ``setup`` it runs before each test
function; ``teardown`` runs after each one -- even when setup or the
test itself raised. Neither name is treated as a test.

Mocks: every test module gets ``mock(name)``, ``mock_return(name,
value)`` and ``unmock(m)`` helpers (see agk/mock.py). Because imports
are compiled inline into a single namespace, replacing a module-level
function name with a Mock intercepts every call to it, including calls
made from imported helper code. The names ``mock``, ``mock_return``
and ``unmock`` are reserved in test files.

Coverage: with ``coverage=True`` (``agk test --coverage``), executed
generated-Python lines are traced with sys.settrace and mapped back to
AGK source lines via the `# AGK file:line` annotations; a per-file
coverage table (covered / total executable AGK lines) is printed after
the summary. Bundled stdlib modules are excluded from the table.

Public API: ``run_tests(path, coverage=False) -> int`` (exit code),
``collect(path)``.
"""

import sys
from pathlib import Path

from .errors import AGKError
from .mock import MOCK_PRELUDE, install_helpers
from .pipeline import (STDLIB_DIR, agk_line_map, compile_source,
                       format_agk_traceback)


def collect(path):
    """Find AGK test files under ``path``.

    A directory is searched recursively for ``test_*.agk`` and
    ``*_test.agk`` files (returned sorted). A single file given
    explicitly is collected as-is. Raises FileNotFoundError when the
    path does not exist.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"no such file or directory: '{path}'")
    if p.is_file():
        return [p]
    return sorted(
        f for f in p.rglob("*.agk")
        if f.name.startswith("test_") or f.name.endswith("_test.agk")
    )


def _test_names(namespace):
    """Sorted names of callables in the namespace starting with test_."""
    return sorted(
        name for name, value in namespace.items()
        if name.startswith("test_") and callable(value)
    )


def _fixture(namespace, name):
    """The module's fixture function, or None when absent/not callable."""
    fn = namespace.get(name)
    return fn if callable(fn) else None


class _Tracer:
    """sys.settrace line tracer limited to one generated file.

    Only frames whose code object filename matches the compiled test
    file are traced, so Python builtins and the runner itself don't
    pollute the results. Restores any previous trace function on exit.
    """

    def __init__(self, filename):
        self.filename = filename
        self.lines = set()
        self._prev = None

    def __enter__(self):
        self._prev = sys.gettrace()
        sys.settrace(self._trace_calls)
        return self

    def __exit__(self, *exc):
        sys.settrace(self._prev)
        return False

    def _trace_calls(self, frame, event, _arg):
        if event == "call" and frame.f_code.co_filename == self.filename:
            return self._trace_lines
        return None

    def _trace_lines(self, frame, event, _arg):
        if event == "line":
            self.lines.add(frame.f_lineno)
        return self._trace_lines


def _is_stdlib(agk_file):
    try:
        return Path(agk_file).is_relative_to(STDLIB_DIR)
    except (ValueError, OSError):
        return False


class Coverage:
    """Per-AGK-file line coverage aggregated over a test run."""

    def __init__(self):
        self._files = {}  # agk path -> [total lines set, covered lines set]

    def add_run(self, code, executed_lines):
        """Fold one compiled test file's executed Python lines in.

        ``executed_lines`` is a set of generated-Python line numbers;
        they are mapped back to AGK (file, line) pairs via the
        `# AGK file:line` annotations. Total executable lines are the
        distinct AGK lines that produced generated code.
        """
        for py_lineno, (agk_file, agk_lineno) in \
                agk_line_map(code).items():
            if _is_stdlib(agk_file):
                continue
            total, covered = self._files.setdefault(agk_file, (set(), set()))
            total.add(agk_lineno)
            if py_lineno in executed_lines:
                covered.add(agk_lineno)

    def rows(self):
        """Sorted [(agk_file, pct, covered, total)] for the report."""
        out = []
        for agk_file in sorted(self._files):
            total, covered = self._files[agk_file]
            pct = round(100 * len(covered) / len(total)) if total else 100
            out.append((agk_file, pct, len(covered), len(total)))
        return out


def _exec_tests(path, code, namespace, results):
    """Exec one compiled test module and run its test_* functions.

    Appends (label, ok) tuples to ``results``. Returns True when the
    module executed cleanly (individual test failures still return
    True; they are recorded in ``results``).
    """
    try:
        exec(compile(code, str(path), "exec"), namespace)  # noqa: S102
    except Exception:
        print(f"{path}: module-level error", file=sys.stderr)
        exc_type, exc_value, tb = sys.exc_info()
        sys.stderr.write(format_agk_traceback(exc_type, exc_value, tb, code))
        results.append((str(path), False))
        return False
    setup = _fixture(namespace, "setup")
    teardown = _fixture(namespace, "teardown")
    for name in _test_names(namespace):
        try:
            try:
                if setup is not None:
                    setup()
                namespace[name]()
            finally:
                if teardown is not None:
                    teardown()
        except Exception:
            print(f"FAIL {path}::{name}")
            exc_type, exc_value, tb = sys.exc_info()
            sys.stderr.write(
                format_agk_traceback(exc_type, exc_value, tb, code))
            results.append((f"{path}::{name}", False))
        else:
            print(f"PASS {path}::{name}")
            results.append((f"{path}::{name}", True))
    return True


def _run_file(path, results, coverage=None):
    """Compile, exec, and run one test file. Appends (label, ok) tuples
    to ``results``. When ``coverage`` (a Coverage) is given, executed
    lines are traced and folded into it. Returns True when the file
    was collected cleanly."""
    try:
        src = path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"agk: cannot read '{path}': {e.strerror}", file=sys.stderr)
        results.append((str(path), False))
        return False
    try:
        code, warnings = compile_source(
            src, filename=str(path), search_paths=[str(path.parent)],
            annotate=True, extra_top_levels=(MOCK_PRELUDE,))
    except AGKError as e:
        print(f"{path}: {e}", file=sys.stderr)
        results.append((str(path), False))
        return False
    for w in warnings:
        print(w, file=sys.stderr)
    namespace = {}
    namespace.update(install_helpers(namespace))
    if coverage is None:
        return _exec_tests(path, code, namespace, results)
    with _Tracer(str(path)) as tracer:
        ok = _exec_tests(path, code, namespace, results)
    coverage.add_run(code, tracer.lines)
    return ok


def run_tests(path=".", coverage=False):
    """Discover and run AGK tests under ``path``.

    Prints PASS/FAIL lines plus a summary, and returns an exit code:
    0 when everything passed, 1 when any test failed or a file could
    not be collected, 2 when the path itself is unusable.

    With ``coverage=True``, a per-file AGK line-coverage table is
    printed after the summary.
    """
    try:
        files = collect(path)
    except FileNotFoundError as e:
        print(f"agk: {e}", file=sys.stderr)
        return 2
    results = []
    cov = Coverage() if coverage else None
    for f in files:
        _run_file(f, results, cov)
    passed = sum(1 for _label, ok in results if ok)
    failed = len(results) - passed
    print(f"{passed} passed, {failed} failed")
    if failed:
        print("failed:")
        for label, ok in results:
            if not ok:
                print(f"  {label}")
    if cov is not None:
        print("coverage:")
        for agk_file, pct, n_covered, n_total in cov.rows():
            print(f"  {agk_file}: {pct}% ({n_covered}/{n_total} lines)")
    return 0 if failed == 0 else 1
