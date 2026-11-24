"""The grounding check (plan section 8.4, check 4): every number written in digits in the answer's
prose must match a number in the tool results it cites, or in those calls' arguments, allowing for
rounding to the decimals written.

Known limit, stated in the plan: it reads digits, not number words. "Roughly twice" is not caught;
the tools return differences and ratios ready-made so the model need not do arithmetic in words.
"""

import math
import re
from collections.abc import Iterable
from typing import Any

# A number: digits with optional thousands commas and an optional decimal part, or a decimal part
# alone (".93"). A hyphen between two numbers ("2016-2025") separates them; nothing here reads a
# minus sign. Digits stuck to letters ("R1", "x7") are not read: result ids and codes are not figures.
_NUMBER = re.compile(r"(?<![\w.])(?:(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?|\.(\d+))")


def numbers_in_text(text: str) -> list[tuple[str, float, int]]:
    """Each number written in digits: (as written, value, decimals written)."""
    found = []
    for match in _NUMBER.finditer(text):
        whole, fraction = match.group(1) or "0", match.group(2) or match.group(3)
        written = match.group(0)
        value = float(whole.replace(",", "") + (f".{fraction}" if fraction else ""))
        found.append((written, value, len(fraction) if fraction else 0))
    return found


def source_numbers(results: Iterable[Any], arguments: Iterable[Any]) -> set[float]:
    """Every number in the cited results and their arguments: numeric values, and digits inside text."""
    numbers: set[float] = set()

    def walk(value: Any) -> None:
        if isinstance(value, bool) or value is None:
            return
        if isinstance(value, (int, float)):
            numbers.add(float(value))
        elif isinstance(value, str):
            numbers.update(n for _, n, _ in numbers_in_text(value))
        elif isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                walk(item)

    for item in [*results, *arguments]:
        walk(item)
    return numbers


def ungrounded(text: str, results: Iterable[Any], arguments: Iterable[Any]) -> list[str]:
    """The numbers in `text` that match nothing in the sources, as written."""
    sources = source_numbers(list(results), list(arguments))
    missing = []
    for written, value, decimals in numbers_in_text(text):
        if not any(math.isclose(_round_half_up(s, decimals), value, abs_tol=1e-9) for s in sources):
            missing.append(written)
    return missing


def _round_half_up(value: float, decimals: int) -> float:
    """Round as a person reads a figure: 2.25 to one decimal is 2.3. A tiny nudge absorbs float error."""
    factor = 10**decimals
    return math.floor(value * factor + 0.5 + 1e-9) / factor
