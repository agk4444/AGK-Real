# Standard library

Twelve `.agk` modules ship with the compiler (in `agk/stdlib/`). Import one by name — `import strutils` — and it is compiled and inlined into your program: its functions become directly callable, no install step, no extra files. Every signature below is taken from the real module source, and every example is compile-and-run verified.

**Modules**

- [[strutils|Stdlib-Reference#strutils]]
- [[listutils|Stdlib-Reference#listutils]]
- [[fileutils|Stdlib-Reference#fileutils]]
- [[jsonutils|Stdlib-Reference#jsonutils]]
- [[httputils|Stdlib-Reference#httputils]]
- [[dateutils|Stdlib-Reference#dateutils]]
- [[csvutils|Stdlib-Reference#csvutils]]
- [[regexutils|Stdlib-Reference#regexutils]]
- [[sqliteutils|Stdlib-Reference#sqliteutils]]
- [[crypto|Stdlib-Reference#crypto]]
- [[graphics|Stdlib-Reference#graphics]]
- [[agent|Stdlib-Reference#agent]]
- [[Writing your own module|Stdlib-Reference#writing-your-own-module]]

Bigger end-to-end programs live on the [[Library cookbook|Library-Cookbook]] page: a password-hashing CLI, a generative-art PNG, and a tool-using agent with a mocked LLM.

## strutils

String helpers. **[stable]**

- `shout(s as String) -> String` — uppercase plus `!`
- `repeat_string(s as String, n as Integer) -> String` — `s` repeated `n` times
- `join_lines(lines as List) -> String` — lines joined with newlines (trailing newline included)
- `slug(s as String) -> String` — lowercase with spaces replaced by `-`

<!-- verify: id=stdlib-strutils output="HELLO!\nababab\na\nb\n\nhello-world\n" -->
```agk
import strutils

define function main:
    print(shout("hello"))
    print(repeat_string("ab", 3))
    print(join_lines(["a", "b"]))
    print(slug("Hello World"))
```

<!-- verify: id=stdlib-strutils-2 output="my-first-post!\n*-*-*-*-\n" -->
```agk
import strutils

define function main:
    print(slug("My First Post!"))
    print(repeat_string("*-", 4))
```

## listutils

List helpers. **[stable]**

- `sum_list(xs as List) -> Integer` — sum of elements
- `max_in_list(xs as List) -> Integer` — largest element
- `min_in_list(xs as List) -> Integer` — smallest element
- `contains_int(xs as List, item as Integer) -> Boolean` — true if `item` is in `xs`

<!-- verify: id=stdlib-listutils output="6\n3\n1\nTrue\nFalse\n" -->
```agk
import listutils

define function main:
    print(sum_list([1, 2, 3]))
    print(max_in_list([3, 1, 2]))
    print(min_in_list([3, 1, 2]))
    print(contains_int([1, 2], 2))
    print(contains_int([1, 2], 9))
```

<!-- verify: id=stdlib-listutils-2 output="28\nTrue\n" -->
```agk
import listutils

define function main:
    create xs as List
    set xs to [5, 1, 9, 3]
    print(sum_list(xs) + max_in_list(xs) + min_in_list(xs))
    print(contains_int(xs, 9) and not contains_int(xs, 7))
```

## fileutils

File utilities (wraps Python's `open` / `os`).

- `read_text(path as String) -> String` — whole file contents
- `write_text(path as String, text as String)` — overwrite (or create) the file
- `append_text(path as String, text as String)` — append to the file
- `file_exists(path as String) -> Boolean`
- `list_dir(path as String) -> List` — names in the directory

<!-- verify: id=stdlib-fileutils output="hello again\nTrue\nFalse\n['demo.txt']\n" -->
```agk
import fileutils

define function main:
    write_text("demo.txt", "hello")
    append_text("demo.txt", " again")
    print(read_text("demo.txt"))
    print(file_exists("demo.txt"))
    print(file_exists("nope.txt"))
    print(list_dir("."))
```

<!-- verify: id=stdlib-fileutils-2 output="line one\nline two\n" -->
```agk
import fileutils

define function main:
    write_text("log.txt", "line one\n")
    append_text("log.txt", "line two")
    print(read_text("log.txt"))
```

## jsonutils

JSON parsing and serialisation (wraps Python's `json`).

- `parse_json(s as String) -> Object` — parse JSON text into lists/dicts
- `to_json(value as Object) -> String` — serialise a value to JSON text

<!-- verify: id=stdlib-jsonutils output='1\n{"a": 1}\n' -->
```agk
import jsonutils

define function main:
    create obj as Object
    set obj to parse_json("{{\"a\": 1}}")
    print(obj["a"])
    print(to_json(obj))
```

<!-- verify: id=stdlib-jsonutils-2 output="amy\n['a', 'b']\n{\"ok\": true}\n" -->
```agk
import jsonutils

define function main:
    create users as Object
    set users to parse_json("[{{\"name\": \"amy\", \"tags\": [\"a\", \"b\"]}}]")
    print(users[0]["name"])
    print(users[0]["tags"])
    print(to_json({"ok": true}))
```

## httputils

HTTP utilities (wraps `urllib.request`).

- `http_get(url as String) -> String` — response body as a String

<!-- verify: id=stdlib-httputils server="static:hello from the test server" output="hello from the test server\n" -->
```agk
import httputils

define function main:
    print(http_get("http://127.0.0.1:{{PORT}}/"))
```

<!-- verify: id=stdlib-httputils-json server='static:{"ok": true, "n": 3}' output="True\n4\n" -->
```agk
import httputils
import jsonutils

define function main:
    create data as Object
    set data to parse_json(http_get("http://127.0.0.1:{{PORT}}/"))
    print(data["ok"])
    print(data["n"] + 1)
```

> [!NOTE]
> The examples above are verified against a local test server; point `http_get` at any real URL in your own programs.

## dateutils

Date utilities. Dates are `"YYYY-MM-DD"` strings.

- `today() -> String` — today's date as `"YYYY-MM-DD"`
- `now() -> String` — current datetime as an ISO string
- `add_days(date_str as String, days as Integer) -> String` — date shifted by `days`

<!-- verify: id=stdlib-dateutils-add output="2026-01-08\n" -->
```agk
import dateutils

define function main:
    print(add_days("2026-01-01", 7))
```

<!-- verify: id=stdlib-dateutils-today output-regex="^\\d{4}-\\d{2}-\\d{2}\n$" -->
```agk
import dateutils

define function main:
    print(today())
```

<!-- verify: id=stdlib-dateutils-now output-regex="^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}" -->
```agk
import dateutils

define function main:
    print(now())
```

## csvutils

CSV utilities (wraps Python's `csv`). Round-trip safe.

- `csv_parse(text as String) -> List` — List of rows, each a List of strings
- `csv_to_text(rows as List) -> String` — rows back to CSV text

<!-- verify: id=stdlib-csvutils output="[['name', 'age'], ['Amy', '30']]\nTrue\n" -->
```agk
import csvutils

define function main:
    create rows as List
    set rows to csv_parse("name,age\nAmy,30")
    print(rows)
    print(csv_parse(csv_to_text(rows)) == rows)
```

<!-- verify: id=stdlib-csvutils-quoting output="True\na,b\n" -->
```agk
import csvutils

define function main:
    create rows as List
    set rows to [["a,b", "c"], ["d", "e"]]
    print(csv_parse(csv_to_text(rows)) == rows)
    print(csv_parse(csv_to_text(rows))[0][0])
```

## regexutils

Regular-expression utilities (wraps Python's `re`). Note the doubled backslashes in patterns: `"\\d+"` is the two-character string `\d+` by the time `re` sees it.

- `regex_match(pattern as String, text as String) -> Boolean` — true if the pattern is found anywhere in the text
- `regex_find_all(pattern as String, text as String) -> List` — all matches
- `regex_replace(pattern as String, replacement as String, text as String) -> String`
- `regex_split(pattern as String, text as String) -> List`

<!-- verify: id=stdlib-regexutils output="True\n['1', '22']\na-b-c\n['a', 'b', 'c']\n" -->
```agk
import regexutils

define function main:
    print(regex_match("\\d+", "abc123"))
    print(regex_find_all("\\d+", "a1b22"))
    print(regex_replace("\\s+", "-", "a b  c"))
    print(regex_split(",", "a,b,c"))
```

<!-- verify: id=stdlib-regexutils-2 output="['the', 'quick', 'brown', 'fox']\n5\n" -->
```agk
import regexutils

define function main:
    print(regex_split("\\s+", "the quick brown fox"))
    print(len(regex_find_all("[aeiou]", "the quick brown fox")))
```

## sqliteutils

SQLite helpers. Deliberately stateless: every call opens the database, runs its statement, commits (for writes), and closes the connection — no connection to manage.

- `db_execute(db_path as String, sql as String) -> String` — executes the statement and commits; returns `"ok"`
- `db_query(db_path as String, sql as String) -> List` — rows, each a List of values

<!-- verify: id=stdlib-sqliteutils output="[['amy', 30]]\n" -->
```agk
import sqliteutils

define function main:
    db_execute("demo.db", "CREATE TABLE t (name TEXT, n INT)")
    db_execute("demo.db", "INSERT INTO t VALUES ('amy', 30)")
    print(db_query("demo.db", "SELECT * FROM t"))
```

<!-- verify: id=stdlib-sqliteutils-2 output="[['milk'], ['bread']]\n" -->
```agk
import sqliteutils

define function main:
    db_execute("shop.db", "CREATE TABLE items (name TEXT, price INT)")
    db_execute("shop.db", "INSERT INTO items VALUES ('apple', 3)")
    db_execute("shop.db", "INSERT INTO items VALUES ('bread', 5)")
    db_execute("shop.db", "INSERT INTO items VALUES ('milk', 4)")
    print(db_query("shop.db", "SELECT name FROM items WHERE price > 3 ORDER BY price"))
```

## crypto

Hashing, message authentication and encoding helpers (wraps Python's `hashlib` / `hmac` / `base64` / `secrets`). Hashing and authentication only — no public-key encryption.

- `sha256(s as String) -> String` — hex digest
- `sha512(s as String) -> String` — hex digest
- `sha1(s as String) -> String` — hex digest
- `md5(s as String) -> String` — hex digest
- `hmac_sha256(key as String, message as String) -> String` — hex digest
- `pbkdf2_hex(password as String, salt as String, iterations as Integer) -> String` — PBKDF2-HMAC-SHA256 hex digest
- `base64_encode(s as String) -> String`
- `base64_decode(s as String) -> String` — raises a clean error on invalid input
- `token_hex(nbytes as Integer) -> String` — `2*nbytes` secure random hex chars
- `compare_digest(a as String, b as String) -> Boolean` — constant-time comparison

<!-- verify: id=stdlib-crypto output="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad\nf7bc83f430538424b13298e6aa6fb143ef4d59a14946175997479dbc2d1a3cd8\naGVsbG8sIGFnaw==\n" -->
```agk
import crypto

define function main:
    print(sha256("abc"))
    print(hmac_sha256("key", "The quick brown fox jumps over the lazy dog"))
    print(base64_encode("hello, agk"))
```

<!-- verify: id=stdlib-crypto-2 output="120fb6cffcf8b32c43e7225256c4f837a86548c92ccc35480805987cb70be17b\n32\nTrue\nround trip\n" -->
```agk
import crypto

define function main:
    print(pbkdf2_hex("password", "salt", 1))
    print(len(token_hex(16)))
    print(compare_digest(sha256("abc"), sha256("abc")))
    print(base64_decode(base64_encode("round trip")))
```

<!-- verify: id=stdlib-crypto-error error="crypto.base64_decode: input is not valid base64" -->
```agk
import crypto

define function main:
    print(base64_decode("!!! not base64 !!!"))
```

A full password-hashing CLI built on `crypto` is on the [[Library cookbook|Library-Cookbook]] page.

## graphics

A tiny software rasterizer: draw on an in-memory canvas and save it as a real PNG. Pure standard library (`struct` + `zlib`) — no display, no windowing, no third-party packages. A canvas is a Dict with `width`, `height` and a flat row-major `pixels` list of `[r, g, b]` colors. Colors are `[r, g, b]` lists (0-255 per channel; out-of-range values are clamped) or `"#rrggbb"` strings. All drawing is clipped to the canvas bounds.

- `new(width as Integer, height as Integer, bg as Object) -> Object` — new canvas filled with `bg`
- `pixel(canvas as Object, x as Integer, y as Integer, color as Object) -> Object` — set one pixel (out-of-bounds is silently skipped)
- `get_pixel(canvas as Object, x as Integer, y as Integer) -> Object` — `[r, g, b]` at a point
- `line(canvas as Object, x1 as Integer, y1 as Integer, x2 as Integer, y2 as Integer, color as Object) -> Object` — Bresenham line
- `rect(canvas as Object, x as Integer, y as Integer, w as Integer, h as Integer, color as Object, fill as Boolean = true) -> Object`
- `circle(canvas as Object, cx as Integer, cy as Integer, r as Integer, color as Object, fill as Boolean = true) -> Object` — midpoint circle
- `save_png(canvas as Object, path as String) -> String` — writes a real PNG file, returns the path

<!-- verify: id=stdlib-graphics output="[233, 69, 96]\n[0, 255, 0]\n" -->
```agk
import graphics

define function main:
    create c as Object
    set c to new(16, 12, "#1a1a2e")
    line(c, 0, 0, 15, 11, "#e94560")
    rect(c, 2, 2, 5, 4, [0, 255, 0], false)
    print(get_pixel(c, 0, 0))
    print(get_pixel(c, 2, 2))
```

<!-- verify: id=stdlib-graphics-save output="badge.png\nTrue\n" -->
```agk
import graphics
import fileutils

define function main:
    create c as Object
    set c to new(32, 24, "#0d1117")
    circle(c, 16, 12, 8, "#e94560", true)
    rect(c, 0, 0, 32, 3, [255, 255, 255], true)
    print(save_png(c, "badge.png"))
    print(file_exists("badge.png"))
```

<!-- verify: id=stdlib-graphics-error error="graphics: color string must look like" -->
```agk
import graphics

define function main:
    create c as Object
    set c to new(8, 8, "nope")
```

A generative-art program that paints a whole canvas pixel by pixel is on the [[Library cookbook|Library-Cookbook]] page.

## agent

LLM-backed helpers over any OpenAI-compatible `/chat/completions` endpoint, using only the standard library (`urllib`). **Requires an API key and network access**: set the `AGK_LLM_API_KEY` environment variable or pass `api_key="..."`; the endpoint defaults to `https://api.openai.com/v1` and can be overridden with `AGK_LLM_BASE_URL` or `base_url="..."`. The examples below run offline against a local mock server that imitates the API's JSON shape.

- `chat(messages as List, model as String = "gpt-4o-mini", api_key as String = "", base_url as String = "", timeout as Integer = 30) -> String` — `messages` is a List of `{"role": ..., "content": ...}` dicts; returns the assistant's reply text. Raises a clean error when the key is missing or the request fails.
- `react(goal as String, tools as Dict, max_steps as Integer = 8, model as String = "gpt-4o-mini", api_key as String = "", base_url as String = "") -> Object` — a ReAct loop: `tools` maps names to callables taking an args Dict. The model replies with either `{"tool": name, "args": {...}}` or `{"answer": ...}`; tool results are fed back as observations. Returns `{"answer": ..., "steps": [...], "done": ..., "goal": ...}`. Malformed model output triggers a retry prompt; unknown tools and tool errors are handled gracefully; the loop always stops after `max_steps`.

`chat` against a mocked endpoint — the mock returns the exact JSON shape a real `/chat/completions` endpoint would:

<!-- verify: id=stdlib-agent-chat server='static:{"choices": [{"message": {"content": "The capital of France is Paris."}}]}' output="The capital of France is Paris.\n" -->
```agk
import agent

define function main:
    create reply as String
    set reply to chat([{"role": "user", "content": "Capital of France?"}], "gpt-4o-mini", "fake-key", "http://127.0.0.1:{{PORT}}")
    print(reply)
```

`react` where the model answers immediately (no tools needed):

<!-- verify: id=stdlib-agent-react-answer server='static:{"choices": [{"message": {"content": "{\"answer\": \"42\"}"}}]}' output="{'answer': '42', 'steps': [], 'done': True, 'goal': 'What is 6 times 7?'}\n" -->
```agk
import agent

define function main:
    create result as Object
    set result to react("What is 6 times 7?", {}, 3, "gpt-4o-mini", "fake-key", "http://127.0.0.1:{{PORT}}")
    print(result)
```

`react` calling a real tool. The mock answers the first request with a tool call and the second with the final answer (`server="seq:A|||B"` serves A first, then B):

<!-- verify: id=stdlib-agent-react-tools server='seq:{"choices": [{"message": {"content": "{\"tool\": \"add\", \"args\": {\"a\": 20, \"b\": 22}}"}}]}|||{"choices": [{"message": {"content": "{\"answer\": \"20 + 22 is 42.\"}"}}]}' output="20 + 22 is 42.\nTrue\n[{'step': 1, 'tool': 'add', 'args': {'a': 20, 'b': 22}, 'observation': '42'}]\n" -->
```agk
import agent

define function add that takes args as Object and returns Object:
    return args["a"] + args["b"]

define function main:
    create result as Object
    set result to react("Add 20 and 22.", {"add": add}, 5, "gpt-4o-mini", "fake-key", "http://127.0.0.1:{{PORT}}")
    print(result["answer"])
    print(result["done"])
    print(result["steps"])
```

A failed request raises a clean error, never a traceback:

<!-- verify: id=stdlib-agent-error error="agent.chat: request to" -->
```agk
import agent

define function main:
    print(chat([{"role": "user", "content": "hi"}], "gpt-4o-mini", "k", "http://127.0.0.1:1"))
```

And `react` with `max_steps=0` makes no model call at all, so it runs anywhere:

<!-- verify: id=stdlib-agent output="{'answer': '', 'steps': [], 'done': False, 'goal': 'Say hi'}\n" -->
```agk
import agent

define function main:
    # max_steps=0: no model call is made, so this runs offline.
    create result as Object
    set result to react("Say hi", {}, 0, "gpt-4o-mini", "k", "http://llm.test")
    print(result)
```

## Writing your own module

Put `helpers.agk` next to your program and write `import helpers` — it is compiled and inlined just like the bundled modules, and you call its functions by bare name.
