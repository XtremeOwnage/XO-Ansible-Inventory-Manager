---
title: Quick start
---

# Quick start

This walks through a small inventory from scratch. It assumes the package is [installed](installation.md); from a git checkout, use `src/ansible-xo-inventory.py` wherever this page says `ansible-xo-inventory.py`.

## 1. Create the inventory folder

```sh
mkdir -p ~/ansible/inventory/{hosts,groups,vars}
cd ~/ansible
```

## 2. Point the config at it

Create `xo_inventory.yaml` in the folder you run Ansible from. It's found there automatically; see [where the config file is found](../guide/configuration.md#where-the-config-file-is-found).

```yaml
# ~/ansible/xo_inventory.yaml
main:
  STORAGE_LOCATION: inventory   # relative to this file
```

## 3. Add some hosts

Each file in `hosts/` is one host. The file name is the host name, and the contents are its variables.

```yaml
# inventory/hosts/web-01.yaml
ansible_host: 10.0.0.11
role: web
env: prod
```

```yaml
# inventory/hosts/web-02.yaml
ansible_host: 10.0.0.12
role: web
env: staging
```

```yaml
# inventory/hosts/db-01.yaml
ansible_host: 10.0.0.21
role: database
env: prod
```

## 4. Add groups with criteria

A group file holds the group's variables and, optionally, `host_criteria`. Every host matching the criteria joins the group.

```yaml
# inventory/groups/webservers.yaml
host_criteria: role = web
http_port: 80
```

```yaml
# inventory/groups/production.yaml
host_criteria: env = prod
```

Variables for every host go in `vars/`:

```yaml
# inventory/vars/common.yaml
ansible_user: deploy
ntp_server: 10.0.0.1
```

## 5. Look at the result

```console
$ ansible-inventory -i /usr/bin/ansible-xo-inventory.py --graph
@all:
  |--@ungrouped:
  |--@production:
  |  |--db-01
  |  |--web-01
  |--@webservers:
  |  |--web-01
  |  |--web-02
```

`ansible-inventory --host` shows a host's variables with group and `all` variables applied, exactly as playbooks will see them:

```console
$ ansible-inventory -i /usr/bin/ansible-xo-inventory.py --host web-01
{
    "ansible_host": "10.0.0.11",
    "ansible_user": "deploy",
    "env": "prod",
    "http_port": 80,
    "ntp_server": "10.0.0.1",
    "role": "web"
}
```

`ansible-xo-inventory.py --host web-01` prints only the host's own variables, and running `ansible-xo-inventory.py` with no arguments pretty-prints the whole inventory as Ansible receives it.

## 6. Use it

```sh
ansible -i /usr/bin/ansible-xo-inventory.py webservers -m ping
```

Or set it once in `ansible.cfg` next to `xo_inventory.yaml`:

```ini
[defaults]
inventory = /usr/bin/ansible-xo-inventory.py
```

## Next steps

- Group hosts with folders, nested child groups and `enabled: false`: [inventory layout](../guide/inventory-layout.md)
- Everything `host_criteria` can do: [criteria expressions](../guide/criteria.md)
- A larger, complete example: [examples](../examples/index.md)
