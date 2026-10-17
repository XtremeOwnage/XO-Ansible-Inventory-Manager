# Criteria expressions

A group can pull hosts in automatically with `host_criteria`:

```yaml
# groups/proxmox_servers.yaml
host_criteria: app = proxmox AND type = bare-metal
```

Every host whose variables satisfy the expression becomes a member of the group, in addition to any hosts placed in the group's `hosts/` folder. `host_criteria` can also be a list, in which case a host matching **any** entry joins the group:

```yaml
host_criteria:
  - cores >= 16 AND type = bare-metal
  - labels CONTAINS gpu
```

Expressions are checked when the inventory is built. An invalid expression stops the build with an error naming the file and pointing at the problem:

```text
ansible-xo-inventory: error: .../groups/web.yaml: invalid host_criteria for group 'web': Expected a value after '=', found end of expression
  app =
       ^
```

## Syntax

An expression is one or more **clauses** joined with `AND` / `OR`, optionally negated with `NOT` and grouped with parentheses.

```text
clause      := variable [NOT] [IS [NOT]] operator [value]
expression  := clause | NOT expression | ( expression ) | expression AND expression | expression OR expression
```

- **Precedence:** `NOT` binds tightest, then `AND`, then `OR`. `NOT a = 1 AND b = 2` means `(NOT a = 1) AND b = 2`. Use parentheses when in doubt.
- **Keywords** (`AND`, `like`, `IsNull`, …) are case-insensitive. **Values are case-sensitive.**
- **Variables** are host variable names, plus `inventory_hostname` (the host's name, unless the host sets a variable with that name itself). A dotted name such as `net.vlan` first looks for a variable literally called `net.vlan`, then for `vlan` inside a dictionary `net`. List items can be reached by index: `disks.0.size`.
- **Values** can be unquoted when they only contain letters, digits and `_ - . : / \ * # % @ +` (e.g. `bare-metal`, `10.0.0.5:22`, `http://x/y`). Anything else, such as spaces, `$` or regex syntax like `^` and `[`, needs single or double quotes. Inside quotes, `\"` / `\'` and `\\` are escapes. Every other backslash is kept as-is, so `"^10\.0\.\d+$"` reaches the regex engine unchanged.
- **Missing variables** behave like `null`: comparisons with them are false (so `x != 5` is true when `x` is not set), and `x IS NULL` is true.

## How values are compared

| Host value | Compared as |
|---|---|
| Both sides look like numbers (`16`, `"16"`, `2.5`) | Numbers: `cores >= 8` works with `cores: 16` or `cores: "16"` |
| `true` / `false` | Matches `true` / `false` in the expression, case-insensitively |
| Anything else | Text, case-sensitive |
| A list or dictionary | Only the collection operators (`IN`, `CONTAINS`, `CMATCH`, `CLIKE`) and `ANY` / `EMPTY` / `NULL` look inside it; other comparisons are false |

Version strings are compared as numbers when they look like one, so `"2.10" >= 2.9` is **false** (2.1 < 2.9). Store versions as separate major/minor variables if you need to compare them.

## Operator reference

<!-- operators:start -->

### Logical

| Operator | Spellings | Meaning |
|---|---|---|
| `AND` | `AND`, `&&`, `&` | Both sides must be true |
| `OR` | `OR`, `\|\|`, `\|` | Either side must be true |
| `NOT` | `NOT`, `!` | Negates what follows: a clause (`NOT app = x`), a group (`NOT (...)`), or, inside a clause, the operator (`app NOT LIKE 'x*'`) |

### Comparison: `variable OPERATOR value`

| Operator | Spellings | Meaning |
|---|---|---|
| `EQUAL` | `=`, `==`, `EQ`, `EQUALS` | Equal |
| `GREATER` | `>`, `GT` | Greater than |
| `GREATER_EQUAL` | `>=`, `GTE` | Greater than or equal |
| `LESS` | `<`, `LT` | Less than |
| `LESS_EQUAL` | `<=`, `LTE` | Less than or equal |
| `MATCH` | `MATCH`, `REX`, `REGEX` | Matches a [Python regular expression](https://docs.python.org/3/library/re.html) anywhere in the value; anchor with `^`/`$` for a full match |
| `LIKE` | `LIKE` | Matches a wildcard pattern over the **whole** value; `*` or `%` match any characters |

### Collection: `variable OPERATOR value`

| Operator | Spellings | Meaning |
|---|---|---|
| `IN` | `IN` | The value is one of a list: `vlan IN (10, 20, 30)`. If the variable is a list, true when any of its items is in the list. `tags IN web` with a single value is the same as `tags CONTAINS web` |
| `CONTAINS` | `CONTAINS` | List variable: has an item equal to the value. Text variable: contains the value as a substring. Dictionary: has the value as a key |
| `CMATCH` | `CMATCH` | Any item of the list matches the regular expression (a non-list value is treated as a one-item list) |
| `CLIKE` | `CLIKE` | Any item of the list matches the wildcard pattern |

### Unary: `variable OPERATOR`

`IS` may be written before these for readability: `x IS NULL`, `x IS NOT EMPTY`.

| Operator | Spellings | Meaning |
|---|---|---|
| `NULL` | `NULL`, `ISNULL`, `IS_NULL`, `NONE` | Not set, or set to `null` |
| `EMPTY` | `EMPTY`, `ISEMPTY`, `IS_EMPTY` | Null, empty text, empty list or empty dictionary |
| `ANY` | `ANY` | A list or dictionary with at least one item |
| `GREATER_ZERO` | `GTZ`, `GT0` | A number greater than 0 (false if not a number) |
| `EQUAL_ZERO` | `EQZ`, `EQ0` | A number equal to 0 |
| `LESS_ZERO` | `LTZ`, `LT0` | A number less than 0 |
| `NOT_EQUAL_ZERO` | `NEZ`, `NE0` | A number other than 0 |

### Negated shorthands

Each of these is the same as `NOT` followed by the operator shown.

| Shorthand | Same as |
|---|---|
| `!=`, `<>`, `NE` | `NOT =` |
| `NOTMATCH` | `NOT MATCH` |
| `NOTLIKE` | `NOT LIKE` |
| `NOTIN` | `NOT IN` |
| `NOTCONTAINS` | `NOT CONTAINS` |
| `NOMATCH` | `NOT CMATCH` |
| `NOTNULL`, `ISNOTNULL`, `IS_NOT_NULL` | `NOT NULL` |
| `NOTEMPTY`, `ISNOTEMPTY`, `IS_NOT_EMPTY` | `NOT EMPTY` |

<!-- operators:end -->

## Examples

| Expression | Hosts it selects |
|---|---|
| `app = proxmox` | `app` is exactly `proxmox` |
| `app = proxmox && type = bare-metal` | Both conditions |
| `(app = proxmox AND type = lxc) OR ansible_host = "10.100.4.100"` | Grouping |
| `app != proxmox` | `app` is anything else, **including not set** |
| `app IS NOT NULL AND app != proxmox` | `app` is set to something other than `proxmox` |
| `NOT app LIKE 'prox*'` | `app` doesn't start with `prox` |
| `ansible_host MATCH "^10\.100\.4\.1\d\d$"` | Address in 10.100.4.100–199 |
| `cores >= 16` | Numeric comparison |
| `labels CONTAINS gpu` | `labels: [gpu, storage]` |
| `vlan IN (10, 20)` | `vlan` is 10 or 20 |
| `labels ANY` | `labels` is a non-empty list |
| `name = "web 01"` | Values with spaces must be quoted |
| `net.vlan = 10` | `net: {vlan: 10}` |
| `monitoring = true` | `monitoring: true` (YAML boolean) |
| `inventory_hostname LIKE 'web-*'` | Hosts whose name starts with `web-` |

## Debugging an expression

Set `MIN_LOG_LEVEL: DEBUG` in the config (or temporarily via a separate config with `--config`) and run the inventory script directly. Each group's parsed expression is logged with explicit parentheses, which shows how precedence was applied:

```text
DEBUG loader._set_criteria: Group web criteria: ((NOT app EQUAL 'x' AND type EQUAL 'vm') OR role NULL)
```
