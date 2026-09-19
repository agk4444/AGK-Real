"""`agk new` — project scaffolding.

Generates a runnable project skeleton so a fresh project starts from
`agk new <name>` and immediately passes `agk run` and `agk test`.

App layout (default):

    <name>/
        agk.json
        README.md
        .gitignore
        src/
            main.agk          # entry point: `define function main`
            greeter.agk       # a tiny module, imported by main.agk
        tests/
            greeter_test.agk  # discovered by `agk test`, imports greeter

Lib layout (`--lib`): no entry point; the module itself is the product.

    <name>/
        agk.json
        README.md
        .gitignore
        src/
            <name>.agk        # the library module
        tests/
            <name>_test.agk

Public API: ``scaffold(name, kind="app", directory=".", force=False)``
returns the created project root Path. Raises ``ScaffoldError`` on bad
input (invalid name, target exists and is non-empty without force).
"""

import os
import re
from pathlib import Path

NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ScaffoldError(Exception):
    """Usage / IO failure for a scaffold operation."""


APP_MAIN = """import greeter

define function main:
    message is greet("AGK")
    say message
"""

APP_GREETER = """to greet with name:
    return "Hello, " + name + "!"
"""

APP_TEST = """import greeter

define function test_greet_includes_name:
    got is greet("Zuck")
    if got is not "Hello, Zuck!":
        raise "expected 'Hello, Zuck!' but got '" + got + "'"

define function test_greet_empty_name:
    got is greet("")
    if got is not "Hello, !":
        raise "empty name failed: " + got
"""

LIB_MODULE = """to double with n:
    return n * 2

to triple with n:
    return n * 3
"""

LIB_TEST = """import {name}

define function test_double:
    if double(21) is not 42:
        raise "double(21) should be 42"

define function test_triple:
    if triple(14) is not 42:
        raise "triple(14) should be 42"
"""

README_APP = """# {name}

An AGK app. Built with [AGK-Real](https://github.com/agk4444/AGK-Real).

## Run

    agk run src/main.agk

## Test

    agk test

## Package

    agk pkg init        # (already done — see agk.json)
    agk pkg install <git-url-or-path> [--name NAME]
"""

README_LIB = """# {name}

An AGK library. Built with [AGK-Real](https://github.com/agk4444/AGK-Real).

## Use it

    import {name}

    answer is double(21)

## Test

    agk test
"""

GITIGNORE = """.agkcache/
__pycache__/
*.pyc
"""

MANIFEST_TEMPLATE = """{{
  "name": "{name}",
  "version": "0.1.0",
  "dependencies": {{}}
}}
"""


def validate_name(name):
    """Project names must also work as module file names."""
    if not name or not NAME_RE.match(name):
        raise ScaffoldError(
            f"invalid project name '{name}': use letters, digits and "
            "underscores, starting with a letter or underscore")
    return name


def _write(root, relpath, content):
    path = root / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def scaffold(name, kind="app", directory=".", force=False):
    """Create a new AGK project skeleton. Returns the project root Path."""
    validate_name(name)
    if kind not in ("app", "lib"):
        raise ScaffoldError(f"unknown scaffold kind '{kind}': app or lib")
    root = Path(directory) / name
    if root.exists():
        if not force and any(root.iterdir()):
            raise ScaffoldError(
                f"'{root}' already exists and is not empty "
                "(use --force to scaffold into it anyway)")
    else:
        root.mkdir(parents=True)

    _write(root, "agk.json", MANIFEST_TEMPLATE.format(name=name))
    _write(root, ".gitignore", GITIGNORE)
    if kind == "app":
        _write(root, "README.md", README_APP.format(name=name))
        _write(root, "src/main.agk", APP_MAIN)
        _write(root, "src/greeter.agk", APP_GREETER)
        _write(root, "tests/greeter_test.agk", APP_TEST)
    else:
        _write(root, "README.md", README_LIB.format(name=name))
        _write(root, f"src/{name}.agk", LIB_MODULE)
        _write(root, f"tests/{name}_test.agk",
               LIB_TEST.format(name=name))
    return root


def describe(root, kind):
    """Human-readable tree of what was created, plus next steps."""
    lines = [f"created {root}/"]
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        rel = os.path.relpath(dirpath, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if rel != ".":
            lines.append("  " * depth + os.path.basename(dirpath) + "/")
        for fn in sorted(filenames):
            lines.append("  " * (depth + 1) + fn)
    lines.append("")
    if kind == "app":
        lines.append(f"next: cd {root.name} && agk run src/main.agk")
    else:
        lines.append(f"next: cd {root.name} && agk test")
    return "\n".join(lines)
