#!/bin/sh
# Python may write bytecode caches next to the modules when the script runs as
# root; remove them so the package directories can be removed cleanly.
rm -rf /usr/lib/xo-ansible-inventory-manager/xo_inventory/__pycache__ \
       /usr/lib/xo-ansible-inventory-manager/xo_inventory/criteria/__pycache__
exit 0
