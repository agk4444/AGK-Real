#!/usr/bin/env python3
"""Extract the playground's sample programs from the wiki's verified examples.

Every fenced ```agk block in wiki/*.md carrying a <!-- verify: --> comment
with an exact `output=` expectation — and needing no stdin, argv, local
HTTP server, or regex matching — becomes playground/samples/<id>.agk with
its expected stdout in <id>.expected.

Examples that cannot run in the browser playground (error demos,
compile-only snippets, argv/server/stdin-dependent programs, regex
outputs) are skipped and reported.

playground/build.py then compile-and-run verifies every extracted sample
against its .expected file, so a broken example can never ship.

Usage:  python playground/extract_wiki_samples.py
"""

import re
import shlex
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
WIKI = ROOT / "wiki"
SAMPLES = HERE / "samples"

# Examples that pass wiki verification only because each wiki example runs
# in a fresh temp dir as CWD. Their output depends on the working
# directory (or other ambient environment), so they cannot be reliable
# playground samples and are skipped.
ENV_DEPENDENT = {
    # lists "." — only ['demo.txt'] in the wiki's fresh temp dir
    "stdlib-fileutils",
    # create demo.db/shop.db in CWD and fail with "table already exists"
    # on any second run in the same directory
    "stdlib-sqliteutils",
    "stdlib-sqliteutils-2",
    # calls libc via ctypes — no system shared libraries in the browser
    # playground
    "ref-simple-use",
}

BLOCK_RE = re.compile(
    r'^[ \t]*<!--\s*verify:\s*(.*?)\s*-->[ \t]*\n'
    r'^[ \t]*```agk[ \t]*\n(.*?)^[ \t]*```[ \t]*$',
    re.DOTALL | re.MULTILINE)


def parse_attrs(raw):
    attrs = {}
    for tok in shlex.split(raw):
        if "=" in tok:
            key, val = tok.split("=", 1)
            attrs[key] = val
        else:
            attrs[tok] = True
    return attrs


def playable(attrs, source):
    """True when the example can run in the browser playground."""
    if "error" in attrs:          # error demo, must fail
        return False, "expects-error"
    if "compile-only" in attrs:   # no runnable output
        return False, "compile-only"
    if "output-regex" in attrs:   # no exact expectation
        return False, "output-regex"
    if "output" not in attrs:
        return False, "no-output"
    if "args" in attrs:
        return False, "needs-args"
    if "server" in attrs:
        return False, "needs-server"
    if re.search(r"(?<![\w])ask(?![\w])", source):
        return False, "needs-stdin"
    return True, ""


def main():
    seen = {}
    kept, skipped = [], []
    for md in sorted(WIKI.glob("*.md")):
        if md.name == "PUSH-TO-WIKI.md":
            continue
        text = md.read_text(encoding="utf-8")
        for m in BLOCK_RE.finditer(text):
            attrs = parse_attrs(m.group(1))
            eid = attrs.get("id")
            if not eid:
                continue
            if eid in seen:
                print(f"duplicate id {eid} in {md.name}", file=sys.stderr)
                sys.exit(1)
            seen[eid] = md.name
            if eid in ENV_DEPENDENT:
                skipped.append((eid, "env-dependent"))
                continue
            ok, reason = playable(attrs, m.group(2))
            if ok:
                kept.append((eid, m.group(2), attrs["output"]))
            else:
                skipped.append((eid, reason))

    shutil.rmtree(SAMPLES, ignore_errors=True)
    SAMPLES.mkdir(parents=True)
    for eid, source, output in kept:
        # Keep the source exactly as documented in the wiki.
        (SAMPLES / f"{eid}.agk").write_text(source, encoding="utf-8")
        # Same decoding as wiki/scripts/verify_examples.py.
        (SAMPLES / f"{eid}.expected").write_text(
            output.replace("\\n", "\n"), encoding="utf-8")

    print(f"extracted {len(kept)} samples from the wiki, "
          f"skipped {len(skipped)} (need stdin/args/server or are "
          f"error/compile-only demos):")
    for eid, reason in skipped:
        print(f"  - {eid} ({reason})")


if __name__ == "__main__":
    main()
