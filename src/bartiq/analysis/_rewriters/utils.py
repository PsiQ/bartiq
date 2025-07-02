# Copyright 2025 PsiQuantum, Corp.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""The Assumptions object allows properties of symbols to be parsed."""
from __future__ import annotations

import re
from ast import literal_eval
from dataclasses import dataclass, field
from enum import Enum

from typing_extensions import Self


class Comparators(str, Enum):
    """A collection of relational symbols for parsing assumptions."""

    GREATER_THAN_OR_EQUAL_TO = ">="
    LESS_THAN_OR_EQUAL_TO = "<="
    GREATER_THAN = ">"
    LESS_THAN = "<"


class Instruction:
    """Base class for all rewriter-transforming instructions."""


@dataclass(frozen=True)
class Initial(Instruction):
    """Special marker for the initial instance."""


@dataclass(frozen=True)
class Simplify(Instruction):
    """Represents a simplify command."""


@dataclass(frozen=True)
class Expand(Instruction):
    """Represents an expand command."""


@dataclass(frozen=True)
class ReapplyAllAssumptions(Instruction):
    """Represents a command that reapplies all assumptions."""


@dataclass(frozen=True)
class Assumption(Instruction):
    """Add a single assumption."""

    symbol_name: str
    comparator: Comparators | str
    value: int | float
    symbol_properties: dict[str, bool | None] = field(init=False)

    def __post_init__(self):
        object.__setattr__(self, "symbol_properties", _get_properties(self.comparator, self.value))

    @classmethod
    def from_string(cls, assumption_string: str) -> Self:
        """Generate an assumption from a valid string.

        Args:
            assumption_string: A string describing an inequality.

        Returns:
            An Assumption class object.
        """
        return cls(*_unpack_assumption(assumption_string))


@dataclass(frozen=True)
class Substitution(Instruction):
    """Substitute a symbol with an expression."""

    symbol: str
    replacement: str


def _get_properties(comparator: str, reference_value: int | float) -> dict[str, bool | None]:
    """Derive properties of an assumption.

    At present this only detects positivity/negativity. The two are calculated independently,
    and so you may see some strange outcomes:
    ```python
    _get_properties(">", 1)
    >>> {positive: True, negative: None}
    ```
    To keep the logic clean, anything unknowable defaults to None. When parsing the symbols in Sympy,
    our only backend at time of writing (July 2025), these fields are filled automatically.

    Args:
        comparator: Comparator in the assumption.
        reference_value: Reference value in the assumption.

    Returns:
        A dictionary of properties for the assumption.
    """

    gt: bool = comparator == Comparators.GREATER_THAN
    gte: bool = comparator == Comparators.GREATER_THAN_OR_EQUAL_TO

    lt: bool = comparator == Comparators.LESS_THAN
    lte: bool = comparator == Comparators.LESS_THAN_OR_EQUAL_TO

    value_positive: bool = reference_value >= 0
    value_negative: bool = reference_value <= 0 or (not value_positive)

    return {"positive": ((gt or gte) and value_positive) or None, "negative": ((lt or lte) and value_negative) or None}


def _unpack_assumption(assumption: str) -> tuple[str, str, int | float]:
    """Unpack an assumption into its components.

    An assumption should take the form of `X ? a`.
    where
    - X is a variable
    - ? is a comparison between X and a, one of '>', '<', '>=', '<='.
    - 'a' is a reference value, either int or float.

    Args:
        assumption (str): An assumption string.

    Raises:
        ValueError: If an unrecognised comparator is passed.

    Returns:
        tuple[str, str, int | float]: A tuple of (variable name, comparator, reference value)
    """
    split_by: str = "(" + ")|(".join(Comparators) + ")"
    parsed = tuple(x for x in re.split(split_by, assumption.replace(" ", "")) if x)
    if len(parsed) != 3:
        raise ValueError(f"Invalid assumption! Could not parse the following input: {assumption}")
    symbol_name, comparator, value = parsed
    try:
        if isinstance(parsed_value := literal_eval(value), int | float):
            value = parsed_value
        else:
            raise ValueError(f"Invalid entry for `value` field. Expected `int | float`, got {type(parsed_value)}.")
    except ValueError as exc:
        if "malformed node or string" in exc.args[0]:
            raise NotImplementedError(
                "Assumption tries to draw a comparison between two variables:"
                f" {symbol_name}, {value}.\n"
                "At present, this is not possible."
            )
        else:
            raise exc
    return symbol_name, comparator, value
