"""Level 6 — Fuzz test (AGK-Real v1 test plan).

500 randomly mutated programs built from the corpus seeds. Every one must
either compile or fail with a clean AGK diagnostic (LexerError, ParseError,
SemanticError, CompileError). A raw traceback from any other exception
type is a failure.
"""

import random
from pathlib import Path

import pytest

from agk.errors import AGKError
from agk.pipeline import compile_source

CORPUS = Path(__file__).parent / "corpus"
SEED = 20260918
CASES = 500

_INSERT_POOL = list("()[]{}<>=+-*/,.\":' \n\t_") + list("abcdefginorstx01239")
_KEYWORDS = ["define", "function", "create", "set", "to", "if", "else",
             "while", "for", "each", "in", "return", "class", "import",
             "true", "false", "and", "or", "not", "self"]


def mutate(rng, src):
    text = src
    for _ in range(rng.randint(1, 4)):
        if not text:
            break
        op = rng.choice(["delete", "insert", "swap", "dup", "truncate",
                         "keyword", "newline"])
        i = rng.randrange(len(text))
        if op == "delete":
            text = text[:i] + text[i + rng.randint(1, 3):]
        elif op == "insert":
            text = text[:i] + rng.choice(_INSERT_POOL) + text[i:]
        elif op == "swap" and i + 1 < len(text):
            text = text[:i] + text[i + 1] + text[i] + text[i + 2:]
        elif op == "dup":
            text = text[:i] + text[i] + text[i:]
        elif op == "truncate":
            text = text[:i]
        elif op == "keyword":
            text = text[:i] + " " + rng.choice(_KEYWORDS) + " " + text[i:]
        elif op == "newline":
            text = text[:i] + "\n" + text[i:]
    return text


def mutated_programs():
    rng = random.Random(SEED)
    seeds = [p.read_text() for p in sorted(CORPUS.glob("*.agk"))]
    for n in range(CASES):
        yield n, mutate(rng, rng.choice(seeds))


@pytest.mark.parametrize("n,src", list(mutated_programs()),
                         ids=lambda v: f"fuzz-{v}" if isinstance(v, int) else v)
def test_fuzz_no_tracebacks(n, src):
    try:
        compile_source(src, filename=f"fuzz-{n}.agk")
    except AGKError:
        pass  # clean diagnostic: this is the expected outcome
    except Exception as e:  # noqa: BLE001 - the test asserts this never happens
        pytest.fail(f"fuzz-{n} raised {type(e).__name__}: {e}\n--- program ---\n{src}")
