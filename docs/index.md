---
title: Home
---

# XO Ansible Inventory Manager

A dynamic [Ansible](https://www.ansible.com/) inventory built from a folder of YAML files.

Write one small file per host and per group, and let **criteria expressions** sort hosts into groups for you:

```yaml
# groups/big_iron.yaml
host_criteria: cores >= 16 AND type = bare-metal
ansible_user: root
```

```console
$ ansible-inventory -i /usr/bin/ansible-xo-inventory.py --graph
@all:
  |--@ungrouped:
  |  |--docker-01
  |  |--nas.example.com
  |--@big_iron:
  |  |--pve-01
  |  |--pve-02
  |--@proxmox_servers:
  |  |--pve-01
  |  |--pve-02
  |--@rke:
  |  |--@rke_control_plane:
  |  |--@rke_workers:
  |  |  |--rke-worker-01
  |  |--rke-cp-01
```

## Features

- **Files and folders, not one giant `hosts.ini`.** Each host is a file (or a folder of files); each group is a file, a folder, or both. Folders nest to make child groups.
- **Groups that fill themselves.** `host_criteria` selects hosts by their variables: `cores >= 16`, `labels CONTAINS gpu`, `ansible_host MATCH "^10\.100\.5\."`, combined with `AND`, `OR`, `NOT` and parentheses.
- **Switch things off.** `enabled: false` removes a host, or a whole group tree, without deleting anything.
- **Fails loudly.** Invalid YAML or a bad expression stops Ansible with an error naming the file, instead of silently running against half an inventory.
- **No dependencies beyond Ansible's own.** Python 3.9+ and PyYAML. Packages for Debian/Ubuntu and Fedora/RHEL.

## Where next

| | |
|---|---|
| [Installation](getting-started/installation.md) | `.deb`, `.rpm`, git checkout or pipx |
| [Quick start](getting-started/quickstart.md) | Build a working inventory in five minutes |
| [Inventory layout](guide/inventory-layout.md) | How hosts, groups and variables are laid out and merged |
| [Criteria expressions](guide/criteria.md) | The `host_criteria` language, every operator |
| [Configuration](guide/configuration.md) | `xo_inventory.yaml` settings |
| [Examples](examples/index.md) | A complete homelab inventory and its output |
| [Recipes](examples/recipes.md) | Common patterns, ready to copy |
