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
from typing import Iterable

from typing_extensions import Self

from bartiq.symbolics.backend import SymbolicBackend

WILDCARD_SYMBOL = "$"


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
    """An instruction dataclass to capture when an assumption is made.

    Args:
        symbol_name: The name of the symbol that the assumption pertains to. Can also be parseable expressions.
        comparator: The comparator: one of ">", "<", ">=", "<=".
        value: The reference value to compare the input symbol to.

    Attributes:
        symbol_properties: A dictionary of properties (non-negativity, non-positivity)
            that can be derived from the assumption.
    """

    symbol_name: str
    comparator: Comparators | str
    value: int | float
    symbol_properties: dict[str, bool | None] = field(init=False)

    def __post_init__(self):
        object.__setattr__(self, "symbol_properties", _get_assumption_properties(self.comparator, self.value))

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
    """An instruction dataclass to capture when an expression is replaced by another.

    Args:
        expr: The (sub)expression to replace.
        replacement: A replacement subexpression.
        backend: The backend to parse the expressions through.
        wild: A tuple of symbols that have been marked as "wild", i.e. they match anything.
    """

    expr: str
    replacement: str
    backend: SymbolicBackend
    wild: tuple[str, ...] = field(default_factory=tuple, init=False)
    linked_params: dict[str, Iterable[str]] = field(default_factory=dict, init=False)

    def __post_init__(self):
        object.__setattr__(self, "wild", _get_wild_characters(self.expr))
        object.__setattr__(self, "linked_params", _get_linked_parameters(self) if not self.wild else {})


def _get_linked_parameters(substitution: Substitution) -> dict[str, Iterable[str]]:
    """Given a substitution object, determine if we can derive a link between parameters.

    Example::
    ```python
        substitution = Substitution("a", "b")
        _get_linked_parameters(substitution)
        >>> { "b": ("a",) }
    ```
    Similarly,
    ```python
        substitution = Substitution("a*(b + c)", "a*X")
        _get_linked_parameters(substitution)
        >>> { "X": ("b", "c")}
    ```
    """

    def free_symbols_in_expr(expr: str) -> Iterable[str]:
        return substitution.backend.free_symbols(substitution.backend.as_expression(expr))

    return {
        x: y
        for x in free_symbols_in_expr(substitution.replacement)
        if x not in (y := free_symbols_in_expr(substitution.expr))
    }


def _get_wild_characters(expression: str) -> tuple[str, ...]:
    """Return all symbols prefixed with the WILDCARD_SYMBOL in an expression."""
    return tuple(re.findall(rf"\{WILDCARD_SYMBOL}([a-zA-Z_][a-zA-Z0-9_]*)", expression))


def _get_assumption_properties(comparator: str, reference_value: int | float) -> dict[str, bool | None]:
    """Derive properties of an assumption.

    The properties derived are:
     - positivity: strictly greater than zero | greater than or equal to a positive value,
     - nonnegativity: greater than or equal to zero | positive,
     - negativity: strictly less than zero | less than or equal to zero,
     - nonpositivity: less than or equal to zero | negative.

    To keep the logic clean, anything unknowable defaults to None.

    When parsing the symbols in Sympy, our only backend at time of writing (July 2025),
    `None` fields are filled automatically.

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

    is_positive = ((gt or gte) and reference_value > 0) or (gt and reference_value == 0)
    is_negative = ((lt or lte) and reference_value < 0) or (lt and reference_value == 0)

    is_nonnegative = is_positive or (gte and reference_value == 0)
    is_nonpositive = is_negative or (lte and reference_value == 0)

    return {
        "positive": is_positive or None,
        "negative": is_negative or None,
        "nonnegative": is_nonnegative or None,
        "nonpositive": is_nonpositive or None,
    }


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


def _unwrap_linked_parameters(
    parameter_connection_reference: dict[str, Iterable[str]],
    variables_to_track: Iterable[str],
    linked: list[str] | None = None,
) -> list[str]:
    """Given a parameter connection reference dictionary (which parameters have been substituted for which),
    and a sequence of variables to track, find all relevant linked parameters.

    Args:
        parameter_connection_reference: All substitutions that have occurred.
        variables_to_track : Which variables we are interested in.
        linked: A list of linked parameters. Defaults to None.

    Returns:
        A list of symbol names, each of which will be transitively related to a variable in variables_to_track.
    """
    linked = linked or []
    for _new, _old in parameter_connection_reference.items():
        if any(x in _old for x in variables_to_track):
            linked.append(_new)
            linked = _unwrap_linked_parameters(parameter_connection_reference, [_new], linked)
    return linked
