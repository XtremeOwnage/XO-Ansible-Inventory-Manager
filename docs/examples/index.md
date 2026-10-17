---
title: Homelab example
---

# Homelab example

This is the complete example shipped in the repository's [`example/`](https://github.com/XtremeOwnage/XO-Ansible-Inventory-Manager/tree/main/example) folder, and installed with the packages under `/usr/share/doc/xo-ansible-inventory-manager/examples/`. Every file below is included straight from the repository, and the output at the bottom is the test suite's golden file, so this page always matches what the code does.

```text
example/inventory/
├── hosts/
│   ├── all.yaml
│   ├── docker-01.yaml
│   ├── nas.example.com.yaml
│   ├── old-box.yaml             (disabled)
│   ├── pve-01/
│   │   ├── hardware.yaml
│   │   └── main.yaml
│   └── pve-02.yaml
├── groups/
│   ├── all.yml
│   ├── big_iron.yaml
│   ├── proxmox_servers.yaml
│   ├── retired.yaml             (disabled)
│   └── rke/
│       ├── _criteria.yaml
│       ├── groups/
│       │   ├── rke_control_plane.yaml
│       │   └── rke_workers/
│       │       ├── _criteria.yaml
│       │       └── hosts/
│       │           └── rke-worker-01.yaml
│       ├── hosts/
│       │   └── rke-cp-01.yaml
│       └── vars/
│           ├── cluster.yaml
│           └── network.yaml
└── vars/
    ├── common.yaml
    └── dns.yaml
```

## Hosts

=== "pve-01/ (folder)"

    A host can be a folder; its files are merged.

    ```yaml title="hosts/pve-01/main.yaml"
    --8<-- "example/inventory/hosts/pve-01/main.yaml"
    ```

    ```yaml title="hosts/pve-01/hardware.yaml"
    --8<-- "example/inventory/hosts/pve-01/hardware.yaml"
    ```

=== "pve-02.yaml"

    ```yaml title="hosts/pve-02.yaml"
    --8<-- "example/inventory/hosts/pve-02.yaml"
    ```

=== "docker-01.yaml"

    ```yaml title="hosts/docker-01.yaml"
    --8<-- "example/inventory/hosts/docker-01.yaml"
    ```

=== "nas.example.com.yaml"

    ```yaml title="hosts/nas.example.com.yaml"
    --8<-- "example/inventory/hosts/nas.example.com.yaml"
    ```

=== "old-box.yaml"

    ```yaml title="hosts/old-box.yaml"
    --8<-- "example/inventory/hosts/old-box.yaml"
    ```

=== "all.yaml"

    ```yaml title="hosts/all.yaml"
    --8<-- "example/inventory/hosts/all.yaml"
    ```

## Groups

=== "proxmox_servers"

    Membership by criteria, plus group variables.

    ```yaml title="groups/proxmox_servers.yaml"
    --8<-- "example/inventory/groups/proxmox_servers.yaml"
    ```

=== "big_iron"

    A list of criteria: a host matching either joins.

    ```yaml title="groups/big_iron.yaml"
    --8<-- "example/inventory/groups/big_iron.yaml"
    ```

=== "rke (folder)"

    A group defined as a folder, with criteria, its own hosts, variable files and child groups.

    ```yaml title="groups/rke/_criteria.yaml"
    --8<-- "example/inventory/groups/rke/_criteria.yaml"
    ```

    ```yaml title="groups/rke/hosts/rke-cp-01.yaml"
    --8<-- "example/inventory/groups/rke/hosts/rke-cp-01.yaml"
    ```

    ```yaml title="groups/rke/vars/cluster.yaml"
    --8<-- "example/inventory/groups/rke/vars/cluster.yaml"
    ```

    ```yaml title="groups/rke/vars/network.yaml"
    --8<-- "example/inventory/groups/rke/vars/network.yaml"
    ```

=== "rke children"

    ```yaml title="groups/rke/groups/rke_control_plane.yaml"
    --8<-- "example/inventory/groups/rke/groups/rke_control_plane.yaml"
    ```

    ```yaml title="groups/rke/groups/rke_workers/_criteria.yaml"
    --8<-- "example/inventory/groups/rke/groups/rke_workers/_criteria.yaml"
    ```

    ```yaml title="groups/rke/groups/rke_workers/hosts/rke-worker-01.yaml"
    --8<-- "example/inventory/groups/rke/groups/rke_workers/hosts/rke-worker-01.yaml"
    ```

=== "retired"

    ```yaml title="groups/retired.yaml"
    --8<-- "example/inventory/groups/retired.yaml"
    ```

=== "all"

    ```yaml title="groups/all.yml"
    --8<-- "example/inventory/groups/all.yml"
    ```

    ```yaml title="vars/dns.yaml"
    --8<-- "example/inventory/vars/dns.yaml"
    ```

    ```yaml title="vars/common.yaml"
    --8<-- "example/inventory/vars/common.yaml"
    ```

## Config

```yaml title="xo_inventory.yaml"
--8<-- "example/xo_inventory.yaml"
```

## Result

What to notice:

- `old-box` and `retired` are gone: `enabled: false`.
- `pve-01` and `pve-02` are in `proxmox_servers` by criteria. They're also in `big_iron`: `pve-02` through `cores >= 16`, and `pve-01` through both entries.
- `rke-cp-01` is in `rke` because it's in `rke/hosts/`. `rke-worker-01` is in `rke_workers`, a child of `rke`, so it inherits the `rke` variables.
- `docker-01` and `nas.example.com` match no group, so they're listed under `ungrouped`.
- Every host has `ansible_user: ansible` from `hosts/all.yaml`, and `all` carries the `vars/` files.

```json title="ansible-xo-inventory.py --list"
--8<-- "tests/golden/example.json"
```

The same inventory as Ansible sees it:

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
