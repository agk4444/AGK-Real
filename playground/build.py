"""Build the AGK Playground single-file HTML.

Embeds the whole `agk` package (compiler + stdlib .agk files) as JSON so
the page can write them into Pyodide's virtual filesystem and compile +
run AGK entirely in the browser. No server needed.

Usage:  python playground/build.py   ->  playground/agk-playground.html
"""

import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
TEMPLATE = Path(__file__).parent / "template.html"
OUT = Path(__file__).parent / "agk-playground.html"


def main():
    sources = {}
    for path in sorted((ROOT / "agk").rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        sources[str(path.relative_to(ROOT))] = path.read_text()
    for path in sorted((ROOT / "agk" / "stdlib").glob("*.agk")):
        sources[str(path.relative_to(ROOT))] = path.read_text()
    html = TEMPLATE.read_text()
    marker = "/*__AGK_SOURCES__*/{}"
    assert marker in html, "template marker missing"
    html = html.replace(marker, json.dumps(sources))
    OUT.write_text(html)
    kb = OUT.stat().st_size // 1024
    print(f"wrote {OUT} ({kb} KB, {len(sources)} embedded files)")


if __name__ == "__main__":
    main()
