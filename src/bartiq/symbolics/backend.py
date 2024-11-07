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
from collections.abc import Iterable, Mapping
from enum import Enum, auto
from typing import Callable, Protocol, TypeAlias, TypeVar

Number = int | float
T = TypeVar("T")

TExpr: TypeAlias = Number | T


class ComparisonResult(Enum):
    equal = auto()
    unequal = auto()
    ambigous = auto()


class SymbolicBackend(Protocol[T]):
    """Protocol describing capabilities of backends used for manipulating symbolic expressions."""

    def as_expression(self, value: TExpr[T] | str) -> TExpr[T]:
        """Convert given value into an expression native to this backend."""

    def as_native(self, expr: TExpr[T]) -> str | int | float:
        """Convert given expression as an instance of a native type."""

    def free_symbols_in(self, expr: TExpr[T], /) -> Iterable[str]:
        """Return an iterable over free symbols in given expression."""

    def reserved_functions(self) -> Iterable[str]:
        """Return an iterable over reserved functions."""

    def value_of(self, expr: TExpr[T], /) -> Number | None:
        """Return value of given expression."""

    def substitute(
        self,
        expr: TExpr[T],
        /,
        replacements: Mapping[str, TExpr[T]],
        functions_map: Mapping[str, Callable[[TExpr[T]], TExpr[T]]] | None = None,
    ) -> TExpr[T]:
        """Substitute all occurrences of symbols and functions in expr with given replacements and functions_map."""

    def is_constant_int(self, expr: TExpr[T], /) -> bool:
        """Return True if a given expression represents a constant int and False otherwise."""

    def serialize(self, expr: TExpr[T], /) -> str:
        """Return a textual representation of given expression."""

    def parse_constant(self, expr: TExpr[T], /) -> TExpr[T]:
        """Parse the expression, replacing known constants while ignoring case."""

    def is_single_parameter(self, expr: TExpr[T], /) -> bool:
        """Determine if given expression is a single paramater."""

    def compare(self, lhs: TExpr[T], rhs: TExpr[T]) -> ComparisonResult:
        """Compare lhs and rhs, returning comparison result.

        Note that unlike boolean values, comparison might be ambigous if the
        backend fails to simplify or interpret the expressions being compared.

        Therefore, meaning of the result should be interpreter as fallows:

        - `ComparisonResult.equal`: `lhs` and `rhs` are certainly equal.
        - `ComparisonResult.unequal': 'lhs' and 'rhs' are certainly not equal.
        - `ComparisonResult.ambigous`: it is not known for certain if `lhs` and `rhs` are equal.
        """

    def func(self, func_name: str) -> Callable[..., TExpr[T]]:
        """Obtain an implementation of a function with given name."""

    def sum(self, term: TExpr[T], iterator_symbol: TExpr[T], start: TExpr[T], end: TExpr[T]) -> TExpr[T]:
        """Express a sum of terms expressed using `iterator_symbol`."""

    def prod(self, term: TExpr[T], iterator_symbol: TExpr[T], start: TExpr[T], end: TExpr[T]) -> TExpr[T]:
        """Express a product of terms expressed using `iterator_symbol`."""
