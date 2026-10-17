# Building an inventory

The inventory lives in the folder named by `STORAGE_LOCATION` in the [configuration](./plugin-configuration.md). A complete working example is in [`example/inventory`](../example/inventory), and its output is in [`tests/golden/example.json`](../tests/golden/example.json).

```
inventory/
├── hosts/                         Hosts: one file or one folder per host
│   ├── all.yaml                   Defaults for every host (optional, lowest priority)
│   ├── pve-01/                    Host "pve-01": all YAML files inside are merged
│   │   ├── main.yaml
│   │   └── hardware.yaml
│   ├── pve-02.yaml                Host "pve-02"
│   └── nas.example.com.yaml       Host "nas.example.com" (dots are fine)
├── groups/                        Groups: one file and/or one folder per group
│   ├── all.yml                    Variables for the "all" group
│   ├── proxmox_servers.yaml       Group "proxmox_servers": variables + host_criteria
│   └── rke/                       Group "rke" defined as a folder
│       ├── _criteria.yaml         host_criteria / enabled for "rke"
│       ├── hosts/                 Hosts defined here are members of "rke"
│       │   └── rke-cp-01.yaml
│       ├── vars/                  Variable files for "rke", merged
│       │   ├── cluster.yaml
│       │   └── network.yaml
│       └── groups/                Child groups of "rke" (same layout as groups/)
│           ├── rke_control_plane.yaml
│           └── rke_workers/
│               ├── _criteria.yaml
│               └── hosts/
│                   └── rke-worker-01.yaml
└── vars/                          Variable files merged into the "all" group
    ├── common.yaml
    └── dns.yaml
```

Every folder is optional. Files must end in `.yaml` or `.yml` (configurable) and contain `key: value` pairs; an empty or comment-only file is fine. Other files, and files starting with `.`, are ignored.

## Hosts

A host is either `hosts/<name>.yaml` or a folder `hosts/<name>/`, whose YAML files are merged in alphabetical order. The file or folder name is the host name, minus the extension.

```yaml
# hosts/pve-02.yaml
ansible_host: 10.100.4.11
app: proxmox
type: bare-metal
cores: 16
```

Hosts can also be defined inside a group's `hosts/` folder, which makes them members of that group. Hosts are global, as in Ansible: if the same host name appears in several places, its variables are merged. A key set to two different values logs a warning, and the file loaded later wins. Files are loaded in path order: `hosts/` first, then `groups/` alphabetically.

### `hosts/all.yaml`

Its variables are copied into every host that doesn't set them itself. Turn it off with `MERGE_HOST_ALL_VARS: false`.

Because they end up as *host* variables, Ansible gives them priority over group variables. For defaults that groups should be able to override, use `groups/all.yaml` or the top-level `vars/` folder instead.

## Groups

A group is `groups/<name>.yaml`, a folder `groups/<name>/`, or both. The YAML file holds the group's variables and, optionally, `host_criteria`:

```yaml
# groups/proxmox_servers.yaml
host_criteria: app = proxmox

ansible_connection: ssh
ansible_port: 22
```

A group folder may contain:

| Entry | Purpose |
|---|---|
| `_criteria.yaml` | `host_criteria` and/or `enabled` for the group. Other keys are ignored with a warning; put variables in `vars/` |
| `hosts/` | Hosts that belong to the group, same format as the top-level `hosts/` |
| `vars/` | Variable files for the group, merged in alphabetical order |
| `groups/` | Child groups, same format as the top-level `groups/`, nested as deep as you like |

Anything else in a group folder is ignored with a warning.

A group's members are the hosts in its `hosts/` folder plus every host matching its `host_criteria` (see [criteria expressions](./expression-syntax.md)). Criteria are evaluated against each host's own variables (including `hosts/all.yaml` defaults), not against group variables.

Like hosts, groups are global: the same group name in two places is one group, which is how a group gets several parents. A group may define `host_criteria` in only one place. A group can't contain itself, directly or indirectly; that's reported as a "group nesting loop" error.

Use letters, digits and underscores in group names. Ansible warns about other characters such as `-`.

### Special groups

- **`all`**: `groups/all.yaml` and every file in the top-level `vars/` folder are merged into the `all` group's variables. `host_criteria` is ignored for `all`. Every group without a parent is listed as a child of `all`.
- **`ungrouped`**: Hosts that are in no group get listed here automatically. You can't define it yourself.

## Turning things off: `enabled: false`

Any host or group can be switched off without deleting it:

| Where | Effect |
|---|---|
| `hosts/web1.yaml`, or any file in `hosts/web1/` | Host `web1` is removed from the whole inventory, including groups that list it |
| `groups/web.yaml`, or `groups/web/_criteria.yaml` | Group `web` is removed, and everything inside `groups/web/` (hosts, child groups) is skipped |
| A file in a `vars/` folder | Just that file is skipped |

The `enabled` key itself never appears in the output. Its name is configurable (`KEY_ENABLED`).

## Variable precedence

The inventory hands Ansible group variables and host variables separately, and Ansible applies its normal [precedence rules](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_variables.html#understanding-variable-precedence): host variables beat group variables, child groups beat parent groups, and every group beats `all`.

Within one host or group, variables from several files are merged:

- Dictionaries are merged key by key, recursively.
- Lists are combined: items from the later file are appended unless already present.
- Anything else: the later file wins (with a warning if the values differ).

## Output

Run the script yourself to see what Ansible will see:

```sh
ansible-xo-inventory.py            # pretty-printed
ansible-xo-inventory.py --list     # compact, as Ansible calls it
ansible-xo-inventory.py --host pve-01
ansible-inventory -i /usr/bin/ansible-xo-inventory.py --graph --vars
```
