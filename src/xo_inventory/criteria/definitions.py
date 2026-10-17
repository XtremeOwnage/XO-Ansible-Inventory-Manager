"""
Vocabulary of the criteria language.

Every keyword and symbol the parser understands is defined here, and only here.
The operator reference in docs/expression-syntax.md is checked against these
tables by the test suite, so the docs cannot drift from the implementation.
"""
from __future__ import annotations

from enum import Enum


class OperatorType(Enum):
    """Every operation the criteria language can perform."""

    # Logical
    AND = "AND"
    OR = "OR"
    NOT = "NOT"

    # Comparison: <variable> <op> <value>
    EQUAL = "EQUAL"
    GREATER = "GREATER"
    GREATER_EQUAL = "GREATER_EQUAL"
    LESS = "LESS"
    LESS_EQUAL = "LESS_EQUAL"
    MATCH = "MATCH"  # Regular expression (re.search)
    LIKE = "LIKE"  # Wildcard pattern, % or * match anything

    # Collection: <variable> <op> <value or (list)>
    IN = "IN"
    CONTAINS = "CONTAINS"
    CMATCH = "CMATCH"  # Any element matches a regular expression
    CLIKE = "CLIKE"  # Any element matches a wildcard pattern

    # Unary: <variable> <op>
    NULL = "NULL"
    EMPTY = "EMPTY"
    ANY = "ANY"
    GREATER_ZERO = "GREATER_ZERO"
    EQUAL_ZERO = "EQUAL_ZERO"
    LESS_ZERO = "LESS_ZERO"
    NOT_EQUAL_ZERO = "NOT_EQUAL_ZERO"

    def __str__(self) -> str:
        return self.name


LOGICAL_OPERATORS: dict[OperatorType, list[str]] = {
    OperatorType.AND: ["AND", "&&", "&"],
    OperatorType.OR: ["OR", "||", "|"],
    OperatorType.NOT: ["NOT", "!"],
}
"""Logical operators. AND binds tighter than OR; NOT binds tightest."""

COMPARISON_OPERATORS: dict[OperatorType, list[str]] = {
    OperatorType.EQUAL: ["=", "==", "EQ", "EQUALS"],
    OperatorType.GREATER: [">", "GT"],
    OperatorType.GREATER_EQUAL: [">=", "GTE"],
    OperatorType.LESS: ["<", "LT"],
    OperatorType.LESS_EQUAL: ["<=", "LTE"],
    OperatorType.MATCH: ["MATCH", "REX", "REGEX"],
    OperatorType.LIKE: ["LIKE"],
}
"""Binary operators comparing a host variable with a single value."""

COLLECTION_OPERATORS: dict[OperatorType, list[str]] = {
    OperatorType.IN: ["IN"],
    OperatorType.CONTAINS: ["CONTAINS"],
    OperatorType.CMATCH: ["CMATCH"],
    OperatorType.CLIKE: ["CLIKE"],
}
"""Binary operators working with lists."""

UNARY_OPERATORS: dict[OperatorType, list[str]] = {
    OperatorType.NULL: ["NULL", "ISNULL", "IS_NULL", "NONE"],
    OperatorType.EMPTY: ["EMPTY", "ISEMPTY", "IS_EMPTY"],
    OperatorType.ANY: ["ANY"],
    OperatorType.GREATER_ZERO: ["GTZ", "GT0"],
    OperatorType.EQUAL_ZERO: ["EQZ", "EQ0"],
    OperatorType.LESS_ZERO: ["LTZ", "LT0"],
    OperatorType.NOT_EQUAL_ZERO: ["NEZ", "NE0"],
}
"""Operators that only take the host variable."""

NEGATED_OPERATORS: dict[str, OperatorType] = {
    "!=": OperatorType.EQUAL,
    "<>": OperatorType.EQUAL,
    "NE": OperatorType.EQUAL,
    "NOTMATCH": OperatorType.MATCH,
    "NOTLIKE": OperatorType.LIKE,
    "NOTIN": OperatorType.IN,
    "NOTCONTAINS": OperatorType.CONTAINS,
    "NOMATCH": OperatorType.CMATCH,
    "NOTNULL": OperatorType.NULL,
    "ISNOTNULL": OperatorType.NULL,
    "IS_NOT_NULL": OperatorType.NULL,
    "NOTEMPTY": OperatorType.EMPTY,
    "ISNOTEMPTY": OperatorType.EMPTY,
    "IS_NOT_EMPTY": OperatorType.EMPTY,
}
"""Single keywords which are shorthand for NOT followed by another operator."""

IS_KEYWORD = "IS"
"""Optional filler before a unary operator: `x IS NULL`, `x IS NOT EMPTY`."""

WORD_SYMBOLS = "_-.:/\\*#%@+"
"""Characters (besides letters and digits) allowed in unquoted variable names and values."""

OPERATOR_SYMBOLS = ["==", "!=", "<>", ">=", "<=", "&&", "||", "=", ">", "<", "&", "|", "!"]
"""Symbolic operators, longest first so the lexer matches greedily."""

QUOTE_SYMBOLS = "\"'"
"""Characters which start and end a quoted value."""

WILDCARD_SYMBOLS = "%*"
"""Wildcards used by LIKE / CLIKE. Each matches any run of characters."""


def _build_lookup() -> dict[str, tuple[str, OperatorType]]:
    """Map every keyword/symbol (upper-cased) to (category, operator)."""
    lookup: dict[str, tuple[str, OperatorType]] = {}
    tables = [
        ("logical", LOGICAL_OPERATORS),
        ("comparison", COMPARISON_OPERATORS),
        ("collection", COLLECTION_OPERATORS),
        ("unary", UNARY_OPERATORS),
    ]
    for category, table in tables:
        for operator, aliases in table.items():
            for alias in aliases:
                if alias in lookup:
                    raise RuntimeError(f"Duplicate criteria keyword: {alias}")
                lookup[alias] = (category, operator)
    for alias, operator in NEGATED_OPERATORS.items():
        if alias in lookup:
            raise RuntimeError(f"Duplicate criteria keyword: {alias}")
        lookup[alias] = ("negated", operator)
    return lookup


KEYWORDS: dict[str, tuple[str, OperatorType]] = _build_lookup()
"""Upper-cased keyword -> (category, operator). Categories: logical, comparison, collection, unary, negated."""
