"""
Reads the inventory folder into an in-memory model.

    <STORAGE_LOCATION>/
    ├── hosts/                  one host per file (web1.yaml) or per folder (web1/*.yaml)
    ├── groups/
    │   ├── all.yaml            variables for every host (the Ansible 'all' group)
    │   ├── web.yaml            group 'web': variables, plus optional host_criteria
    │   └── rke/                group 'rke' as a folder
    │       ├── _criteria.yaml  host_criteria (and enabled) for 'rke'
    │       ├── hosts/          hosts that are members of 'rke'
    │       ├── vars/           variable files for 'rke', merged
    │       └── groups/         child groups of 'rke', same layout as groups/
    └── vars/                   variable files merged into the 'all' group

Hosts and groups are global, as in Ansible: a name defined in more than one
place is a single host/group, and its variables are merged in path order.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .config import Config
from .criteria import Criteria, CriteriaError, compile_criteria
from .log import logger
from .merge import merge_data

ALL_GROUP = "all"
UNGROUPED_GROUP = "ungrouped"


class InventoryError(Exception):
    """Raised when the inventory folder contains something that cannot be loaded."""


class _InventoryYamlLoader(yaml.SafeLoader):
    """
    SafeLoader that understands Ansible's `!vault` and `!unsafe` tags.

    Tagged values are passed to Ansible in the JSON form its inventory script
    decoder understands ({"__ansible_vault": ...} / {"__ansible_unsafe": ...}),
    so vault-encrypted variables are decrypted by Ansible as usual.
    """


def _tagged(key: str):
    def construct(loader: yaml.SafeLoader, node: yaml.Node) -> dict:
        if not isinstance(node, yaml.ScalarNode):
            raise yaml.constructor.ConstructorError(None, None, f"{node.tag} must be applied to a string", node.start_mark)
        return {key: loader.construct_scalar(node)}

    return construct


_InventoryYamlLoader.add_constructor("!vault", _tagged("__ansible_vault"))
_InventoryYamlLoader.add_constructor("!unsafe", _tagged("__ansible_unsafe"))


@dataclass
class Host:
    name: str
    vars: dict = field(default_factory=dict)
    sources: list[Path] = field(default_factory=list)


@dataclass
class Group:
    name: str
    vars: dict = field(default_factory=dict)
    hosts: dict[str, None] = field(default_factory=dict)  # Ordered set of host names
    children: dict[str, None] = field(default_factory=dict)  # Ordered set of group names
    criteria: Criteria | None = None
    criteria_source: Path | None = None
    sources: list[Path] = field(default_factory=list)


@dataclass
class InventoryData:
    hosts: dict[str, Host] = field(default_factory=dict)
    groups: dict[str, Group] = field(default_factory=dict)
    host_all_vars: dict = field(default_factory=dict)  # hosts/all.yaml
    disabled_hosts: set[str] = field(default_factory=set)
    disabled_groups: set[str] = field(default_factory=set)


class InventoryLoader:
    def __init__(self, config: Config):
        self.config = config
        self.root = Path(config.storage_location)
        self.data = InventoryData()

    # region Files

    def _yaml_name(self, path: Path) -> str | None:
        """The host/group name for a YAML file (file name minus extension), or None if not a YAML file."""
        if path.name.startswith("."):
            return None
        for extension in self.config.yaml_extensions:
            if path.name.endswith(extension) and len(path.name) > len(extension):
                return path.name[: -len(extension)]
        return None

    def _entries(self, folder: Path) -> list[Path]:
        try:
            return sorted(folder.iterdir(), key=lambda p: p.name)
        except OSError as exc:
            raise InventoryError(f"Cannot read folder {folder}: {exc}") from None

    def _yaml_files(self, folder: Path) -> list[Path]:
        return [p for p in self._entries(folder) if p.is_file() and self._yaml_name(p) is not None]

    def read_yaml(self, path: Path) -> dict:
        """Load a YAML file that must contain a mapping (an empty file is an empty mapping)."""
        try:
            with open(path, encoding="utf-8") as handle:
                data = yaml.load(handle, Loader=_InventoryYamlLoader)  # noqa: S506 - SafeLoader subclass
        except yaml.YAMLError as exc:
            raise InventoryError(f"{path}: invalid YAML: {exc}") from None
        except OSError as exc:
            raise InventoryError(f"Cannot read {path}: {exc}") from None
        if data is None:
            return {}
        if not isinstance(data, dict):
            raise InventoryError(f"{path}: must contain key: value pairs, found {type(data).__name__}")
        return data

    def _is_disabled(self, data: dict) -> bool:
        return data.get(self.config.key_enabled, True) is False

    def _strip_control_keys(self, data: dict) -> dict:
        return {k: v for k, v in data.items() if k not in (self.config.key_enabled, self.config.host_criteria_var)}

    def _conflict_logger(self, kind: str, name: str, source: Path):
        def on_conflict(key: str, old: Any, new: Any) -> None:
            logger.warning("%s '%s': '%s' is set more than once; %s overrides the earlier value", kind, name, key, source)

        return on_conflict

    def _merge_var_files(self, folder: Path, kind: str, name: str) -> dict:
        """Merge every enabled YAML file in `folder` (not recursive)."""
        merged: dict = {}
        for path in self._yaml_files(folder):
            data = self.read_yaml(path)
            if self._is_disabled(data):
                logger.info("Skipping disabled file %s", path)
                continue
            merged = merge_data(merged, self._strip_control_keys(data), self._conflict_logger(kind, name, path))
        return merged

    # endregion

    # region Hosts

    def _add_host(self, name: str, host_vars: dict, source: Path) -> None:
        host = self.data.hosts.get(name)
        if host is None:
            host = self.data.hosts[name] = Host(name)
        host.vars = merge_data(host.vars, host_vars, self._conflict_logger("Host", name, source))
        host.sources.append(source)
        logger.debug("Loaded host %s from %s", name, source)

    def load_hosts(self, folder: Path) -> list[str]:
        """
        Load every host in a hosts folder.

        A host is either `<name>.yaml` or a folder `<name>/` whose YAML files are merged.
        `enabled: false` in any of a host's files disables the host everywhere.

        Returns:
            Names of the hosts found in this folder, enabled or not.
        """
        names: list[str] = []
        for path in self._entries(folder):
            if path.is_dir():
                name = path.name
                files = [(f, self.read_yaml(f)) for f in self._yaml_files(path)]
            else:
                name = self._yaml_name(path)
                if name is None:
                    logger.debug("Ignoring non-YAML file %s", path)
                    continue
                files = [(path, self.read_yaml(path))]

            names.append(name)
            if any(self._is_disabled(data) for _, data in files):
                logger.info("Host %s is disabled (%s)", name, path)
                self.data.disabled_hosts.add(name)
                continue

            for source, data in files:
                host_vars = {k: v for k, v in data.items() if k != self.config.key_enabled}
                if name == ALL_GROUP:
                    self.data.host_all_vars = merge_data(self.data.host_all_vars, host_vars)
                else:
                    self._add_host(name, host_vars, source)
            if not files and name != ALL_GROUP:
                self._add_host(name, {}, path)
        return names

    # endregion

    # region Groups

    def _group(self, name: str) -> Group:
        group = self.data.groups.get(name)
        if group is None:
            group = self.data.groups[name] = Group(name)
        return group

    def _set_criteria(self, group: Group, raw: Any, source: Path) -> None:
        var = self.config.host_criteria_var
        if group.criteria is not None:
            raise InventoryError(
                f"Group '{group.name}' has {var} in both {group.criteria_source} and {source}; keep only one"
            )
        if isinstance(raw, list):
            if not raw or not all(isinstance(item, str) for item in raw):
                raise InventoryError(f"{source}: {var} must be a string or a list of strings")
            # A list means "any of these": join as OR.
            text = " OR ".join(f"({item})" for item in raw)
        elif isinstance(raw, str):
            text = raw
        else:
            raise InventoryError(f"{source}: {var} must be a string or a list of strings, got {type(raw).__name__}")
        try:
            group.criteria = compile_criteria(text)
        except CriteriaError as exc:
            raise InventoryError(f"{source}: invalid {var} for group '{group.name}': {exc}") from None
        group.criteria_source = source
        logger.debug("Group %s criteria: %s", group.name, group.criteria)

    def load_groups(self, folder: Path, parent: str | None = None) -> None:
        """
        Load every group in a groups folder. A group is `<name>.yaml`, a folder `<name>/`, or both.
        `parent` is the group whose `groups/` folder this is.
        """
        files: dict[str, Path] = {}
        folders: dict[str, Path] = {}
        for path in self._entries(folder):
            if path.is_dir():
                folders[path.name] = path
            elif (name := self._yaml_name(path)) is not None:
                if name in files:
                    raise InventoryError(f"Group '{name}' is defined by both {files[name]} and {path}")
                files[name] = path
            else:
                logger.debug("Ignoring non-YAML file %s", path)

        for name in sorted(set(files) | set(folders)):
            self._load_group(name, files.get(name), folders.get(name), parent)

    def _load_group(self, name: str, file: Path | None, folder: Path | None, parent: str | None) -> None:
        cfg = self.config
        file_data = self.read_yaml(file) if file else {}
        criteria_path = folder / cfg.group_criteria_file if folder else None
        criteria_data = self.read_yaml(criteria_path) if criteria_path and criteria_path.is_file() else {}

        if self._is_disabled(file_data) or self._is_disabled(criteria_data):
            logger.info("Group %s is disabled (%s); skipping it and everything inside it", name, file or criteria_path)
            self.data.disabled_groups.add(name)
            return

        if name == UNGROUPED_GROUP:
            raise InventoryError(f"'{UNGROUPED_GROUP}' is managed automatically and cannot be defined ({file or folder})")
        if name == ALL_GROUP and parent is not None:
            raise InventoryError(f"'{ALL_GROUP}' cannot be a child group ({file or folder})")

        group = self._group(name)
        if parent is not None and parent != name:
            self._group(parent).children[name] = None

        for source, data in ((file, file_data), (criteria_path, criteria_data)):
            if source is None or cfg.host_criteria_var not in data:
                continue
            if name == ALL_GROUP:
                logger.warning("%s: %s is ignored for the 'all' group", source, cfg.host_criteria_var)
            else:
                self._set_criteria(group, data[cfg.host_criteria_var], source)

        if file:
            group.vars = merge_data(group.vars, self._strip_control_keys(file_data), self._conflict_logger("Group", name, file))
            group.sources.append(file)
        if criteria_data:
            ignored = sorted(set(self._strip_control_keys(criteria_data)))
            if ignored:
                logger.warning(
                    "%s: only %s and %s are read from this file; ignoring %s (put variables in %s/)",
                    criteria_path, cfg.host_criteria_var, cfg.key_enabled, ", ".join(ignored), cfg.vars_folder,
                )

        if folder is None:
            return
        group.sources.append(folder)
        for path in self._entries(folder):
            if path.is_dir() and path.name == cfg.hosts_folder:
                for host_name in self.load_hosts(path):
                    group.hosts[host_name] = None
            elif path.is_dir() and path.name == cfg.vars_folder:
                group.vars = merge_data(
                    group.vars, self._merge_var_files(path, "Group", name), self._conflict_logger("Group", name, path)
                )
            elif path.is_dir() and path.name == cfg.groups_folder:
                self.load_groups(path, parent=name)
            elif path.name == cfg.group_criteria_file:
                continue
            else:
                logger.warning(
                    "Ignoring %s: a group folder may only contain %s, %s/, %s/ and %s/",
                    path, cfg.group_criteria_file, cfg.hosts_folder, cfg.vars_folder, cfg.groups_folder,
                )

    # endregion

    def load(self) -> InventoryData:
        cfg = self.config
        if not self.root.is_dir():
            raise InventoryError(f"STORAGE_LOCATION {self.root} does not exist or is not a folder")
        logger.debug("Loading inventory from %s", self.root)

        hosts_folder = self.root / cfg.hosts_folder
        groups_folder = self.root / cfg.groups_folder
        vars_folder = self.root / cfg.vars_folder

        if hosts_folder.is_dir():
            self.load_hosts(hosts_folder)
        if groups_folder.is_dir():
            self.load_groups(groups_folder)
        if vars_folder.is_dir():
            all_group = self._group(ALL_GROUP)
            all_group.vars = merge_data(
                all_group.vars, self._merge_var_files(vars_folder, "Group", ALL_GROUP),
                self._conflict_logger("Group", ALL_GROUP, vars_folder),
            )

        for name in self.data.disabled_hosts:
            self.data.hosts.pop(name, None)
        return self.data


def load_inventory(config: Config) -> InventoryData:
    return InventoryLoader(config).load()


__all__ = ["ALL_GROUP", "UNGROUPED_GROUP", "Group", "Host", "InventoryData", "InventoryError", "InventoryLoader", "load_inventory"]
