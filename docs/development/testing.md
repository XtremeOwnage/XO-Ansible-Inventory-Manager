# Testing

## Running the tests

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest
.venv/bin/ruff check src tests
```

`requirements-dev.txt` includes `ansible-core`, which the end-to-end test uses to check the output with the real `ansible-inventory`. Without it, that one test is skipped.

## What is tested

| File | Covers |
|---|---|
| `tests/test_criteria.py` | The criteria language: lexer, precedence, every operator, error messages |
| `tests/test_inventory.py` | Loading the folder layout and building the Ansible JSON, including the golden-file test below |
| `tests/test_config.py` | Config defaults, validation, search order, legacy keys |
| `tests/test_cli_and_cache.py` | Command line, exit codes, cache invalidation and permission checks, end-to-end with `ansible-inventory` |
| `tests/test_docs.py` | The operator tables in `docs/expression-syntax.md` match the code |

### Golden file

`tests/golden/example.json` is the expected output for [`example/inventory`](../example/inventory). If you change the example on purpose, regenerate it and review the diff:

```sh
python3 src/ansible-xo-inventory.py --config example/xo_inventory.yaml --list --pretty > tests/golden/example.json
git diff tests/golden/example.json
```

## CI

Every push and pull request runs ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml)):

1. `ruff check`
2. The test suite on Python 3.9 to 3.14
3. Building the `.deb`
4. Installing that `.deb` on Debian 11, 12 and 13 and Ubuntu 22.04 and 24.04, comparing its output with the golden file, then removing and purging it

## Releasing

1. Update the version in `src/xo_inventory/__init__.py`, add an entry to `debian/changelog` (`dch -v X.Y.Z`), and add a `## [X.Y.Z]` section to `CHANGELOG.md`.
2. Merge to `main`, then tag: `git tag vX.Y.Z && git push origin vX.Y.Z`.
3. The [release workflow](../.github/workflows/release.yml) runs CI, checks that the tag matches both version numbers, and publishes a GitHub release with the `.deb` and the changelog section.
