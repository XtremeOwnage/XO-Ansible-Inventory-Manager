"""
Splits a criteria string into raw tokens.

The lexer only knows about shapes (words, quoted strings, symbols, parentheses).
Whether a word is a variable, a value or a keyword depends on where it appears,
so that decision is left to the parser.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .definitions import OPERATOR_SYMBOLS, QUOTE_SYMBOLS, WORD_SYMBOLS
from .errors import CriteriaError


class TokenKind(Enum):
    WORD = "word"  # Unquoted text: variable, keyword or value
    STRING = "string"  # Quoted text: always a value
    SYMBOL = "symbol"  # Symbolic operator such as >= or &&
    LPAREN = "("
    RPAREN = ")"
    COMMA = ","
    END = "end"


@dataclass(frozen=True)
class Token:
    kind: TokenKind
    text: str
    position: int

    def __str__(self) -> str:
        if self.kind is TokenKind.END:
            return "end of expression"
        if self.kind is TokenKind.STRING:
            return f'"{self.text}"'
        return f"'{self.text}'"


def _is_word_char(char: str) -> bool:
    return char.isalnum() or char in WORD_SYMBOLS


def _read_quoted(criteria: str, start: int) -> tuple[str, int]:
    """
    Read a quoted value starting at `start` (the opening quote).

    A backslash only escapes the active quote character or another backslash.
    Any other backslash is kept, so regular expressions such as "^10\\.0\\.\\d+$"
    reach the regex engine unchanged.

    Returns:
        (value without quotes, index after the closing quote)
    """
    quote = criteria[start]
    i = start + 1
    chars: list[str] = []
    while i < len(criteria):
        char = criteria[i]
        if char == "\\" and i + 1 < len(criteria) and criteria[i + 1] in (quote, "\\"):
            chars.append(criteria[i + 1])
            i += 2
            continue
        if char == quote:
            return "".join(chars), i + 1
        chars.append(char)
        i += 1
    raise CriteriaError(f"Unterminated quoted value starting at position {start}", criteria, start)


def tokenize(criteria: str) -> list[Token]:
    """
    Split `criteria` into tokens. The returned list always ends with an END token.

    Raises:
        CriteriaError: On an unterminated quote or a character that cannot start a token.
    """
    tokens: list[Token] = []
    i = 0
    while i < len(criteria):
        char = criteria[i]

        if char.isspace():
            i += 1
        elif char in QUOTE_SYMBOLS:
            value, end = _read_quoted(criteria, i)
            tokens.append(Token(TokenKind.STRING, value, i))
            i = end
        elif char == "(":
            tokens.append(Token(TokenKind.LPAREN, char, i))
            i += 1
        elif char == ")":
            tokens.append(Token(TokenKind.RPAREN, char, i))
            i += 1
        elif char == ",":
            tokens.append(Token(TokenKind.COMMA, char, i))
            i += 1
        elif _is_word_char(char):
            start = i
            while i < len(criteria) and _is_word_char(criteria[i]):
                i += 1
            tokens.append(Token(TokenKind.WORD, criteria[start:i], start))
        else:
            symbol = next((s for s in OPERATOR_SYMBOLS if criteria.startswith(s, i)), None)
            if symbol is None:
                raise CriteriaError(f"Unexpected character '{char}' at position {i}", criteria, i)
            tokens.append(Token(TokenKind.SYMBOL, symbol, i))
            i += len(symbol)

    tokens.append(Token(TokenKind.END, "", len(criteria)))
    return tokens
