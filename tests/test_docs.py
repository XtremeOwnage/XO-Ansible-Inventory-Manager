"""Keeps docs/guide/criteria.md in sync with the operator definitions."""

import re
from pathlib import Path

from xo_inventory.criteria import definitions as d

DOC = Path(__file__).resolve().parent.parent / "docs" / "guide" / "criteria.md"


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


def test_readme_links_to_repository_files_exist():
    readme = DOC.parent.parent.parent / "README.md"
    root = readme.parent
    targets = re.findall(r"\]\(([^)\s]+)\)", readme.read_text())
    local = [t.split("#")[0] for t in targets if not t.startswith(("http://", "https://", "#", "mailto:"))]
    assert local, "expected some relative links"
    missing = [t for t in local if not (root / t).exists()]
    assert missing == []


def test_readme_links_to_site_pages_exist():
    readme = DOC.parent.parent.parent / "README.md"
    site = "https://xtremeownage.github.io/XO-Ansible-Inventory-Manager/"
    docs = DOC.parent.parent
    pages = re.findall(re.escape(site) + r"([^)\s>]*)", readme.read_text())
    assert pages
    for page in pages:
        page = page.rstrip("/")
        candidates = [docs / "index.md"] if not page else [docs / f"{page}.md", docs / page / "index.md"]
        assert any(c.exists() for c in candidates), page
