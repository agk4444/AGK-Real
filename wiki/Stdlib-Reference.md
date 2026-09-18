# Standard library

Nine `.agk` modules ship with the compiler (in `agk/stdlib/`). Import one by name — `import strutils` — and it is compiled and inlined into your program: its functions become directly callable, no install step, no extra files. Every signature below is taken from the real module source, and every example is compile-and-run verified.

**Modules**

- [[Stdlib-Reference#strutils|strutils]]
- [[Stdlib-Reference#listutils|listutils]]
- [[Stdlib-Reference#fileutils|fileutils]]
- [[Stdlib-Reference#jsonutils|jsonutils]]
- [[Stdlib-Reference#httputils|httputils]]
- [[Stdlib-Reference#dateutils|dateutils]]
- [[Stdlib-Reference#csvutils|csvutils]]
- [[Stdlib-Reference#regexutils|regexutils]]
- [[Stdlib-Reference#sqliteutils|sqliteutils]]
- [[Stdlib-Reference#writing-your-own-module|Writing your own module]]

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

## httputils

HTTP utilities (wraps `urllib.request`).

- `http_get(url as String) -> String` — response body as a String

<!-- verify: id=stdlib-httputils server="static:hello from the test server" output="hello from the test server\n" -->
```agk
import httputils

define function main:
    print(http_get("http://127.0.0.1:{{PORT}}/"))
```

> [!NOTE]
> The example above is verified against a local test server; point `http_get` at any real URL in your own programs.

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

<!-- verify: id=stdlib-dateutils-today output-regex="^\d{4}-\d{2}-\d{2}\n$" -->
```agk
import dateutils

define function main:
    print(today())
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

## Writing your own module

Put `helpers.agk` next to your program and write `import helpers` — it is compiled and inlined just like the bundled modules, and you call its functions by bare name.
