import logging
from pathlib import Path

import pytest

from xo_inventory.config import CONFIG_ENV_VAR, ConfigError, find_config_file, load_config, parse_config

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_example_config_loads():
    config = load_config(REPO_ROOT / "example" / "xo_inventory.yaml")
    assert config.storage_location == (REPO_ROOT / "example" / "inventory").resolve()
    assert config.cache_enabled is False
    assert config.enable_file_logging is False
    assert config.warnings == []


def test_minimal_config_uses_defaults(tmp_path):
    config = parse_config({"main": {"STORAGE_LOCATION": "/srv/inventory"}}, tmp_path / "c.yaml")
    assert config.storage_location == Path("/srv/inventory")
    assert config.hosts_folder == "hosts"
    assert config.host_criteria_var == "host_criteria"
    assert config.log_level == logging.WARNING
    assert config.cache_location.name == "inventory.json"


def test_relative_paths_are_relative_to_config_file(tmp_path):
    config = parse_config(
        {"main": {"STORAGE_LOCATION": "inv"}, "cache": {"CACHE_LOCATION": "c/cache.json"}}, tmp_path / "x.yaml"
    )
    assert config.storage_location == tmp_path / "inv"
    assert config.cache_location == tmp_path / "c" / "cache.json"


def test_storage_location_required(tmp_path):
    with pytest.raises(ConfigError, match="STORAGE_LOCATION"):
        parse_config({"logging": {"MIN_LOG_LEVEL": "DEBUG"}}, tmp_path / "c.yaml")


@pytest.mark.parametrize(
    "data, message",
    [
        ({"features": {"MERGE_HOST_ALL_VARS": "maybe"}}, "true or false"),
        ({"logging": {"MIN_LOG_LEVEL": "LOUD"}}, "MIN_LOG_LEVEL"),
        ({"logging": {"LOG_FILE_MAX_SIZE": "big"}}, "whole number"),
        ({"directories": {"LOADER_YAML_EXTENSIONS": [1]}}, "list of strings"),
        ({"logging": {"ENABLE_FILE_LOGGING": True}}, "LOG_FILE_PATH"),
        ({"features": "yes"}, "must be a mapping"),
    ],
)
def test_invalid_values(tmp_path, data, message):
    data = {"main": {"STORAGE_LOCATION": "/x"}, **data}
    with pytest.raises(ConfigError, match=message):
        parse_config(data, tmp_path / "c.yaml")


def test_values_are_converted(tmp_path):
    config = parse_config(
        {
            "main": {"STORAGE_LOCATION": "/x"},
            "logging": {"MIN_LOG_LEVEL": "verbose"},
            "features": {"MERGE_HOST_ALL_VARS": "no"},
            "directories": {"LOADER_YAML_EXTENSIONS": "yml"},
        },
        tmp_path / "c.yaml",
    )
    assert config.log_level == logging.DEBUG
    assert config.merge_host_all_vars is False
    assert config.yaml_extensions == [".yml"]


def test_legacy_keys_are_accepted_with_warnings(tmp_path):
    config = parse_config(
        {
            "main": {"STORAGE_LOCATION": "/x"},
            "logging": {"CUSTOM_LOG_FORMAT": "{message}", "EXIT_ON_ERROR": False},
            "debugging": {"DEBUG_EVALUATOR_SHUNTING_YARD": True},
            "keys": {"KEY_HOST_VARS": "host_vars"},
            "made-up": {"THING": 1},
        },
        tmp_path / "c.yaml",
    )
    text = "\n".join(config.warnings)
    assert "CUSTOM_LOG_FORMAT" in text
    assert "EXIT_ON_ERROR" in text
    assert "DEBUG_EVALUATOR_SHUNTING_YARD" in text
    assert "'keys' is ignored" in text
    assert "made-up.THING" in text


def test_find_config_order(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.delenv(CONFIG_ENV_VAR, raising=False)

    xdg_file = tmp_path / "xdg" / "xo-inventory" / "xo_inventory.yaml"
    xdg_file.parent.mkdir(parents=True)
    xdg_file.write_text("main: {STORAGE_LOCATION: /x}")
    assert find_config_file() == xdg_file

    cwd_file = tmp_path / "xo_inventory.yaml"
    cwd_file.write_text("main: {STORAGE_LOCATION: /x}")
    assert find_config_file() == cwd_file

    env_file = tmp_path / "env.yaml"
    env_file.write_text("main: {STORAGE_LOCATION: /x}")
    monkeypatch.setenv(CONFIG_ENV_VAR, str(env_file))
    assert find_config_file() == env_file

    explicit = tmp_path / "explicit.yaml"
    explicit.write_text("main: {STORAGE_LOCATION: /x}")
    assert find_config_file(explicit) == explicit


def test_missing_explicit_config_is_an_error(tmp_path, monkeypatch):
    with pytest.raises(ConfigError, match="--config"):
        find_config_file(tmp_path / "nope.yaml")
    monkeypatch.setenv(CONFIG_ENV_VAR, str(tmp_path / "nope.yaml"))
    with pytest.raises(ConfigError, match=CONFIG_ENV_VAR):
        find_config_file()


def test_no_config_anywhere(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.delenv(CONFIG_ENV_VAR, raising=False)
    if Path("/etc/ansible/xo_inventory.yaml").exists():
        pytest.skip("system config present")
    with pytest.raises(ConfigError, match="No config file found"):
        find_config_file()


def test_invalid_yaml(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("main: [unclosed")
    with pytest.raises(ConfigError, match="not valid YAML"):
        load_config(path)
