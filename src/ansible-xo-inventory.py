#!/usr/bin/env python3
"""
Launcher used by the .deb package and for running from a git checkout.

Point Ansible at this file (or the /usr/bin symlink to it):
    ansible-inventory -i /usr/bin/ansible-xo-inventory.py --graph
"""
import os
import sys

# Make the xo_inventory package next to this file importable, even when this
# script is reached through a symlink such as /usr/bin/ansible-xo-inventory.py.
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

from xo_inventory.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
