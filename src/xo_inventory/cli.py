"""
Command-line entry point, following Ansible's inventory script protocol:

    ansible-xo-inventory --list           full inventory as JSON (what Ansible calls)
    ansible-xo-inventory --host <name>    variables for one host
    ansible-xo-inventory                  full inventory, pretty-printed

On any error a message goes to stderr and the exit code is non-zero, so Ansible
reports a failed inventory instead of silently running against a partial one.
"""
from __future__ import annotations

import argparse
import json
import sys

from . import __version__, cache
from .builder import HOSTVARS, META, build_inventory
from .config import CONFIG_ENV_VAR, ConfigError, load_config
from .loader import InventoryError
from .log import configure_logging, logger


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ansible-xo-inventory",
        description="Dynamic Ansible inventory built from a folder of YAML files.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--list", action="store_true", help="print the whole inventory as JSON")
    mode.add_argument("--host", metavar="HOST", help="print the variables of one host as JSON")
    parser.add_argument("--config", metavar="PATH", help=f"config file (default: ${CONFIG_ENV_VAR}, then the standard locations)")
    parser.add_argument("--no-cache", action="store_true", help="ignore and do not write the cache")
    parser.add_argument("--pretty", action="store_true", help="indent the JSON output")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def get_inventory(config, use_cache: bool = True) -> dict:
    """Build the inventory, going through the cache when it is enabled."""
    if not (config.cache_enabled and use_cache):
        return build_inventory(config)
    key = cache.fingerprint(config)
    inventory = cache.load(config, key)
    if inventory is None:
        inventory = build_inventory(config)
        cache.save(config, key, inventory)
    return inventory


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    try:
        config = load_config(args.config)
        configure_logging(config)
        inventory = get_inventory(config, use_cache=not args.no_cache)
    except (ConfigError, InventoryError) as exc:
        print(f"ansible-xo-inventory: error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - last-resort guard
        logger.debug("Unhandled error", exc_info=True)
        print(f"ansible-xo-inventory: unexpected error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    if args.host is not None:
        output = inventory[META][HOSTVARS].get(args.host, {})
    else:
        output = inventory
    indent = 4 if (args.pretty or not (args.list or args.host is not None)) else None
    json.dump(output, sys.stdout, indent=indent)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
