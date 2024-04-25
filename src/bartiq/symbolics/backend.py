"""
..  Copyright © 2024 PsiQuantum Corp.  All rights reserved.
    PSIQUANTUM CORP. CONFIDENTIAL
    This file includes unpublished proprietary source code of PsiQuantum Corp.
    The copyright notice above does not evidence any actual or intended publication
    of such source code. Disclosure of this source code or any related proprietary
    information is strictly prohibited without the express written permission of
    PsiQuantum Corp.
"""

from typing import Callable, Iterable, Optional, Protocol, TypeVar, Union

from ..compilation.types import Number

T_expr = TypeVar("T_expr")


class SymbolicBackend(Protocol[T_expr]):
    """Protocol describing capabilities of backends used for manipulating symbolic expressions."""

    def as_expression(self, value: str | int | float) -> T_expr:
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

    def rename_function(self, expr: T_expr, old_name: str, new_name: str) -> T_expr:
        """Rename all instances of given function call."""

    def define_function(self, expr: T_expr, func_name: str, function: Callable) -> T_expr:
        """Define an undefined function."""

    def is_constant_int(self, expr: T_expr) -> bool:
        """Return True if a given expression represents a constant int and False otherwise."""

    def serialize(self, expr: T_expr) -> str:
        """Return a textual representation of given expression."""
