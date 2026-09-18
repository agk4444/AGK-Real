"""Documentation regression test: every ```agk block in GUIDE.md must
compile. Fragments and error examples use other fence types so they are
not picked up."""

import re
from pathlib import Path

import pytest

from agk.pipeline import compile_source

GUIDE = Path(__file__).parent.parent / "GUIDE.md"


def agk_blocks():
    return re.findall(r"```agk\n(.*?)```", GUIDE.read_text(), re.DOTALL)


def test_guide_has_blocks():
    assert len(agk_blocks()) >= 10


@pytest.mark.parametrize("i,src", list(enumerate(agk_blocks())))
def test_guide_block_compiles(i, src):
    compile_source(src, filename=f"guide-{i}.agk")
