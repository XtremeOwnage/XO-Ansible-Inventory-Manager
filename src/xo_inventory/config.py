"""
Configuration loading.

Every setting has a default, so a config file only needs to set what it changes;
in practice that is usually just `main.STORAGE_LOCATION`. The file layout
(sections and UPPER_CASE keys) is the same one used before 1.0.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

CONFIG_FILE_NAME = "xo_inventory.yaml"
CONFIG_ENV_VAR = "XO_INVENTORY_CONFIG"


class ConfigError(Exception):
    """Raised when the configuration cannot be found or is invalid."""


def _default_cache_location() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return Path(base) / "xo-inventory" / "inventory.json"


@dataclass
class Config:
    # main
    storage_location: Path = None  # type: ignore[assignment]
    config_path: Path | None = None

    # logging
    log_level: int = logging.WARNING
    log_format: str = "%(asctime)s %(levelname)s %(module)s.%(funcName)s: %(message)s"
    log_timestamp_format: str = "%Y-%m-%dT%H:%M:%S"
    enable_file_logging: bool = False
    log_file_path: Path | None = None
    enable_log_rotation: bool = True
    log_file_max_size: int = 10 * 1024 * 1024
    log_file_backup_count: int = 3

    # directories
    hosts_folder: str = "hosts"
    groups_folder: str = "groups"
    vars_folder: str = "vars"
    yaml_extensions: list[str] = field(default_factory=lambda: [".yaml", ".yml"])

    # special keys
    host_criteria_var: str = "host_criteria"
    key_enabled: str = "enabled"
    group_criteria_file: str = "_criteria.yaml"

    # features
    add_all_hosts_to_all_group: bool = True
    merge_host_all_vars: bool = True
    evaluate_group_criteria: bool = True

    # sorting
    sort_enabled: bool = True
    sort_group_keys: bool = True
    sort_hostvar_keys: bool = True
    sort_hostvar_vars: bool = True
    sort_group_vars: bool = True
    sort_group_hosts: bool = True
    sort_group_children: bool = True

    # cache
    cache_enabled: bool = False
    cache_location: Path = field(default_factory=_default_cache_location)

    # Messages about the config file itself (unknown / deprecated keys).
    # Logged once logging has been configured from this config.
    warnings: list[str] = field(default_factory=list)


# (section, KEY) -> (attribute, type)
_SCHEMA: dict[tuple[str, str], tuple[str, type]] = {
    ("main", "STORAGE_LOCATION"): ("storage_location", Path),
    ("logging", "MIN_LOG_LEVEL"): ("log_level", int),
    ("logging", "LOG_FORMAT"): ("log_format", str),
    ("logging", "LOG_TIMESTAMP_FORMAT"): ("log_timestamp_format", str),
    ("logging", "ENABLE_FILE_LOGGING"): ("enable_file_logging", bool),
    ("logging", "LOG_FILE_PATH"): ("log_file_path", Path),
    ("logging", "ENABLE_LOG_ROTATION"): ("enable_log_rotation", bool),
    ("logging", "LOG_FILE_MAX_SIZE"): ("log_file_max_size", int),
    ("logging", "LOG_FILE_BACKUP_COUNT"): ("log_file_backup_count", int),
    ("directories", "HOST_VARS_FOLDER"): ("hosts_folder", str),
    ("directories", "GROUP_VARS_FOLDER"): ("groups_folder", str),
    ("directories", "VARS_FOLDER"): ("vars_folder", str),
    ("directories", "LOADER_YAML_EXTENSIONS"): ("yaml_extensions", list),
    ("special-keys", "HOST_CRITERIA_VAR"): ("host_criteria_var", str),
    ("special-keys", "KEY_ENABLED"): ("key_enabled", str),
    ("special-keys", "GROUP_CRITERIA_FILE"): ("group_criteria_file", str),
    ("features", "ADD_ALL_HOSTS_TO_ALL_GROUP"): ("add_all_hosts_to_all_group", bool),
    ("features", "MERGE_HOST_ALL_VARS"): ("merge_host_all_vars", bool),
    ("features", "EVALUATE_GROUP_CRITERIA"): ("evaluate_group_criteria", bool),
    ("sorting", "SORT_ENABLED"): ("sort_enabled", bool),
    ("sorting", "SORT_GROUP_KEYS"): ("sort_group_keys", bool),
    ("sorting", "SORT_HOSTVAR_KEYS"): ("sort_hostvar_keys", bool),
    ("sorting", "SORT_HOSTVAR_VARS"): ("sort_hostvar_vars", bool),
    ("sorting", "SORT_GROUP_VARS"): ("sort_group_vars", bool),
    ("sorting", "SORT_GROUP_HOSTS"): ("sort_group_hosts", bool),
    ("sorting", "SORT_GROUP_CHILDREN"): ("sort_group_children", bool),
    ("cache", "CACHE_ENABLED"): ("cache_enabled", bool),
    ("cache", "CACHE_LOCATION"): ("cache_location", Path),
}

# Settings from before 1.0 that no longer do anything. They are accepted so
# existing config files keep working.
_DEPRECATED: dict[tuple[str, str], str] = {
    ("logging", "CUSTOM_LOG_FORMAT"): "use %(module)s / %(funcName)s in LOG_FORMAT instead",
    ("logging", "EXIT_ON_ERROR"): "errors always stop the inventory build now",
    ("logging", "EXIT_ON_FATAL"): "errors always stop the inventory build now",
    ("debugging", "DEBUG_EVALUATOR_SHUNTING_YARD"): "set MIN_LOG_LEVEL: DEBUG instead",
}
_DEPRECATED_SECTIONS: dict[str, str] = {
    "keys": "output key names are fixed by Ansible and can no longer be changed",
}

_LOG_LEVELS = {
    "VERBOSE": logging.DEBUG,
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "WARN": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
    "FATAL": logging.CRITICAL,
}


def candidate_paths(cwd: Path | None = None) -> list[Path]:
    """Where the config file is looked for, in priority order (used when no path is given)."""
    cwd = cwd or Path.cwd()
    paths = [cwd / CONFIG_FILE_NAME]
    xdg = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    paths.append(Path(xdg) / "xo-inventory" / CONFIG_FILE_NAME)
    paths.append(Path("/etc/ansible") / CONFIG_FILE_NAME)
    return paths


def find_config_file(explicit: str | os.PathLike | None = None) -> Path:
    """
    Locate the config file.

    Order: the explicit path (--config), $XO_INVENTORY_CONFIG, ./xo_inventory.yaml,
    $XDG_CONFIG_HOME/xo-inventory/xo_inventory.yaml, /etc/ansible/xo_inventory.yaml.
    An explicit path or environment variable that points at a missing file is an error,
    rather than silently falling back to another file.
    """
    for source, value in (("--config", explicit), (CONFIG_ENV_VAR, os.environ.get(CONFIG_ENV_VAR))):
        if value:
            path = Path(value).expanduser()
            if not path.is_file():
                raise ConfigError(f"Config file given by {source} does not exist: {path}")
            return path

    searched = candidate_paths()
    for path in searched:
        if path.is_file():
            return path
    raise ConfigError(
        "No config file found. Looked in: " + ", ".join(str(p) for p in searched)
        + f". Set {CONFIG_ENV_VAR} or pass --config."
    )


def _convert(section: str, key: str, value: Any, kind: type, base_dir: Path) -> Any:
    where = f"{section}.{key}"
    if kind is bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.strip().lower() in ("true", "yes", "on", "1", "false", "no", "off", "0"):
            return value.strip().lower() in ("true", "yes", "on", "1")
        raise ConfigError(f"{where} must be true or false, got {value!r}")
    if key == "MIN_LOG_LEVEL":
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        level = _LOG_LEVELS.get(str(value).strip().upper())
        if level is None:
            raise ConfigError(f"{where} must be one of {', '.join(_LOG_LEVELS)}, got {value!r}")
        return level
    if kind is int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigError(f"{where} must be a whole number, got {value!r}")
        return value
    if kind is str:
        if not isinstance(value, str) or not value:
            raise ConfigError(f"{where} must be a non-empty string, got {value!r}")
        return value
    if kind is list:
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
            raise ConfigError(f"{where} must be a list of strings, got {value!r}")
        return [v if v.startswith(".") else f".{v}" for v in value]
    if kind is Path:
        if not isinstance(value, str) or not value:
            raise ConfigError(f"{where} must be a path, got {value!r}")
        path = Path(os.path.expandvars(value)).expanduser()
        # Relative paths are relative to the config file, not the current directory,
        # so the inventory resolves the same no matter where ansible is run from.
        return path if path.is_absolute() else (base_dir / path)
    raise AssertionError(kind)  # pragma: no cover


def parse_config(data: Any, config_path: Path | None = None) -> Config:
    """Build a Config from the parsed YAML of a config file."""
    base_dir = config_path.parent if config_path else Path.cwd()
    config = Config(config_path=config_path)

    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ConfigError("Config file must contain a mapping of sections")

    for section, values in data.items():
        if section in _DEPRECATED_SECTIONS:
            config.warnings.append(f"Config section '{section}' is ignored: {_DEPRECATED_SECTIONS[section]}")
            continue
        if values is None:
            continue
        if not isinstance(values, dict):
            raise ConfigError(f"Config section '{section}' must be a mapping")
        for key, value in values.items():
            if (section, key) in _DEPRECATED:
                config.warnings.append(f"Config key {section}.{key} is ignored: {_DEPRECATED[(section, key)]}")
                continue
            if (section, key) not in _SCHEMA:
                config.warnings.append(f"Unknown config key {section}.{key} (ignored)")
                continue
            if value is None:
                continue
            attribute, kind = _SCHEMA[(section, key)]
            setattr(config, attribute, _convert(section, key, value, kind, base_dir))

    if config.storage_location is None:
        raise ConfigError("main.STORAGE_LOCATION is not set; it must point at your inventory folder")
    if config.enable_file_logging and config.log_file_path is None:
        raise ConfigError("logging.LOG_FILE_PATH must be set when ENABLE_FILE_LOGGING is true")
    return config


def load_config(explicit: str | os.PathLike | None = None) -> Config:
    """Find, read and validate the config file."""
    path = find_config_file(explicit)
    try:
        with open(path, encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        raise ConfigError(f"Config file {path} is not valid YAML: {exc}") from None
    except OSError as exc:
        raise ConfigError(f"Cannot read config file {path}: {exc}") from None
    return parse_config(data, path.resolve())
