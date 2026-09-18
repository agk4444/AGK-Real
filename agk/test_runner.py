"""AGK-Real v2 test runner.

Discovers ``test_*.agk`` / ``*_test.agk`` files, compiles each with the
real pipeline (``compile_source`` with ``annotate=True`` and the file's
own directory on the search path so sibling ``import``s work), executes
it, and runs every namespace callable named ``test_*``. A test passes
if it returns without raising; anything raised (test authors use
``raise "message"``) fails it, and the failure is reported with an
AGK-mapped traceback so it points at AGK source lines, not generated
Python.

Public API: ``run_tests(path) -> int`` (exit code), ``collect(path)``.
"""

import sys
from pathlib import Path

from .errors import AGKError
from .pipeline import compile_source, format_agk_traceback


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


def _run_file(path, results):
    """Compile, exec, and run one test file. Appends (label, ok) tuples
    to ``results``. Returns True when the file was collected cleanly."""
    try:
        src = path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"agk: cannot read '{path}': {e.strerror}", file=sys.stderr)
        results.append((str(path), False))
        return False
    try:
        code, warnings = compile_source(
            src, filename=str(path), search_paths=[str(path.parent)],
            annotate=True)
    except AGKError as e:
        print(f"{path}: {e}", file=sys.stderr)
        results.append((str(path), False))
        return False
    for w in warnings:
        print(w, file=sys.stderr)
    namespace = {}
    try:
        exec(compile(code, str(path), "exec"), namespace)  # noqa: S102
    except Exception:
        print(f"{path}: module-level error", file=sys.stderr)
        exc_type, exc_value, tb = sys.exc_info()
        sys.stderr.write(format_agk_traceback(exc_type, exc_value, tb, code))
        results.append((str(path), False))
        return False
    for name in _test_names(namespace):
        try:
            namespace[name]()
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


def run_tests(path="."):
    """Discover and run AGK tests under ``path``.

    Prints PASS/FAIL lines plus a summary, and returns an exit code:
    0 when everything passed, 1 when any test failed or a file could
    not be collected, 2 when the path itself is unusable.
    """
    try:
        files = collect(path)
    except FileNotFoundError as e:
        print(f"agk: {e}", file=sys.stderr)
        return 2
    results = []
    for f in files:
        _run_file(f, results)
    passed = sum(1 for _label, ok in results if ok)
    failed = len(results) - passed
    print(f"{passed} passed, {failed} failed")
    if failed:
        print("failed:")
        for label, ok in results:
            if not ok:
                print(f"  {label}")
    return 0 if failed == 0 else 1
