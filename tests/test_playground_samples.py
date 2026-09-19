"""Playground sample tests.

Every .agk program in playground/samples/ is compiled through the full
pipeline and executed; its stdout must match the .expected file exactly.
These are the examples shipped in the AGK Playground's sample dropdown,
so they must stay warning-clean and byte-exact — playground/build.py
enforces the same checks at build time.
"""

from pathlib import Path

import pytest

from agk.pipeline import run_source, compile_source

SAMPLES = Path(__file__).parent.parent / "playground" / "samples"


def sample_programs():
    return sorted(SAMPLES.glob("*.agk"))


def test_samples_directory_is_not_empty():
    assert sample_programs(), "playground/samples/ has no .agk files"


@pytest.mark.parametrize("prog", sample_programs(), ids=lambda p: p.stem)
def test_sample_program_output(prog):
    src = prog.read_text()
    expected = (prog.with_suffix(".expected")).read_text()
    stdout, _ns, _warnings = run_source(src, filename=prog.name)
    assert stdout == expected


def test_sample_programs_emit_no_warnings():
    for prog in sample_programs():
        _, warnings = compile_source(prog.read_text(), filename=prog.name)
        assert warnings == [], f"{prog.name}: {warnings}"


def test_samples_use_simple_agk():
    # The playground is the Simple AGK showcase: no classic-form
    # declarations may sneak into the samples.
    classic_markers = ("define function", "create ", "set ")
    for prog in sample_programs():
        for lineno, line in enumerate(prog.read_text().splitlines(), 1):
            stripped = line.strip()
            for marker in classic_markers:
                assert not stripped.startswith(marker), (
                    f"{prog.name}:{lineno}: classic form {marker!r} "
                    f"in a Simple AGK sample"
                )
