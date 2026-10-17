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
| `tests/test_docs.py` | The operator tables in `docs/guide/criteria.md` match the code |
| `tests/test_recipes.py` | Every `host_criteria` in the docs is valid, and the [recipes](../examples/recipes.md) behave as described |

### Golden file

`tests/golden/example.json` is the expected output for [`example/inventory`](https://github.com/XtremeOwnage/XO-Ansible-Inventory-Manager/tree/main/example/inventory). If you change the example on purpose, regenerate it and review the diff:

```sh
python3 src/ansible-xo-inventory.py --config example/xo_inventory.yaml --list --pretty > tests/golden/example.json
git diff tests/golden/example.json
```

## CI

Every push and pull request runs ([`.github/workflows/ci.yml`](https://github.com/XtremeOwnage/XO-Ansible-Inventory-Manager/blob/main/.github/workflows/ci.yml)):

1. `ruff check`
2. The test suite on Python 3.9 to 3.14
3. Building this documentation site with [Netdocs](https://github.com/XtremeOwnage/Netdocs) in strict mode, so broken links, anchors and orphan pages fail the build
4. Building the `.deb` (debhelper) and `.rpm` ([nfpm](https://nfpm.goreleaser.com/), from `packaging/nfpm.yaml`), and checking they install the same files
5. Installing each package on Debian 11–13, Ubuntu 22.04/24.04, Fedora and AlmaLinux 9/10, comparing its output with the golden file, then removing it

## Releasing

1. Update the version in `src/xo_inventory/__init__.py`, add an entry to `debian/changelog` (`dch -v X.Y.Z`), and add a `## [X.Y.Z]` section to `CHANGELOG.md`.
2. Merge to `main`, then tag: `git tag vX.Y.Z && git push origin vX.Y.Z`.
3. The [release workflow](https://github.com/XtremeOwnage/XO-Ansible-Inventory-Manager/blob/main/.github/workflows/release.yml) runs CI, checks that the tag matches both version numbers, and publishes a GitHub release with the `.deb`, the `.rpm`, their SHA-256 checksums, and the changelog section.

## Documentation site

The site is built from `docs/` with [Netdocs](https://github.com/XtremeOwnage/Netdocs), configured in `netdocs.json`. Preview it locally:

```sh
netdocs serve --config netdocs.json
```

Pages can include repository files with `--8<-- "path/from/repo/root"`. The [homelab example](../examples/index.md) uses this to show the real example files and golden output. Every push to `main` publishes the site to GitHub Pages.
