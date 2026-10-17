"""
The criteria language used by `host_criteria` to place hosts into groups.

    from xo_inventory.criteria import compile_criteria
    criteria = compile_criteria('app = proxmox AND NOT type = lxc')
    criteria.matches({'app': 'proxmox', 'type': 'vm'})  # True

See docs/expression-syntax.md for the full language reference.
"""
from .errors import CriteriaError
from .parser import Criteria, compile_criteria, lookup_variable

__all__ = ["Criteria", "CriteriaError", "compile_criteria", "lookup_variable"]
