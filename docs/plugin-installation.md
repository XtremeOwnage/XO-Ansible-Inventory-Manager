# Installation

Requirements: Python 3.9+ and PyYAML, both already present on any machine that runs Ansible.

## Debian / Ubuntu package (recommended)

Download the `.deb` from the [latest release](https://github.com/XtremeOwnage/XO-Ansible-Inventory-Manager/releases/latest), then:

```sh
sudo apt install ./xo-ansible-inventory-manager_1.0.0_all.deb
```

This installs:

| Path | What |
|---|---|
| `/usr/bin/ansible-xo-inventory.py` | The inventory script (symlink) |
| `/usr/lib/xo-ansible-inventory-manager/` | The code |
| `/etc/ansible/xo_inventory.yaml` | Config file, kept across upgrades |
| `/usr/share/doc/xo-ansible-inventory-manager/` | Docs and the example inventory |

Then:

1. Set `STORAGE_LOCATION` in `/etc/ansible/xo_inventory.yaml` (the default, `inventory`, means `/etc/ansible/inventory`).
2. Tell Ansible to use the script, either in `ansible.cfg`:

   ```ini
   [defaults]
   inventory = /usr/bin/ansible-xo-inventory.py
   ```

   or per command: `ansible-playbook -i /usr/bin/ansible-xo-inventory.py site.yml`.
3. Check it: `ansible-inventory -i /usr/bin/ansible-xo-inventory.py --graph`

Tested on Debian 11–13 and Ubuntu 22.04 / 24.04.

## From a git checkout

```sh
git clone https://github.com/XtremeOwnage/XO-Ansible-Inventory-Manager.git
cd XO-Ansible-Inventory-Manager
cp example/xo_inventory.yaml .   # then edit STORAGE_LOCATION
ansible-inventory -i src/ansible-xo-inventory.py --graph
```

`src/ansible-xo-inventory.py` works from anywhere, including through a symlink.

## With pip / pipx

```sh
pipx install git+https://github.com/XtremeOwnage/XO-Ansible-Inventory-Manager.git
ansible-inventory -i "$(command -v ansible-xo-inventory)" --graph
```

## Upgrading from a pre-1.0 build

- **Config:** existing files keep working. Settings that no longer apply are reported as warnings (see [configuration](./plugin-configuration.md#settings-from-before-10)). File logging and caching are now **off by default**; turn them back on if you relied on them.
- **Criteria language:** `NOT` now applies only to the clause or parenthesised group right after it, so `NOT a = 1 AND b = 2` means `(NOT a = 1) AND b = 2`. Before 1.0 it negated the whole rest of the expression. `MATCH` now searches anywhere in the value; use `^` to anchor it.
- **Errors stop the build:** invalid YAML, an invalid criteria expression or a missing `STORAGE_LOCATION` makes the script exit with an error, instead of quietly producing a partial inventory.

## Removing

```sh
sudo apt remove xo-ansible-inventory-manager   # keeps /etc/ansible/xo_inventory.yaml
sudo apt purge xo-ansible-inventory-manager    # also removes the config
```

The optional cache lives in `~/.cache/xo-inventory/`; delete it by hand if you enabled caching.
