#!/bin/sh
find /usr/lib/xo-ansible-inventory-manager -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
exit 0
