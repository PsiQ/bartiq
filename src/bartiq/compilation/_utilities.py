# Copyright 2024 PsiQuantum, Corp.
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

import ast
from typing import Any, TypeVar

from .. import Routine
from ..errors import BartiqCompilationError
from .types import NUMBER_TYPES, Number

T = TypeVar("T", bound=Routine)


def is_single_parameter(expression: Any) -> bool:
    """Returns True if the expression is just a single parameter, else False."""
    try:
        return _is_python_tree_a_single_param(
            ast.parse(
                expression.replace("#", "__hash__").replace(  # Handle hashes in port names
                    "lambda", "__lambda__"
                )  # Handle special case of lambda
            )
        )
    except (TypeError, AttributeError):
        return False  # If it's not a string then certainly it's not a single parameter
    except SyntaxError as e:  # In principle this should not happen
        raise ValueError(
            f"Expression {expression} failed to parse. This is most likely a bug " "in Bartiq, please report it."
        ) from e


def _is_python_tree_a_single_param(tree):
    return (
        # is parsed expression a module?
        isinstance(tree, ast.Module)
        and
        # Having one child?
        len(tree.body) == 1
        and
        # And this only child is an expression?
        isinstance(tree.body[0], ast.Expr)
        and
        # And this expression contains only a variable Name or an Attribute access?
        isinstance(tree.body[0].value, (ast.Name, ast.Attribute))
    )


def is_number_string(s: str) -> bool:
    """Returns False if the string encodes a number."""
    try:
        float(s)
        return True
    except ValueError:
        return False


def is_non_negative_int(value: Any) -> bool:
    """Returns True if the expression corresponds to a positive integer."""
    try:
        return float(value) >= 0 and int(value) == float(value)
    except ValueError:
        return False


def is_constant_int(expression: Any) -> bool:
    """Returns True if the expression corresponds to a constant."""
    expression = str(expression)
    if isinstance(expression, str):
        try:
            int(expression)
            return True
        except ValueError:
            return False
    return isinstance(expression, int)


def get_children_in_walk_order(routine: T) -> list[T]:
    """Returns routine children in walk order."""
    return [op for op in routine.walk() if op in routine.children.values()]


def parse_value(value_str: str) -> Number:
    """Attempts to parse a single value string, but throws a compilation error if this isn't possible."""
    try:
        value = ast.literal_eval(value_str)
        if not isinstance(value, NUMBER_TYPES):
            raise ValueError
        return value
    except ValueError:
        raise BartiqCompilationError(f"Could not parse value {value_str}; values must be integers or floats.")


def split_equation(equation: str) -> tuple[str, str]:
    """Splits an equation string and returns the left and right side."""
    if equation.count("=") != 1:
        raise ValueError(f"Equations must contain a single equals sign; found {equation}")

    lhs, rhs = equation.split("=")
    lhs = lhs.strip()
    rhs = rhs.strip()

    if not lhs or not rhs:
        raise ValueError(f"Equations must have both a left- and right-hand side; found {equation}")

    return (lhs, rhs)
