"""
Optional on-disk cache of the built inventory.

The cache is keyed on a fingerprint of everything the output depends on: this
program's version, the config file, and the name/size/mtime of every file and
folder under STORAGE_LOCATION. Any edit to the inventory invalidates it.

The cached JSON ends up as host variables in Ansible, and variables such as
`ansible_ssh_common_args` can run commands. So a cache file is only trusted if
it is owned by the current user and not writable by anyone else.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path

from . import __version__
from .config import Config
from .log import logger

_FORMAT_VERSION = 1


def fingerprint(config: Config) -> str:
    """Hash of everything the built inventory depends on."""
    digest = hashlib.sha256()
    digest.update(f"xo-inventory {__version__} format {_FORMAT_VERSION}\n".encode())

    if config.config_path:
        digest.update(str(config.config_path).encode() + b"\0")
        try:
            digest.update(Path(config.config_path).read_bytes())
        except OSError:
            digest.update(b"<unreadable>")
        digest.update(b"\0")

    root = Path(config.storage_location)
    digest.update(str(root).encode() + b"\0")
    entries = []
    for directory, dirnames, filenames in os.walk(root, followlinks=True):
        dirnames.sort()
        for name in [*dirnames, *filenames]:
            path = os.path.join(directory, name)
            try:
                info = os.stat(path)
            except OSError:
                continue
            entries.append(f"{os.path.relpath(path, root)}\0{info.st_size}\0{info.st_mtime_ns}\0{stat.S_IFMT(info.st_mode)}")
    entries.sort()
    for entry in entries:
        digest.update(entry.encode() + b"\n")
    return digest.hexdigest()


def _is_trusted(info: os.stat_result) -> bool:
    if not stat.S_ISREG(info.st_mode):
        return False
    if hasattr(os, "getuid") and info.st_uid != os.getuid():
        return False
    return not (info.st_mode & (stat.S_IWGRP | stat.S_IWOTH))


def load(config: Config, key: str) -> dict | None:
    """Return the cached inventory if it exists, is trusted and matches `key`; otherwise None."""
    path = Path(config.cache_location)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except FileNotFoundError:
        logger.debug("No cache file at %s", path)
        return None
    except OSError as exc:
        logger.warning("Ignoring cache %s: %s", path, exc)
        return None

    with os.fdopen(fd, "r", encoding="utf-8") as handle:
        if not _is_trusted(os.fstat(handle.fileno())):
            logger.warning(
                "Ignoring cache %s: it must be a regular file owned by you and not writable by others", path
            )
            return None
        try:
            data = json.load(handle)
        except (ValueError, OSError) as exc:
            logger.warning("Ignoring unreadable cache %s: %s", path, exc)
            return None

    if not isinstance(data, dict) or data.get("format") != _FORMAT_VERSION or data.get("key") != key:
        logger.debug("Cache %s is stale", path)
        return None
    inventory = data.get("inventory")
    if not isinstance(inventory, dict):
        return None
    logger.debug("Using cached inventory from %s", path)
    return inventory


def save(config: Config, key: str, inventory: dict) -> None:
    """Write the cache atomically with 0600 permissions. Failures are logged, never raised."""
    path = Path(config.cache_location)
    try:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=".xo-inventory-", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump({"format": _FORMAT_VERSION, "key": key, "inventory": inventory}, handle)
            os.chmod(temp_name, 0o600)
            os.replace(temp_name, path)
        except BaseException:
            try:
                os.unlink(temp_name)
            except OSError:
                pass
            raise
    except OSError as exc:
        logger.warning("Could not write cache %s: %s", path, exc)
        return
    logger.debug("Saved inventory cache to %s", path)
