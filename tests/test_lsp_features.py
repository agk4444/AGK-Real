"""Protocol tests for the v0.4.0 LSP additions in agk/lsp.py:
completion, rename, references, and document symbols.

Drives the language server as a subprocess over stdio with
Content-Length framing, using the same harness as test_lsp.py.
"""

import json
import os
import select
import subprocess
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

COMPLETE_SRC = """\
define function greet that takes name as String:
    create greeting as String
    set greeting to "hello"
    print(greeting)

"""

RENAME_SRC = """\
define function first:
    create x as Integer
    set x to 1
    print(x)

define function second:
    create x as Integer
    set x to 2
    print(x)
"""

REF_SRC = """\
define function add that takes a as Integer, b as Integer and returns Integer:
    return a + b

define function main:
    print(add(1, 2))
    print(add(3, 4))
"""

SYMBOL_SRC = """\
define constant PI as Float = 3.14159

define function circle_area that takes r as Float and returns Float:
    return PI * r * r

define class Account:
    variable balance as Float
    define constructor that takes initial as Float:
        set balance to initial
    define function deposit that takes amount as Float:
        set balance to balance + amount

define function main:
    create a as Object
    set a to Account(100.0)
"""

MODULE_ATTR_SRC = """\
import strutils

define function main:
    print(strutils.
"""


class LSPClient:
    def __init__(self):
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "agk.lsp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=REPO,
        )
        self._next_id = 1

    def _frame(self, obj):
        body = json.dumps(obj).encode("utf-8")
        self.proc.stdin.write(b"Content-Length: %d\r\n\r\n" % len(body))
        self.proc.stdin.write(body)
        self.proc.stdin.flush()

    def recv(self, timeout=10):
        r, _, _ = select.select([self.proc.stdout], [], [], timeout)
        assert r, "timed out waiting for server message"
        headers = {}
        while True:
            line = self.proc.stdout.readline().decode("ascii").strip()
            if not line:
                break
            name, _, value = line.partition(":")
            headers[name.strip().lower()] = value.strip()
        length = int(headers["content-length"])
        body = self.proc.stdout.read(length)
        return json.loads(body.decode("utf-8"))

    def request(self, method, params):
        msg_id = self._next_id
        self._next_id += 1
        self._frame({"jsonrpc": "2.0", "id": msg_id,
                     "method": method, "params": params})
        return msg_id

    def notify(self, method, params):
        self._frame({"jsonrpc": "2.0", "method": method, "params": params})

    def did_open(self, uri, text, version=1):
        self.notify("textDocument/didOpen", {
            "textDocument": {"uri": uri, "languageId": "agk",
                             "version": version, "text": text}})

    def close(self):
        try:
            self.proc.kill()
        except OSError:
            pass
        self.proc.wait()


def _handshake(c):
    msg_id = c.request("initialize", {"processId": None, "capabilities": {}})
    resp = c.recv()
    assert resp["id"] == msg_id
    c.notify("initialized", {})
    return resp["result"]


def _open(c, uri, text):
    c.did_open(uri, text)
    notif = c.recv()
    assert notif["method"] == "textDocument/publishDiagnostics"
    return notif


def _offset(lines, line, character):
    return sum(len(l) + 1 for l in lines[:line]) + character


def apply_edits(text, edits):
    """Apply LSP TextEdits (as returned by rename) to text."""
    lines = text.split("\n")
    spans = []
    for e in edits:
        s, en = e["range"]["start"], e["range"]["end"]
        spans.append((_offset(lines, s["line"], s["character"]),
                      _offset(lines, en["line"], en["character"]),
                      e["newText"]))
    out = text
    for start, end, new in sorted(spans, reverse=True):
        out = out[:start] + new + out[end:]
    return out


@pytest.fixture()
def client():
    c = LSPClient()
    yield c
    c.close()


# -- capabilities -------------------------------------------------------


def test_initialize_advertises_new_providers(client):
    result = _handshake(client)
    caps = result["capabilities"]
    assert caps["completionProvider"]["triggerCharacters"] == ["."]
    assert caps["renameProvider"] is True
    assert caps["referencesProvider"] is True
    assert caps["documentSymbolProvider"] is True


# -- completion ---------------------------------------------------------


def _complete(client, uri, line, character):
    msg_id = client.request("textDocument/completion", {
        "textDocument": {"uri": uri},
        "position": {"line": line, "character": character},
    })
    resp = client.recv()
    assert resp["id"] == msg_id
    result = resp["result"]
    assert result["isIncomplete"] is False
    return {i["label"]: i for i in result["items"]}


def test_completion_prefix_suggests_function_and_variable(client):
    _handshake(client)
    uri = "file:///tmp/complete.agk"
    _open(client, uri, COMPLETE_SRC)
    # cursor mid-word in `greeting` on line 3: `    print(gre|eting)`
    items = _complete(client, uri, 3, 13)
    assert items["greet"]["kind"] == 3  # Function
    assert "(name as String)" in items["greet"]["detail"]
    assert items["greeting"]["kind"] == 6  # Variable
    assert items["greeting"]["detail"] == "String"
    # 'name' (the parameter) does not match the 'gre' prefix
    assert "name" not in items


def test_completion_empty_prefix_suggests_keywords_builtins_stdlib(client):
    _handshake(client)
    uri = "file:///tmp/complete2.agk"
    _open(client, uri, COMPLETE_SRC)
    # empty line 4, char 0: everything is a candidate
    items = _complete(client, uri, 4, 0)
    assert items["define"]["kind"] == 14  # Keyword
    assert items["print"]["kind"] == 3  # Function
    assert items["print"]["detail"] == "builtin function"
    assert items["strutils"]["kind"] == 9  # Module
    assert items["strutils"]["detail"] == "standard library module"


def test_completion_inside_function_suggests_param_and_local(client):
    _handshake(client)
    uri = "file:///tmp/complete3.agk"
    _open(client, uri, COMPLETE_SRC)
    # start of line 3, inside the function body: param 'name' and
    # local 'greeting' are in scope, as is the function itself
    items = _complete(client, uri, 3, 4)
    assert items["name"]["kind"] == 6  # Variable (parameters map to 6)
    assert items["greeting"]["kind"] == 6
    assert items["greet"]["kind"] == 3


def test_completion_after_module_dot_suggests_stdlib_functions(client):
    _handshake(client)
    uri = "file:///tmp/modattr.agk"
    _open(client, uri, MODULE_ATTR_SRC)
    # cursor right after `strutils.` on line 3
    items = _complete(client, uri, 3, 19)
    assert items["shout"]["kind"] == 2  # Method
    assert "(s as String)" in items["shout"]["detail"]
    assert "repeat_string" in items
    assert "slug" in items
    # plain identifiers are not suggested in dot mode
    assert "print" not in items


def test_completion_after_unknown_module_dot_is_empty(client):
    _handshake(client)
    uri = "file:///tmp/modattr2.agk"
    _open(client, uri, MODULE_ATTR_SRC.replace("strutils.", "nosuchmod."))
    items = _complete(client, uri, 3, 20)
    assert items == {}


def test_completion_on_broken_file_does_not_crash(client):
    _handshake(client)
    uri = "file:///tmp/brokencomplete.agk"
    _open(client, uri, "define function oops(:\n    create x as\n")
    items = _complete(client, uri, 1, 4)
    assert isinstance(items, dict)
    # keywords/builtins still work with no parse tree
    assert "define" in items
    assert "print" in items


def test_completion_unopened_document_is_empty(client):
    _handshake(client)
    msg_id = client.request("textDocument/completion", {
        "textDocument": {"uri": "file:///tmp/never-opened.agk"},
        "position": {"line": 0, "character": 0},
    })
    resp = client.recv()
    assert resp["id"] == msg_id
    assert resp["result"]["items"] == []


# -- rename -------------------------------------------------------------


def _rename(client, uri, line, character, new_name):
    msg_id = client.request("textDocument/rename", {
        "textDocument": {"uri": uri},
        "position": {"line": line, "character": character},
        "newName": new_name,
    })
    resp = client.recv()
    assert resp["id"] == msg_id
    return resp["result"]


def test_rename_variable_renames_def_and_uses(client):
    _handshake(client)
    uri = "file:///tmp/rename.agk"
    _open(client, uri, RENAME_SRC)
    # rename from a *use* of x: `set x to 1` (line 2, char 8)
    result = _rename(client, uri, 2, 8, "counter")
    edits = result["changes"][uri]
    assert len(edits) == 3
    new_text = apply_edits(RENAME_SRC, edits)
    assert new_text == RENAME_SRC.replace(
        "create x as Integer\n    set x to 1\n    print(x)",
        "create counter as Integer\n    set counter to 1\n    print(counter)",
        1)


def test_rename_shadowed_variable_only_affects_its_scope(client):
    _handshake(client)
    uri = "file:///tmp/renameshadow.agk"
    _open(client, uri, RENAME_SRC)
    # rename x inside `second` (use at line 7, char 8)
    result = _rename(client, uri, 7, 8, "total")
    edits = result["changes"][uri]
    assert len(edits) == 3
    lines = RENAME_SRC.split("\n")
    for e in edits:
        assert e["range"]["start"]["line"] in (6, 7, 8), \
            "rename leaked into the other function's scope"
    new_text = apply_edits(RENAME_SRC, edits)
    # first function's x untouched
    assert "create x as Integer\n    set x to 1\n    print(x)" in new_text
    assert "create total as Integer\n    set total to 2\n    print(total)" \
        in new_text


def test_rename_from_definition_site(client):
    _handshake(client)
    uri = "file:///tmp/renamedef.agk"
    _open(client, uri, RENAME_SRC)
    # cursor on the definition `create x as Integer` (line 1, char 11)
    result = _rename(client, uri, 1, 11, "n")
    edits = result["changes"][uri]
    assert len(edits) == 3
    assert apply_edits(RENAME_SRC, edits).split("\n")[1] == \
        "    create n as Integer"


def test_rename_function_renames_call_sites(client):
    _handshake(client)
    uri = "file:///tmp/renamefn.agk"
    _open(client, uri, REF_SRC)
    # rename `add` from a call site (line 5, char 11)
    result = _rename(client, uri, 5, 11, "plus")
    edits = result["changes"][uri]
    assert len(edits) == 3  # def + 2 calls
    new_text = apply_edits(REF_SRC, edits)
    assert "define function plus that takes" in new_text
    assert new_text.count("plus(") == 2
    assert "add(" not in new_text


def test_rename_unknown_word_returns_null(client):
    _handshake(client)
    uri = "file:///tmp/renamenull.agk"
    _open(client, uri, RENAME_SRC)
    # `print` is a builtin: no renameable symbol
    result = _rename(client, uri, 3, 6, "whatever")
    assert result is None


def test_rename_invalid_new_name_is_rejected(client):
    _handshake(client)
    uri = "file:///tmp/renamebad.agk"
    _open(client, uri, RENAME_SRC)
    msg_id = client.request("textDocument/rename", {
        "textDocument": {"uri": uri},
        "position": {"line": 2, "character": 8},
        "newName": "not a name",
    })
    resp = client.recv()
    assert resp["id"] == msg_id
    assert resp["error"]["code"] == -32602


# -- references ---------------------------------------------------------


def _references(client, uri, line, character, include_declaration=True):
    msg_id = client.request("textDocument/references", {
        "textDocument": {"uri": uri},
        "position": {"line": line, "character": character},
        "context": {"includeDeclaration": include_declaration},
    })
    resp = client.recv()
    assert resp["id"] == msg_id
    return resp["result"]


def _starts(result):
    return sorted((l["range"]["start"]["line"],
                   l["range"]["start"]["character"]) for l in result)


def test_references_include_definition_and_all_uses(client):
    _handshake(client)
    uri = "file:///tmp/refs.agk"
    _open(client, uri, REF_SRC)
    # `add` call site (line 5, char 11)
    result = _references(client, uri, 5, 11)
    assert _starts(result) == [(0, 16), (4, 10), (5, 10)]
    for loc in result:
        assert loc["uri"] == uri
        r = loc["range"]
        assert r["end"]["line"] == r["start"]["line"]
        assert r["end"]["character"] - r["start"]["character"] == 3  # 'add'


def test_references_excluding_declaration(client):
    _handshake(client)
    uri = "file:///tmp/refs2.agk"
    _open(client, uri, REF_SRC)
    result = _references(client, uri, 5, 11, include_declaration=False)
    assert _starts(result) == [(4, 10), (5, 10)]


def test_references_of_shadowed_variable_are_scope_local(client):
    _handshake(client)
    uri = "file:///tmp/refs3.agk"
    _open(client, uri, RENAME_SRC)
    # x in `first` (use at line 2, char 8)
    result = _references(client, uri, 2, 8)
    assert _starts(result) == [(1, 11), (2, 8), (3, 10)]
    # x in `second` (use at line 7, char 8)
    result = _references(client, uri, 7, 8)
    assert _starts(result) == [(6, 11), (7, 8), (8, 10)]


def test_references_of_parameter(client):
    _handshake(client)
    uri = "file:///tmp/refs4.agk"
    _open(client, uri, REF_SRC)
    # parameter `a` (use at line 1, char 11: `return a + b`)
    result = _references(client, uri, 1, 11)
    assert _starts(result) == [(0, 31), (1, 11)]
    # parameter `b` must not leak in
    labels = {(l["range"]["start"]["line"], l["range"]["start"]["character"])
              for l in result}
    assert (1, 15) not in labels


def test_references_unknown_word_is_empty(client):
    _handshake(client)
    uri = "file:///tmp/refs5.agk"
    _open(client, uri, REF_SRC)
    result = _references(client, uri, 4, 6)  # `print` builtin
    assert result == []


# -- document symbols ----------------------------------------------------


def _symbols(client, uri):
    msg_id = client.request("textDocument/documentSymbol", {
        "textDocument": {"uri": uri},
    })
    resp = client.recv()
    assert resp["id"] == msg_id
    return resp["result"]


def test_document_symbol_outline(client):
    _handshake(client)
    uri = "file:///tmp/symbols.agk"
    _open(client, uri, SYMBOL_SRC)
    syms = _symbols(client, uri)
    by_name = {s["name"]: s for s in syms}
    assert set(by_name) == {"PI", "circle_area", "Account", "main"}

    pi = by_name["PI"]
    assert pi["kind"] == 14  # Constant
    assert pi["range"]["start"] == {"line": 0, "character": 16}
    assert pi["range"]["end"]["line"] == 0

    area = by_name["circle_area"]
    assert area["kind"] == 12  # Function
    assert area["range"]["start"]["line"] == 2
    assert area["range"]["end"]["line"] == 3
    assert area["selectionRange"]["start"] == {"line": 2, "character": 16}
    assert [c["name"] for c in area["children"]] == ["r"]
    assert area["children"][0]["kind"] == 13  # Variable

    acct = by_name["Account"]
    assert acct["kind"] == 5  # Class
    assert acct["range"]["start"]["line"] == 5
    assert acct["range"]["end"]["line"] == 10
    kids = {c["name"]: c for c in acct["children"]}
    assert kids["balance"]["kind"] == 8  # Field
    assert kids["constructor"]["kind"] == 9  # Constructor
    assert [p["name"] for p in kids["constructor"]["children"]] == ["initial"]
    assert kids["deposit"]["kind"] == 6  # Method
    assert [p["name"] for p in kids["deposit"]["children"]] == ["amount"]

    main = by_name["main"]
    assert main["kind"] == 12
    assert main["range"]["start"]["line"] == 12
    assert main["range"]["end"]["line"] == 14
    assert main["children"] == []


def test_document_symbol_broken_file_is_empty(client):
    _handshake(client)
    uri = "file:///tmp/symbolsbroken.agk"
    _open(client, uri, "define function oops(:\n")
    assert _symbols(client, uri) == []


def test_shutdown_and_exit(client):
    _handshake(client)
    msg_id = client.request("shutdown", None)
    resp = client.recv()
    assert resp["id"] == msg_id
    assert resp["result"] is None
    client.notify("exit", None)
    assert client.proc.wait(timeout=10) == 0
