"""
Recursive-descent parser for criteria expressions.

Grammar (keywords are case-insensitive):

    expression := or_expr END
    or_expr    := and_expr ( OR and_expr )*
    and_expr   := not_expr ( AND not_expr )*
    not_expr   := NOT not_expr | primary
    primary    := "(" or_expr ")" | clause
    clause     := VARIABLE modifiers operator [ operand ]
    modifiers  := ( NOT | IS )*
    operand    := VALUE | "(" VALUE ( "," VALUE )* ")"      -- lists are only valid after IN

NOT binds tighter than AND, which binds tighter than OR, so
`NOT a=1 AND b=2` means `(NOT a=1) AND b=2`.

The result is a tree of nodes, each with `evaluate(host_vars) -> bool`.
Parsing happens once per expression; evaluating against many hosts is cheap.
"""
from __future__ import annotations

import re
from typing import Any, Callable

from . import definitions as d
from .definitions import OperatorType as Op
from .errors import CriteriaError
from .lexer import Token, TokenKind, tokenize

_MISSING = object()


# region Value helpers


def lookup_variable(host_vars: dict, name: str) -> Any:
    """
    Get a host variable. Returns None if it is not defined.

    A name containing dots (`net.vlan`) is first looked up as-is, then as a path
    through nested dictionaries / lists (`host_vars['net']['vlan']`).
    """
    if name in host_vars:
        return host_vars[name]
    if "." not in name:
        return None
    current: Any = host_vars
    for part in name.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return None
    return current


def _to_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _is_collection(value: Any) -> bool:
    return isinstance(value, (list, tuple, set, dict))


def _equals(left: Any, right: str) -> bool:
    """Compare a host value with a criteria value: booleans, numbers, then text."""
    if left is None or _is_collection(left):
        return False
    if isinstance(left, bool):
        return right.strip().lower() == ("true" if left else "false")
    left_number, right_number = _to_number(left), _to_number(right)
    if left_number is not None and right_number is not None:
        return left_number == right_number
    return str(left) == right


def _ordered(left: Any, right: str, compare: Callable[[Any, Any], bool]) -> bool:
    """Ordering comparison: numeric when both sides are numbers, otherwise text."""
    if left is None or isinstance(left, bool) or _is_collection(left):
        return False
    left_number, right_number = _to_number(left), _to_number(right)
    if left_number is not None and right_number is not None:
        return compare(left_number, right_number)
    return compare(str(left), right)


def _wildcard_regex(pattern: str) -> re.Pattern:
    parts = []
    for char in pattern:
        parts.append(".*" if char in d.WILDCARD_SYMBOLS else re.escape(char))
    return re.compile("".join(parts), re.DOTALL)


def _elements(value: Any) -> list:
    """Treat a scalar as a one-element list and a dict as its keys."""
    if value is None:
        return []
    if isinstance(value, dict):
        return list(value.keys())
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


# endregion

# region Nodes


class Node:
    def evaluate(self, host_vars: dict) -> bool:  # pragma: no cover - interface
        raise NotImplementedError


class AndNode(Node):
    def __init__(self, left: Node, right: Node):
        self.left, self.right = left, right

    def evaluate(self, host_vars: dict) -> bool:
        return self.left.evaluate(host_vars) and self.right.evaluate(host_vars)

    def __str__(self) -> str:
        return f"({self.left} AND {self.right})"


class OrNode(Node):
    def __init__(self, left: Node, right: Node):
        self.left, self.right = left, right

    def evaluate(self, host_vars: dict) -> bool:
        return self.left.evaluate(host_vars) or self.right.evaluate(host_vars)

    def __str__(self) -> str:
        return f"({self.left} OR {self.right})"


class NotNode(Node):
    def __init__(self, operand: Node):
        self.operand = operand

    def evaluate(self, host_vars: dict) -> bool:
        return not self.operand.evaluate(host_vars)

    def __str__(self) -> str:
        return f"NOT {self.operand}"


class ClauseNode(Node):
    """A single test against one host variable, e.g. `app = proxmox`."""

    def __init__(self, variable: str, operator: Op, operand: str | list[str] | None):
        self.variable = variable
        self.operator = operator
        self.operand = operand
        self._regex: re.Pattern | None = None
        if operator in (Op.MATCH, Op.CMATCH):
            self._regex = re.compile(str(operand))
        elif operator in (Op.LIKE, Op.CLIKE):
            self._regex = _wildcard_regex(str(operand))

    def __str__(self) -> str:
        if self.operand is None:
            return f"{self.variable} {self.operator}"
        if isinstance(self.operand, list):
            return f"{self.variable} {self.operator} ({', '.join(repr(v) for v in self.operand)})"
        return f"{self.variable} {self.operator} {self.operand!r}"

    def evaluate(self, host_vars: dict) -> bool:
        value = lookup_variable(host_vars, self.variable)
        op, operand = self.operator, self.operand

        if op is Op.NULL:
            return value is None
        if op is Op.EMPTY:
            return value is None or value == "" or (_is_collection(value) and len(value) == 0)
        if op is Op.ANY:
            return _is_collection(value) and len(value) > 0
        if op in (Op.GREATER_ZERO, Op.EQUAL_ZERO, Op.LESS_ZERO, Op.NOT_EQUAL_ZERO):
            number = _to_number(value)
            if number is None:
                return False
            return {
                Op.GREATER_ZERO: number > 0,
                Op.EQUAL_ZERO: number == 0,
                Op.LESS_ZERO: number < 0,
                Op.NOT_EQUAL_ZERO: number != 0,
            }[op]

        if op is Op.EQUAL:
            return _equals(value, operand)
        if op is Op.GREATER:
            return _ordered(value, operand, lambda a, b: a > b)
        if op is Op.GREATER_EQUAL:
            return _ordered(value, operand, lambda a, b: a >= b)
        if op is Op.LESS:
            return _ordered(value, operand, lambda a, b: a < b)
        if op is Op.LESS_EQUAL:
            return _ordered(value, operand, lambda a, b: a <= b)
        if op in (Op.MATCH, Op.LIKE):
            if value is None or _is_collection(value):
                return False
            text = str(value).lower() if isinstance(value, bool) else str(value)
            if op is Op.MATCH:
                return self._regex.search(text) is not None
            return self._regex.fullmatch(text) is not None

        if op is Op.IN:
            choices = operand if isinstance(operand, list) else [operand]
            return any(_equals(element, choice) for element in _elements(value) for choice in choices)
        if op is Op.CONTAINS:
            if isinstance(value, str):
                return operand in value
            return any(_equals(element, operand) for element in _elements(value))
        if op is Op.CMATCH:
            return any(self._regex.search(str(element)) for element in _elements(value))
        if op is Op.CLIKE:
            return any(self._regex.fullmatch(str(element)) for element in _elements(value))

        raise AssertionError(f"Unhandled operator {op}")  # pragma: no cover


# endregion

# region Parser

_CATEGORY_OF: dict[Op, str] = {}
for _category, _table in (
    ("comparison", d.COMPARISON_OPERATORS),
    ("collection", d.COLLECTION_OPERATORS),
    ("unary", d.UNARY_OPERATORS),
):
    for _op in _table:
        _CATEGORY_OF[_op] = _category


class _Parser:
    def __init__(self, criteria: str):
        self.criteria = criteria
        self.tokens = tokenize(criteria)
        self.index = 0

    # Token helpers

    @property
    def current(self) -> Token:
        return self.tokens[self.index]

    def advance(self) -> Token:
        token = self.tokens[self.index]
        if token.kind is not TokenKind.END:
            self.index += 1
        return token

    def error(self, message: str, token: Token | None = None) -> CriteriaError:
        token = token or self.current
        return CriteriaError(message, self.criteria, token.position)

    def keyword(self, token: Token | None = None) -> tuple[str, Op] | None:
        """The (category, operator) for a WORD or SYMBOL token, or None if it is not a keyword."""
        token = token or self.current
        if token.kind not in (TokenKind.WORD, TokenKind.SYMBOL):
            return None
        return d.KEYWORDS.get(token.text.upper())

    def is_logical(self, operator: Op) -> bool:
        found = self.keyword()
        return found is not None and found == ("logical", operator)

    # Grammar

    def parse(self) -> Node:
        if self.current.kind is TokenKind.END:
            raise self.error("Criteria is empty")
        node = self.parse_or()
        if self.current.kind is not TokenKind.END:
            raise self.error(f"Expected AND, OR or end of expression, found {self.current}")
        return node

    def parse_or(self) -> Node:
        node = self.parse_and()
        while self.is_logical(Op.OR):
            self.advance()
            node = OrNode(node, self.parse_and())
        return node

    def parse_and(self) -> Node:
        node = self.parse_not()
        while self.is_logical(Op.AND):
            self.advance()
            node = AndNode(node, self.parse_not())
        return node

    def parse_not(self) -> Node:
        if self.is_logical(Op.NOT):
            self.advance()
            return NotNode(self.parse_not())
        return self.parse_primary()

    def parse_primary(self) -> Node:
        token = self.current
        if token.kind is TokenKind.LPAREN:
            self.advance()
            node = self.parse_or()
            if self.current.kind is not TokenKind.RPAREN:
                raise self.error(f"Expected ')', found {self.current}")
            self.advance()
            return node
        if token.kind is TokenKind.WORD and self.keyword(token) is None:
            return self.parse_clause()
        if token.kind is TokenKind.END:
            raise self.error("Expression ends unexpectedly; expected a variable name")
        raise self.error(f"Expected a variable name or '(', found {token}")

    def parse_clause(self) -> Node:
        variable = self.advance().text
        negate = False
        saw_is = False

        # Modifiers: NOT / IS, in any order (`x IS NOT NULL`, `x NOT NULL`, `x NOT LIKE y`)
        while True:
            if self.is_logical(Op.NOT):
                negate = not negate
                self.advance()
            elif self.current.kind is TokenKind.WORD and self.current.text.upper() == d.IS_KEYWORD:
                saw_is = True
                self.advance()
            else:
                break

        op_token = self.current
        found = self.keyword(op_token)
        if found is None or found[0] == "logical":
            raise self.error(f"Expected an operator after '{variable}', found {op_token}", op_token)
        self.advance()

        category, operator = found
        if category == "negated":
            negate = not negate
            category = _CATEGORY_OF[operator]

        if saw_is and category != "unary":
            raise self.error(f"IS can only be used with unary operators such as NULL, found {op_token}", op_token)

        operand: str | list[str] | None = None
        if category in ("comparison", "collection"):
            operand = self.parse_operand(allow_list=operator is Op.IN, operator_token=op_token)

        try:
            node: Node = ClauseNode(variable, operator, operand)
        except re.error as exc:
            raise self.error(f"Invalid pattern for {operator}: {exc}", op_token) from None
        return NotNode(node) if negate else node

    def parse_value(self, operator_token: Token) -> str:
        token = self.current
        if token.kind in (TokenKind.WORD, TokenKind.STRING):
            self.advance()
            return token.text
        raise self.error(f"Expected a value after '{operator_token.text}', found {token}")

    def parse_operand(self, allow_list: bool, operator_token: Token) -> str | list[str]:
        if self.current.kind is not TokenKind.LPAREN:
            return self.parse_value(operator_token)
        if not allow_list:
            raise self.error(f"A list of values is only allowed after IN, not '{operator_token.text}'")
        self.advance()
        values = [self.parse_value(operator_token)]
        while self.current.kind is TokenKind.COMMA:
            self.advance()
            values.append(self.parse_value(operator_token))
        if self.current.kind is not TokenKind.RPAREN:
            raise self.error(f"Expected ',' or ')' in value list, found {self.current}")
        self.advance()
        return values


# endregion


class Criteria:
    """A compiled criteria expression."""

    def __init__(self, text: str):
        self.text = text
        self.root = _Parser(text).parse()

    def matches(self, host_vars: dict) -> bool:
        """True if a host with these variables satisfies the expression."""
        return bool(self.root.evaluate(host_vars or {}))

    def __str__(self) -> str:
        return str(self.root)

    def __repr__(self) -> str:
        return f"Criteria({self.text!r})"


def compile_criteria(text: str) -> Criteria:
    """
    Parse a criteria expression.

    Raises:
        CriteriaError: If the expression is invalid. The message points at the problem.
    """
    if not isinstance(text, str):
        raise CriteriaError(f"Criteria must be a string, got {type(text).__name__}")
    return Criteria(text)
