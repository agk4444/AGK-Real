# Releasing AGK-Real

**Do NOT publish a release without the maintainer's (Gopi's) explicit go-ahead.**
There are no PyPI credentials in this environment, and test/PyPI uploads are
never done on speculation.

## Checklist

1. **Bump the version** in `pyproject.toml` (`[project] version`) and keep
   `COMPILER_VERSION` in `agk/pipeline.py` in sync (it keys the `.agkcache/`
   fingerprints, so a mismatch safely invalidates old caches).
   Follow semver: `0.4.0` is a milestone release, so patch bumps for fixes
   (`0.4.1`), minor for new features (`0.5.0`).

2. **Run the full test suite** and confirm green:
   ```sh
   cd ~/workspace/agk-real
   .venv/bin/python -m pytest tests/ -q
   ```

3. **Build the distribution** (needs `build` installed: `pip install build`):
   ```sh
   python -m build
   ```
   This produces `dist/agk-real-<version>.tar.gz` and
   `dist/agk_real-<version>-py3-none-any.whl`.

4. **Check the packages** (needs `twine`: `pip install twine`):
   ```sh
   twine check dist/*
   ```
   Must report no errors (valid long description, metadata renders on PyPI).

5. **Upload to TestPyPI first** (needs an API token from test.pypi.org):
   ```sh
   twine upload --repository testpypi dist/*
   ```
   Install from TestPyPI in a clean venv and smoke-test:
   `pip install -i https://test.pypi.org/simple/ agk-real && agk --help`.

6. **Upload to PyPI** (needs an API token from pypi.org):
   ```sh
   twine upload dist/*
   ```

7. **Tag the release** in git:
   ```sh
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

## Notes

- The `agk/stdlib/*.agk` files ship inside the wheel via `package-data`
  in `pyproject.toml` — `twine check` plus the TestPyPI install verify they
  are included (`agk run` with a stdlib import is the real proof).
- GitHub Actions runs the test suite on Python 3.9–3.12 for every push and PR
  (see `.github/workflows/ci.yml`); releases should not go out with CI red.
