"""v0.4.0 — package manager (`agk pkg`) tests.

All installs use local git repos / local directories: no network.
"""

import json
import subprocess
import tempfile
from pathlib import Path

import pytest

from agk.__main__ import main
from agk.pkg import cmd_install, cmd_list, find_project_root, package_module_dirs

GREETER_MOD = (
    "define function greet that takes s as String and returns String:\n"
    '    return "hi, " + s + "!"\n'
)
GREETER_PKG_MANIFEST = json.dumps({"name": "greeter", "version": "1.2.0"})


def git(args, cwd):
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True,
        check=True)


def make_repo(path, files):
    """Create a git repo at *path* with the given {name: content} files."""
    path.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (path / name).write_text(content)
    git(["init", "-q"], path)
    git(["add", "."], path)
    git(["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm",
         "init"], path)
    return git(["rev-parse", "HEAD"], path).stdout.strip()


@pytest.fixture()
def project(tmp_path, monkeypatch):
    """A fresh AGK project dir; cwd is chdir'd into it."""
    monkeypatch.chdir(tmp_path)
    assert main(["pkg", "init", "--name", "demo"]) == 0
    manifest = json.loads((tmp_path / "agk.json").read_text())
    assert manifest == {"name": "demo", "version": "0.1.0", "dependencies": {}}
    return tmp_path


def test_init_creates_manifest(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["pkg", "init"]) == 0
    assert "created agk.json" in capsys.readouterr().out
    manifest = json.loads((tmp_path / "agk.json").read_text())
    assert manifest["name"] == tmp_path.name
    assert manifest["version"] == "0.1.0"
    assert manifest["dependencies"] == {}


def test_init_refuses_existing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["pkg", "init"]) == 0
    assert main(["pkg", "init"]) == 2  # already exists


def test_install_git_url_records_hash(project, tmp_path):
    repo = tmp_path / "greeter-repo"
    commit = make_repo(repo, {"greeter.agk": GREETER_MOD,
                              "agk.json": GREETER_PKG_MANIFEST})
    assert main(["pkg", "install", f"file://{repo}"]) == 0

    dest = project / "packages" / "greeter-repo"
    assert (dest / "greeter.agk").read_text() == GREETER_MOD

    manifest = json.loads((project / "agk.json").read_text())
    entry = manifest["dependencies"]["greeter-repo"]
    assert entry["url"] == f"file://{repo}"
    assert entry["commit"] == commit
    assert len(entry["commit"]) == 40
    assert entry["version"] == "1.2.0"


def test_install_local_path_copies(project, tmp_path):
    src = tmp_path / "mathx"
    src.mkdir()
    (src / "mathx.agk").write_text(
        "define function double that takes n as Integer and returns Integer:\n"
        "    return n * 2\n")
    assert main(["pkg", "install", str(src)]) == 0

    dest = project / "packages" / "mathx"
    assert (dest / "mathx.agk").is_file()
    manifest = json.loads((project / "agk.json").read_text())
    entry = manifest["dependencies"]["mathx"]
    assert entry["commit"] is None
    assert entry["url"] == str(src.resolve())


def test_install_needs_init(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["pkg", "install", "https://example.com/x.git"]) == 2
    assert "agk pkg" in capsys.readouterr().err


def test_import_installed_package_end_to_end(project, tmp_path, capsys):
    repo = tmp_path / "greeter"
    make_repo(repo, {"greeter.agk": GREETER_MOD})
    assert main(["pkg", "install", f"file://{repo}"]) == 0
    capsys.readouterr()

    entry = project / "main.agk"
    entry.write_text("import greeter\n"
                     "define function main:\n"
                     '    print(greet("gopi"))\n')
    assert main(["run", str(entry)]) == 0
    assert capsys.readouterr().out == "hi, gopi!\n"


def test_import_from_subdirectory_still_finds_packages(project, tmp_path,
                                                       capsys):
    """An entry file in a subdir resolves packages via the project root."""
    repo = tmp_path / "greeter"
    make_repo(repo, {"greeter.agk": GREETER_MOD})
    assert main(["pkg", "install", f"file://{repo}"]) == 0
    capsys.readouterr()

    sub = project / "app"
    sub.mkdir()
    entry = sub / "main.agk"
    entry.write_text("import greeter\n"
                     "define function main:\n"
                     '    print(greet("deep"))\n')
    assert main(["run", str(entry)]) == 0
    assert capsys.readouterr().out == "hi, deep!\n"


def test_sibling_module_shadows_package(project, tmp_path, capsys):
    """Precedence: importing file's dir > search paths > stdlib > packages."""
    repo = tmp_path / "greeter"
    make_repo(repo, {"greeter.agk": GREETER_MOD})
    assert main(["pkg", "install", f"file://{repo}"]) == 0
    capsys.readouterr()

    # A same-named sibling module wins over the installed package.
    (project / "greeter.agk").write_text(
        "define function greet that takes s as String and returns String:\n"
        '    return "sibling: " + s\n')
    entry = project / "main.agk"
    entry.write_text("import greeter\n"
                     "define function main:\n"
                     '    print(greet("gopi"))\n')
    assert main(["run", str(entry)]) == 0
    assert capsys.readouterr().out == "sibling: gopi\n"


def test_package_module_dirs(project):
    (project / "packages" / "greeter").mkdir(parents=True)
    manifest = json.loads((project / "agk.json").read_text())
    manifest["dependencies"]["greeter"] = {"url": "x", "commit": None,
                                            "version": None}
    (project / "agk.json").write_text(json.dumps(manifest))
    dirs = package_module_dirs(str(project))
    assert dirs == [project / "packages" / "greeter"]


def test_find_project_root_walks_up(project, tmp_path):
    sub = project / "a" / "b"
    sub.mkdir(parents=True)
    assert find_project_root(sub) == project
    outside = Path(tempfile.mkdtemp())
    assert find_project_root(outside) is None


def test_list_shows_installed(project, tmp_path, capsys):
    repo = tmp_path / "greeter"
    commit = make_repo(repo, {"greeter.agk": GREETER_MOD,
                              "agk.json": GREETER_PKG_MANIFEST})
    assert main(["pkg", "install", f"file://{repo}"]) == 0

    items = cmd_list()
    assert len(items) == 1
    pkg_name, entry, present = items[0]
    assert pkg_name == "greeter"
    assert present is True
    assert entry["commit"] == commit

    assert main(["pkg", "list"]) == 0
    out = capsys.readouterr().out
    assert "greeter" in out and "1.2.0" in out and commit[:12] in out


def test_list_empty(project, capsys):
    assert main(["pkg", "list"]) == 0
    assert "no packages installed" in capsys.readouterr().out


def test_reinstall_is_idempotent(project, tmp_path, capsys):
    repo = tmp_path / "greeter"
    make_repo(repo, {"greeter.agk": GREETER_MOD})
    assert main(["pkg", "install", f"file://{repo}"]) == 0
    before = (project / "agk.json").read_text()

    info = cmd_install(f"file://{repo}")
    assert info["already_installed"] is True
    assert (project / "agk.json").read_text() == before

    assert main(["pkg", "install", f"file://{repo}"]) == 0
    assert "already installed" in capsys.readouterr().out
    assert len(cmd_list()) == 1


def test_install_with_explicit_name(project, tmp_path):
    src = tmp_path / "somelib"
    src.mkdir()
    (src / "util.agk").write_text(
        "define function one:\n    return 1\n")
    info = cmd_install(str(src), name="renamed")
    assert info["name"] == "renamed"
    assert (project / "packages" / "renamed" / "util.agk").is_file()
    assert "renamed" in json.loads((project / "agk.json").read_text())[
        "dependencies"]
