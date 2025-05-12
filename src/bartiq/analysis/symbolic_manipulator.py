from typing import TypeAlias
from collections.abc import Iterable

from bartiq import CompiledRoutine

from abc import ABC, abstractmethod

# class Manipulator(ABC):

#     def __init__(self, routine: CompiledRoutine, resource: str):
#         self.routine = routine
#         self._expr = self.routine.resources[resource]

#     @property
#     def expression(self) -> TExpr:
#         """Return the current form of the expression."""
#         return self._expr

#     @expression.setter
#     def expression(self, other: TExpr):
#         self._expr = other

#     @property
#     @abstractmethod
#     def variables(self)-> Iterable[TExpr]:
#         """Return the variable parameters in the expression."""

#     @property
#     @abstractmethod
#     def as_individual_terms(self)-> Iterable[TExpr]:
#         """Return the expression as an iterable of individual terms."""

#     @abstractmethod
#     def substitute(self, pattern_to_replace: TExpr, replace_with: TExpr)->None:
#         """Substitute a pattern in the expression with a user-defined"""

from sympy import Basic, Expr


class SympyManipulation:
    def __init__(self, routine: CompiledRoutine, resource: str):
        self.routine = routine
        self._expr = self.routine.resources[resource]

    @property
    def expression(self) -> Expr:
        return self._expr

    @expression.setter
    def expression(self, other: Expr) -> None:
        self._expr = other

    @property
    def variables(self) -> set[Basic]:
        return self.expression.free_symbols

    def expand(self) -> None:
        self.expression.expand()

    def simplify(self) -> None:
        self.expression.simplify()
