# Standard library

Twenty-seven `.agk` modules ship with the compiler (in `agk/stdlib/`). Import one by name — `import strutils` — and it is compiled and inlined into your program: its functions become directly callable, no install step, no extra files. Every signature below is taken from the real module source, and every example is compile-and-run verified.

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
- [[mathutils|Stdlib-Reference#mathutils]]
- [[randutils|Stdlib-Reference#randutils]]
- [[timeutils|Stdlib-Reference#timeutils]]
- [[sysutils|Stdlib-Reference#sysutils]]
- [[pathutils|Stdlib-Reference#pathutils]]
- [[urlutils|Stdlib-Reference#urlutils]]
- [[uuidutils|Stdlib-Reference#uuidutils]]
- [[ziputils|Stdlib-Reference#ziputils]]
- [[iniutils|Stdlib-Reference#iniutils]]
- [[htmlutils|Stdlib-Reference#htmlutils]]
- [[xmlutils|Stdlib-Reference#xmlutils]]
- [[statutils|Stdlib-Reference#statutils]]
- [[iterutils|Stdlib-Reference#iterutils]]
- [[colorutils|Stdlib-Reference#colorutils]]
- [[logutils|Stdlib-Reference#logutils]]
- [[transformers|Stdlib-Reference#transformers]]
- [[tokenizer|Stdlib-Reference#tokenizer]]
- [[torchutils|Stdlib-Reference#torchutils]]
- [[datasets|Stdlib-Reference#datasets]]
- [[embeddings|Stdlib-Reference#embeddings]]
- [[finetune|Stdlib-Reference#finetune]]
- [[tensor|Stdlib-Reference#tensor]]
- [[infer|Stdlib-Reference#infer]]
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

## mathutils

Math helpers. **[stable]**

- `pi_value() -> Float` — π
- `e_value() -> Float` — e
- `sqrt_of(x as Float) -> Float` — square root (errors on negatives)
- `floor_of(x as Float) -> Integer`, `ceil_of(x as Float) -> Integer`
- `round_to(x as Float, n as Integer) -> Float` — round to `n` decimals
- `sin_of(x)`, `cos_of(x)`, `tan_of(x) -> Float` — radians
- `ln(x)`, `log10_of(x)`, `log_base(x, base) -> Float`
- `exp_of(x)`, `power(x, y) -> Float`
- `gcd_of(a, b as Integer) -> Integer`
- `factorial_of(n as Integer) -> Integer`
- `to_radians(deg)`, `to_degrees(rad) -> Float`
- `is_close(a, b as Float) -> Boolean`
- `hypot_of(x, y as Float) -> Float` — √(x² + y²)

<!-- verify: id=stdlib-mathutils output="1.4142135623730951\n3\n6\n120\n1024.0\n" -->
```agk
import mathutils

define function main:
    print(sqrt_of(2.0))
    print(floor_of(3.7))
    print(gcd_of(12, 18))
    print(factorial_of(5))
    print(power(2.0, 10.0))
```

## randutils

Random numbers. **[stable]**

Call `seed(n)` first for reproducible results.

- `seed(n as Integer)` — seed the generator
- `randint_between(a, b as Integer) -> Integer` — inclusive on both ends
- `randfloat() -> Float` — in [0.0, 1.0)
- `randfloat_between(a, b as Float) -> Float`
- `choice_of(xs as List)` — one random element (errors on empty lists)
- `shuffle_list(xs as List) -> List` — shuffled in place, returned
- `sample_of(xs as List, k as Integer) -> List` — `k` unique elements

<!-- verify: id=stdlib-randutils output="True\n7\n" -->
```agk
import randutils

define function main:
    seed(42)
    create a as Integer
    set a to randint_between(1, 100)
    seed(42)
    print(randint_between(1, 100) == a)
    print(choice_of([7]))
```

## timeutils

Clocks and sleeping. **[stable]**

- `sleep_seconds(s as Float)` — pause the program
- `epoch_seconds() -> Float` — Unix timestamp
- `monotonic_seconds() -> Float` — steady clock, good for timing
- `cpu_seconds() -> Float` — CPU time used by the process
- `format_epoch(ts as Float) -> String` — `"YYYY-MM-DD HH:MM:SS"`

<!-- verify: id=stdlib-timeutils output="True\nTrue\n" -->
```agk
import timeutils

define function main:
    sleep_seconds(0.0)
    print(epoch_seconds() > 1000000000.0)
    print(monotonic_seconds() > 0.0)
```

## sysutils

Environment, arguments, and platform. **[stable]**

- `getenv(name as String) -> String` — `""` when unset
- `getenv_or(name, default as String) -> String`
- `setenv(name, value as String)` — set for this process
- `argv() -> List` — command-line arguments (not including the program name)
- `exit_with_code(n as Integer)` — stop the program with an exit code
- `platform_name() -> String` — e.g. `"Linux"`
- `python_version() -> String`
- `cwd() -> String` — current working directory
- `home_dir() -> String`
- `path_sep() -> String` — `"/"` on POSIX, `"\\"` on Windows

<!-- verify: id=stdlib-sysutils output="hi\nfallback\nTrue\n" -->
```agk
import sysutils

define function main:
    setenv("AGK_DEMO_VAR", "hi")
    print(getenv("AGK_DEMO_VAR"))
    print(getenv_or("AGK_NOPE_VAR", "fallback"))
    print(platform_name() != "")
```

## pathutils

File path manipulation (no disk access). **[stable]**

- `join_path(a, b as String) -> String`
- `base_name(p as String) -> String` — last component
- `dir_name(p as String) -> String` — everything but the last component
- `abs_path(p as String) -> String`
- `norm_path(p as String) -> String` — collapse `.`, `..`, doubled separators
- `file_extension(p as String) -> String` — e.g. `".gz"`
- `file_stem(p as String) -> String` — basename without extension
- `is_abs_path(p as String) -> Boolean`

<!-- verify: id=stdlib-pathutils output="docs/guide.md\nreport.csv\n.gz\nreport\na/b/c\n" -->
```agk
import pathutils

define function main:
    print(join_path("docs", "guide.md"))
    print(base_name("/tmp/x/report.csv"))
    print(file_extension("archive.tar.gz"))
    print(file_stem("/tmp/x/report.csv"))
    print(norm_path("a//b/./c"))
```

## urlutils

URL encoding and splitting. **[stable]**

- `url_encode(s as String) -> String` — percent-encode, e.g. for query values
- `url_decode(s as String) -> String`
- `url_join(base, url as String) -> String` — resolve a relative URL
- `url_parts(s as String) -> List` — `[scheme, host, path, query]`
- `url_scheme(s as String) -> String`
- `url_host(s as String) -> String`

<!-- verify: id=stdlib-urlutils output="hello%20world%21\na b\nexample.com:8080\n" -->
```agk
import urlutils

define function main:
    print(url_encode("hello world!"))
    print(url_decode("a%20b"))
    print(url_host("https://example.com:8080/p"))
```

## uuidutils

Universally unique identifiers. **[stable]**

- `uuid4_hex() -> String` — 32 random hex digits
- `uuid4_str() -> String` — canonical `"8-4-4-4-12"` form
- `uuid1_hex() -> String` — time-based, 32 hex digits

<!-- verify: id=stdlib-uuidutils output="True\nTrue\n" -->
```agk
import uuidutils

define function main:
    print(len(uuid4_hex()) == 32)
    print(len(uuid4_str()) == 36)
```

## ziputils

Compression and zip archives. **[stable]**

`gzip_compress` returns hex text so compressed bytes travel as an AGK `String`.

- `gzip_compress(s as String) -> String`
- `gzip_decompress(h as String) -> String`
- `zip_create(zip_path as String, files as List)` — archive files by path
- `zip_list(zip_path as String) -> List` — names in the archive
- `zip_read_text(zip_path, name as String) -> String`

<!-- verify: id=stdlib-ziputils output="hello, agk!\n" -->
```agk
import ziputils

define function main:
    create h as String
    set h to gzip_compress("hello, agk!")
    print(gzip_decompress(h))
```

## iniutils

Classic INI config files (`[section]` / `key = value`). **[stable]**

- `ini_get(path, section, key as String) -> String` — `""` when missing
- `ini_get_or(path, section, key, default as String) -> String`
- `ini_has(path, section, key as String) -> Boolean`
- `ini_has_section(path, section as String) -> Boolean`
- `ini_sections(path as String) -> List`
- `ini_keys(path, section as String) -> List`

<!-- verify: id=stdlib-iniutils output="example.com\nTrue\n['server']\n" -->
```agk
import fileutils
import iniutils

define function main:
    write_text("app.ini", "[server]\nhost = example.com\nport = 8080\n")
    print(ini_get("app.ini", "server", "host"))
    print(ini_has("app.ini", "server", "port"))
    print(ini_sections("app.ini"))
```

## htmlutils

HTML escaping. **[stable]**

- `html_escape(s as String) -> String` — `&`, `<`, `>`, quotes
- `html_unescape(s as String) -> String`

<!-- verify: id=stdlib-htmlutils output="&lt;b&gt;hi &amp; bye&lt;/b&gt;\n<3\n" -->
```agk
import htmlutils

define function main:
    print(html_escape("<b>hi & bye</b>"))
    print(html_unescape("&lt;3"))
```

## xmlutils

Tag lookup for small XML documents. **[stable]**

- `xml_root_tag(xml_text as String) -> String`
- `xml_find_texts(xml_text, tag as String) -> List` — text of every `<tag>`
- `xml_find_attr(xml_text, tag, attr as String) -> String` — first match's attribute, `""` when absent

<!-- verify: id=stdlib-xmlutils output="catalog\n['one', 'two']\n" -->
```agk
import xmlutils

define function main:
    create doc as String
    set doc to "<catalog><item>one</item><item>two</item></catalog>"
    print(xml_root_tag(doc))
    print(xml_find_texts(doc, "item"))
```

## statutils

Descriptive statistics over lists of numbers. **[stable]**

- `mean_of(xs as List) -> Float`
- `median_of(xs as List) -> Float`
- `stdev_of(xs as List) -> Float` — sample standard deviation
- `variance_of(xs as List) -> Float` — sample variance
- `mode_of(xs as List)` — most common value
- `min_max_of(xs as List) -> List` — `[min, max]`

<!-- verify: id=stdlib-statutils output="2.5\n2.5\n2\n" -->
```agk
import statutils

define function main:
    print(mean_of([1, 2, 3, 4]))
    print(median_of([1, 2, 3, 4]))
    print(mode_of([1, 2, 2, 3]))
```

## iterutils

Iteration helpers, written in pure AGK. **[stable]**

- `chunked(xs as List, n as Integer) -> List` — split into groups of `n`
- `flatten(xss as List) -> List` — one level
- `unique(xs as List) -> List` — deduplicate, order kept
- `pairwise(xs as List) -> List` — `[[a, b], [b, c], ...]`
- `zip_lists(a, b as List) -> List` — pairs, stops at the shorter list

<!-- verify: id=stdlib-iterutils output="[[1, 2], [3, 4], [5]]\n[1, 2, 3]\n[[1, 2], [2, 3]]\n" -->
```agk
import iterutils

define function main:
    print(chunked([1, 2, 3, 4, 5], 2))
    print(unique([1, 2, 1, 3, 2]))
    print(pairwise([1, 2, 3]))
```

## colorutils

ANSI terminal colors for CLI output. **[stable]**

Colors only render on ANSI-capable terminals; `strip_ansi` removes them again.

- `red(s)`, `green(s)`, `yellow(s)`, `blue(s)`, `magenta(s)`, `cyan(s)`, `bold(s) -> String`
- `strip_ansi(s as String) -> String`

<!-- verify: id=stdlib-colorutils output="hello\nTrue\n" -->
```agk
import colorutils

define function main:
    print(strip_ansi(red("hello")))
    print(red("hi") != "hi")
```

## logutils

Timestamped log lines appended to a file. **[stable]**

- `log_line(path, level, message as String)`
- `log_debug(path, message)`, `log_info(path, message)`, `log_warn(path, message)`, `log_error(path, message)`

<!-- verify: id=stdlib-logutils output="True\n" -->
```agk
import fileutils
import logutils
import regexutils

define function main:
    log_info("app.log", "started")
    create text as String
    set text to read_text("app.log")
    print(regex_match("INFO: started", text))
```

## transformers

HuggingFace transformers: text generation, classification, summarization, translation, fill-mask, question answering, zero-shot classification, embeddings, tokenization and model downloading. Requires `pip install transformers torch` (some tokenizers also need `pip install sentencepiece`). Importing this module never requires the packages — each function raises a clear `pip install ...` error only when its backend is missing. **[experimental]**

- `tf_generate(model as String, prompt as String, max_new_tokens as Integer = 20, temperature as Float = 0.0)` — greedy (`temperature 0.0`) or sampled generation. Runs as an explicit tokenize → forward → pick-next loop because AGK cannot pass keyword arguments to Python calls.
- `tf_generate_pipeline(model, prompt)` — one-shot `text-generation` pipeline with library defaults
- `tf_classify(model, text)` — sentiment pipeline, returns `{"label", "score"}`
- `tf_summarize(model, text)`, `tf_translate(model, text)` — pipelines, return the text
- `tf_fill_mask(model, text)` — top `token_str` for `[MASK]`
- `tf_answer(model, question, context)` — question-answering pipeline
- `tf_zero_shot(model, text, labels as List)` — top label
- `tf_embed(model, text)` — feature-extraction pipeline, mean-pooled to one vector
- `tf_encode(model, text)` / `tf_decode(model, ids)` — tokenizer round-trip
- `tf_download(model)` — `snapshot_download`, returns the local path

<!-- verify: id=stdlib-transformers-missing error="pip install transformers" -->
```agk
import transformers

define function main:
    print(tf_encode("gpt2", "hi"))
```

## tokenizer

Token counting, truncation and chunking for LLM prompts. The `tok_estimate` heuristic needs nothing; the `tok_*` functions need `pip install transformers`; the `tok_tiktoken_*` functions need `pip install tiktoken`. **[experimental]**

- `tok_estimate(text)` — dependency-free estimate: `len(text)/4 + 1`
- `tok_count(model, text)` — exact count with a HuggingFace tokenizer
- `tok_encode(model, text)` / `tok_decode(model, ids)`
- `tok_truncate(model, text, max_tokens)` — cut to a token budget, decode back
- `tok_chunks(model, text, max_tokens)` — split on blank lines, greedily pack paragraphs into token-budget chunks
- `tok_tiktoken_encode/decode/count(encoding_name, ...)` — OpenAI encodings like `"cl100k_base"`

<!-- verify: id=stdlib-tokenizer-estimate output="3\n" -->
```agk
import tokenizer

define function main:
    print(tok_estimate("hello world"))
```

<!-- verify: id=stdlib-tokenizer-missing error="pip install transformers" -->
```agk
import tokenizer

define function main:
    print(tok_count("gpt2", "hi"))
```

## torchutils

PyTorch tensor creation, math, softmax/argmax, seeding and save/load. Requires `pip install torch`. **[experimental]**

- `torch_version()`, `torch_cuda_available()`, `torch_device()` — `"cuda"` or `"cpu"`
- `torch_seed(seed)`, `torch_tensor(data)`, `torch_zeros(shape)`, `torch_ones(shape)`, `torch_rand(shape)`
- `torch_shape(t)`, `torch_to_list(t)`
- `torch_add/sub/mul(a, b)`, `torch_matmul(a, b)`, `torch_softmax(t, dim)`, `torch_argmax(t)`, `torch_sum(t)`, `torch_mean(t)`, `torch_norm(t)`
- `torch_save(t, path)`, `torch_load(path)`

<!-- verify: id=stdlib-torchutils-missing error="pip install torch" -->
```agk
import torchutils

define function main:
    print(torch_version())
```

## datasets

HuggingFace datasets: load, inspect, slice, shuffle, split, build, save and reload. Requires `pip install datasets`. **[experimental]**

- `ds_load(name, split = "train")`, `ds_load_config(name, config, split = "train")`
- `ds_len(ds)`, `ds_row(ds, i)`, `ds_column(ds, name)`, `ds_column_names(ds)`
- `ds_select(ds, indices)`, `ds_take(ds, n)`, `ds_skip(ds, n)`, `ds_shuffle(ds, seed = 42)`
- `ds_split(ds, test_fraction = 0.2, seed = 42)` — returns `[train, test]`
- `ds_from_records(records)`, `ds_to_records(ds)`
- `ds_save(ds, path)`, `ds_load_disk(path)`

<!-- verify: id=stdlib-datasets-missing error="pip install datasets" -->
```agk
import datasets

define function main:
    print(ds_len(ds_load("squad")))
```

## embeddings

Sentence embeddings via `sentence-transformers`, plus dependency-free cosine similarity and semantic search. Requires `pip install sentence-transformers` for the encode functions; `emb_cosine` always works. **[experimental]**

- `emb_encode(model, texts as List)` — list of vectors
- `emb_encode_one(model, text)` — one vector
- `emb_cosine(a, b)` — pure AGK, no dependencies
- `emb_search(model, query, corpus as List)` — `[[index, score], ...]` best-first

<!-- verify: id=stdlib-embeddings-cosine output="1.0\n0.0\n" -->
```agk
import embeddings

define function main:
    print(emb_cosine([1.0, 0.0], [1.0, 0.0]))
    print(emb_cosine([1.0, 0.0], [0.0, 1.0]))
```

<!-- verify: id=stdlib-embeddings-missing error="pip install sentence-transformers" -->
```agk
import embeddings

define function main:
    print(emb_encode("all-MiniLM-L6-v2", ["hi"]))
```

## finetune

LoRA fine-tuning of causal language models via `peft` + `transformers` + `datasets`. Requires `pip install torch transformers datasets peft`. Because AGK cannot pass keyword arguments, `ft_lora_train` uses `TrainingArguments(output_dir)` library defaults (3 epochs, lr 5e-5, batch size 8, no eval split) and builds `LoraConfig` positionally as `(r=8, target_modules, lora_alpha=16)`. **[experimental]**

- `ft_prepare_lm(model, texts as List, max_length as Integer = 256)` — tokenize, truncate, pad (with the eos id) and build attention masks; returns `[{"input_ids", "attention_mask", "labels"}]`
- `ft_lora_train(model, records, output_dir, target_modules as List)` — trains and saves the adapter; pass `["q_proj", "v_proj"]` for LLaMA/Mistral-style models
- `ft_merge_lora(base_model, adapter_dir, output_dir)` — merge the adapter back into the base model and save
- `ft_generate_adapter(base_model, adapter_dir, prompt, max_new_tokens as Integer = 20, temperature as Float = 0.0)` — generate with the adapter loaded

<!-- verify: id=stdlib-finetune-missing error="pip install transformers" -->
```agk
import finetune

define function main:
    print(ft_prepare_lm("gpt2", ["hi"]))
```

## tensor

NumPy-backed n-dimensional array primitives for neural network inference: creation, shapes, matrix multiplication, elementwise math, softmax, RMSNorm, SiLU/sigmoid, row selection, stacking, seeded random sampling and `.npz` weight loading. Everything is float32. Requires `pip install numpy`; importing this module never requires it — each function raises a clear `pip install numpy` error only when called without the backend. **[experimental]**

- `tensor_zeros(shape)`, `tensor_ones(shape)`, `tensor_randn(shape, seed)`, `tensor_from_list(xs)` / `tensor_to_list(t)` — create and convert
- `tensor_shape(t)`, `tensor_numel(t)`, `tensor_reshape(t, shape)`, `tensor_transpose(t)` — shapes
- `tensor_matmul(a, b)`, `tensor_add/sub/mul/div(a, b)`, `tensor_neg/exp/sqrt/sigmoid/silu(t)` — math
- `tensor_sum(t)`, `tensor_sum_axis(t, axis)`, `tensor_max(t)`, `tensor_argmax(t)` — reductions
- `tensor_take(t, idx, axis)`, `tensor_take1(t, i, axis)` — select one row (or several)
- `tensor_stack(xs)` — stack a List of 1-D tensors into rows
- `tensor_softmax_1d(t)`, `tensor_softmax_rows(t)` — numerically stable softmax
- `tensor_rmsnorm(x, weight, eps)` — `x / sqrt(mean(x^2) + eps) * weight`
- `tensor_max_abs_diff(a, b)` — largest elementwise difference, for testing
- `tensor_seed(seed)`, `tensor_random_choice(n, probs)` — reproducible sampling
- `tensor_load_npz(path)`, `tensor_npz_names(npz)`, `tensor_npz_get(npz, name)` — weight files

<!-- verify: id=stdlib-tensor-matmul output="[[19.0, 22.0], [43.0, 50.0]]\n" -->
```agk
import tensor

define function main:
    create a as Object
    set a to tensor_from_list([[1.0, 2.0], [3.0, 4.0]])
    create b as Object
    set b to tensor_from_list([[5.0, 6.0], [7.0, 8.0]])
    print(tensor_to_list(tensor_matmul(a, b)))
```

## infer

A real transformer inference engine in AGK: a Llama-style decoder (RMSNorm, RoPE, SwiGLU MLP) with a proper per-head KV-cache, greedy / temperature sampling and a character-level tokenizer. AGK orchestrates every step of the forward pass; the `tensor` module (NumPy) does the arithmetic. Requires `pip install numpy`. **[experimental]**

Weight convention: every matrix is stored `(in_features, out_features)` and activations are row vectors, so a projection is `x @ w`.

- `infer_random_model(config, seed)` — a small random model for experiments; `config` is `[n_layer, n_head, n_embd, head_dim, ffn_hidden, block_size, vocab_size]`
- `infer_load_model(path)` — load a `.npz` saved in the `infer` layout (see `examples/tinyshakespeare/train.py`)
- `infer_encode(model, text)` / `infer_decode(model, ids)` — character tokenizer round-trip
- `infer_step(model, caches, tok_id, pos)` — one cached forward step, returns logits
- `infer_new_caches(model)` — fresh per-head KV-cache
- `infer_forward_logits(model, ids)` — logits for the last token of a prompt
- `infer_sample(logits, temperature)` — argmax at `0.0`, sampled otherwise
- `infer_generate(model, prompt, max_new_tokens, temperature)` — generate text

<!-- verify: id=stdlib-infer-generate output="bead\nfffffg\n" -->
```agk
import infer

define function main:
    create model as List
    set model to infer_random_model([1, 2, 8, 4, 16, 16, 10], 7)
    print(infer_decode(model, infer_encode(model, "bead")))
    print(infer_generate(model, "ab", 6, 0.0))
```

The cached incremental engine is verified against an independent full-sequence NumPy reference: identical weights produce identical logits (see `tests/test_stdlib7.py`). A trained demo lives in `examples/tinyshakespeare/` — train a tiny Shakespeare model, then talk to it from AGK:

```shell
cd examples/tinyshakespeare
python train.py --steps 2500   # needs pip install torch numpy
agk run demo.agk
```

## Writing your own module

Put `helpers.agk` next to your program and write `import helpers` — it is compiled and inlined just like the bundled modules, and you call its functions by bare name.
