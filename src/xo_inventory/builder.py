"""
Turns the loaded inventory model into the JSON structure Ansible expects from an
inventory script:

    {
      "_meta": {"hostvars": {"web1": {...}}},
      "all": {"children": ["web", "ungrouped"], "hosts": [...], "vars": {...}},
      "web": {"hosts": ["web1"], "vars": {...}, "children": [...]},
      "ungrouped": {"hosts": [...]}
    }

See https://docs.ansible.com/ansible/latest/dev_guide/developing_inventory.html
"""
from __future__ import annotations

import copy

from .config import Config
from .loader import ALL_GROUP, UNGROUPED_GROUP, InventoryData, InventoryError, load_inventory
from .log import logger

META = "_meta"
HOSTVARS = "hostvars"
HOSTS = "hosts"
VARS = "vars"
CHILDREN = "children"


def _check_cycles(children: dict[str, list[str]]) -> None:
    """Raise if a group is (indirectly) its own child; Ansible rejects such inventories."""
    VISITING, DONE = 1, 2
    state: dict[str, int] = {}

    def visit(name: str, path: list[str]) -> None:
        state[name] = VISITING
        for child in children.get(name, []):
            if state.get(child) == VISITING:
                cycle = path[path.index(child):] + [child] if child in path else [name, child]
                raise InventoryError("Group nesting loop: " + " -> ".join(cycle))
            if state.get(child) is None:
                visit(child, path + [child])
        state[name] = DONE

    for name in children:
        if state.get(name) is None:
            visit(name, [name])


def build_from_data(data: InventoryData, config: Config) -> dict:
    """Build Ansible inventory JSON from loaded data."""
    # Host variables
    hostvars: dict[str, dict] = {}
    for name, host in data.hosts.items():
        host_vars = copy.deepcopy(host.vars)
        if config.merge_host_all_vars:
            # hosts/all.yaml: lowest priority, only fills in what the host does not set.
            for key, value in data.host_all_vars.items():
                host_vars.setdefault(key, copy.deepcopy(value))
        hostvars[name] = host_vars

    # Groups (minus disabled ones), with membership limited to known hosts / groups
    disabled = data.disabled_groups
    groups = {name: group for name, group in data.groups.items() if name not in disabled}
    members: dict[str, list[str]] = {}
    children: dict[str, list[str]] = {}
    for name, group in groups.items():
        members[name] = [h for h in group.hosts if h in hostvars]
        children[name] = [c for c in group.children if c in groups and c not in disabled]
        for missing in (h for h in group.hosts if h not in hostvars and h not in data.disabled_hosts):
            logger.warning("Group %s lists unknown host %s", name, missing)

    # Dynamic membership
    if config.evaluate_group_criteria:
        for name, group in groups.items():
            if group.criteria is None:
                continue
            already = set(members[name])
            for host_name, host_vars in hostvars.items():
                if host_name not in already and group.criteria.matches(host_vars):
                    members[name].append(host_name)
                    already.add(host_name)
            logger.debug("Group %s matched %d host(s) by criteria", name, len(members[name]))

    _check_cycles(children)

    # Assemble output
    all_group = groups.get(ALL_GROUP)
    # Children of 'all' (e.g. from groups/all/groups/) are still top-level groups.
    has_parent = {child for name, kids in children.items() if name != ALL_GROUP for child in kids}
    top_level = [name for name in groups if name != ALL_GROUP and name not in has_parent]
    grouped_hosts = {h for name, hosts in members.items() if name != ALL_GROUP for h in hosts}
    ungrouped = [h for h in hostvars if h not in grouped_hosts]

    inventory: dict = {}
    for name in groups:
        if name == ALL_GROUP:
            continue
        entry: dict = {}
        if members[name]:
            entry[HOSTS] = members[name]
        if groups[name].vars:
            entry[VARS] = copy.deepcopy(groups[name].vars)
        if children[name]:
            entry[CHILDREN] = children[name]
        inventory[name] = entry

    all_entry: dict = {CHILDREN: top_level + ([UNGROUPED_GROUP] if ungrouped else [])}
    if config.add_all_hosts_to_all_group and hostvars:
        all_entry[HOSTS] = list(hostvars)
    if all_group is not None and all_group.vars:
        all_entry[VARS] = copy.deepcopy(all_group.vars)
    inventory[ALL_GROUP] = all_entry
    if ungrouped:
        inventory[UNGROUPED_GROUP] = {HOSTS: ungrouped}

    inventory[META] = {HOSTVARS: hostvars}

    if config.sort_enabled:
        inventory = sort_inventory(inventory, config)
    return inventory


def build_inventory(config: Config) -> dict:
    """Load the inventory folder named in `config` and build the Ansible JSON."""
    return build_from_data(load_inventory(config), config)


def sort_inventory(inventory: dict, config: Config) -> dict:
    """
    Sort the output for readability. Ansible does not care about order; this is
    purely cosmetic, controlled by the `sorting` config section.
    """

    def by_key(d: dict) -> dict:
        return dict(sorted(d.items(), key=lambda item: str(item[0])))

    groups = [name for name in inventory if name != META]
    if config.sort_group_keys:
        # 'all' first, then alphabetical, '_meta' last.
        groups = sorted(groups, key=lambda name: (name != ALL_GROUP, name))

    result: dict = {}
    for name in groups:
        entry = dict(inventory[name])
        if config.sort_group_hosts and HOSTS in entry:
            entry[HOSTS] = sorted(entry[HOSTS])
        if config.sort_group_children and CHILDREN in entry:
            # Keep 'ungrouped' at the end of all.children, where Ansible users expect it.
            entry[CHILDREN] = sorted(entry[CHILDREN], key=lambda c: (c == UNGROUPED_GROUP, c))
        if config.sort_group_vars and VARS in entry:
            entry[VARS] = by_key(entry[VARS])
        result[name] = entry

    hostvars = inventory[META][HOSTVARS]
    if config.sort_hostvar_keys:
        hostvars = by_key(hostvars)
    if config.sort_hostvar_vars:
        hostvars = {host: by_key(host_vars) for host, host_vars in hostvars.items()}
    result[META] = {HOSTVARS: hostvars}
    return result
