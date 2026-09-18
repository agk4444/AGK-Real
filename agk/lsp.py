"""Minimal JSON-RPC-over-stdio language server for AGK (.agk) files.

Run it with::

    python -m agk.lsp

It speaks LSP over stdin/stdout with ``Content-Length`` framing. Supported:
- ``initialize`` -> capabilities {textDocumentSync: full, hover, definition}
- ``initialized`` (notification)
- ``textDocument/didOpen`` / ``textDocument/didChange`` (full sync) ->
  the document is run through the real compile pipeline and
  ``textDocument/publishDiagnostics`` is emitted
- ``textDocument/hover`` -> markdown summary for defined
  functions/classes/constants/variables/parameters/fields
- ``textDocument/definition`` -> Location of the defining line
- ``shutdown`` / ``exit``

No workspace symbols, no incremental sync, no external dependencies.
"""

import json
import os
import re
import sys
from urllib.parse import unquote
from urllib.request import url2pathname

from . import ast_nodes as A
from .errors import AGKError
from .parser import parse
from .pipeline import compile_program

SERVER_NAME = "agk-lsp"
SERVER_VERSION = "0.2.0"

_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_WARN_RE = re.compile(r"^(.*?):(\d+):(\d+): warning: (.*)$")


# -- framing --------------------------------------------------------------


def read_message(stream):
    """Read one Content-Length framed JSON-RPC message from a binary stream.

    Returns the decoded dict, or None on EOF.
    """
    headers = {}
    while True:
        line = stream.readline()
        if not line:
            return None  # EOF
        line = line.decode("ascii", errors="replace").strip()
        if not line:
            break
        name, _, value = line.partition(":")
        headers[name.strip().lower()] = value.strip()
    try:
        length = int(headers.get("content-length", "0"))
    except ValueError:
        return None
    if length <= 0:
        return None
    body = stream.read(length)
    if not body:
        return None
    return json.loads(body.decode("utf-8"))


def write_message(stream, obj):
    body = json.dumps(obj, separators=(",", ":")).encode("utf-8")
    stream.write(b"Content-Length: %d\r\n\r\n" % len(body))
    stream.write(body)
    stream.flush()


# -- documents and symbol index -------------------------------------------


def uri_to_path(uri):
    if uri.startswith("file://"):
        return url2pathname(unquote(uri[len("file://"):]))
    return None


def word_at(line_text, character):
    for m in _WORD_RE.finditer(line_text):
        if m.start() <= character <= m.end():
            return m.group(0)
    return None


def _extend_to_word(line_text, character):
    """Expand (line, character) to the identifier end for nicer ranges."""
    m = _WORD_RE.search(line_text, character)
    if m and m.start() <= character:
        return m.end()
    return character + 1


class SymbolIndex:
    """name -> list of {kind, name, line (1-based), col (0-based), detail}."""

    def __init__(self):
        self.symbols = {}

    @classmethod
    def from_program(cls, program):
        index = cls()
        try:
            index._walk(program.statements)
        except Exception:
            pass
        return index

    def _add(self, kind, name, node, detail=""):
        self.symbols.setdefault(name, []).append({
            "kind": kind,
            "name": name,
            "line": node.line,
            "col": node.col,
            "detail": detail or "",
        })

    def _sig(self, fn):
        params = ", ".join(
            p.name + (f" as {p.type_name}" if p.type_name else "")
            for p in fn.params)
        ret = f" -> {fn.return_type}" if fn.return_type else ""
        return f"({params}){ret}"

    def _walk(self, stmts):
        for s in stmts or []:
            if isinstance(s, A.FunctionDef):
                self._add("function", s.name, s, self._sig(s))
                for p in s.params:
                    self._add("parameter", p.name, p, p.type_name or "")
                self._walk(s.body)
            elif isinstance(s, A.ClassDef):
                self._add("class", s.name, s,
                          f"extends {s.base}" if s.base else "")
                for f in s.fields:
                    self._add("field", f.name, f, f.type_name or "")
                    self._add("field", f"{s.name}.{f.name}", f,
                              f.type_name or "")
                if s.constructor:
                    for p in s.constructor.params:
                        self._add("parameter", p.name, p, p.type_name or "")
                    self._walk(s.constructor.body)
                for m in s.methods:
                    self._add("method", m.name, m, self._sig(m))
                    self._add("method", f"{s.name}.{m.name}", m,
                              self._sig(m))
                    for p in m.params:
                        self._add("parameter", p.name, p, p.type_name or "")
                    self._walk(m.body)
            elif isinstance(s, A.ConstantDef):
                self._add("constant", s.name, s, s.type_name or "")
            elif isinstance(s, A.CreateStmt):
                self._add("variable", s.name, s, s.type_name or "")
            elif isinstance(s, A.IfStmt):
                self._walk(s.then_body)
                for _cond, body in s.elifs:
                    self._walk(body)
                self._walk(s.else_body)
            elif isinstance(s, (A.WhileStmt, A.ForEachStmt, A.ForRangeStmt)):
                self._walk(s.body)
            elif isinstance(s, A.TryStmt):
                self._walk(s.body)
                self._walk(s.catch_body)
                self._walk(s.finally_body)


# -- diagnostics ----------------------------------------------------------


def _range(source_lines, line1, col):
    """AGK is 1-based lines, 0-based cols; LSP is 0-based both."""
    lsp_line = max(line1 - 1, 0)
    char = max(col, 0)
    end = char + 1
    if 0 <= lsp_line < len(source_lines):
        end = _extend_to_word(source_lines[lsp_line], char)
    return {
        "start": {"line": lsp_line, "character": char},
        "end": {"line": lsp_line, "character": end},
    }


def validate(source, filename, search_paths):
    """Run source through the real pipeline.

    Returns (diagnostics, symbol_index). The pipeline raises on the first
    error, so diagnostics carry at most one error plus any warnings.
    """
    source_lines = source.splitlines()
    diagnostics = []
    program = None
    try:
        program = parse(source, filename=filename)
        _code, warnings, _modules = compile_program(
            program, filename=filename, search_paths=search_paths)
    except AGKError as e:
        diagnostics.append({
            "range": _range(source_lines, e.line or 1, e.column),
            "severity": 1,  # Error
            "source": SERVER_NAME,
            "message": f"{e.phase}: {e.message}",
        })
    except Exception as e:  # never kill the server on a compiler bug
        diagnostics.append({
            "range": _range(source_lines, 1, 0),
            "severity": 1,
            "source": SERVER_NAME,
            "message": f"internal error: {e}",
        })
    else:
        for w in warnings:
            m = _WARN_RE.match(w)
            if not m:
                continue
            _wfile, wline, wcol, msg = m.groups()
            diagnostics.append({
                "range": _range(source_lines, int(wline), int(wcol)),
                "severity": 2,  # Warning
                "source": SERVER_NAME,
                "message": f"warning: {msg}",
            })
    return diagnostics, (SymbolIndex.from_program(program)
                         if program is not None else SymbolIndex())


# -- server ---------------------------------------------------------------


class LanguageServer:
    def __init__(self, stdin=None, stdout=None):
        self.stdin = stdin or sys.stdin.buffer
        self.stdout = stdout or sys.stdout.buffer
        self.documents = {}   # uri -> {"text", "version", "path"}
        self.indexes = {}     # uri -> SymbolIndex
        self._shutdown = False

    # -- io ---------------------------------------------------------------

    def send(self, obj):
        write_message(self.stdout, obj)

    def notify(self, method, params):
        self.send({"jsonrpc": "2.0", "method": method, "params": params})

    def respond(self, msg_id, result):
        self.send({"jsonrpc": "2.0", "id": msg_id, "result": result})

    def error(self, msg_id, code, message):
        self.send({"jsonrpc": "2.0", "id": msg_id,
                   "error": {"code": code, "message": message}})

    # -- documents --------------------------------------------------------

    def _store(self, uri, text, version):
        path = uri_to_path(uri)
        self.documents[uri] = {
            "text": text,
            "version": version,
            "path": path or "<input>",
        }

    def _publish_diagnostics(self, uri):
        doc = self.documents[uri]
        search_paths = []
        if doc["path"] != "<input>":
            d = os.path.dirname(os.path.abspath(doc["path"]))
            if os.path.isdir(d):
                search_paths.append(d)
        diagnostics, index = validate(doc["text"], doc["path"], search_paths)
        self.indexes[uri] = index
        self.notify("textDocument/publishDiagnostics",
                    {"uri": uri, "diagnostics": diagnostics})

    # -- handlers ---------------------------------------------------------

    def on_initialize(self, msg_id, _params):
        self.respond(msg_id, {
            "capabilities": {
                "textDocumentSync": 1,  # full document sync
                "hoverProvider": True,
                "definitionProvider": True,
            },
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        })

    def on_did_open(self, params):
        doc = params["textDocument"]
        self._store(doc["uri"], doc["text"], doc.get("version"))
        self._publish_diagnostics(doc["uri"])

    def on_did_change(self, params):
        uri = params["textDocument"]["uri"]
        version = params["textDocument"].get("version")
        changes = params.get("contentChanges", [])
        if uri in self.documents and changes:
            # full sync: the last change carries the whole document
            self._store(uri, changes[-1]["text"], version)
            self._publish_diagnostics(uri)

    def _word_and_entries(self, uri, position):
        doc = self.documents.get(uri)
        if doc is None:
            return None, []
        lines = doc["text"].splitlines()
        line_no = position.get("line", 0)
        if not (0 <= line_no < len(lines)):
            return None, []
        word = word_at(lines[line_no], position.get("character", 0))
        if not word:
            return None, []
        entries = self.indexes.get(uri)
        entries = entries.symbols.get(word, []) if entries else []
        return word, entries

    def on_hover(self, msg_id, params):
        _word, entries = self._word_and_entries(
            params["textDocument"]["uri"], params["position"])
        if not entries:
            self.respond(msg_id, None)
            return
        e = entries[0]
        title = {"function": "**function**",
                 "method": "**method**",
                 "class": "**class**",
                 "constant": "**constant**",
                 "variable": "**variable**",
                 "parameter": "**parameter**",
                 "field": "**field**"}.get(e["kind"], f"**{e['kind']}**")
        md = f"{title} `{e['name']}`"
        if e["detail"]:
            md += f"\n\n{e['detail']}"
        md += f"\n\ndefined at line {e['line']}"
        self.respond(msg_id, {
            "contents": {"kind": "markdown", "value": md},
        })

    def on_definition(self, msg_id, params):
        uri = params["textDocument"]["uri"]
        _word, entries = self._word_and_entries(uri, params["position"])
        if not entries:
            self.respond(msg_id, None)
            return
        e = entries[0]
        doc = self.documents[uri]
        lines = doc["text"].splitlines()
        lsp_line = max(e["line"] - 1, 0)
        char = e["col"]
        if 0 <= lsp_line < len(lines):
            found = lines[lsp_line].find(e["name"].split(".")[-1], e["col"])
            if found >= 0:
                char = found
        end = char + len(e["name"].split(".")[-1])
        self.respond(msg_id, {
            "uri": uri,
            "range": {
                "start": {"line": lsp_line, "character": char},
                "end": {"line": lsp_line, "character": end},
            },
        })

    # -- main loop --------------------------------------------------------

    def dispatch(self, msg):
        method = msg.get("method", "")
        msg_id = msg.get("id")
        params = msg.get("params", {}) or {}
        is_request = "id" in msg

        handler = {
            "initialize": lambda: self.on_initialize(msg_id, params),
            "shutdown": lambda: self._do_shutdown(msg_id),
            "textDocument/hover": lambda: self.on_hover(msg_id, params),
            "textDocument/definition":
                lambda: self.on_definition(msg_id, params),
        }.get(method)

        if handler is not None:
            if is_request or method == "shutdown":
                handler()
            return

        # notifications
        if method == "initialized":
            return
        if method == "exit":
            sys.exit(0 if self._shutdown else 1)
        if method == "textDocument/didOpen":
            self.on_did_open(params)
            return
        if method == "textDocument/didChange":
            self.on_did_change(params)
            return
        # unknown: reply MethodNotFound to requests, ignore notifications
        if is_request:
            self.error(msg_id, -32601, f"method not found: {method}")

    def _do_shutdown(self, msg_id):
        self._shutdown = True
        self.respond(msg_id, None)

    def run(self):
        while True:
            msg = read_message(self.stdin)
            if msg is None:
                break
            try:
                self.dispatch(msg)
            except Exception:
                # a bad handler must not take the server down
                if "id" in msg:
                    self.error(msg.get("id"), -32603, "internal error")


def main():
    LanguageServer().run()


if __name__ == "__main__":
    main()
