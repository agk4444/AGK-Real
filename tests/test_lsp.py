"""End-to-end tests for agk/lsp.py: drive the language server as a
subprocess over stdio with Content-Length framing."""

import json
import os
import select
import subprocess
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GOOD_SRC = """\
define constant PI as Float = 3.14159

define function greet that takes name as String:
    create msg as String
    set msg to "hi {name}"
    print(msg)

define function main:
    greet("world")
    print(PI)
"""

BAD_SRC = """\
define function greet that takes name as String:
    create msg as String
    set msg to "hi {name}"
    print(msg)
    set bogus to 1
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


@pytest.fixture()
def client():
    c = LSPClient()
    yield c
    c.close()


def handshake(c):
    msg_id = c.request("initialize", {"processId": None,
                                      "capabilities": {}})
    resp = c.recv()
    assert resp["id"] == msg_id
    c.notify("initialized", {})
    return resp["result"]


def test_initialize_capabilities(client):
    result = handshake(client)
    caps = result["capabilities"]
    assert caps["textDocumentSync"] == 1
    assert caps["hoverProvider"] is True
    assert caps["definitionProvider"] is True


def test_did_open_clean_file_has_no_diagnostics(client):
    handshake(client)
    client.did_open("file:///tmp/clean.agk", GOOD_SRC)
    notif = client.recv()
    assert notif["method"] == "textDocument/publishDiagnostics"
    assert notif["params"]["uri"] == "file:///tmp/clean.agk"
    assert notif["params"]["diagnostics"] == []


def test_did_open_bad_file_publishes_error_diagnostic(client):
    handshake(client)
    client.did_open("file:///tmp/bad.agk", BAD_SRC)
    notif = client.recv()
    assert notif["method"] == "textDocument/publishDiagnostics"
    diags = notif["params"]["diagnostics"]
    assert len(diags) == 1
    d = diags[0]
    assert d["severity"] == 1  # Error
    assert d["source"] == "agk-lsp"
    assert "bogus" in d["message"]
    # `set bogus to 1` is AGK line 5 -> LSP line 4
    assert d["range"]["start"]["line"] == 4


def test_did_change_updates_diagnostics(client):
    handshake(client)
    uri = "file:///tmp/changing.agk"
    client.did_open(uri, BAD_SRC)
    notif = client.recv()
    assert len(notif["params"]["diagnostics"]) == 1
    client.notify("textDocument/didChange", {
        "textDocument": {"uri": uri, "version": 2},
        "contentChanges": [{"text": GOOD_SRC}],
    })
    notif = client.recv()
    assert notif["method"] == "textDocument/publishDiagnostics"
    assert notif["params"]["diagnostics"] == []


def test_hover_function(client):
    handshake(client)
    uri = "file:///tmp/hover.agk"
    client.did_open(uri, GOOD_SRC)
    client.recv()  # diagnostics
    msg_id = client.request("textDocument/hover", {
        "textDocument": {"uri": uri},
        # 'greet' on the `define function greet ...` line (LSP line 2)
        "position": {"line": 2, "character": 18},
    })
    resp = client.recv()
    assert resp["id"] == msg_id
    value = resp["result"]["contents"]["value"]
    assert "function" in value
    assert "greet" in value


def test_hover_variable(client):
    handshake(client)
    uri = "file:///tmp/hovervar.agk"
    client.did_open(uri, GOOD_SRC)
    client.recv()  # diagnostics
    msg_id = client.request("textDocument/hover", {
        "textDocument": {"uri": uri},
        # 'msg' in `set msg to "hi {name}"` (LSP line 4)
        "position": {"line": 4, "character": 9},
    })
    resp = client.recv()
    value = resp["result"]["contents"]["value"]
    assert "variable" in value
    assert "msg" in value


def test_definition_function(client):
    handshake(client)
    uri = "file:///tmp/def.agk"
    client.did_open(uri, GOOD_SRC)
    client.recv()  # diagnostics
    msg_id = client.request("textDocument/definition", {
        "textDocument": {"uri": uri},
        # 'greet' where it is called in main (LSP line 8)
        "position": {"line": 8, "character": 6},
    })
    resp = client.recv()
    assert resp["id"] == msg_id
    loc = resp["result"]
    assert loc["uri"] == uri
    # definition is the `define function greet` line -> LSP line 2
    assert loc["range"]["start"]["line"] == 2
    assert loc["range"]["start"]["character"] == 16  # 'greet' starts here


def test_unknown_word_hover_returns_null(client):
    handshake(client)
    uri = "file:///tmp/nullhover.agk"
    client.did_open(uri, GOOD_SRC)
    client.recv()  # diagnostics
    msg_id = client.request("textDocument/hover", {
        "textDocument": {"uri": uri},
        # 'print' is a builtin, not a defined symbol
        "position": {"line": 5, "character": 6},
    })
    resp = client.recv()
    assert resp["id"] == msg_id
    assert resp["result"] is None


def test_shutdown_and_exit(client):
    handshake(client)
    msg_id = client.request("shutdown", None)
    resp = client.recv()
    assert resp["id"] == msg_id
    assert resp["result"] is None
    client.notify("exit", None)
    assert client.proc.wait(timeout=10) == 0
