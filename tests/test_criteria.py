import pytest

from xo_inventory.criteria import CriteriaError, compile_criteria, lookup_variable
from xo_inventory.criteria.lexer import TokenKind, tokenize

K = TokenKind

HOSTS = {
    "host1": {"app": "proxmox", "type": "bare-metal", "ansible_host": "10.100.4.100", "deprecated": None, "property_2": "lol"},
    "host2": {"app": "kubernetes", "type": "vm", "ansible_host": "10.100.4.101", "deprecated": "no", "property_2": None},
    "host3": {"app": "proxmox", "type": "lxc", "ansible_host": "10.100.4.102", "deprecated": None},
    "host4": {"app": "docker", "type": "bare-metal", "ansible_host": "10.100.4.200", "deprecated": "yes"},
    "host5": {"app": "kubernetes", "type": "bare-metal", "ansible_host": "10.100.4.201", "deprecated": None},
    "host6": {"app": "proxmox", "type": "vm", "ansible_host": "10.100.4.202", "deprecated": "no"},
    "host7": {"app": "docker", "type": "lxc", "ansible_host": "10.100.4.203", "deprecated": "yes"},
}


def matching(criteria: str) -> list[str]:
    compiled = compile_criteria(criteria)
    return sorted(name for name, host_vars in HOSTS.items() if compiled.matches(host_vars))


# Cases carried over from the original criteria_evaluator_tests.py.
@pytest.mark.parametrize(
    "criteria, expected",
    [
        # Logical operators
        ("app=proxmox && type=bare-metal", ["host1"]),
        ("app=kubernetes || type=vm", ["host2", "host5", "host6"]),
        ('(app=proxmox && type=lxc) || ansible_host="10.100.4.100"', ["host1", "host3"]),
        ('app="proxmox" OR app="kubernetes"', ["host1", "host2", "host3", "host5", "host6"]),
        # Negated logical operators
        ("NOT (app=proxmox && type=bare-metal)", ["host2", "host3", "host4", "host5", "host6", "host7"]),
        ("NOT (app=kubernetes || type=vm)", ["host1", "host3", "host4", "host7"]),
        ('NOT ((app=proxmox && type=lxc) || ansible_host="10.100.4.100")', ["host2", "host4", "host5", "host6", "host7"]),
        ('NOT (app="proxmox" OR app="kubernetes")', ["host4", "host7"]),
        # Comparison operators
        ('app=proxmox && ansible_host="10.100.4.100"', ["host1"]),
        ("type=bare-metal", ["host1", "host4", "host5"]),
        ('ansible_host="10.100.4.100"', ["host1"]),
        ("app=proxmox", ["host1", "host3", "host6"]),
        ("app!=proxmox", ["host2", "host4", "host5", "host7"]),
        # Negated comparison operators
        ('NOT (app=proxmox && ansible_host="10.100.4.100")', ["host2", "host3", "host4", "host5", "host6", "host7"]),
        ("NOT (type=bare-metal)", ["host2", "host3", "host6", "host7"]),
        ('NOT (ansible_host="10.100.4.100")', ["host2", "host3", "host4", "host5", "host6", "host7"]),
        ("NOT (app=proxmox)", ["host2", "host4", "host5", "host7"]),
        ("NOT (app!=proxmox)", ["host1", "host3", "host6"]),
        # NULL checks
        ("deprecated ISNULL", ["host1", "host3", "host5"]),
        ("property_2 ISNOTNULL", ["host1"]),
        ("NOT (property_2 ISNULL)", ["host1"]),
        ("NOT (deprecated ISNOTNULL)", ["host1", "host3", "host5"]),
        # LIKE
        ('app LIKE "prox%"', ["host1", "host3", "host6"]),
        ('NOT app LIKE "prox%"', ["host2", "host4", "host5", "host7"]),
        # MATCH
        ('ansible_host MATCH "^10\\.100\\.4\\.1.*$"', ["host1", "host2", "host3"]),
        ('NOT ansible_host MATCH "^10\\.100\\.4\\.1.*$"', ["host4", "host5", "host6", "host7"]),
        # No match
        ("app=invalid", []),
        # Previously commented out: collection operators
        ('app IN ("proxmox", "kubernetes")', ["host1", "host2", "host3", "host5", "host6"]),
        ('NOT app IN ("proxmox", "kubernetes")', ["host4", "host7"]),
        ('type CMATCH "bare.*"', ["host1", "host4", "host5"]),
        ('NOT type CMATCH "bare.*"', ["host2", "host3", "host6", "host7"]),
    ],
)
def test_original_cases(criteria, expected):
    assert matching(criteria) == expected


# Regressions for bugs in the pre-1.0 evaluator.
@pytest.mark.parametrize(
    "criteria, host_vars, expected",
    [
        # NOT used to swallow the whole remaining expression.
        ("NOT a=1 AND b=2", {"a": "1", "b": "2"}, False),
        ("NOT a=1 AND b=3", {"a": "1", "b": "2"}, False),
        ("NOT a=2 AND b=2", {"a": "1", "b": "2"}, True),
        ("a=1 AND NOT b=2", {"a": "1", "b": "2"}, False),
        ("a=1 AND NOT b=3", {"a": "1", "b": "2"}, True),
        # AND binds tighter than OR.
        ("a=1 OR b=2 AND a=9", {"a": "1", "b": "2"}, True),
        ("a=9 OR b=2 AND a=9", {"a": "1", "b": "2"}, False),
        # Quoted values with spaces / regex characters were rejected.
        ('name="web 01"', {"name": "web 01"}, True),
        ("name='web 01'", {"name": "web 01"}, True),
        ('a MATCH "^1$"', {"a": "1"}, True),
        (r'a MATCH "^\d+$"', {"a": "123"}, True),
        (r'a MATCH "^\d+$"', {"a": "12x"}, False),
        ('q = "say \\"hi\\""', {"q": 'say "hi"'}, True),
        # IS NULL / ANY used to raise "Unsupported TokenType".
        ("n IS NULL", {}, True),
        ("n IS NULL", {"n": 1}, False),
        ("n IS NOT NULL", {"n": 1}, True),
        ("n NOT NULL", {"n": 1}, True),
        ("tags ANY", {"tags": ["x"]}, True),
        ("tags ANY", {"tags": []}, False),
        ("tags ANY", {}, False),
        # Unary numeric checks on missing / non-numeric values used to raise TypeError.
        ("n GTZ", {}, False),
        ("n GTZ", {"n": "abc"}, False),
        ("n GTZ", {"n": 3}, True),
        ("n EQZ", {"n": "0"}, True),
        ("n LTZ", {"n": -1.5}, True),
        ("n NEZ", {"n": 2}, True),
        ("n NEZ", {"n": 0}, False),
    ],
)
def test_regressions(criteria, host_vars, expected):
    assert compile_criteria(criteria).matches(host_vars) is expected


@pytest.mark.parametrize(
    "criteria, host_vars, expected",
    [
        # Numbers compare numerically when both sides are numeric.
        ("cores >= 8", {"cores": 16}, True),
        ("cores > 8", {"cores": "8"}, False),
        ("cores = 8", {"cores": 8.0}, True),
        ("cores < 10", {"cores": 9}, True),
        ("cores <= 9", {"cores": 9}, True),
        ("cores GT 8", {"cores": 9}, True),
        # Text otherwise.
        ("name > m", {"name": "z"}, True),
        # Booleans match true/false case-insensitively.
        ("enabled_feature = true", {"enabled_feature": True}, True),
        ("enabled_feature = TRUE", {"enabled_feature": True}, True),
        ("enabled_feature = false", {"enabled_feature": True}, False),
        ("enabled_feature = 1", {"enabled_feature": True}, False),
        # Missing variables never match a comparison...
        ("missing = x", {}, False),
        ("missing > 1", {}, False),
        # ...so the negation does.
        ("missing != x", {}, True),
        # Nested variables via dotted path.
        ("net.vlan = 10", {"net": {"vlan": 10}}, True),
        ("disks.0.size GTZ", {"disks": [{"size": 5}]}, True),
        ("net.vlan = 10", {"net.vlan": 10}, True),
        # Collections.
        ("tags CONTAINS web", {"tags": ["web", "db"]}, True),
        ("tags CONTAINS mail", {"tags": ["web", "db"]}, False),
        ("tags NOT CONTAINS mail", {"tags": ["web", "db"]}, True),
        ("tags NOTCONTAINS web", {"tags": ["web"]}, False),
        ("name CONTAINS prod", {"name": "web-prod-01"}, True),
        ("tags IN (web, mail)", {"tags": ["web", "db"]}, True),
        ("tags IN web", {"tags": ["web", "db"]}, True),
        ("vlan IN (10, 20)", {"vlan": 20}, True),
        ("vlan NOTIN (10, 20)", {"vlan": 30}, True),
        ("tags CLIKE 'w*'", {"tags": ["db", "web"]}, True),
        ("tags CLIKE 'x*'", {"tags": ["db", "web"]}, False),
        ("tags NOMATCH '^w'", {"tags": ["db", "web"]}, False),
        # EMPTY
        ("x EMPTY", {"x": ""}, True),
        ("x EMPTY", {"x": []}, True),
        ("x IS EMPTY", {}, True),
        ("x IS NOT EMPTY", {"x": "a"}, True),
        # LIKE is a full, case-sensitive match.
        ("host LIKE 'web*'", {"host": "web01"}, True),
        ("host LIKE 'web*'", {"host": "aweb01"}, False),
        ("host LIKE 'WEB*'", {"host": "web01"}, False),
        ("host LIKE '*01'", {"host": "web01"}, True),
        # MATCH searches anywhere unless anchored.
        ("host MATCH 'eb0'", {"host": "web01"}, True),
        # Keywords are case-insensitive, values are not.
        ("app = proxmox and type = vm", {"app": "proxmox", "type": "vm"}, True),
        ("app = Proxmox", {"app": "proxmox"}, False),
        # Alternative spellings.
        ("a == 1 & b EQ 2", {"a": 1, "b": 2}, True),
        ("a = 9 | b EQUALS 2", {"a": 1, "b": 2}, True),
        ("!a = 9", {"a": 1}, True),
        ("a <> 9", {"a": 1}, True),
        ("a NE 1", {"a": 1}, False),
        ("a NOTMATCH '^1'", {"a": "12"}, False),
        ("a NOTLIKE '1*'", {"a": "21"}, True),
        # Double negation.
        ("NOT NOT a = 1", {"a": 1}, True),
        ("a NOT != 1", {"a": 1}, True),
        # Values that look like keywords are still values after an operator.
        ("mode = and", {"mode": "and"}, True),
        # Unquoted values may contain URL / address characters.
        ("url = http://example.com/a", {"url": "http://example.com/a"}, True),
        ("ep = 10.1.2.3:913", {"ep": "10.1.2.3:913"}, True),
        ("mail = root@example.com", {"mail": "root@example.com"}, True),
    ],
)
def test_semantics(criteria, host_vars, expected):
    assert compile_criteria(criteria).matches(host_vars) is expected


@pytest.mark.parametrize(
    "criteria",
    [
        "",
        "   ",
        "app",
        "app =",
        "= proxmox",
        "app = proxmox AND",
        "app = proxmox OR OR type = vm",
        "(app = proxmox",
        "app = proxmox)",
        "app proxmox",
        "app = 'unterminated",
        "app = $x",
        "app IS = x",
        "app = (a, b)",
        "app IN (a, b",
        "app IN ()",
        "app MATCH '('",
        "AND app = x",
        "NOT",
    ],
)
def test_invalid(criteria):
    with pytest.raises(CriteriaError):
        compile_criteria(criteria)


def test_error_points_at_problem():
    with pytest.raises(CriteriaError) as info:
        compile_criteria("app = = proxmox")
    assert info.value.position == 6
    assert "app = = proxmox\n        ^" in str(info.value)


def test_non_string_rejected():
    with pytest.raises(CriteriaError):
        compile_criteria(5)


def test_str_shows_structure():
    assert str(compile_criteria("NOT a=1 AND b=2 OR c ISNULL")) == "((NOT a EQUAL '1' AND b EQUAL '2') OR c NULL)"


@pytest.mark.parametrize(
    "text, expected",
    [
        ('"test"', [(K.STRING, "test")]),
        ("(test)", [(K.LPAREN, "("), (K.WORD, "test"), (K.RPAREN, ")")]),
        ("a>=1", [(K.WORD, "a"), (K.SYMBOL, ">="), (K.WORD, "1")]),
        ("a!=b", [(K.WORD, "a"), (K.SYMBOL, "!="), (K.WORD, "b")]),
        ("x&&y||z", [(K.WORD, "x"), (K.SYMBOL, "&&"), (K.WORD, "y"), (K.SYMBOL, "||"), (K.WORD, "z")]),
        ("bare-metal", [(K.WORD, "bare-metal")]),
        ("IS_NOT_NULL", [(K.WORD, "IS_NOT_NULL")]),
        ("10.1.2.3:913", [(K.WORD, "10.1.2.3:913")]),
        ("'10.1.2.3:913'", [(K.STRING, "10.1.2.3:913")]),
        ("http://example.com", [(K.WORD, "http://example.com")]),
        ("'hello world!'", [(K.STRING, "hello world!")]),
        ('"symbol_test!@#"', [(K.STRING, "symbol_test!@#")]),
        ("proxm%", [(K.WORD, "proxm%")]),
        ("proxm*", [(K.WORD, "proxm*")]),
        ("(a, b)", [(K.LPAREN, "("), (K.WORD, "a"), (K.COMMA, ","), (K.WORD, "b"), (K.RPAREN, ")")]),
        (r"'a\'b'", [(K.STRING, "a'b")]),
        (r"'a\\b'", [(K.STRING, "a\\b")]),
        (r"'a\.b'", [(K.STRING, "a\\.b")]),
    ],
)
def test_lexer(text, expected):
    tokens = tokenize(text)
    assert tokens[-1].kind is TokenKind.END
    assert [(t.kind, t.text) for t in tokens[:-1]] == expected


def test_lookup_variable():
    host_vars = {"a": 1, "b": {"c": {"d": 2}}, "l": [10, 20], "x.y": 3}
    assert lookup_variable(host_vars, "a") == 1
    assert lookup_variable(host_vars, "b.c.d") == 2
    assert lookup_variable(host_vars, "l.1") == 20
    assert lookup_variable(host_vars, "l.5") is None
    assert lookup_variable(host_vars, "x.y") == 3
    assert lookup_variable(host_vars, "missing") is None
    assert lookup_variable(host_vars, "b.missing") is None
