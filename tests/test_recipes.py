"""
Checks the examples in the documentation:

- every `host_criteria` written in the docs or README is a valid expression;
- the recipes in docs/examples/recipes.md behave as described.
"""

import re
from pathlib import Path

import pytest
import yaml

from xo_inventory.builder import build_inventory
from xo_inventory.criteria import compile_criteria

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_FILES = sorted((REPO_ROOT / "docs").rglob("*.md")) + [REPO_ROOT / "README.md"]


def _documented_criteria() -> list[tuple[str, str]]:
    """Every `host_criteria` value in the docs: YAML blocks, folder diagrams and the criteria examples table."""
    found: list[tuple[str, str]] = []
    for path in DOC_FILES:
        lines = path.read_text().splitlines()
        for index, line in enumerate(lines):
            match = re.search(r"host_criteria: ?(.*)$", line)
            if not match or "`" in line:
                continue
            value = match.group(1).strip()
            if value:
                found.append((path.name, yaml.safe_load(f"v: {value}")["v"] if value[0] in "'\"" else value))
                continue
            # A list follows on the next lines: "  - expr"
            for item in lines[index + 1 :]:
                item_match = re.match(r"\s+- (.+)$", item)
                if not item_match:
                    break
                found.append((path.name, item_match.group(1).strip()))
        if path.name == "criteria.md":
            text = "\n".join(lines)
            section = text[text.index("## Examples") : text.index("## Debugging")]
            for expr in re.findall(r"^\| `([^`]+)` \|", section, re.MULTILINE):
                found.append((path.name, expr))
    return sorted(set(found))


DOCUMENTED = _documented_criteria()


def test_docs_contain_criteria():
    assert len(DOCUMENTED) > 40


@pytest.mark.parametrize("source, criteria", DOCUMENTED, ids=[f"{s}:{c}" for s, c in DOCUMENTED])
def test_documented_criteria_are_valid(source, criteria):
    compile_criteria(criteria)


def build(inventory_dir, make_config, files):
    return build_inventory(make_config(inventory_dir(files)))


def test_recipe_environments(inventory_dir, make_config):
    inv = build(
        inventory_dir,
        make_config,
        {
            "hosts/web-01.yaml": "env: prod\nrole: web",
            "hosts/web-02.yaml": "env: staging\nrole: web",
            "hosts/db-01.yaml": "env: prod\nrole: db",
            "groups/prod.yaml": "host_criteria: env = prod",
            "groups/staging.yaml": "host_criteria: env = staging",
            "groups/prod_web.yaml": "host_criteria: env = prod AND role = web",
        },
    )
    assert inv["prod"]["hosts"] == ["db-01", "web-01"]
    assert inv["staging"]["hosts"] == ["web-02"]
    assert inv["prod_web"]["hosts"] == ["web-01"]


def test_recipe_host_names_and_network(inventory_dir, make_config):
    inv = build(
        inventory_dir,
        make_config,
        {
            "hosts/web-01.yaml": "ansible_host: 10.100.5.10",
            "hosts/db-1.yaml": "ansible_host: 10.100.4.10",
            "hosts/db-x.yaml": "",
            "groups/webservers.yaml": "host_criteria: inventory_hostname LIKE 'web-*'",
            "groups/numbered_db.yaml": "host_criteria: inventory_hostname MATCH '^db-\\d+$'",
            "groups/vlan_5.yaml": "host_criteria: ansible_host MATCH '^10\\.100\\.5\\.'",
        },
    )
    assert inv["webservers"]["hosts"] == ["web-01"]
    assert inv["numbered_db"]["hosts"] == ["db-1"]
    assert inv["vlan_5"]["hosts"] == ["web-01"]


def test_recipe_labels_and_alternatives(inventory_dir, make_config):
    inv = build(
        inventory_dir,
        make_config,
        {
            "hosts/nas-01.yaml": "labels: [backup, nfs]",
            "hosts/gpu-01.yaml": "labels: [gpu]",
            "hosts/ml-02.yaml": "labels: []",
            "hosts/box.yaml": "gpu_model: rtx",
            "groups/backup_targets.yaml": "host_criteria: labels CONTAINS backup",
            "groups/storage.yaml": "host_criteria: labels IN (nfs, iscsi, smb)",
            "groups/labelled.yaml": "host_criteria: labels ANY",
            "groups/needs_gpu_driver.yaml": (
                "host_criteria:\n  - labels CONTAINS gpu\n  - gpu_model IS NOT NULL\n  - inventory_hostname LIKE 'ml-*'"
            ),
        },
    )
    assert inv["backup_targets"]["hosts"] == ["nas-01"]
    assert inv["storage"]["hosts"] == ["nas-01"]
    assert inv["labelled"]["hosts"] == ["gpu-01", "nas-01"]
    assert inv["needs_gpu_driver"]["hosts"] == ["box", "gpu-01", "ml-02"]


def test_recipe_maintenance(inventory_dir, make_config):
    inv = build(
        inventory_dir,
        make_config,
        {
            "hosts/a.yaml": "env: prod\nmaintenance: true",
            "hosts/b.yaml": "env: prod\nmaintenance: false",
            "hosts/c.yaml": "env: prod",
            "groups/patch_tonight.yaml": "host_criteria: env = prod AND NOT maintenance = true",
        },
    )
    assert inv["patch_tonight"]["hosts"] == ["b", "c"]


def test_recipe_pinned_plus_criteria(inventory_dir, make_config):
    inv = build(
        inventory_dir,
        make_config,
        {
            "hosts/node-01.yaml": "labels: [monitored]",
            "groups/monitoring/_criteria.yaml": "host_criteria: labels CONTAINS monitored",
            "groups/monitoring/hosts/prometheus-01.yaml": "",
        },
    )
    assert inv["monitoring"]["hosts"] == ["node-01", "prometheus-01"]


def test_recipe_kubernetes_folder(inventory_dir, make_config):
    inv = build(
        inventory_dir,
        make_config,
        {
            "groups/k8s/vars/cluster.yaml": "k8s_version: v1.31.2",
            "groups/k8s/groups/k8s_control_plane/_criteria.yaml": "host_criteria: k8s_role = control-plane",
            "groups/k8s/groups/k8s_control_plane/hosts/cp-01.yaml": "k8s_role: control-plane",
            "groups/k8s/groups/k8s_control_plane/hosts/cp-02.yaml": "k8s_role: control-plane",
            "groups/k8s/groups/k8s_workers/_criteria.yaml": "host_criteria: k8s_role = worker",
            "groups/k8s/groups/k8s_workers/hosts/worker-01.yaml": "k8s_role: worker",
        },
    )
    assert inv["k8s"] == {"vars": {"k8s_version": "v1.31.2"}, "children": ["k8s_control_plane", "k8s_workers"]}
    assert inv["k8s_control_plane"]["hosts"] == ["cp-01", "cp-02"]
    assert inv["k8s_workers"]["hosts"] == ["worker-01"]
    assert inv["all"]["children"] == ["k8s"]
