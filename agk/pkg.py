"""`agk pkg` — minimal, registry-free package manager.

Packages are plain git repositories containing .agk modules; there is no
central registry (Go-modules style, minus the proxy). ``agk pkg install``
clones a package (shallow) into ``<project>/packages/<name>/`` and pins
the commit hash in ``agk.json``. A local directory installs by copy,
which makes offline testing possible.

``import <module>`` resolves installed packages *after* the importing
file's own directory, the caller's search paths, and the bundled stdlib
(see pipeline._find_module); the search is driven by the nearest
``agk.json`` found walking up from the entry file.

Manifest format (agk.json):

    {
      "name": "myproject",
      "version": "0.1.0",
      "dependencies": {
        "greeter": {
          "url": "https://example.com/greeter.git",
          "commit": "abc1234def...",
          "version": "1.2.0"
        }
      }
    }

``commit`` is null for local-directory installs; ``version`` is read
from the package's own agk.json when it has one, else null.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

MANIFEST_NAME = "agk.json"
PACKAGES_DIR_NAME = "packages"
DEFAULT_VERSION = "0.1.0"


class PkgError(Exception):
    """Usage / IO / git failure for a pkg operation."""


def find_project_root(start=None):
    """Nearest ancestor of *start* (or cwd) containing agk.json."""
    d = Path(start if start is not None else os.getcwd()).resolve()
    for p in (d, *d.parents):
        if (p / MANIFEST_NAME).is_file():
            return p
    return None


def load_manifest(root):
    path = Path(root) / MANIFEST_NAME
    try:
        with open(path, encoding="utf-8") as f:
            manifest = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise PkgError(f"cannot read '{path}': {e}")
    if not isinstance(manifest, dict):
        raise PkgError(f"'{path}' is not a JSON object")
    manifest.setdefault("dependencies", {})
    return manifest


def save_manifest(root, manifest):
    path = Path(root) / MANIFEST_NAME
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")


def cmd_init(cwd=None, name=None, version=DEFAULT_VERSION):
    """Create agk.json in *cwd*. Raises PkgError if one already exists."""
    root = Path(cwd if cwd is not None else os.getcwd()).resolve()
    path = root / MANIFEST_NAME
    if path.exists():
        raise PkgError(f"'{path}' already exists")
    manifest = {
        "name": name or root.name,
        "version": version,
        "dependencies": {},
    }
    save_manifest(root, manifest)
    return manifest


def _run_git(args, cwd):
    try:
        return subprocess.run(
            ["git", *args], cwd=str(cwd),
            capture_output=True, text=True, check=True)
    except FileNotFoundError:
        raise PkgError("git is not installed")
    except subprocess.CalledProcessError as e:
        raise PkgError(f"git {' '.join(args)} failed: {e.stderr.strip()}")


def _derive_name(source, explicit=None):
    if explicit:
        return explicit
    s = source.rstrip("/").rstrip("\\")
    tail = s
    if "://" in s:
        tail = s.split("://", 1)[1]
    elif "@" in s and ":" in s:
        # scp-like syntax: git@host:path/to/repo.git
        tail = s.split(":", 1)[1]
    base = tail.rsplit("/", 1)[-1]
    if base.endswith(".git"):
        base = base[:-4]
    if not base:
        raise PkgError(f"cannot derive a package name from '{source}'; "
                       "pass --name")
    return base


def _package_version(pkg_dir):
    """Version from the package's own agk.json, or None."""
    path = Path(pkg_dir) / MANIFEST_NAME
    if path.is_file():
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f).get("version")
        except (OSError, json.JSONDecodeError, AttributeError):
            return None
    return None


def _record_dependency(root, pkg_name, url, commit):
    manifest = load_manifest(root)
    deps = manifest.setdefault("dependencies", {})
    deps[pkg_name] = {
        "url": url,
        "commit": commit,
        "version": _package_version(root / PACKAGES_DIR_NAME / pkg_name),
    }
    save_manifest(root, manifest)
    return deps[pkg_name]


def cmd_install(source, cwd=None, name=None):
    """Install a package from a git URL (cloned shallow) or a local
    directory (copied). Records url + commit hash in agk.json.
    Reinstalling an already-installed package is a no-op (idempotent).

    Returns a dict describing the install (with 'already_installed').
    """
    cwd = Path(cwd if cwd is not None else os.getcwd()).resolve()
    root = find_project_root(cwd) or cwd
    if not (root / MANIFEST_NAME).is_file():
        raise PkgError(f"no '{MANIFEST_NAME}' in '{root}' "
                       "(run 'agk pkg init' first)")
    pkg_name = _derive_name(source, name)
    dest = root / PACKAGES_DIR_NAME / pkg_name
    manifest = load_manifest(root)
    recorded = manifest.get("dependencies", {}).get(pkg_name)

    if dest.is_dir() and recorded is not None:
        return {"name": pkg_name, "path": str(dest),
                "already_installed": True, "entry": recorded}

    local = Path(source).expanduser()
    if local.is_dir():
        # Local directory install: plain copy (offline-friendly).
        if dest.exists():
            shutil.rmtree(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(local, dest, ignore=shutil.ignore_patterns(".git"))
        url = str(local.resolve())
        commit = None
    else:
        # Git URL (file:// URLs also work offline for tests).
        if dest.exists():
            raise PkgError(f"'{dest}' already exists but is not recorded "
                           f"in '{MANIFEST_NAME}'")
        dest.parent.mkdir(parents=True, exist_ok=True)
        _run_git(["clone", "--depth", "1", source, str(dest)], cwd=root)
        url = source
        commit = _run_git(["rev-parse", "HEAD"], cwd=dest).stdout.strip()

    entry = _record_dependency(root, pkg_name, url, commit)
    return {"name": pkg_name, "path": str(dest), "already_installed": False,
            "entry": entry}


def cmd_list(cwd=None):
    """Installed packages per agk.json. Returns [(name, entry, present)]."""
    cwd = Path(cwd if cwd is not None else os.getcwd()).resolve()
    root = find_project_root(cwd) or cwd
    if not (root / MANIFEST_NAME).is_file():
        raise PkgError(f"no '{MANIFEST_NAME}' in '{root}' "
                       "(run 'agk pkg init' first)")
    manifest = load_manifest(root)
    pkg_root = root / PACKAGES_DIR_NAME
    result = []
    for pkg_name, entry in manifest.get("dependencies", {}).items():
        result.append((pkg_name, entry,
                       (pkg_root / pkg_name).is_dir()))
    return result


def package_module_dirs(entry_dir=None):
    """Search dirs for .agk module resolution: <project>/packages/<dep>
    for every dependency in the nearest agk.json. Returns [Path, ...]."""
    root = find_project_root(entry_dir)
    if root is None:
        return []
    pkg_root = root / PACKAGES_DIR_NAME
    dirs = []
    for pkg_name in load_manifest(root).get("dependencies", {}):
        d = pkg_root / pkg_name
        if d.is_dir():
            dirs.append(d)
    return dirs
