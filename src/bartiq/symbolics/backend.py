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

from enum import Enum, auto
from typing import Callable, Iterable, Mapping, Optional, Protocol, TypeVar, Union

from ..compilation.types import Number

T_expr = TypeVar("T_expr", bound=Number, contravariant=True)


class ComparisonResult(Enum):
    equal = auto()
    unequal = auto()
    ambigous = auto()


class SymbolicBackend(Protocol[T_expr]):
    """Protocol describing capabilities of backends used for manipulating symbolic expressions."""

    def as_expression(self, value: Union[str, int, float]) -> T_expr:
        """Convert given value into an expression native to this backend."""

    def free_symbols_in(self, expr: T_expr) -> Iterable[str]:
        """Return an iterable over free symbols in given expression."""

    def functions_in(self, expr: T_expr) -> Iterable[str]:
        """Return an iterable over functions in expr."""

    def reserved_functions(self) -> Iterable[str]:
        """Return an iterable over reserved functions."""

    def value_of(self, expr: T_expr) -> Optional[Number]:
        """Return value of given expression."""

    def substitute(self, expr: T_expr, symbol: str, replacement: Union[T_expr, Number]) -> T_expr:
        """Substitute all occurrences of symbol in expr with given replacement."""

    def substitute_all(self, expr: T_expr, replacements: Mapping[str, Union[T_expr, Number]]) -> T_expr:
        """Substitute all occurrences of all symbols in expr with given replacements."""

    def rename_function(self, expr: T_expr, old_name: str, new_name: str) -> T_expr:
        """Rename all instances of given function call."""

    def define_function(self, expr: T_expr, func_name: str, function: Callable) -> T_expr:
        """Define an undefined function."""

    def is_constant_int(self, expr: T_expr) -> bool:
        """Return True if a given expression represents a constant int and False otherwise."""

    def serialize(self, expr: T_expr) -> str:
        """Return a textual representation of given expression."""

    def parse_constant(self, expr: T_expr) -> T_expr:
        """Parse the expression, replacing known constants while ignoring case."""

    def compare(self, lhs: T_expr, rhs: T_expr) -> ComparisonResult:
        """Compare lhs and rhs, returning comparison result.

        Note that unlike boolean values, comparison might be ambigous if the
        backend fails to simplify or interpret the expressions being compared.

        Therefore, meaning of the result should be interpreter as fallows:

        - `ComparisonResult.equal`: `lhs` and `rhs` are certainly equal.
        - `ComparisonResult.unequal': 'lhs' and 'rhs' are certainly not equal.
        - `ComparisonResult.ambigous`: it is not known for certain if `lhs` and `rhs` are equal.
        """
