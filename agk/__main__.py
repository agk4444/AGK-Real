"""AGK-Real v2 command line.

    python -m agk run <file.agk> [--no-opt]   compile and run
    python -m agk debug <file.agk>      run under the AGK-aware debugger
                                       (break/step/list/p use AGK lines)
    python -m agk build <file.agk> [-o out.py] [--clean] [--no-opt]
                                              compile to Python
                                              (incremental via .agkcache/)
    python -m agk clean [dir]         wipe the .agkcache/ compilation cache
    python -m agk check <file.agk>       compile only; report errors/warnings
    python -m agk test [path]             discover and run test_*.agk /
                                         *_test.agk files (default: .)
    python -m agk test --coverage [path]  same, plus a per-file AGK line-
                                         coverage table
    python -m agk fmt [--check] <file.agk>   canonical formatting (rewrite in
                                             place, or just check with --check)
    python -m agk new <name> [--lib] [--force]
                                         scaffold a new app (default) or
                                         library project
    python -m agk pkg init [--name NAME] [--version VER]
    python -m agk pkg install <git-url-or-path> [--name NAME]
    python -m agk pkg list
    python -m agk repl                   interactive session
    python -m agk                        interactive session

Exit codes: 0 ok, 1 compile error, 2 runtime or usage error.
For fmt: 0 ok (or clean under --check), 1 would reformat / lex error,
2 usage/IO error.
For test: 0 all tests passed, 1 some test failed or a file could not
be collected, 2 usage/IO error.
"""

import os
import sys

from .debugger import debug_file
from .errors import AGKError, LexerError
from .format import format_source
from .pipeline import (CACHE_DIR_NAME, compile_source, compile_source_cached,
                       format_agk_traceback, wipe_cache)
from .pkg import PkgError, cmd_init, cmd_install, cmd_list
from .repl import repl
from .scaffold import ScaffoldError, describe, scaffold
from .test_runner import run_tests

USAGE = __doc__


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        print(f"agk: cannot read '{path}': {e.strerror}", file=sys.stderr)
        raise SystemExit(2)


def _compile(path, annotate=False, no_opt=False):
    src = _read(path)
    search = [os.path.dirname(os.path.abspath(path))]
    try:
        return compile_source(src, filename=path, search_paths=search,
                              annotate=annotate, optimize=not no_opt)
    except AGKError as e:
        print(e, file=sys.stderr)
        raise SystemExit(1)


def _report_warnings(warnings):
    for w in warnings:
        print(w, file=sys.stderr)


def cmd_run(path, no_opt=False):
    code, warnings = _compile(path, annotate=True, no_opt=no_opt)
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


def cmd_build(path, out, clean=False, no_opt=False):
    src = _read(path)
    search = [os.path.dirname(os.path.abspath(path))]
    cache_dir = os.path.join(os.path.dirname(os.path.abspath(path)),
                             CACHE_DIR_NAME)
    if clean:
        wipe_cache(cache_dir)
    try:
        code, warnings, status = compile_source_cached(
            src, filename=path, search_paths=search, cache_dir=cache_dir,
            optimize=not no_opt)
    except AGKError as e:
        print(e, file=sys.stderr)
        raise SystemExit(1)
    for name, hit in status:
        print(("cache hit: " if hit else "compiled: ") + name)
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


def cmd_clean(path):
    cache_dir = os.path.join(os.path.abspath(path), CACHE_DIR_NAME)
    if wipe_cache(cache_dir):
        print(f"removed {cache_dir}")
    else:
        print(f"no cache at {cache_dir}")
    return 0


def cmd_check(path):
    _code, warnings = _compile(path)
    _report_warnings(warnings)
    print(f"{path}: OK")
    return 0


def cmd_debug(path):
    return debug_file(path)


def cmd_fmt(path, check=False):
    src = _read(path)
    try:
        out = format_source(src, filename=path)
    except LexerError as e:
        print(f"agk: cannot format '{path}': {e}", file=sys.stderr)
        return 1
    if out == src:
        if check:
            print("ok")
        return 0
    if check:
        print(f"would reformat {path}")
        return 1
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(out)
    except OSError as e:
        print(f"agk: cannot write '{path}': {e.strerror}", file=sys.stderr)
        raise SystemExit(2)
    return 0


def cmd_new(args):
    kind = "app"
    force = False
    rest = []
    for a in args:
        if a == "--lib":
            kind = "lib"
        elif a == "--force":
            force = True
        else:
            rest.append(a)
    if len(rest) != 1:
        print("agk new <name> [--lib] [--force]", file=sys.stderr)
        return 2
    try:
        root = scaffold(rest[0], kind=kind, force=force)
    except ScaffoldError as e:
        print(f"agk new: {e}", file=sys.stderr)
        return 2
    print(describe(root, kind))
    return 0


def cmd_pkg(args):
    if not args:
        print("agk pkg: init | install <url-or-path> [--name NAME] | list",
              file=sys.stderr)
        return 2
    sub, rest = args[0], args[1:]
    try:
        if sub == "init":
            return _pkg_init(rest)
        if sub == "install":
            return _pkg_install(rest)
        if sub == "list":
            return _pkg_list(rest)
    except PkgError as e:
        print(f"agk pkg: {e}", file=sys.stderr)
        return 2
    print(f"agk pkg: unknown subcommand '{sub}'", file=sys.stderr)
    return 2


def _flag(args, flag):
    """Split off '--flag VALUE' from args. Returns (value, remaining)."""
    out, value, i = [], None, 0
    while i < len(args):
        if args[i] == flag and i + 1 < len(args):
            value = args[i + 1]
            i += 2
        else:
            out.append(args[i])
            i += 1
    return value, out


def _pkg_init(args):
    name, rest = _flag(args, "--name")
    version, rest = _flag(rest, "--version")
    if rest:
        print("agk pkg init [--name NAME] [--version VER]", file=sys.stderr)
        return 2
    manifest = cmd_init(name=name, version=version or "0.1.0")
    print(f"created agk.json ({manifest['name']} {manifest['version']})")
    return 0


def _pkg_install(args):
    name, rest = _flag(args, "--name")
    if len(rest) != 1:
        print("agk pkg install <git-url-or-path> [--name NAME]",
              file=sys.stderr)
        return 2
    info = cmd_install(rest[0], name=name)
    if info["already_installed"]:
        print(f"{info['name']}: already installed ({info['path']})")
    else:
        commit = info["entry"]["commit"]
        print(f"installed {info['name']} -> {info['path']}"
              + (f" @ {commit[:12]}" if commit else ""))
    return 0


def _pkg_list(args):
    if args:
        print("agk pkg list", file=sys.stderr)
        return 2
    items = cmd_list()
    if not items:
        print("no packages installed")
        return 0
    for pkg_name, entry, present in items:
        ver = entry.get("version") or "?"
        commit = (entry.get("commit") or "local")[:12]
        status = "" if present else " (missing)"
        print(f"{pkg_name} {ver} {entry.get('url')} @ {commit}{status}")
    return 0


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if not argv or argv[0] == "repl":
        repl()
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd == "run" and rest:
        no_opt = "--no-opt" in rest
        args = [a for a in rest if a != "--no-opt"]
        if len(args) == 1:
            return cmd_run(args[0], no_opt=no_opt)
    if cmd == "debug" and len(rest) == 1:
        return cmd_debug(rest[0])
    if cmd == "build" and rest:
        args = list(rest)
        clean = False
        if args[0] == "--clean":
            clean = True
            args = args[1:]
        no_opt = "--no-opt" in args
        args = [a for a in args if a != "--no-opt"]
        if args and args[0].endswith(".agk"):
            out = None
            if len(args) == 3 and args[1] == "-o":
                out = args[2]
            elif len(args) != 1:
                print(USAGE, file=sys.stderr)
                return 2
            return cmd_build(args[0], out, clean=clean, no_opt=no_opt)
    if cmd == "clean" and len(rest) <= 1:
        return cmd_clean(rest[0] if rest else ".")
    if cmd == "check" and len(rest) == 1:
        return cmd_check(rest[0])
    if cmd == "test":
        args = list(rest)
        coverage = False
        if "--coverage" in args:
            coverage = True
            args = [a for a in args if a != "--coverage"]
        if len(args) > 1:
            print(USAGE, file=sys.stderr)
            return 2
        return run_tests(args[0] if args else ".", coverage=coverage)
    if cmd == "pkg":
        return cmd_pkg(rest)
    if cmd == "new":
        return cmd_new(rest)
    if cmd == "fmt":
        check = bool(rest) and rest[0] == "--check"
        args = rest[1:] if check else rest
        if len(args) != 1:
            print(USAGE, file=sys.stderr)
            return 2
        return cmd_fmt(args[0], check=check)
    print(USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
