# AGK for VS Code

Syntax highlighting for AGK-Real (`.agk`) files.

## Install

1. Copy the `editors/vscode` folder contents into
   `~/.vscode/extensions/agk-0.2.0/` (create the folder).
2. Reload VS Code (`Developer: Reload Window`).
3. Open any `.agk` file — keywords, strings (including `{interpolation}`),
   comments, and definitions are highlighted, with auto-indent for blocks.

No build step needed: the extension is a pure TextMate grammar.

## Language server

`agk.lsp` is a minimal JSON-RPC language server for `.agk` files, built on
the real compiler (lexer/parser/semantic/pipeline). It is stdio-only:
messages use `Content-Length` framing over stdin/stdout, so it plugs into
any editor with a generic stdio LSP client.

Run it with:

    ~/workspace/agk-real/.venv/bin/python -m agk.lsp

(or `python -m agk.lsp` once AGK-Real is installed).

It handles `initialize` (capabilities: full document sync, hover,
definition), `textDocument/didOpen` / `textDocument/didChange`, and
`shutdown` / `exit`. Opening or editing a file runs it through the real
compile pipeline and publishes `textDocument/publishDiagnostics` with the
compiler's actual errors mapped to LSP ranges. `textDocument/hover` shows a
short markdown summary (kind, name, signature, defining line) for defined
functions, classes, constants, variables, parameters, and fields;
`textDocument/definition` jumps to the defining `define ...` line.

Example config for a generic stdio LSP client extension:

```json
{
  "agk.serverCommand": ["~/workspace/agk-real/.venv/bin/python", "-m", "agk.lsp"],
  "agk.filePatterns": ["**/*.agk"]
}
```

Honest limits: no incremental sync (full document re-sent on each change),
no workspace symbols, and diagnostics carry the first compiler error only
(the pipeline raises on the first error) plus any warnings.
