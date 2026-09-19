"""`agk new` scaffolding tests."""

import json
import os

import pytest

from agk.__main__ import main
from agk.scaffold import ScaffoldError, scaffold


def test_app_scaffold_layout(tmp_path):
    root = scaffold("myapp", directory=str(tmp_path))
    assert (root / "agk.json").is_file()
    assert (root / "README.md").is_file()
    assert (root / ".gitignore").is_file()
    assert (root / "src" / "main.agk").is_file()
    assert (root / "src" / "greeter.agk").is_file()
    assert (root / "tests" / "greeter_test.agk").is_file()
    manifest = json.loads((root / "agk.json").read_text())
    assert manifest["name"] == "myapp"
    assert manifest["version"] == "0.1.0"
    assert manifest["dependencies"] == {}


def test_lib_scaffold_layout(tmp_path):
    root = scaffold("mylib", kind="lib", directory=str(tmp_path))
    assert (root / "src" / "mylib.agk").is_file()
    assert (root / "tests" / "mylib_test.agk").is_file()
    assert not (root / "src" / "main.agk").exists()


def test_app_runs_and_tests_pass(tmp_path, capsys):
    root = scaffold("myapp", directory=str(tmp_path))
    assert main(["run", str(root / "src" / "main.agk")]) == 0
    assert capsys.readouterr().out == "Hello, AGK!\n"
    assert main(["test", str(root)]) == 0
    out = capsys.readouterr().out
    assert "2 passed, 0 failed" in out


def test_lib_tests_pass(tmp_path, capsys):
    root = scaffold("mylib", kind="lib", directory=str(tmp_path))
    assert main(["test", str(root)]) == 0
    assert "2 passed, 0 failed" in capsys.readouterr().out


def test_bad_name_rejected(tmp_path):
    for bad in ("", "has space", "9lives", "with-dash"):
        with pytest.raises(ScaffoldError):
            scaffold(bad, directory=str(tmp_path))
    assert main(["new", "with-dash"]) == 2


def test_existing_nonempty_dir_rejected_without_force(tmp_path, capsys,
                                                      monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "myapp").mkdir()
    (tmp_path / "myapp" / "x.txt").write_text("x")
    with pytest.raises(ScaffoldError):
        scaffold("myapp", directory=str(tmp_path))
    assert main(["new", "myapp"]) == 2
    assert "not empty" in capsys.readouterr().err


def test_force_scaffolds_into_existing_dir(tmp_path):
    d = tmp_path / "myapp"
    d.mkdir()
    (d / "x.txt").write_text("x")
    root = scaffold("myapp", directory=str(tmp_path), force=True)
    assert (root / "src" / "main.agk").is_file()
    assert (root / "x.txt").is_file()  # existing files left alone


def test_unknown_kind_rejected(tmp_path):
    with pytest.raises(ScaffoldError):
        scaffold("myapp", kind="game", directory=str(tmp_path))


def test_new_usage_error_without_name(capsys):
    assert main(["new"]) == 2


def test_new_cli_lib_and_force(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["new", "cool", "--lib", "--force"]) == 0
    assert (tmp_path / "cool" / "src" / "cool.agk").is_file()
    assert main(["test", str(tmp_path / "cool")]) == 0


def test_scaffolded_app_builds(tmp_path):
    root = scaffold("myapp", directory=str(tmp_path))
    out = root / "src" / "main.py"
    assert main(["build", str(root / "src" / "main.agk"),
                 "-o", str(out)]) == 0
    assert out.is_file()
