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

from abc import abstractmethod
from collections.abc import Iterable, Mapping
from functools import singledispatchmethod
from typing import Callable, Concatenate, ParamSpec, Protocol, TypeVar

import sympy
from sympy import Expr, N, Order, Symbol, symbols
from sympy.core.function import AppliedUndef
from typing_extensions import TypeAlias

from ..errors import BartiqCompilationError
from .ast_parser import parse
from .backend import ComparisonResult, Number
from .sympy_interpreter import SPECIAL_FUNCS, SympyInterpreter
from .sympy_interpreter import parse_to_sympy as legacy_parse_to_sympy
from .sympy_serializer import serialize_expression

NUM_DIGITS_PRECISION = 15
# Order included here to allow for user-defined big O's
SYMPY_USER_FUNCTION_TYPES = (AppliedUndef, Order)

BUILT_IN_FUNCTIONS = list(SPECIAL_FUNCS)


T_expr: TypeAlias = Expr | Number

T = TypeVar("T")
P = ParamSpec("P")


MATH_CONSTANTS = {
    "pi": sympy.pi,
    "E": sympy.exp(1),
    "oo": sympy.oo,
    "infinity": sympy.oo,
}


ExprTransformer = Callable[Concatenate["SympyBackend", Expr, P], T]
TExprTransformer = Callable[Concatenate["SympyBackend", T_expr, P], T]


def empty_for_numbers(func: ExprTransformer[P, Iterable[T]]) -> TExprTransformer[P, Iterable[T]]:
    def _inner(backend: SympyBackend, expr: T_expr, *args: P.args, **kwargs: P.kwargs) -> Iterable[T]:
        return () if isinstance(expr, Number) else func(backend, expr, *args, **kwargs)

    return _inner


def identity_for_numbers(func: ExprTransformer[P, T | Number]) -> TExprTransformer[P, T | Number]:
    def _inner(backend: SympyBackend, expr: T_expr, *args: P.args, **kwargs: P.kwargs) -> T | Number:
        return expr if isinstance(expr, Number) else func(backend, expr, *args, **kwargs)

    return _inner


class _SympyParser(Protocol[P]):

    @abstractmethod
    def __call__(self, expression: str, *args: P.args, **kwargs: P.kwargs) -> T_expr:
        pass


def parse_to_sympy(expression: str, debug: bool = False) -> T_expr:
    """Parse given mathematical expression into a sympy expression.

    Args:
        expression: expression to be parsed.
        debug: flag indicating if SympyInterpreter should use debug prints. Defaults to False
            for performance reasons.
    Returns:
        A Sympy expression object parsed from `expression`.
    """
    return parse(expression, interpreter=SympyInterpreter(debug=debug))


class SympyBackend:

    def __init__(self, parse_function: _SympyParser[P] = parse_to_sympy):
        self.parse = parse_function

    @singledispatchmethod
    def _as_expression(self, value: Expr | Number) -> T_expr:
        return value

    @_as_expression.register
    def _parse(self, value: str) -> T_expr:
        return parse_to_sympy(value)

    def as_expression(self, value: str | T_expr) -> T_expr:
        """Convert numerical or textual value into an expression."""
        return self._as_expression(value)

    @identity_for_numbers
    def parse_constant(self, expr: Expr) -> T_expr:
        """Parse the expression, replacing known constants while ignoring case."""
        for symbol_str, constant in MATH_CONSTANTS.items():
            expr = expr.subs(Symbol(symbol_str.casefold()), constant)
            expr = expr.subs(Symbol(symbol_str.upper()), constant)
            expr = expr.subs(Symbol(symbol_str.capitalize()), constant)

        return expr

    @empty_for_numbers
    def free_symbols_in(self, expr: Expr) -> Iterable[str]:
        """Return an iterable over free symbol names in given expression."""
        return tuple(map(str, expr.free_symbols))  # type: ignore

    def reserved_functions(self) -> Iterable[str]:
        """Return an iterable over all built-in functions."""
        return BUILT_IN_FUNCTIONS

    @identity_for_numbers
    def value_of(self, expr: Expr) -> Number | None:
        """Compute a numerical value of an expression, return None if it's not possible."""
        try:
            value = N(expr).round(n=NUM_DIGITS_PRECISION)
        except TypeError as e:
            if str(e) == "Cannot round symbolic expression":
                return None
            else:
                raise e

        # Map to integer if possible
        if int(value) == value or value.is_Float and value % 1 == 0:
            value = int(value)
        else:
            value = float(value)
        return value

    @identity_for_numbers
    def substitute(self, expr: Expr, symbol: str, replacement: T_expr | Number) -> T_expr:
        return expr.subs(symbols(symbol), replacement) if symbol in self.free_symbols_in(expr) else expr

    @identity_for_numbers
    def substitute_all(self, expr: Expr, replacements: Mapping[str, T_expr]) -> T_expr:
        symbols_in_expr = self.free_symbols_in(expr)
        restricted_replacements = [(symbols(old), new) for old, new in replacements.items() if old in symbols_in_expr]
        return expr.subs(restricted_replacements)

    # @identity_for_numbers
    def define_function(self, expr: T_expr, func_name: str, function: Callable) -> T_expr:
        """Define an undefined function."""
        # Catch attempt to define special function names
        if func_name in BUILT_IN_FUNCTIONS:
            raise BartiqCompilationError(
                f"Attempted to redefine the special function {func_name}; cannot define special functions."
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

    def is_constant_int(self, expr: T_expr):
        """Return True if a given expression represents a constant int and False otherwise."""
        try:
            _ = int(str(expr))
            return True
        except ValueError:
            return False

    def serialize(self, expr: T_expr) -> str:
        """Return a textual representation of given expression."""
        if isinstance(expr, Number):
            return str(expr)
        return serialize_expression(expr)

    def compare(self, lhs: T_expr, rhs: T_expr) -> ComparisonResult:
        difference = self.as_expression(lhs - rhs).expand()
        if difference == 0:
            return ComparisonResult.equal
        elif self.is_constant_int(difference):
            return ComparisonResult.unequal
        else:
            return ComparisonResult.ambigous

    @property
    def expr_type(self) -> type[T_expr]:
        return T_expr


# Define sympy_backend for backwards compatibility
sympy_backend = SympyBackend(parse_to_sympy)

# And a shortcut for backend using a legacy parser
legacy_sympy_backend = SympyBackend(legacy_parse_to_sympy)
