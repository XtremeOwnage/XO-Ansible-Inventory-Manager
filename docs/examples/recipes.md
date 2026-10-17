---
title: Recipes
---

# Recipes

Short patterns for common inventory layouts. Each one is a few files you can drop into your own inventory. The test suite checks the behaviour shown here.

## Environments from a variable

Tag each host with its environment and let groups collect them.

```yaml title="hosts/web-01.yaml"
env: prod
role: web
```

```yaml title="groups/prod.yaml"
host_criteria: env = prod
```

```yaml title="groups/staging.yaml"
host_criteria: env = staging
```

Combine conditions for narrower groups:

```yaml title="groups/prod_web.yaml"
host_criteria: env = prod AND role = web
```

## Group by host name

Criteria can use `inventory_hostname`, so naming conventions work without extra variables:

```yaml title="groups/webservers.yaml"
host_criteria: inventory_hostname LIKE 'web-*'
```

```yaml title="groups/numbered_db.yaml"
host_criteria: inventory_hostname MATCH '^db-\d+$'
```

## Group by network

Match addresses with a regular expression, anchored at the start:

```yaml title="groups/vlan_5.yaml"
host_criteria: ansible_host MATCH '^10\.100\.5\.'
```

!!! note
    Proper subnet matching (`INSUBNET 10.100.5.0/24`) is planned; see the [roadmap issue](https://github.com/XtremeOwnage/XO-Ansible-Inventory-Manager/issues/3).

## Labels and feature flags

Lists make good labels. `CONTAINS` checks for one entry, `IN (...)` for any of several, and `ANY` for a non-empty list.

```yaml title="hosts/nas-01.yaml"
labels: [backup, nfs]
```

```yaml title="groups/backup_targets.yaml"
host_criteria: labels CONTAINS backup
```

```yaml title="groups/storage.yaml"
host_criteria: labels IN (nfs, iscsi, smb)
```

```yaml title="groups/labelled.yaml"
host_criteria: labels ANY
```

## Several ways in

A list of criteria means "any of these". It's easier to read than one long `OR`:

```yaml title="groups/needs_gpu_driver.yaml"
host_criteria:
  - labels CONTAINS gpu
  - gpu_model IS NOT NULL
  - inventory_hostname LIKE 'ml-*'
```

## Exclude hosts in maintenance

```yaml title="groups/patch_tonight.yaml"
host_criteria: env = prod AND NOT maintenance = true
```

`NOT maintenance = true` also selects hosts that don't set `maintenance` at all, which is usually what you want.

## Pin a host into a group, plus criteria

Hosts in a group folder's `hosts/` are always members. Criteria add more on top.

```text
groups/monitoring/
├── _criteria.yaml        host_criteria: labels CONTAINS monitored
└── hosts/
    └── prometheus-01.yaml
```

## A Kubernetes cluster as a folder

Group folders nest, so one folder can describe a whole cluster: shared variables, control-plane and worker child groups, and the hosts themselves.

```text
groups/k8s/
├── vars/
│   └── cluster.yaml          k8s_version: v1.31.2
└── groups/
    ├── k8s_control_plane/
    │   ├── _criteria.yaml    host_criteria: k8s_role = control-plane
    │   └── hosts/
    │       ├── cp-01.yaml    k8s_role: control-plane
    │       └── cp-02.yaml    k8s_role: control-plane
    └── k8s_workers/
        ├── _criteria.yaml    host_criteria: k8s_role = worker
        └── hosts/
            └── worker-01.yaml
```

Every host in either child group inherits `k8s_version` from `k8s`. Target the whole cluster with `-l k8s`, or one role with `-l k8s_workers`.

## Split a host into several files

A host folder keeps unrelated settings apart, for example generated hardware facts next to hand-written settings:

```text
hosts/pve-01/
├── main.yaml          ansible_host, app, role
├── hardware.yaml      cores, memory, disks (generated)
└── secrets.yaml       vaulted values
```

## Secrets with Ansible Vault

Inline vault values work in any host, group or vars file:

```yaml title="hosts/db-01/secrets.yaml"
db_password: !vault |
  $ANSIBLE_VAULT;1.1;AES256
  6236326531...
```

They're passed to Ansible still encrypted, and Ansible decrypts them as usual (`--vault-password-file`, `--ask-vault-pass`, …). `!unsafe` works too. Files encrypted as a whole with `ansible-vault encrypt` are not supported; use inline values.

## Retire without deleting

```yaml title="hosts/old-box.yaml"
enabled: false
ansible_host: 10.100.4.99
```

The host disappears from every group. Put `enabled: false` in a group file or `_criteria.yaml` to drop the group and everything inside its folder.

## Per-project inventories

Because `./xo_inventory.yaml` is checked first, each project can carry its own inventory next to its playbooks:

```text
my-project/
├── ansible.cfg           inventory = /usr/bin/ansible-xo-inventory.py
├── xo_inventory.yaml     main: { STORAGE_LOCATION: inventory }
├── inventory/
└── site.yml
```

Run `ansible-playbook site.yml` from `my-project/` and that project's inventory is used.
