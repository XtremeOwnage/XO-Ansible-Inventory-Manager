# Configuration

All settings live in `xo_inventory.yaml`. Only `main.STORAGE_LOCATION` is required; everything else has a default. The [example config](https://github.com/XtremeOwnage/XO-Ansible-Inventory-Manager/blob/main/example/xo_inventory.yaml) lists every setting with its default value and a comment.

## Where the config file is found

The first match wins:

1. `--config <path>` on the command line
2. The `XO_INVENTORY_CONFIG` environment variable
3. `xo_inventory.yaml` in the current directory (where you run `ansible` from), handy for per-project inventories
4. `~/.config/xo-inventory/xo_inventory.yaml` (respects `$XDG_CONFIG_HOME`)
5. `/etc/ansible/xo_inventory.yaml`, installed by the `.deb` package

If `--config` or `XO_INVENTORY_CONFIG` names a file that doesn't exist, that's an error. The script won't silently fall back to another file.

Relative paths in the config (`STORAGE_LOCATION`, `LOG_FILE_PATH`, `CACHE_LOCATION`) are relative to the **config file's folder**, so the inventory resolves the same wherever Ansible is run from. `~` and `$VARIABLES` are expanded.

## Settings

### `main`

| Key | Default | Description |
|---|---|---|
| `STORAGE_LOCATION` | *(required)* | Folder containing `hosts/`, `groups/` and `vars/` |

### `logging`

Log messages go to **stderr** (stdout carries the JSON for Ansible), and optionally to a file.

| Key | Default | Description |
|---|---|---|
| `MIN_LOG_LEVEL` | `WARNING` | `DEBUG`, `INFO`, `WARNING`, `ERROR` or `CRITICAL` |
| `LOG_FORMAT` | `%(asctime)s %(levelname)s %(module)s.%(funcName)s: %(message)s` | [Python logging format](https://docs.python.org/3/library/logging.html#logrecord-attributes) |
| `LOG_TIMESTAMP_FORMAT` | `%Y-%m-%dT%H:%M:%S` | `strftime` format for `%(asctime)s` |
| `ENABLE_FILE_LOGGING` | `false` | Also log to `LOG_FILE_PATH`. If the file can't be opened, a warning is printed and the inventory still works |
| `LOG_FILE_PATH` | *(none)* | Required when file logging is on |
| `ENABLE_LOG_ROTATION` | `true` | Rotate the log file by size |
| `LOG_FILE_MAX_SIZE` | `10485760` | Bytes before rotating |
| `LOG_FILE_BACKUP_COUNT` | `3` | Rotated files to keep |

### `directories`

| Key | Default | Description |
|---|---|---|
| `HOST_VARS_FOLDER` | `hosts` | Host folder name, at the top level and inside group folders |
| `GROUP_VARS_FOLDER` | `groups` | Group folder name, at the top level and inside group folders (child groups) |
| `VARS_FOLDER` | `vars` | Variable-file folder name: top level (merged into `all`) and inside group folders |
| `LOADER_YAML_EXTENSIONS` | `['.yaml', '.yml']` | File extensions to load. Contents must be YAML regardless |

### `special-keys`

| Key | Default | Description |
|---|---|---|
| `HOST_CRITERIA_VAR` | `host_criteria` | Group variable holding the [criteria expression](criteria.md) |
| `KEY_ENABLED` | `enabled` | Set to `false` to leave a host, group or vars file out |
| `GROUP_CRITERIA_FILE` | `_criteria.yaml` | File in a group folder holding its criteria / enabled flag |

### `features`

| Key | Default | Description |
|---|---|---|
| `ADD_ALL_HOSTS_TO_ALL_GROUP` | `true` | List every host under `all.hosts` |
| `MERGE_HOST_ALL_VARS` | `true` | Copy `hosts/all.yaml` variables into hosts that don't set them |
| `EVALUATE_GROUP_CRITERIA` | `true` | Evaluate `host_criteria`. When off, only folder-based membership is used |

### `sorting`

Purely cosmetic; Ansible ignores order. With sorting on, the output is in alphabetical order (`all` first, `_meta` last).

| Key | Default | Description |
|---|---|---|
| `SORT_ENABLED` | `true` | Master switch for the keys below |
| `SORT_GROUP_KEYS` | `true` | Order of groups |
| `SORT_HOSTVAR_KEYS` | `true` | Order of hosts in `_meta.hostvars` |
| `SORT_HOSTVAR_VARS` | `true` | Order of each host's variables |
| `SORT_GROUP_VARS` | `true` | Order of each group's variables |
| `SORT_GROUP_HOSTS` | `true` | Order of each group's host list |
| `SORT_GROUP_CHILDREN` | `true` | Order of each group's children |

### `cache`

Building the inventory is fast (milliseconds for hundreds of files), so the cache is off by default.

| Key | Default | Description |
|---|---|---|
| `CACHE_ENABLED` | `false` | Reuse the last built inventory when nothing has changed |
| `CACHE_LOCATION` | `~/.cache/xo-inventory/inventory.json` | Cache file (respects `$XDG_CACHE_HOME`) |

The cache is rebuilt whenever the config file, or the name, size or modification time of anything under `STORAGE_LOCATION`, changes. Run with `--no-cache` to bypass it once.

Cached variables are handed to Ansible, and some (like `ansible_ssh_common_args`) can run commands. So the cache is written with `0600` permissions and only read back if it's a regular file (not a symlink) owned by the current user and not writable by anyone else.

## Legacy settings

These are accepted so old config files keep working, but they have no effect and log a warning:

| Setting | Why |
|---|---|
| `keys:` section | Output key names are fixed by Ansible's inventory format |
| `logging.CUSTOM_LOG_FORMAT` | Use `%(module)s` / `%(funcName)s` in `LOG_FORMAT` |
| `logging.EXIT_ON_ERROR`, `logging.EXIT_ON_FATAL` | Errors always stop the build with a non-zero exit code |
| `debugging.DEBUG_EVALUATOR_SHUNTING_YARD` | Use `MIN_LOG_LEVEL: DEBUG` |

Unknown keys are also reported as warnings, which catches typos.
