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

# This module is an implementation of SymbolicBackend protocol (with T_expr = sympy.Expr)
# See https://peps.python.org/pep-0544/#modules-as-implementations-of-protocols
# for explanation how a module can implement a protocol.

from __future__ import annotations

from functools import singledispatch
from typing import Callable, Iterable, Optional, Union

from sympy import Expr, Function, N, Order, symbols, sympify
from sympy.core.function import AppliedUndef

from ..compilation.types import Number
from ..errors import BartiqCompilationError
from .sympy_interpreter import SPECIAL_FUNCS, TRY_IF_POSSIBLE_FUNCS, parse_to_sympy
from .sympy_serializer import serialize_expression

NUM_DIGITS_PRECISION = 15
# Order included here to allow for user-defined big O's
SYMPY_USER_FUNCTION_TYPES = (AppliedUndef, Order)

BUILT_IN_FUNCTIONS = list(SPECIAL_FUNCS) + list(TRY_IF_POSSIBLE_FUNCS)


T_expr = Expr


@singledispatch
def _as_expression(value: Union[str | int | float]) -> T_expr:
    return sympify(value)


@_as_expression.register
def _parse(value: str) -> T_expr:
    return parse_to_sympy(value)


def as_expression(value: Union[str | int | float]) -> T_expr:
    """Convert numerical or textual value into an expression."""
    return _as_expression(value)


def free_symbols_in(expr: T_expr) -> Iterable[str]:
    """Return an iterable over free symbol names in given expression."""
    return map(str, expr.free_symbols)


def functions_in(expr: T_expr) -> Iterable[str]:
    """Returns the (non-built-in) functions referenced in the expression."""
    return [
        func_name
        for atom in expr.atoms(*SYMPY_USER_FUNCTION_TYPES)
        if (func_name := str(type(atom))) not in reserved_functions()
    ]


def reserved_functions() -> Iterable[str]:
    """Return an iterable over all built-in functions."""
    return BUILT_IN_FUNCTIONS


def value_of(expr: T_expr) -> Optional[Number]:
    """Compute a numerical value of an expression, return None if it not possible."""
    # If numeric value possible, evaluate, otherwise return None
    try:
        value = N(expr).round(n=NUM_DIGITS_PRECISION)

    except TypeError as e:
        if str(e) == "Cannot round symbolic expression":
            return None
        else:
            raise e

    # Map to integer if possible
    if int(value) == value:
        value = int(value)

    return value


def substitute(expr: T_expr, symbol: str, replacement: Union[T_expr, Number]) -> T_expr:
    """Substitute occurrences of given symbol with an expression or numerical value."""
    return (
        as_expression(serialize(expr.subs(symbols(symbol), replacement))) if symbol in free_symbols_in(expr) else expr
    )


def rename_function(expr: T_expr, old_name: str, new_name: str) -> T_expr:
    """Rename all instances of given function call."""
    if old_name in BUILT_IN_FUNCTIONS:
        raise BartiqCompilationError(
            f"Attempted to rename the special function {old_name} (to {new_name}); cannot rename special functions."
        )
    if new_name in BUILT_IN_FUNCTIONS:
        raise BartiqCompilationError(
            f"Attempted to rename the function {old_name} to the special function {new_name}); "
            " cannot rename functions to special functions."
        )

    # Rename the function
    return expr.replace(
        lambda pattern: isinstance(pattern, SYMPY_USER_FUNCTION_TYPES) and str(type(pattern)) == old_name,
        lambda function: Function(new_name)(*function.args),
    )


def define_function(expr: T_expr, func_name: str, function: Callable) -> T_expr:
    """Define an undefined function."""
    # Catch attempt to define special function names
    if func_name in BUILT_IN_FUNCTIONS:
        raise BartiqCompilationError(
            f"Attempted to redefine the special function {func_name}; cannot " "define special functions."
        )

    # Trying to evaluate a function which cannot be evaluated symbolically raises TypeError.
    # This, however, is expected for certain functions (e.g. with conditions)
    try:
        return expr.replace(
            lambda pattern: isinstance(pattern, SYMPY_USER_FUNCTION_TYPES) and str(type(pattern)) == func_name,
            lambda match: function(*match.args),
        )
    except TypeError:
        return expr


def is_constant_int(expr: T_expr):
    """Return True if a given expression represents a constant int and False otherwise."""
    try:
        int(str(expr))
        return True
    except ValueError:
        return False


def serialize(expr: T_expr) -> str:
    """Return a textual representation of given expression."""
    return serialize_expression(expr)
