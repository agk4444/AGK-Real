#!/usr/bin/env python3
"""Check that every internal link in the wiki resolves.

- For each .md page, extracts [[Page Name]] / [[Page Name|label]] /
  [[Page#section]] / [[Page#section|label]] links (code spans and fenced
  code blocks are stripped first so `[[Page Name]]` inside backticks is
  not treated as a link).
- Page names resolve GitHub-style: spaces, hyphens, and underscores are
  equivalent ("Language-Reference" == "Language Reference").
- #section anchors must match a heading in the target page, slugged the
  way GitHub slugs headings (lowercase, punctuation removed, spaces to
  hyphens).
- Relative .md links (e.g. Tutorial.md) are flagged: this wiki uses
  [[Page Name]] links only.
- External (http/https) links are checked for well-formedness only
  (no network fetch, so the check is deterministic offline).

Exit 0 = zero broken links.
Usage: python check_links.py [wiki_dir]
"""

import os
import re
import sys
from urllib.parse import urlparse

WIKI = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else
                       os.path.join(os.path.dirname(__file__), ".."))

WIKILINK_RE = re.compile(r"\[\[([^\]|]+?)(?:\|[^\]]+)?\]\]")
MDLINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
CODESPAN_RE = re.compile(r"`[^`\n]+`")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


def strip_markup(text):
    text = FENCE_RE.sub("", text)
    text = COMMENT_RE.sub("", text)
    return CODESPAN_RE.sub("", text)


def normalize_page(name):
    return re.sub(r"\s+", " ",
                  name.strip().replace("_", " ").replace("-", " ")).lower()


def github_slug(heading):
    # Strip inline markdown formatting first (GitHub slugs the rendered text).
    text = re.sub(r"[*_`]", "", heading)
    text = text.lower()
    # Remove punctuation/symbols (GitHub's slugger), keeping letters,
    # numbers, spaces, hyphens, underscores; then EVERY space -> hyphen.
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    return text.strip().replace(" ", "-")


def page_headings(path):
    with open(path, encoding="utf-8") as f:
        text = strip_markup(f.read())
    return {github_slug(m.group(2)) for m in HEADING_RE.finditer(text)}


def main():
    errors = []
    checked = 0
    pages = {normalize_page(os.path.splitext(f)[0]): f
             for f in os.listdir(WIKI) if f.endswith(".md")}
    headings_cache = {}

    for fname in sorted(f for f in os.listdir(WIKI) if f.endswith(".md")):
        path = os.path.join(WIKI, fname)
        with open(path, encoding="utf-8") as f:
            raw = f.read()
        text = strip_markup(raw)
        for raw_link in WIKILINK_RE.findall(text):
            checked += 1
            target, _, anchor = raw_link.partition("#")
            key = normalize_page(target)
            if key not in pages:
                errors.append(f"{fname}: broken wiki link [[{raw_link}]] "
                              f"(no such page: {target!r})")
                continue
            if anchor:
                tpath = os.path.join(WIKI, pages[key])
                if tpath not in headings_cache:
                    headings_cache[tpath] = page_headings(tpath)
                if github_slug(anchor) not in headings_cache[tpath]:
                    errors.append(f"{fname}: broken section #{anchor!r} in "
                                  f"[[{raw_link}]] (page {pages[key]} has no "
                                  f"such heading)")
        for href in MDLINK_RE.findall(text):
            checked += 1
            parsed = urlparse(href)
            if parsed.scheme in ("http", "https"):
                continue  # external: well-formedness only
            if parsed.scheme == "mailto":
                continue
            if parsed.scheme or href.endswith(".md"):
                errors.append(f"{fname}: non-wiki internal link {href!r} "
                              f"(use [[Page Name]] links)")
                continue
            if parsed.path and not parsed.path.startswith("#"):
                errors.append(f"{fname}: unexpected relative link {href!r}")
    print(f"checked {checked} links")
    if errors:
        print(f"{len(errors)} BROKEN:")
        for e in errors:
            print("  " + e)
        return 1
    print("zero broken links")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
