import json
import logging
from pathlib import Path

import pytest

from xo_inventory.builder import build_inventory
from xo_inventory.config import load_config
from xo_inventory.loader import InventoryError
from xo_inventory.merge import merge_data

REPO_ROOT = Path(__file__).resolve().parent.parent


def build(inventory_dir, make_config, files, **sections):
    return build_inventory(make_config(inventory_dir(files), **sections))


def test_example_matches_golden_file():
    config = load_config(REPO_ROOT / "example" / "xo_inventory.yaml")
    expected = json.loads((REPO_ROOT / "tests" / "golden" / "example.json").read_text())
    assert build_inventory(config) == expected


def test_output_shape(inventory_dir, make_config):
    inv = build(inventory_dir, make_config, {"hosts/web1.yaml": "app: web"})
    assert inv == {
        "all": {"children": ["ungrouped"], "hosts": ["web1"]},
        "ungrouped": {"hosts": ["web1"]},
        "_meta": {"hostvars": {"web1": {"app": "web"}}},
    }


def test_empty_inventory(inventory_dir, make_config):
    inv = build(inventory_dir, make_config, {})
    assert inv == {"all": {"children": []}, "_meta": {"hostvars": {}}}


def test_missing_storage_location(tmp_path, make_config):
    with pytest.raises(InventoryError, match="does not exist"):
        build_inventory(make_config(tmp_path / "nope"))


# region Hosts


def test_host_names_keep_dots(inventory_dir, make_config):
    inv = build(inventory_dir, make_config, {"hosts/web.example.com.yaml": "a: 1"})
    assert "web.example.com" in inv["_meta"]["hostvars"]


def test_empty_and_comment_only_files(inventory_dir, make_config):
    inv = build(inventory_dir, make_config, {"hosts/a.yaml": "", "hosts/b.yml": "# just a comment\n", "groups/all.yaml": "# nothing\n"})
    assert inv["_meta"]["hostvars"] == {"a": {}, "b": {}}


def test_host_folder_is_merged(inventory_dir, make_config):
    inv = build(
        inventory_dir,
        make_config,
        {"hosts/web1/a.yaml": "x: 1\nlist: [1]\nd: {p: 1}", "hosts/web1/b.yaml": "y: 2\nlist: [2]\nd: {q: 2}"},
    )
    assert inv["_meta"]["hostvars"]["web1"] == {"d": {"p": 1, "q": 2}, "list": [1, 2], "x": 1, "y": 2}


def test_disabled_host(inventory_dir, make_config):
    inv = build(
        inventory_dir,
        make_config,
        {
            "hosts/on.yaml": "app: x",
            "hosts/off.yaml": "enabled: false\napp: x",
            "hosts/folder/a.yaml": "app: x",
            "hosts/folder/b.yaml": "enabled: false",
            "groups/g.yaml": "host_criteria: app = x",
        },
    )
    assert list(inv["_meta"]["hostvars"]) == ["on"]
    assert inv["g"]["hosts"] == ["on"]


def test_enabled_key_is_not_output(inventory_dir, make_config):
    inv = build(inventory_dir, make_config, {"hosts/a.yaml": "enabled: true\nx: 1", "groups/g.yaml": "enabled: true\nv: 1"})
    assert inv["_meta"]["hostvars"]["a"] == {"x": 1}
    assert inv["g"] == {"vars": {"v": 1}}


def test_host_all_vars_are_lowest_priority(inventory_dir, make_config):
    inv = build(inventory_dir, make_config, {"hosts/all.yaml": "user: base\nport: 22", "hosts/a.yaml": "user: me"})
    assert inv["_meta"]["hostvars"] == {"a": {"port": 22, "user": "me"}}


def test_host_all_vars_can_be_disabled(inventory_dir, make_config):
    inv = build(
        inventory_dir, make_config, {"hosts/all.yaml": "port: 22", "hosts/a.yaml": "x: 1"},
        features={"MERGE_HOST_ALL_VARS": False},
    )
    assert inv["_meta"]["hostvars"] == {"a": {"x": 1}}


def test_host_defined_twice_merges_and_warns(inventory_dir, make_config, caplog):
    caplog.set_level(logging.WARNING, logger="xo_inventory")
    inv = build(
        inventory_dir,
        make_config,
        {"hosts/a.yaml": "x: 1\ny: 1", "groups/g/hosts/a.yaml": "y: 2\nz: 3"},
    )
    assert inv["_meta"]["hostvars"]["a"] == {"x": 1, "y": 2, "z": 3}
    assert inv["g"]["hosts"] == ["a"]
    assert "'y' is set more than once" in caplog.text


def test_non_yaml_and_hidden_files_are_ignored(inventory_dir, make_config):
    inv = build(inventory_dir, make_config, {"hosts/a.yaml": "x: 1", "hosts/README.md": "hi", "hosts/.a.yaml.swp": "junk"})
    assert list(inv["_meta"]["hostvars"]) == ["a"]


@pytest.mark.parametrize("content, message", [("x: [", "invalid YAML"), ("- a\n- b", "key: value pairs")])
def test_bad_yaml_fails_loudly(inventory_dir, make_config, content, message):
    with pytest.raises(InventoryError, match=message):
        build(inventory_dir, make_config, {"hosts/a.yaml": content})


# endregion

# region Groups


def test_group_file_vars_and_criteria(inventory_dir, make_config):
    inv = build(
        inventory_dir,
        make_config,
        {
            "hosts/a.yaml": "app: proxmox",
            "hosts/b.yaml": "app: docker",
            "groups/pve.yaml": "host_criteria: app = proxmox\nport: 22",
        },
    )
    assert inv["pve"] == {"hosts": ["a"], "vars": {"port": 22}}
    assert inv["ungrouped"] == {"hosts": ["b"]}


def test_criteria_list_means_any(inventory_dir, make_config):
    inv = build(
        inventory_dir,
        make_config,
        {
            "hosts/a.yaml": "x: 1",
            "hosts/b.yaml": "y: 1",
            "hosts/c.yaml": "z: 1",
            "groups/g.yaml": "host_criteria:\n  - x = 1\n  - y = 1",
        },
    )
    assert inv["g"]["hosts"] == ["a", "b"]


def test_criteria_can_use_inventory_hostname(inventory_dir, make_config):
    inv = build(
        inventory_dir,
        make_config,
        {
            "hosts/web-01.yaml": "",
            "hosts/web-02.yaml": "",
            "hosts/db-01.yaml": "",
            "groups/web.yaml": "host_criteria: inventory_hostname LIKE 'web-*'",
        },
    )
    assert inv["web"] == {"hosts": ["web-01", "web-02"]}
    assert "inventory_hostname" not in inv["_meta"]["hostvars"]["web-01"]


def test_vault_and_unsafe_tags(inventory_dir, make_config):
    inv = build(
        inventory_dir,
        make_config,
        {"hosts/a.yaml": "secret: !vault |\n  $ANSIBLE_VAULT;1.1;AES256\n  6162\nraw: !unsafe '{{ x }}'\nsecret_set: true"},
    )
    assert inv["_meta"]["hostvars"]["a"] == {
        "raw": {"__ansible_unsafe": "{{ x }}"},
        "secret": {"__ansible_vault": "$ANSIBLE_VAULT;1.1;AES256\n6162\n"},
        "secret_set": True,
    }


def test_vault_tag_on_a_mapping_is_an_error(inventory_dir, make_config):
    with pytest.raises(InventoryError, match="must be applied to a string"):
        build(inventory_dir, make_config, {"hosts/a.yaml": "x: !vault {a: 1}"})


def test_criteria_can_be_turned_off(inventory_dir, make_config):
    inv = build(
        inventory_dir, make_config, {"hosts/a.yaml": "x: 1", "groups/g.yaml": "host_criteria: x = 1"},
        features={"EVALUATE_GROUP_CRITERIA": False},
    )
    assert inv["g"] == {}


def test_group_folder(inventory_dir, make_config, caplog):
    caplog.set_level(logging.WARNING, logger="xo_inventory")
    inv = build(
        inventory_dir,
        make_config,
        {
            "hosts/match.yaml": "role: k8s",
            "groups/rke/_criteria.yaml": "host_criteria: role = k8s\nstray: 1",
            "groups/rke/hosts/cp1.yaml": "ip: 1",
            "groups/rke/vars/a.yaml": "a: 1",
            "groups/rke/vars/b.yaml": "b: 2",
            "groups/rke/vars/off.yaml": "enabled: false\nc: 3",
            "groups/rke/groups/workers.yaml": "w: 1",
            "groups/rke/groups/etcd/hosts/e1.yaml": "",
            "groups/rke/notes.txt": "hi",
        },
    )
    assert inv["rke"] == {"hosts": ["cp1", "match"], "vars": {"a": 1, "b": 2}, "children": ["etcd", "workers"]}
    assert inv["workers"] == {"vars": {"w": 1}}
    assert inv["etcd"] == {"hosts": ["e1"]}
    assert inv["all"]["children"] == ["rke"]
    assert "ungrouped" not in inv
    assert "ignoring stray" in caplog.text
    assert "notes.txt" in caplog.text


def test_group_file_and_folder_combine(inventory_dir, make_config):
    inv = build(
        inventory_dir,
        make_config,
        {"groups/web.yaml": "port: 80", "groups/web/vars/x.yaml": "x: 1", "groups/web/hosts/w1.yaml": ""},
    )
    assert inv["web"] == {"hosts": ["w1"], "vars": {"port": 80, "x": 1}}


def test_group_with_two_criteria_is_an_error(inventory_dir, make_config):
    with pytest.raises(InventoryError, match="keep only one"):
        build(inventory_dir, make_config, {"groups/g.yaml": "host_criteria: a = 1", "groups/g/_criteria.yaml": "host_criteria: b = 1"})


def test_group_defined_by_yaml_and_yml_is_an_error(inventory_dir, make_config):
    with pytest.raises(InventoryError, match="defined by both"):
        build(inventory_dir, make_config, {"groups/g.yaml": "a: 1", "groups/g.yml": "b: 1"})


def test_invalid_criteria_names_the_file(inventory_dir, make_config):
    with pytest.raises(InventoryError, match=r"groups/bad\.yaml: invalid host_criteria for group 'bad'"):
        build(inventory_dir, make_config, {"groups/bad.yaml": "host_criteria: app = = x"})


@pytest.mark.parametrize("value", ["5", "[]", "[1]", "{a: 1}"])
def test_criteria_must_be_text(inventory_dir, make_config, value):
    with pytest.raises(InventoryError, match="string or a list of strings"):
        build(inventory_dir, make_config, {"groups/g.yaml": f"host_criteria: {value}"})


def test_disabled_group_skips_its_folder(inventory_dir, make_config):
    inv = build(
        inventory_dir,
        make_config,
        {
            "hosts/a.yaml": "x: 1",
            "groups/off.yaml": "enabled: false\nhost_criteria: x = 1",
            "groups/off/hosts/inside.yaml": "",
            "groups/off/groups/child.yaml": "",
            "groups/off2/_criteria.yaml": "enabled: false",
            "groups/off2/hosts/inside2.yaml": "",
        },
    )
    assert set(inv) == {"all", "ungrouped", "_meta"}
    assert list(inv["_meta"]["hostvars"]) == ["a"]


def test_all_group_vars(inventory_dir, make_config):
    inv = build(
        inventory_dir,
        make_config,
        {"groups/all.yaml": "a: 1\nhost_criteria: x = 1", "vars/dns.yaml": "dns: [1.1.1.1]", "vars/b.yml": "b: 2"},
    )
    assert inv["all"]["vars"] == {"a": 1, "b": 2, "dns": ["1.1.1.1"]}


def test_all_group_folder(inventory_dir, make_config):
    inv = build(
        inventory_dir,
        make_config,
        {"groups/all/vars/a.yaml": "a: 1", "groups/all/groups/web.yaml": "w: 1", "groups/db.yaml": ""},
    )
    assert inv["all"]["children"] == ["db", "web"]
    assert inv["all"]["vars"] == {"a": 1}
    assert inv["web"] == {"vars": {"w": 1}}


def test_ungrouped_cannot_be_defined(inventory_dir, make_config):
    with pytest.raises(InventoryError, match="managed automatically"):
        build(inventory_dir, make_config, {"groups/ungrouped.yaml": "a: 1"})


def test_all_cannot_be_a_child(inventory_dir, make_config):
    with pytest.raises(InventoryError, match="cannot be a child"):
        build(inventory_dir, make_config, {"groups/g/groups/all.yaml": "a: 1"})


def test_group_nesting_loop_is_an_error(inventory_dir, make_config):
    with pytest.raises(InventoryError, match="Group nesting loop: a -> b -> a|Group nesting loop: b -> a -> b"):
        build(inventory_dir, make_config, {"groups/a/groups/b.yaml": "", "groups/b/groups/a.yaml": ""})


def test_group_with_several_parents(inventory_dir, make_config):
    inv = build(inventory_dir, make_config, {"groups/p1/groups/shared.yaml": "", "groups/p2/groups/shared.yaml": ""})
    assert inv["p1"]["children"] == ["shared"]
    assert inv["p2"]["children"] == ["shared"]
    assert inv["all"]["children"] == ["p1", "p2"]


def test_custom_folder_and_key_names(inventory_dir, make_config):
    inv = build(
        inventory_dir,
        make_config,
        {
            "machines/a.yaml": "x: 1\nactive: true",
            "machines/b.yaml": "active: false",
            "sets/s.yaml": "match: x = 1",
            "sets/f/rules.yaml": "match: x = 2",
            "common/c.yaml": "c: 1",
        },
        directories={"HOST_VARS_FOLDER": "machines", "GROUP_VARS_FOLDER": "sets", "VARS_FOLDER": "common"},
        special_keys={"HOST_CRITERIA_VAR": "match", "KEY_ENABLED": "active", "GROUP_CRITERIA_FILE": "rules.yaml"},
    )
    assert inv["s"] == {"hosts": ["a"]}
    assert inv["f"] == {}
    assert inv["all"]["vars"] == {"c": 1}
    assert inv["_meta"]["hostvars"] == {"a": {"x": 1}}


# endregion

# region Output options


def test_all_hosts_listing_can_be_turned_off(inventory_dir, make_config):
    inv = build(inventory_dir, make_config, {"hosts/a.yaml": ""}, features={"ADD_ALL_HOSTS_TO_ALL_GROUP": False})
    assert "hosts" not in inv["all"]


def test_sorting(inventory_dir, make_config):
    files = {
        "hosts/b.yaml": "z: 1\na: 1\nk: 1",
        "hosts/a.yaml": "k: 1",
        "groups/zeta.yaml": "host_criteria: k = 1\nz: 1\na: 1",
        "groups/alpha.yaml": "",
    }
    sorted_inv = build(inventory_dir, make_config, files)
    assert list(sorted_inv) == ["all", "alpha", "zeta", "_meta"]
    assert list(sorted_inv["_meta"]["hostvars"]) == ["a", "b"]
    assert list(sorted_inv["_meta"]["hostvars"]["b"]) == ["a", "k", "z"]
    assert list(sorted_inv["zeta"]["vars"]) == ["a", "z"]
    assert sorted_inv["zeta"]["hosts"] == ["a", "b"]

    unsorted_inv = build(inventory_dir, make_config, files, sorting={"SORT_ENABLED": False})
    assert list(unsorted_inv["_meta"]["hostvars"]["b"]) == ["z", "a", "k"]
    assert list(unsorted_inv["zeta"]["vars"]) == ["z", "a"]


# endregion


def test_merge_data_does_not_modify_inputs():
    base = {"a": {"b": [1]}, "c": 1}
    overlay = {"a": {"b": [2], "d": 1}, "c": 2}
    conflicts = []
    result = merge_data(base, overlay, lambda key, old, new: conflicts.append((key, old, new)))
    assert result == {"a": {"b": [1, 2], "d": 1}, "c": 2}
    assert base == {"a": {"b": [1]}, "c": 1}
    assert overlay == {"a": {"b": [2], "d": 1}, "c": 2}
    assert conflicts == [("c", 1, 2)]
