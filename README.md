# XO Ansible Inventory Manager

A dynamic [Ansible](https://www.ansible.com/) inventory built from a folder of YAML files.

- **One file per host, one file (or folder) per group.** Nested folders make child groups.
- **Groups that fill themselves.** `host_criteria: app = proxmox AND cores >= 16` puts every matching host in the group.
- **`enabled: false`** switches a host or a whole group tree off without deleting anything.
- **Fails loudly.** Bad YAML or a bad expression stops Ansible with a clear error, instead of running against half an inventory.

```
inventory/
├── hosts/
│   ├── pve-01.yaml               ansible_host: 10.100.4.10
│   │                             app: proxmox
│   └── docker-01.yaml
├── groups/
│   ├── proxmox_servers.yaml      host_criteria: app = proxmox
│   └── rke/
│       ├── _criteria.yaml        host_criteria: labels CONTAINS kubernetes
│       ├── hosts/                (hosts that are always in "rke")
│       ├── vars/                 (variables for "rke")
│       └── groups/               (child groups of "rke")
└── vars/
    └── dns.yaml                  (variables for every host)
```

```
$ ansible-inventory -i /usr/bin/ansible-xo-inventory.py --graph
@all:
  |--@ungrouped:
  |  |--docker-01
  |--@proxmox_servers:
  |  |--pve-01
  |--@rke:
  |  |--@rke_workers:
  ...
```

## Quick start

1. Install the `.deb` from the [latest release](https://github.com/XtremeOwnage/XO-Ansible-Inventory-Manager/releases/latest):

   ```sh
   sudo apt install ./xo-ansible-inventory-manager_*_all.deb
   ```

2. Point `STORAGE_LOCATION` in `/etc/ansible/xo_inventory.yaml` at your inventory folder:

   ```yaml
   main:
     STORAGE_LOCATION: /home/you/ansible/inventory
   ```

3. Use it:

   ```sh
   ansible-inventory -i /usr/bin/ansible-xo-inventory.py --graph
   ```

   or set `inventory = /usr/bin/ansible-xo-inventory.py` in `ansible.cfg`.

Not on Debian/Ubuntu? Run it from a git checkout or install with pipx; see [installation](docs/plugin-installation.md).

## Documentation

| | |
|---|---|
| [Building an inventory](docs/building-inventory.md) | Folder layout, hosts, groups, `enabled`, variable merging |
| [Criteria expressions](docs/expression-syntax.md) | The `host_criteria` language and every operator |
| [Configuration](docs/plugin-configuration.md) | `xo_inventory.yaml` settings and where it's looked for |
| [Installation](docs/plugin-installation.md) | `.deb`, git checkout, pipx, upgrading, removal |
| [Debugging](docs/debugging.md) | Inspecting output, errors, logging |
| [Testing](docs/testing.md) | Running the tests, CI, releasing |

A complete example is in [`example/`](example/): an [inventory](example/inventory), a [config](example/xo_inventory.yaml), and the [output it produces](tests/golden/example.json).

## Expression examples

```yaml
host_criteria: app = proxmox
host_criteria: type = bare-metal AND cores >= 16
host_criteria: (app = proxmox AND type = lxc) OR ansible_host = "10.100.4.100"
host_criteria: NOT app LIKE 'prox*'
host_criteria: ansible_host MATCH "^10\.100\.5\."
host_criteria: labels CONTAINS gpu
host_criteria: vlan IN (10, 20, 30)
host_criteria: decommissioned IS NULL
```

## Roadmap

Ideas for after 1.0 are tracked as [issues](https://github.com/XtremeOwnage/XO-Ansible-Inventory-Manager/issues), including:

- IP / subnet operators (`ansible_host INSUBNET 10.100.4.0/24`)
- Group criteria based on group membership
- Proxmox discovery of nodes, VMs and LXCs
- Packaging as an Ansible inventory plugin / Galaxy collection

## License

[GPL-3.0](LICENSE). Contributions welcome; see [CONTRIBUTING.md](CONTRIBUTING.md).
