#!/usr/bin/env python3
"""Verify every annotated AGK example block in the wiki Markdown pages.

An example is a fenced ```agk block immediately preceded by a verification
comment:

    <!-- verify: id=tutorial-hello output="hello, agk\n" -->
    ```agk
    define function main:
        print("hello, agk")
    ```

Comment attributes (shlex syntax, quotes allowed):

  id=NAME               example identifier (for reporting)
  output="..."          exact stdout match ("\\n" in the attribute = newline)
  output-regex="..."    stdout must match this regex (re.DOTALL)
  error="substring"     compile/run must FAIL, error message contains substring
  compile-only          compiles (run_source) but stdout is ignored
  args="a b c"          extra argv[1:] while running
  server="static:TXT"   spin up a local HTTP server serving TXT at /,
                        replace {{PORT}} in the source with its port
  server="seq:A|||B"    like static:, but serve payload A to the first
                        request, B to the second, and repeat the last
                        payload for further requests. The server answers
                        both GET and POST (so it can mock JSON APIs).

Fenced blocks WITHOUT a verify comment are ignored: 0.4.0 preview sketches
(not yet compilable), shell/REPL transcripts, and error demos are not AGK
source and are deliberately excluded.

Each example runs in a fresh temp dir as CWD. Exit 0 = all green.
Usage: python verify_examples.py [wiki_dir]
"""

import io
import os
import re
import shlex
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

WIKI = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else
                       os.path.join(os.path.dirname(__file__), ".."))
# AGK_ROOT_DIR env override lets verification run against a pristine
# checkout (e.g. git HEAD) when the working tree is mid-flight.
AGK_ROOT = os.path.abspath(os.environ.get("AGK_ROOT_DIR",
                                           os.path.dirname(WIKI)))
sys.path.insert(0, AGK_ROOT)

from agk.pipeline import run_source  # noqa: E402
from agk.errors import AGKError  # noqa: E402

BLOCK_RE = re.compile(
    r'^[ \t]*<!--\s*verify:\s*(.*?)\s*-->[ \t]*\n'
    r'^[ \t]*```agk[ \t]*\n(.*?)^[ \t]*```[ \t]*$',
    re.DOTALL | re.MULTILINE)


def decode_output(value):
    return value.replace("\\n", "\n")


def extract_examples(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    examples = []
    for i, m in enumerate(BLOCK_RE.finditer(text)):
        attrs = {}
        for token in shlex.split(m.group(1)):
            if "=" in token:
                k, _, v = token.partition("=")
                attrs[k] = v
            else:
                attrs[token] = True
        code = m.group(2).strip("\n")
        code = "\n".join(line.rstrip() for line in code.split("\n"))
        examples.append({"id": attrs.get("id", f"example-{i}"),
                         "code": code, "attrs": attrs,
                         "page": os.path.basename(path)})
    return examples


class _StaticHandler(BaseHTTPRequestHandler):
    payloads = [b""]
    payload_idx = [0]

    def _serve(self):
        n = _StaticHandler.payload_idx[0]
        _StaticHandler.payload_idx[0] = n + 1
        body = _StaticHandler.payloads[min(n, len(_StaticHandler.payloads) - 1)]
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._serve()

    def do_POST(self):
        self._serve()

    def log_message(self, *args):
        pass


def with_local_server(payloads, fn):
    _StaticHandler.payloads = [p.encode() for p in payloads]
    _StaticHandler.payload_idx = [0]
    server = HTTPServer(("127.0.0.1", 0), _StaticHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        return fn(port)
    finally:
        server.shutdown()
        thread.join()


def run_example(ex):
    attrs = ex["attrs"]
    tmpdir = tempfile.mkdtemp(prefix="wiki_ex_")
    old_cwd, old_argv = os.getcwd(), sys.argv[:]
    try:
        os.chdir(tmpdir)
        src = ex["code"]
        server_spec = attrs.get("server")
        if server_spec:
            if server_spec.startswith("seq:"):
                payloads = server_spec[len("seq:"):].split("|||")
            elif server_spec.startswith("static:"):
                payloads = [server_spec[len("static:"):]]
            else:
                payloads = None

            if payloads is not None:
                def _run(port):
                    return run_source(src.replace("{{PORT}}", str(port)),
                                      filename=ex["page"])
                if attrs.get("args"):
                    sys.argv = ["prog.agk"] + attrs["args"].split()
                try:
                    out, _ns, _w = with_local_server(payloads, _run)
                finally:
                    sys.argv = old_argv
                return out, None
            # Unknown server spec: fall through to a plain run.
        if attrs.get("args"):
            sys.argv = ["prog.agk"] + attrs["args"].split()
        try:
            out, _ns, _w = run_source(src, filename=ex["page"])
        finally:
            sys.argv = old_argv
        return out, None
    except Exception as e:  # noqa: BLE001 - we report, not swallow: returned below
        return None, e
    finally:
        os.chdir(old_cwd)
        sys.argv = old_argv
        for root, dirs, files in os.walk(tmpdir, topdown=False):
            for n in files:
                os.unlink(os.path.join(root, n))
            for n in dirs:
                os.rmdir(os.path.join(root, n))
        os.rmdir(tmpdir)


def check_example(ex):
    attrs = ex["attrs"]
    out, err = run_example(ex)
    want_error = attrs.get("error")
    if want_error is not None:
        if err is None:
            return f"expected error containing {want_error!r}, but it ran fine"
        if want_error not in str(err):
            return (f"error mismatch:\n  expected substring: {want_error!r}\n"
                    f"  actual error: {str(err)[:300]!r}")
        return None
    if err is not None:
        return f"raised unexpectedly: {str(err)[:400]}"
    if "compile-only" in attrs:
        return None
    if "output-regex" in attrs:
        if not re.match(attrs["output-regex"], out or "", re.DOTALL):
            return (f"regex mismatch:\n  pattern: {attrs['output-regex']!r}\n"
                    f"  actual: {(out or '')[:300]!r}")
        return None
    if "output" in attrs:
        want = decode_output(attrs["output"])
        if (out or "") != want:
            return (f"output mismatch:\n  expected: {want!r}\n"
                    f"  actual:   {(out or '')!r}")
        return None
    return ("no expectation declared (add output=, output-regex=, error=, "
            "or compile-only)")


def main():
    pages = sorted(f for f in os.listdir(WIKI) if f.endswith(".md"))
    if not pages:
        print("no .md pages found in", WIKI)
        return 2
    failures, total = [], 0
    for page in pages:
        for ex in extract_examples(os.path.join(WIKI, page)):
            total += 1
            problem = check_example(ex)
            status = "ok  " if problem is None else "FAIL"
            print(f"[{status}] {page} :: {ex['id']}")
            if problem:
                failures.append((page, ex["id"], problem))
    print(f"\n{total - len(failures)}/{total} examples verified")
    for page, eid, problem in failures:
        print(f"\nFAIL {page} :: {eid}\n  {problem}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
