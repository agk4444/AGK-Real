# Publishing this wiki to GitHub

The `*.md` files in this directory are a GitHub wiki: each file is one wiki page, and every internal link uses the `[[Page Name]]` convention (never relative `.md` links). To publish them under the repo's **Wiki** tab:

```sh
# 1. Clone the wiki repo (GitHub creates the .wiki.git remote for any repo)
git clone https://github.com/agk4444/AGK-Real.wiki.git /tmp/agk-wiki

# 2. Copy the wiki pages in (no HTML, no CSS — Markdown only)
cp ~/workspace/agk-real/wiki/*.md /tmp/agk-wiki/

# 3. Commit and push
cd /tmp/agk-wiki
git add -A
git commit -m "Publish AGK-Real v0.4.0 wiki"
git push origin master
```

Notes:

- `Home.md` becomes the wiki's landing page; `_Sidebar.md` renders as the navigation sidebar on every page.
- Internal links (`[[Page Name]]`, `[[Page#section|label]]`) resolve automatically on GitHub — do not convert them to relative links.
- This file (`PUSH-TO-WIKI.md`) is an instruction sheet, not documentation. You may leave it out of the copy step, or push it as a "PUSH-TO-WIKI" page — your call. (It is intentionally excluded from `_Sidebar.md` either way.)
- `scripts/verify_examples.py` and `scripts/check_links.py` are authoring tools that live alongside the pages; push them if you want the verification tooling in the wiki history, otherwise keep the wiki repo Markdown-only.
