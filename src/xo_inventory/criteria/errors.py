from __future__ import annotations


class CriteriaError(ValueError):
    """Raised when a criteria expression cannot be parsed."""

    def __init__(self, message: str, criteria: str = "", position: int | None = None):
        self.criteria = criteria
        self.position = position
        detail = message
        if criteria and position is not None:
            # Point at the offending character, e.g.
            #   app = = proxmox
            #         ^
            detail = f"{message}\n  {criteria}\n  {' ' * position}^"
        super().__init__(detail)
