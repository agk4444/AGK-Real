"""Incremental compilation cache tests (v0.4.0 workstream 9).

`agk build` keeps a project-local `.agkcache/` manifest keyed by
sha256(source) + compiler version. Unchanged modules are cache hits;
edited modules recompile; importers of an edited module are
conservatively recompiled too.
"""

import json

from agk.__main__ import main
from agk.pipeline import compile_source


UTILS_V1 = (
    "define function greet that takes name as String and returns String:\n"
    '    return "hi " + name + "!"\n'
)
UTILS_V2 = (
    "define function greet that takes name as String and returns String:\n"
    '    return "hello " + name + "!"\n'
)
OTHER = (
    "define function shout that takes s as String and returns String:\n"
    '    return s + "?"\n'
)
# three-level chain for transitive invalidation: main -> mid -> utils
MID = "import utils\n\ndefine function relay that takes n as String and returns String:\n    return greet(n)\n"
MAIN = (
    "import utils\n"
    "import other\n"
    "\n"
    "define function main:\n"
    '    print(greet("bob"))\n'
    '    print(shout("wow"))\n'
)
MAIN_CHAIN = (
    "import mid\n"
    "\n"
    "define function main:\n"
    '    print(relay("bob"))\n'
)


def write(tmp_path, name, src):
    p = tmp_path / name
    p.write_text(src)
    return str(p)


def build(path):
    assert main(["build", str(path)]) == 0


def cache_dir(tmp_path):
    return tmp_path / ".agkcache"


def test_rebuild_no_changes_is_all_cache_hits(tmp_path, capsys):
    write(tmp_path, "utils.agk", UTILS_V1)
    write(tmp_path, "other.agk", OTHER)
    main_p = write(tmp_path, "main.agk", MAIN)
    build(main_p)
    out1 = (tmp_path / "main.py").read_text()
    assert cache_dir(tmp_path).is_dir()
    capsys.readouterr()

    build(main_p)
    out = capsys.readouterr().out
    assert out.count("cache hit:") == 3  # utils, other, main.agk
    assert "compiled:" not in out
    # identical output, rewritten from cache
    assert (tmp_path / "main.py").read_text() == out1


def test_cached_output_matches_uncached_compile(tmp_path):
    """The cache assembly must be byte-identical to a fresh compile."""
    write(tmp_path, "utils.agk", UTILS_V1)
    write(tmp_path, "other.agk", OTHER)
    main_p = write(tmp_path, "main.agk", MAIN)
    code, _warnings = compile_source(
        MAIN, filename=main_p, search_paths=[str(tmp_path)])
    build(main_p)
    assert (tmp_path / "main.py").read_text() == code


def test_edit_module_recompiles_it_and_its_importer(tmp_path, capsys):
    write(tmp_path, "utils.agk", UTILS_V1)
    write(tmp_path, "other.agk", OTHER)
    main_p = write(tmp_path, "main.agk", MAIN)
    build(main_p)
    capsys.readouterr()

    write(tmp_path, "utils.agk", UTILS_V2)  # edit one module
    build(main_p)
    out = capsys.readouterr().out
    assert "compiled: utils" in out       # edited module recompiled
    assert "compiled: main.agk" in out    # its importer recompiled too
    assert "cache hit: other" in out      # untouched module stays a hit
    assert out.count("cache hit:") == 1
    assert '"hello "' in (tmp_path / "main.py").read_text()

    # steady state again: everything is a hit
    build(main_p)
    out = capsys.readouterr().out
    assert out.count("cache hit:") == 3
    assert "compiled:" not in out


def test_transitive_invalidation_through_chain(tmp_path, capsys):
    write(tmp_path, "utils.agk", UTILS_V1)
    write(tmp_path, "mid.agk", MID)
    main_p = write(tmp_path, "main.agk", MAIN_CHAIN)
    build(main_p)
    capsys.readouterr()

    write(tmp_path, "utils.agk", UTILS_V2)  # leaf change
    build(main_p)
    out = capsys.readouterr().out
    assert "compiled: utils" in out
    assert "compiled: mid" in out       # transitive dependent recompiled
    assert "compiled: main.agk" in out
    assert "cache hit:" not in out


def test_circular_imports_terminate(tmp_path, capsys):
    write(tmp_path, "a.agk",
          "import b\n\ndefine function fa that takes x as Integer and returns Integer:\n    return x + 1\n")
    write(tmp_path, "b.agk",
          "import a\n\ndefine function fb that takes x as Integer and returns Integer:\n    return x + 2\n")
    main_p = write(tmp_path, "main.agk",
                   "import b\n\ndefine function main:\n    print(fb(1))\n")
    build(main_p)
    capsys.readouterr()
    build(main_p)
    assert capsys.readouterr().out.count("cache hit:") == 3


def test_clean_wipes_cache(tmp_path, capsys):
    write(tmp_path, "utils.agk", UTILS_V1)
    write(tmp_path, "other.agk", OTHER)
    main_p = write(tmp_path, "main.agk", MAIN)
    build(main_p)
    assert cache_dir(tmp_path).is_dir()

    assert main(["clean", str(tmp_path)]) == 0
    assert "removed" in capsys.readouterr().out
    assert not cache_dir(tmp_path).exists()

    # cleaning an already-clean dir is fine
    assert main(["clean", str(tmp_path)]) == 0
    assert "no cache" in capsys.readouterr().out


def test_build_clean_flag_rebuilds_fresh(tmp_path, capsys):
    write(tmp_path, "utils.agk", UTILS_V1)
    write(tmp_path, "other.agk", OTHER)
    main_p = write(tmp_path, "main.agk", MAIN)
    build(main_p)
    capsys.readouterr()

    assert main(["build", "--clean", main_p]) == 0
    out = capsys.readouterr().out
    assert "cache hit:" not in out
    assert out.count("compiled:") == 3  # utils + other + main.agk
    assert cache_dir(tmp_path).is_dir()  # cache repopulated


def test_manifest_records_version_and_hashes(tmp_path):
    write(tmp_path, "utils.agk", UTILS_V1)
    write(tmp_path, "other.agk", OTHER)
    main_p = write(tmp_path, "main.agk", MAIN)
    build(main_p)
    data = json.loads((cache_dir(tmp_path) / "manifest.json").read_text())
    assert data["version"] == "0.5.0"
    assert data["format"] == 1
    entry_paths = list(data["entries"])
    assert any(p.endswith("utils.agk") for p in entry_paths)
    assert any(p.endswith("main.agk") for p in entry_paths)
    for e in data["entries"].values():
        assert len(e["fingerprint"]) == 64  # sha256 hex


def test_annotate_flag_is_part_of_cache_key(tmp_path):
    """annotate=True/False builds must never share cache entries."""
    from agk.parser import parse
    from agk.pipeline import compile_program, compile_program_cached

    write(tmp_path, "utils.agk", UTILS_V1)
    write(tmp_path, "other.agk", OTHER)
    main_p = write(tmp_path, "main.agk", MAIN)
    cache = str(cache_dir(tmp_path))
    for annotate in (False, True):
        prog = parse(MAIN, filename=main_p)
        plain, _, _ = compile_program(prog, filename=main_p,
                                       search_paths=[str(tmp_path)],
                                       annotate=annotate)
        prog = parse(MAIN, filename=main_p)
        cached, _, _, _ = compile_program_cached(
            prog, filename=main_p, search_paths=[str(tmp_path)],
            annotate=annotate, cache_dir=cache, entry_source=MAIN)
        assert cached == plain


def test_async_main_cached_matches_uncached(tmp_path):
    """The cache must reproduce _generate_all's asyncio prelude/wrapper."""
    from agk.parser import parse
    from agk.pipeline import compile_program, compile_program_cached

    src = "define async function main:\n    return\n"
    main_p = write(tmp_path, "a.agk", src)
    cache = str(cache_dir(tmp_path))
    prog = parse(src, filename=main_p)
    plain, _, _ = compile_program(prog, filename=main_p,
                                   search_paths=[str(tmp_path)])
    assert "asyncio.run(main())" in plain
    prog = parse(src, filename=main_p)
    cached, _, _, _ = compile_program_cached(
        prog, filename=main_p, search_paths=[str(tmp_path)],
        cache_dir=cache, entry_source=src)
    assert cached == plain


def test_built_program_runs_from_cache(tmp_path, capsys):
    write(tmp_path, "utils.agk", UTILS_V1)
    write(tmp_path, "other.agk", OTHER)
    main_p = write(tmp_path, "main.agk", MAIN)
    build(main_p)
    capsys.readouterr()
    build(main_p)  # all cache hits
    capsys.readouterr()
    assert main(["run", main_p]) == 0
    assert capsys.readouterr().out == "hi bob!\nwow?\n"
