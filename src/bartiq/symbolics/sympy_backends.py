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

# This module is an implementation of SymbolicBackend protocol (with TExpr[S] = sympy.Expr)
# See https://peps.python.org/pep-0544/#modules-as-implementations-of-protocols
# for explanation how a module can implement a protocol.

from __future__ import annotations

from collections.abc import Iterable, Mapping
from functools import singledispatchmethod
from typing import Callable, Concatenate, ParamSpec, TypeVar

import sympy
from sympy import Expr, N, Order, Symbol, symbols
from sympy.core.function import AppliedUndef
from typing_extensions import TypeAlias

from ..errors import BartiqCompilationError
from .ast_parser import parse
from .backend import ComparisonResult, Number, TExpr
from .sympy_interpreter import SPECIAL_FUNCS, SympyInterpreter
from .sympy_interpreter import parse_to_sympy as legacy_parse_to_sympy
from .sympy_serializer import serialize_expression

NUM_DIGITS_PRECISION = 15
# Order included here to allow for user-defined big O's
SYMPY_USER_FUNCTION_TYPES = (AppliedUndef, Order)

BUILT_IN_FUNCTIONS = list(SPECIAL_FUNCS)


S: TypeAlias = Expr | Number

T = TypeVar("T")
P = ParamSpec("P")


MATH_CONSTANTS = {
    "pi": sympy.pi,
    "E": sympy.exp(1),
    "oo": sympy.oo,
    "infinity": sympy.oo,
}


ExprTransformer = Callable[Concatenate["SympyBackend", Expr, P], T]
TExprTransformer = Callable[Concatenate["SympyBackend", TExpr[Expr], P], T]


def empty_for_numbers(func: ExprTransformer[P, Iterable[T]]) -> TExprTransformer[P, Iterable[T]]:
    def _inner(backend: SympyBackend, expr: TExpr[S], *args: P.args, **kwargs: P.kwargs) -> Iterable[T]:
        return () if isinstance(expr, Number) else func(backend, expr, *args, **kwargs)

    return _inner


def identity_for_numbers(func: ExprTransformer[P, T | Number]) -> TExprTransformer[P, T | Number]:
    def _inner(backend: SympyBackend, expr: TExpr[S], *args: P.args, **kwargs: P.kwargs) -> T | Number:
        return expr if isinstance(expr, Number) else func(backend, expr, *args, **kwargs)

    return _inner


def parse_to_sympy(expression: str, debug: bool = False) -> Expr:
    """Parse given mathematical expression into a sympy expression.

    Args:
        expression: expression to be parsed.
        debug: flag indicating if SympyInterpreter should use debug prints. Defaults to False
            for performance reasons.
    Returns:
        A Sympy expression object parsed from `expression`.
    """
    return parse(expression, interpreter=SympyInterpreter(debug=debug))


@identity_for_numbers
def _define_function(expr: Expr, func_name: str, function: Callable) -> TExpr[Expr]:
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


class SympyBackend:

    def __init__(self, parse_function: Callable[[str], Expr] = parse_to_sympy):
        self.parse = parse_function

    @singledispatchmethod
    def _as_expression(self, value: TExpr[Expr]) -> TExpr[Expr]:
        return value

    @_as_expression.register
    def _parse(self, value: str) -> TExpr[Expr]:
        return parse_to_sympy(value)

    def as_expression(self, value: TExpr[S] | str) -> TExpr[Expr]:
        """Convert numerical or textual value into an expression."""
        return self._as_expression(value)

    @identity_for_numbers
    def parse_constant(self, expr: Expr) -> TExpr[Expr]:
        """Parse the expression, replacing known constants while ignoring case."""
        for symbol_str, constant in MATH_CONSTANTS.items():
            expr = expr.subs(Symbol(symbol_str.casefold()), constant)
            expr = expr.subs(Symbol(symbol_str.upper()), constant)
            expr = expr.subs(Symbol(symbol_str.capitalize()), constant)

        return expr

    @identity_for_numbers
    def as_native(self, expr: Expr) -> str | int | float:
        return value if (value := self.value_of(expr)) is not None else self.serialize(expr)

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
    def substitute(
        self,
        expr: Expr,
        /,
        replacements: Mapping[str, TExpr[Expr]],
        functions_map: Mapping[str, Callable[[TExpr[Expr]], TExpr[Expr]]] | None = None,
    ) -> TExpr[Expr]:

        symbols_in_expr = self.free_symbols_in(expr)
        restricted_replacements = [(symbols(old), new) for old, new in replacements.items() if old in symbols_in_expr]
        expr = expr.subs(restricted_replacements)
        if functions_map is None:
            functions_map = {}
        for func_name, func in functions_map.items():
            expr = _define_function(expr, func_name, func)
        return value if (value := self.value_of(expr)) is not None else expr

    def is_constant_int(self, expr: TExpr[Expr]):
        """Return True if a given expression represents a constant int and False otherwise."""
        try:
            _ = int(str(expr))
            return True
        except ValueError:
            return False

    def is_single_parameter(self, expr: TExpr[Expr]) -> bool:
        """Determine if the expression is a single parameter.

        For SymPy backend, single parameters are just instances of Symbol.
        """
        return isinstance(expr, Symbol)

    def serialize(self, expr: TExpr[Expr]) -> str:
        """Return a textual representation of given expression."""
        if isinstance(expr, Number):
            return str(expr)
        return serialize_expression(expr)

    def compare(self, lhs: TExpr[Expr], rhs: TExpr[Expr]) -> ComparisonResult:
        difference = self.as_expression(lhs - rhs)
        if not isinstance(difference, Number):
            difference = difference.expand()
        if difference == 0 or difference == 0.0:  # In sympy 0.0 is different than 0
            return ComparisonResult.equal
        elif self.is_constant_int(difference):
            return ComparisonResult.unequal
        else:
            return ComparisonResult.ambigous

    def func(self, func_name: str) -> Callable[..., TExpr[Expr]]:
        try:
            return SPECIAL_FUNCS[func_name]
        except KeyError:
            return sympy.Function(func_name)

    def sum(self, term: TExpr[T], iterator_symbol: TExpr[T], start: TExpr[T], end: TExpr[T]) -> TExpr[T]:
        """Express a sum of terms expressed using `iterator_symbol`."""
        return sympy.Sum(term, (iterator_symbol, start, end))

    def prod(self, term: TExpr[T], iterator_symbol: TExpr[T], start: TExpr[T], end: TExpr[T]) -> TExpr[T]:
        """Express a product of terms expressed using `iterator_symbol`."""
        return sympy.Product(term, (iterator_symbol, start, end))


# Define sympy_backend for backwards compatibility
sympy_backend = SympyBackend(parse_to_sympy)

# And a shortcut for backend using a legacy parser
legacy_sympy_backend = SympyBackend(legacy_parse_to_sympy)
