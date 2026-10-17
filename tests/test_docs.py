"""Keeps docs/expression-syntax.md in sync with the operator definitions."""

import re
from pathlib import Path

from xo_inventory.criteria import definitions as d

DOC = Path(__file__).resolve().parent.parent / "docs" / "expression-syntax.md"


def _reference_rows() -> list[list[str]]:
    text = DOC.read_text()
    section = text[text.index("<!-- operators:start -->") : text.index("<!-- operators:end -->")]
    rows = []
    for line in section.splitlines():
        if not line.startswith("| `"):
            continue
        cells = [cell.strip() for cell in re.split(r"(?<!\\)\|", line)[1:-1]]
        rows.append([cell.replace("\\|", "|") for cell in cells])
    return rows


def _codes(cell: str) -> list[str]:
    return re.findall(r"`([^`]+)`", cell)


def test_operator_tables_match_definitions():
    documented: dict[str, list[str]] = {}
    for row in _reference_rows():
        names = _codes(row[0])
        if len(names) == 1 and names[0] in d.OperatorType.__members__:
            documented[names[0]] = _codes(row[1])

    expected: dict[str, list[str]] = {}
    for table in (d.LOGICAL_OPERATORS, d.COMPARISON_OPERATORS, d.COLLECTION_OPERATORS, d.UNARY_OPERATORS):
        for operator, aliases in table.items():
            expected[operator.name] = aliases

    assert documented == expected


def test_negated_shorthands_match_definitions():
    documented: dict[str, str] = {}
    for row in _reference_rows():
        shorthands = _codes(row[0])
        targets = _codes(row[1])
        if len(targets) == 1 and targets[0].startswith("NOT "):
            for shorthand in shorthands:
                documented[shorthand] = targets[0][len("NOT ") :]

    # The doc names the operator by its first spelling, e.g. "NOT =" for EQUAL.
    first_spelling = {
        op: aliases[0]
        for table in (d.COMPARISON_OPERATORS, d.COLLECTION_OPERATORS, d.UNARY_OPERATORS)
        for op, aliases in table.items()
    }
    expected = {shorthand: first_spelling[op] for shorthand, op in d.NEGATED_OPERATORS.items()}
    assert documented == expected
