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
from numbers import Number
import re

from dataclasses import dataclass
from sympy import Symbol

from enum import StrEnum


class Relationals(StrEnum):
    """A collection of relational symbols for parsing assumptions."""

    GREATER_THAN_OR_EQUAL_TO = ">="
    LESS_THAN_OR_EQUAL_TO = "<="
    GREATER_THAN = ">"
    LESS_THAN = "<"


@dataclass
class Assumption:
    """A simple class for storing information about symbol assumptions."""

    symbol_name: str
    relationship: Relationals
    value: Number

    def __post_init__(self):
        self.symbol_properties = _get_properties(self.symbol_name, self.relationship, self.value)

    def to_symbol(self) -> Symbol:
        """Return a sympy Symbol object with the correct properties."""
        return Symbol(self.symbol_name, **self.symbol_properties)

    @classmethod
    def from_string(cls, assumption_string: str) -> Assumption:
        return Assumption(*_unpack_assumption(assumption_string))


# def _apply_assumption(expression: Expr, assumption: str) -> Expr:
#     """Apply an assumption to a given expression.

#     Args:
#         expression (Expr): Expression to add an assumption to.
#         assumption (str): Assumption, of the form A ? B.

#     Returns:
#         Expr
#     """
#     var, _, value, properties = _parse_assumption(assumption=assumption)
#     try:
#         reference_symbol: Symbol = next(symbol for symbol in expression.free_symbols if symbol.name == var)
#         replacement = Symbol(
#             var,
#             positive=properties.get("positive"),
#             negative=properties.get("negative"),
#             nonzero=properties.get("nonzero"),
#         )
#         expression = expression.subs({reference_symbol: replacement})
#         reference_symbol = replacement
#     except StopIteration:
#         reference_symbol: Expr = parse_to_sympy(var)
#         for _sym in reference_symbol.free_symbols:
#             reference_symbol = reference_symbol.subs(
#                 _sym, next(symbol for symbol in expression.free_symbols if symbol.name == _sym.name)
#             )

#     replacement_symbol = Symbol(
#         name="O",
#         positive=properties.get("positive"),
#         negative=properties.get("negative"),
#         nonzero=properties.get("nonzero"),
#     )
#     expression = expression.subs({reference_symbol: replacement_symbol + value}).subs(
#         {replacement_symbol: reference_symbol - value}
#     )
#     return expression


def _get_properties(variable: str, relationship: str, reference_value: str | Number) -> dict[str, bool | None]:
    """Derive properties of a

    Args:
        variable: Variable involved in the assumption.
        relationship: Relationship in the assumption.
        reference_value: Reference value in the assumption.

    Returns:
        A dictionary of properties for the assumption.
    """

    if not isinstance(reference_value, Number):
        try:
            reference_value = eval(reference_value)
        except NameError:
            raise NotImplementedError(
                f"""Assumption tries to draw a relationship between two variables: {variable}, {reference_value}.
                At present, this is not possible!"""
            )

    gt: bool = relationship == Relationals.GREATER_THAN
    gte: bool = relationship == Relationals.GREATER_THAN_OR_EQUAL_TO

    lt: bool = relationship == Relationals.LESS_THAN
    lte: bool = relationship == Relationals.LESS_THAN_OR_EQUAL_TO

    value_positive: bool = reference_value >= 0
    value_negative: bool = reference_value <= 0 or (not value_positive)
    value_non_zero: bool = reference_value != 0

    properties: dict[str, bool | None] = dict(
        positive=((gt or gte) and value_positive),
        negative=((lt or lte) and value_negative),
        zero=(gt and value_positive)
        or (lt and value_negative)
        or (gte and value_positive and value_non_zero)
        or (lte and value_negative and value_non_zero)
        or None,
    )

    return properties


def _unpack_assumption(assumption: str) -> tuple[str, str, str]:
    """Unpack an assumption into its components.

    An assumption should take the form of `A ? B`.
    where
    - A is a variable
    - ? is a relation between A and B, one of '>', '<', '>=', '<='.
    - B is a reference value, either another variable or a number.

    Args:
        assumption (str): An assumption string.

    Raises:
        ValueError: If an unrecognised relationship is passed.

    Returns:
        tuple[str, str, str]: A tuple of (variable name, relation, reference value)
    """
    split_by: str = "(" + ")|(".join(Relationals) + ")"
    parsed = tuple(x for x in re.split(split_by, assumption.replace(" ", "")) if x)
    if len(parsed) != 3:
        raise ValueError(f"Invalid assumption! Could not parse the following input: {assumption}")
    return parsed


if __name__ == "__main__":
    a = Assumption("A", ">=", 0)
    print(a.symbol_properties)
