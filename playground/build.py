"""Build the AGK Playground single-file HTML.

Embeds the whole `agk` package (compiler + stdlib .agk files) as JSON so
the page can write them into Pyodide's virtual filesystem and compile +
run AGK entirely in the browser. No server needed.

The sample dropdown is generated from tests/corpus/*.agk. Every sample is
compile-and-run verified against its .expected file at build time, so a
broken example can never ship in the playground.

Usage:  python playground/build.py   ->  playground/agk-playground.html
"""

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).parent.parent
TEMPLATE = Path(__file__).parent / "template.html"
OUT = Path(__file__).parent / "agk-playground.html"
CORPUS = ROOT / "tests" / "corpus"

# Showcased first, then the rest alphabetically.
FIRST = ["hello", "simple_showcase"]


def load_samples():
    sys.path.insert(0, str(ROOT))
    from agk.pipeline import compile_source

    progs = sorted(CORPUS.glob("*.agk"), key=lambda p: p.stem)
    progs.sort(key=lambda p: (FIRST.index(p.stem) if p.stem in FIRST else len(FIRST), p.stem))

    samples = {}
    for prog in progs:
        src = prog.read_text()
        expected_file = prog.with_suffix(".expected")
        if not expected_file.exists():
            raise SystemExit(f"build aborted: {prog.name} has no .expected file")
        expected = expected_file.read_text()
        code, warnings = compile_source(src, filename=prog.name)
        if warnings:
            raise SystemExit(f"build aborted: {prog.name} has warnings: {warnings}")
        ns = {"__name__": "__main__"}
        buf = io.StringIO()
        with redirect_stdout(buf):
            exec(compile(code, prog.name, "exec"), ns)
        actual = buf.getvalue()
        if actual != expected:
            raise SystemExit(
                f"build aborted: {prog.name} output mismatch\n"
                f"--- expected ---\n{expected}--- actual ---\n{actual}"
            )
        samples[prog.stem] = src
    return samples


def main():
    sources = {}
    for path in sorted((ROOT / "agk").rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        sources[str(path.relative_to(ROOT))] = path.read_text()
    for path in sorted((ROOT / "agk" / "stdlib").glob("*.agk")):
        sources[str(path.relative_to(ROOT))] = path.read_text()

    samples = load_samples()

    html = TEMPLATE.read_text()
    marker = "/*__AGK_SOURCES__*/{}"
    assert marker in html, "sources marker missing"
    html = html.replace(marker, json.dumps(sources))
    marker = "/*__AGK_SAMPLES__*/{}"
    assert marker in html, "samples marker missing"
    html = html.replace(marker, json.dumps(samples))

    OUT.write_text(html)
    kb = OUT.stat().st_size // 1024
    print(f"wrote {OUT} ({kb} KB, {len(sources)} embedded files, {len(samples)} samples)")


if __name__ == "__main__":
    main()
