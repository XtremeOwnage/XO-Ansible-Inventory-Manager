from __future__ import annotations

import copy
from typing import Any, Callable

ConflictHandler = Callable[[str, Any, Any], None]


def merge_data(base: dict, overlay: dict, on_conflict: ConflictHandler | None = None, _path: str = "") -> dict:
    """
    Merge `overlay` into a copy of `base` and return it. Neither input is modified.

    - Nested dictionaries are merged recursively.
    - Lists are combined: items from `overlay` that are not already present are appended.
    - Any other value in `overlay` replaces the one in `base`. If the two differ,
      `on_conflict(key_path, old, new)` is called first.
    """
    result = copy.deepcopy(base)
    for key, value in overlay.items():
        key_path = f"{_path}.{key}" if _path else str(key)
        if key not in result:
            result[key] = copy.deepcopy(value)
            continue
        current = result[key]
        if isinstance(current, dict) and isinstance(value, dict):
            result[key] = merge_data(current, value, on_conflict, key_path)
        elif isinstance(current, list) and isinstance(value, list):
            result[key] = current + [copy.deepcopy(item) for item in value if item not in current]
        elif current != value:
            if on_conflict:
                on_conflict(key_path, current, value)
            result[key] = copy.deepcopy(value)
    return result
