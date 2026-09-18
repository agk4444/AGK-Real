# Library cookbook

Three complete programs built on the standard library. Each one is a full, runnable AGK program — copy it into a `.agk` file and run it with `agk run`. Every program on this page is compile-and-run verified.

- [[Library-Cookbook#password-hasher|Password hasher]] — a CLI that salts and hashes a password with `crypto`
- [[Library-Cookbook#generative-art|Generative art]] — a pixel-by-pixel painting saved as PNG with `graphics`
- [[Library-Cookbook#tool-using-assistant|Tool-using assistant]] — a ReAct agent that calls a real tool, with the LLM mocked

## Password hasher

`hasher.agk` takes a password on the command line, generates a random salt, and derives a hash with PBKDF2 (100,000 iterations). Store the salt and the hash; to check a login, re-derive with the stored salt and compare with `compare_digest`.

Run it with `agk run hasher.agk -- s3cret` (everything after `--` reaches the program as `sys.argv[1:]`).

<!-- verify: id=cook-crypto-hasher args="s3cret" output-regex="^salt: [0-9a-f]{16}\nhash: [0-9a-f]{64}\n$" -->
```agk
import crypto
import sys

define function main:
    create pw as String
    set pw to sys.argv[1]
    create salt as String
    set salt to token_hex(8)
    create hash as String
    set hash to pbkdf2_hex(pw, salt, 100000)
    print("salt: " + salt)
    print("hash: " + hash)
```

Verifying a login later is one more call:

<!-- verify: id=cook-crypto-check output="True\nFalse\n" -->
```agk
import crypto

define function check that takes pw as String, salt as String, want as String and returns Boolean:
    return compare_digest(pbkdf2_hex(pw, salt, 100000), want)

define function main:
    create salt as String
    set salt to "fixed-salt-for-demo"
    create stored as String
    set stored to pbkdf2_hex("s3cret", salt, 100000)
    print(check("s3cret", salt, stored))
    print(check("wrong", salt, stored))
```

## Generative art

`art.agk` paints a 64×40 canvas pixel by pixel — a color gradient, a ring, and a diagonal line — then writes it out as a real PNG with `save_png`. No display or graphics card needed; open `art.png` in any image viewer afterwards.

<!-- verify: id=cook-graphics-art output="art.png\nTrue\n" -->
```agk
import graphics
import fileutils

define function main:
    create c as Object
    set c to new(64, 40, "#0d1117")
    for y from 0 to 39:
        for x from 0 to 63:
            create r as Integer
            set r to (x * 4) % 256
            create b as Integer
            set b to (y * 6) % 256
            pixel(c, x, y, [r, 64, b])
    circle(c, 32, 20, 12, "#e94560", true)
    circle(c, 32, 20, 7, "#0d1117", true)
    line(c, 0, 0, 63, 39, [255, 255, 255])
    print(save_png(c, "art.png"))
    print(file_exists("art.png"))
```

## Tool-using assistant

`assistant.agk` gives the model two tools — `add` and `shout` — and asks it to use them. Here the "model" is a local mock server returning the exact `/chat/completions` JSON shape, so the whole ReAct loop runs offline: the mock tells the agent to call `add`, the agent runs the real AGK function, feeds the observation back, and the mock replies with the final answer.

In your own programs, drop the mock and pass your real key: `react("...", {"add": add}, 8, "gpt-4o-mini", "YOUR_KEY")` (or set `AGK_LLM_API_KEY`).

<!-- verify: id=cook-agent-assistant server='seq:{"choices": [{"message": {"content": "{\"tool\": \"shout\", \"args\": {\"text\": \"it works\"}}"}}]}|||{"choices": [{"message": {"content": "{\"answer\": \"The assistant shouted: IT WORKS!\"}"}}]}' output="The assistant shouted: IT WORKS!\nTrue\n1\n" -->
```agk
import agent
import strutils

define function add that takes args as Object and returns Object:
    return args["a"] + args["b"]

define function shout_tool that takes args as Object and returns Object:
    return shout(args["text"])

define function main:
    create tools as Object
    set tools to {"add": add, "shout": shout_tool}
    create result as Object
    set result to react("Shout 'it works' for me.", tools, 5, "gpt-4o-mini", "fake-key", "http://127.0.0.1:{{PORT}}")
    print(result["answer"])
    print(result["done"])
    print(len(result["steps"]))
```
