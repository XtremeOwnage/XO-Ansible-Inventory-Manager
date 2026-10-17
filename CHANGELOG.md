# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [semantic versioning](https://semver.org/).

## [1.0.0] - 2026-10-17

First stable release. The pre-1.0 development code was largely rewritten.

### Added

- Folder-based inventory layout: `hosts/` (file or folder per host), `groups/` (file and/or folder per group, with `_criteria.yaml`, `hosts/`, `vars/` and nested `groups/`), and top-level `vars/` merged into `all`.
- `host_criteria` may be a list; a host matching any entry joins the group.
- Criteria operators: `IN (a, b, c)` lists, `CONTAINS`, `CLIKE`, `EMPTY`, `NEZ`, `IS NULL` / `IS NOT NULL`, `NOTLIKE`, `NOTCONTAINS`, `<>`, and `!` as `NOT`.
- Dotted variable names in criteria (`net.vlan`, `disks.0.size`).
- `--config`, `--no-cache`, `--pretty` and `--version` options; `XO_INVENTORY_CONFIG` environment variable; `~/.config/xo-inventory/xo_inventory.yaml` config location.
- Warnings for conflicting variable definitions, stray files in group folders, and unknown config keys.
- Test suite (Python 3.9–3.14) with an end-to-end check against `ansible-inventory`, and CI that installs the `.deb` on Debian 11–13 and Ubuntu 22.04/24.04.
- `pyproject.toml`, so the tool can also be installed with pip/pipx.

### Changed

- Output now follows Ansible's inventory script format (`_meta.hostvars`). Hosts not in any group are listed under `ungrouped`.
- The criteria parser was rewritten. `NOT` binds to the clause or group right after it (`NOT a=1 AND b=2` is `(NOT a=1) AND b=2`), and `AND` binds tighter than `OR`.
- `MATCH` searches anywhere in the value (anchor with `^`/`$`); `LIKE` matches the whole value.
- Booleans compare with `true`/`false`; numbers compare numerically even when stored as strings.
- Every config setting has a default; only `STORAGE_LOCATION` is required. Relative paths are relative to the config file.
- Config file search order: `--config`, `$XO_INVENTORY_CONFIG`, `./`, `~/.config/xo-inventory/`, `/etc/ansible/`.
- Logging goes to stderr only by default; file logging is opt-in and never breaks the inventory.
- The cache is opt-in, lives in `~/.cache/xo-inventory/`, is invalidated whenever the inventory or config changes, and is only trusted if owned by the current user and not writable by others.
- Debian packaging updated to debhelper 13; `/usr/bin/ansible-xo-inventory.py` is now a package-managed symlink.

### Fixed

- The inventory could not run at all (syntax error, missing loader method).
- Host variables were emitted under `_meta.host_vars`, which Ansible ignores.
- Quoted criteria values containing spaces or regex characters were rejected.
- `IS NULL` and `ANY` raised errors; `GTZ`/`EQZ`/`LTZ` crashed on missing values.
- Each folder was re-read once per file, and every log call inspected the call stack, making evaluation slow.
- Invalid YAML and invalid criteria were silently skipped, dropping hosts from the inventory.
- `_criteria.yaml` criteria were never applied.
- Host names containing dots were truncated.
- A cache in `/tmp` could be pre-created by another user to inject host variables.

### Removed

- The `keys` config section, `CUSTOM_LOG_FORMAT`, `EXIT_ON_ERROR`, `EXIT_ON_FATAL` and `DEBUG_EVALUATOR_SHUNTING_YARD`. They are still accepted, with a warning.
- `run-tests` and `test-deb` helper scripts (use `pytest` and CI).
