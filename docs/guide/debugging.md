# Debugging

## See what Ansible sees

Run the script directly. Without arguments it pretty-prints the whole inventory:

```sh
ansible-xo-inventory.py
ansible-xo-inventory.py --host pve-01          # one host's variables
ansible-inventory -i /usr/bin/ansible-xo-inventory.py --graph --vars
```

Use `--config path/to/xo_inventory.yaml` to try a different config without touching the real one.

## Errors

Problems that would make the inventory wrong stop the build: Ansible reports the inventory as failed rather than running against a partial one. The message names the file:

```text
ansible-xo-inventory: error: /etc/ansible/inventory/groups/web.yaml: invalid YAML: ...
ansible-xo-inventory: error: .../groups/web.yaml: invalid host_criteria for group 'web': Expected a value after '=', found end of expression
ansible-xo-inventory: error: STORAGE_LOCATION /etc/ansible/inventory does not exist or is not a folder
ansible-xo-inventory: error: Group nesting loop: a -> b -> a
```

Ansible shows these when you add `-vvv`, or you can run the script directly.

## Warnings

Things that are suspicious but not fatal are logged as warnings on stderr:

- A host or group variable set to different values in two files
- Variables in a `_criteria.yaml` file (only `host_criteria` / `enabled` are read there)
- Unexpected files in a group folder
- Unknown or obsolete keys in the config file

## More detail

Set the log level to `DEBUG` to see every file loaded, each group's parsed criteria (with explicit parentheses showing precedence), and how many hosts each criteria matched:

```yaml
logging:
  MIN_LOG_LEVEL: DEBUG
```

To keep a log file as well:

```yaml
logging:
  ENABLE_FILE_LOGGING: true
  LOG_FILE_PATH: ~/.local/state/xo-inventory/inventory.log
```

## Cache

If caching is enabled and you suspect stale output, run with `--no-cache`, or delete `~/.cache/xo-inventory/inventory.json`. The cache is invalidated automatically when any file under `STORAGE_LOCATION` or the config file changes.
