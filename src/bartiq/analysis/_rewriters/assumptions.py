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
from typing import Self
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
    value: Number | str

    def __post_init__(self):
        self.symbol_properties = _get_properties(self.symbol_name, self.relationship, self.value)

    def __repr__(self)->str:
        return f"{self.__class__.__name__}({self.symbol_name}{self.relationship}{self.value})"

    @classmethod
    def from_string(cls, assumption_string: str) -> Self:
        return cls(*_unpack_assumption(assumption_string))
    

class SympyAssumption(Assumption):
    "A class for defining assumptions on variables in sympy."
    def to_symbol(self) -> Symbol:
        """Return a sympy Symbol object with the correct properties."""
        return Symbol(self.symbol_name, **self.symbol_properties)



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
        nonzero=(gt and value_positive)
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
