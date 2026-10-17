import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from xo_inventory import cache
from xo_inventory.cli import get_inventory, main

REPO_ROOT = Path(__file__).resolve().parent.parent
LAUNCHER = REPO_ROOT / "src" / "ansible-xo-inventory.py"
EXAMPLE_CONFIG = REPO_ROOT / "example" / "xo_inventory.yaml"


def write_config(path: Path, storage: Path, extra: str = "") -> Path:
    path.write_text(f"main:\n  STORAGE_LOCATION: {storage}\n{extra}")
    return path


# region CLI


def test_list(capsys):
    assert main(["--config", str(EXAMPLE_CONFIG), "--list"]) == 0
    out = capsys.readouterr().out
    assert "\n" not in out.strip()  # compact for Ansible
    assert json.loads(out) == json.loads((REPO_ROOT / "tests" / "golden" / "example.json").read_text())


def test_default_is_pretty(capsys):
    assert main(["--config", str(EXAMPLE_CONFIG)]) == 0
    assert '\n    "all"' in capsys.readouterr().out


def test_host(capsys):
    assert main(["--config", str(EXAMPLE_CONFIG), "--host", "pve-02"]) == 0
    assert json.loads(capsys.readouterr().out)["ansible_host"] == "10.100.4.11"
    assert main(["--config", str(EXAMPLE_CONFIG), "--host", "nope"]) == 0
    assert json.loads(capsys.readouterr().out) == {}


def test_errors_go_to_stderr_with_nonzero_exit(tmp_path, capsys):
    root = tmp_path / "inv"
    (root / "groups").mkdir(parents=True)
    (root / "groups" / "bad.yaml").write_text("host_criteria: a = = b")
    config = write_config(tmp_path / "c.yaml", root)
    assert main(["--config", str(config), "--list"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "invalid host_criteria" in captured.err

    assert main(["--config", str(tmp_path / "missing.yaml"), "--list"]) == 1
    assert "does not exist" in capsys.readouterr().err


def test_launcher_works_through_symlink(tmp_path):
    link = tmp_path / "ansible-xo-inventory.py"
    link.symlink_to(LAUNCHER)
    result = subprocess.run(
        [sys.executable, "-I", str(link), "--list", "--config", str(EXAMPLE_CONFIG)],
        capture_output=True, text=True, cwd=tmp_path, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "pve-01" in json.loads(result.stdout)["_meta"]["hostvars"]


def test_module_entry_point():
    result = subprocess.run(
        [sys.executable, "-m", "xo_inventory", "--version"],
        capture_output=True, text=True, env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}, check=False,
    )
    assert result.returncode == 0
    assert "1.0.0" in result.stdout


# endregion

# region Cache


@pytest.fixture
def cached_setup(tmp_path, inventory_dir):
    root = inventory_dir({"hosts/a.yaml": "x: 1"})
    cache_file = tmp_path / "cache" / "inventory.json"
    config_path = write_config(
        tmp_path / "c.yaml", root, f"cache:\n  CACHE_ENABLED: true\n  CACHE_LOCATION: {cache_file}\n"
    )
    from xo_inventory.config import load_config

    return load_config(config_path), root, cache_file


def test_cache_round_trip_and_permissions(cached_setup):
    config, root, cache_file = cached_setup
    first = get_inventory(config)
    assert cache_file.is_file()
    assert (cache_file.stat().st_mode & 0o777) == 0o600
    key = cache.fingerprint(config)
    assert cache.load(config, key) == first


def test_cache_is_invalidated_by_inventory_edits(cached_setup):
    config, root, cache_file = cached_setup
    assert get_inventory(config)["_meta"]["hostvars"] == {"a": {"x": 1}}

    time.sleep(0.01)
    (root / "hosts" / "a.yaml").write_text("x: 22")
    assert get_inventory(config)["_meta"]["hostvars"] == {"a": {"x": 22}}

    (root / "hosts" / "b.yaml").write_text("")
    assert set(get_inventory(config)["_meta"]["hostvars"]) == {"a", "b"}

    (root / "hosts" / "b.yaml").unlink()
    assert set(get_inventory(config)["_meta"]["hostvars"]) == {"a"}


def test_cache_used_when_unchanged(cached_setup):
    config, root, cache_file = cached_setup
    get_inventory(config)
    # Tamper with the cached content (keeping it trusted) to prove it is read back.
    data = json.loads(cache_file.read_text())
    data["inventory"]["_meta"]["hostvars"]["a"]["x"] = "from-cache"
    cache_file.write_text(json.dumps(data))
    assert get_inventory(config)["_meta"]["hostvars"]["a"]["x"] == "from-cache"
    assert get_inventory(config, use_cache=False)["_meta"]["hostvars"]["a"]["x"] == 1


def test_cache_writable_by_others_is_ignored(cached_setup):
    config, root, cache_file = cached_setup
    get_inventory(config)
    data = json.loads(cache_file.read_text())
    data["inventory"]["_meta"]["hostvars"]["a"]["ansible_ssh_common_args"] = "-o ProxyCommand=evil"
    cache_file.write_text(json.dumps(data))
    os.chmod(cache_file, 0o666)
    assert "ansible_ssh_common_args" not in get_inventory(config)["_meta"]["hostvars"]["a"]


def test_cache_symlink_is_ignored(cached_setup, tmp_path):
    config, root, cache_file = cached_setup
    get_inventory(config)
    planted = tmp_path / "planted.json"
    shutil.copy(cache_file, planted)
    cache_file.unlink()
    cache_file.symlink_to(planted)
    assert cache.load(config, cache.fingerprint(config)) is None


@pytest.mark.parametrize("content", ["not json", "[]", '{"format": 1, "key": "x", "inventory": {}}'])
def test_bad_cache_content_is_ignored(cached_setup, content):
    config, root, cache_file = cached_setup
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(content)
    os.chmod(cache_file, 0o600)
    assert get_inventory(config)["_meta"]["hostvars"] == {"a": {"x": 1}}


def test_unwritable_cache_location_does_not_break_inventory(tmp_path, inventory_dir):
    from xo_inventory.config import load_config

    root = inventory_dir({"hosts/a.yaml": ""})
    blocker = tmp_path / "file"
    blocker.write_text("")
    config = load_config(
        write_config(tmp_path / "c.yaml", root, f"cache:\n  CACHE_ENABLED: true\n  CACHE_LOCATION: {blocker}/sub/c.json\n")
    )
    assert "a" in get_inventory(config)["_meta"]["hostvars"]


def test_unwritable_log_file_does_not_break_inventory(tmp_path, inventory_dir, capsys):
    root = inventory_dir({"hosts/a.yaml": ""})
    blocker = tmp_path / "file"
    blocker.write_text("")
    config = write_config(
        tmp_path / "c.yaml", root, f"logging:\n  ENABLE_FILE_LOGGING: true\n  LOG_FILE_PATH: {blocker}/x.log\n"
    )
    assert main(["--config", str(config), "--list"]) == 0
    captured = capsys.readouterr()
    assert "File logging disabled" in captured.err
    assert json.loads(captured.out)["_meta"]["hostvars"] == {"a": {}}


# endregion


# region Real Ansible


@pytest.mark.skipif(shutil.which("ansible-inventory") is None, reason="ansible-core not installed")
def test_ansible_inventory_reads_the_example(tmp_path):
    env = {**os.environ, "XO_INVENTORY_CONFIG": str(EXAMPLE_CONFIG), "ANSIBLE_LOCAL_TEMP": str(tmp_path)}
    result = subprocess.run(
        ["ansible-inventory", "-i", str(LAUNCHER), "--list"],
        capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL, check=False,
    )
    assert result.returncode == 0, result.stderr
    # Deprecation notices about the Python/Ansible versions themselves are not our concern.
    warnings = [line for line in result.stderr.splitlines() if "WARNING" in line and "DEPRECATION" not in line]
    assert warnings == [], result.stderr
    data = json.loads(result.stdout)
    assert sorted(data["proxmox_servers"]["hosts"]) == ["pve-01", "pve-02"]
    assert data["rke"]["children"] == ["rke_control_plane", "rke_workers"]
    assert data["_meta"]["hostvars"]["pve-01"]["ansible_connection"] == "ssh"  # group var applied
    assert data["_meta"]["hostvars"]["rke-worker-01"]["rke_cluster_name"] == "homelab"  # inherited from parent group
    assert "old-box" not in data["_meta"]["hostvars"]


# endregion


@pytest.mark.skipif(shutil.which("ansible-playbook") is None, reason="ansible-core not installed")
def test_vault_values_are_decrypted_by_ansible(tmp_path):
    password_file = tmp_path / "pw"
    password_file.write_text("testpass\n")
    encrypted = subprocess.run(
        ["ansible-vault", "encrypt_string", "--vault-password-file", str(password_file), "s3cret", "--name", "db_password"],
        capture_output=True, text=True, stdin=subprocess.DEVNULL, check=True,
    ).stdout
    (tmp_path / "inventory" / "hosts").mkdir(parents=True)
    (tmp_path / "inventory" / "hosts" / "web-01.yaml").write_text(encrypted + "template: !unsafe '{{ not_templated }}'\n")
    config = write_config(tmp_path / "xo_inventory.yaml", tmp_path / "inventory")
    playbook = tmp_path / "pb.yml"
    playbook.write_text(
        "- hosts: all\n  gather_facts: false\n  tasks:\n    - debug:\n        msg: 'VALUE={{ db_password }} {{ template }}'\n"
    )

    env = {**os.environ, "XO_INVENTORY_CONFIG": str(config), "ANSIBLE_LOCAL_TEMP": str(tmp_path)}
    result = subprocess.run(
        ["ansible-playbook", "-i", str(LAUNCHER), str(playbook), "-c", "local", "--vault-password-file", str(password_file)],
        capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "VALUE=s3cret {{ not_templated }}" in result.stdout
