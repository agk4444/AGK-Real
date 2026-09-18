"""Level 5 — End-to-end tests (AGK-Real v1 test plan).

Every .agk program in tests/corpus/ is compiled through the full
pipeline and executed; its stdout must match the .expected file exactly.
These corpus programs double as the runnable documentation examples.
"""

from pathlib import Path

import pytest

from agk.pipeline import run_source, compile_source

CORPUS = Path(__file__).parent / "corpus"


def corpus_programs():
    return sorted(CORPUS.glob("*.agk"))


@pytest.mark.parametrize("prog", corpus_programs(), ids=lambda p: p.stem)
def test_corpus_program_output(prog):
    src = prog.read_text()
    expected = (prog.with_suffix(".expected")).read_text()
    stdout, _ns, _warnings = run_source(src, filename=prog.name)
    assert stdout == expected


def test_no_main_produces_no_output_and_is_callable():
    src = (CORPUS / "no_main.agk").read_text()
    stdout, ns, _ = run_source(src, filename="no_main.agk")
    assert stdout == ""
    assert ns["add"](2, 3) == 5


def test_main_entrypoint_runs_automatically():
    src = (CORPUS / "hello.agk").read_text()
    stdout, _ns, _ = run_source(src, filename="hello.agk")
    assert stdout == "hello, agk\n"


def test_corpus_programs_emit_no_warnings():
    # The doc examples should be warning-clean (unused vars etc.).
    for prog in corpus_programs():
        _, warnings = compile_source(prog.read_text(), filename=prog.name)
        assert warnings == [], f"{prog.name}: {warnings}"
