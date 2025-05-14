from __future__ import annotations
from typing import Any, TypeVar
from collections.abc import Callable, Iterable
from abc import ABC, abstractmethod

from bartiq import CompiledRoutine
from bartiq.symbolics.backend import SymbolicBackend

T = TypeVar("T")
TExpr = str | T


def update_expression(function: Callable[[Any], TExpr]):
    """Decorator for updating the stored expression in Manipulator."""

    def wrapper(self: Manipulator, *args, **kwargs):
        self.expression = function(self, *args, **kwargs)
        return self.expression

    return wrapper


class Manipulator(ABC):
    """A base class for symbolic manipulation, or simplification, tools.

    Args:
        routine: A compiled routine object.
        resource: A string indicating the resource we wish to act on.
        backend: Optional argument indicating the symbolic backend required, by default sympy_backend.
    """

    def __init__(self, routine: CompiledRoutine, resource: str, backend: SymbolicBackend):
        self.routine = routine
        self._expr = self.routine.resources[resource].value
        self.original_expression = self._expr

        self._backend = backend

    @property
    def expression(self) -> TExpr:
        """Return the current form of the expression."""
        return self._expr

    @expression.setter
    def expression(self, other: TExpr):
        self._expr = other

    @update_expression
    def evaluate_expression(
        self,
        variable_assignments: dict[str, float],
        original_expression: bool = False,
        functions_map: dict[str, Callable[[Any], int | float]] | None = None,
    ) -> TExpr:
        """Assign explicit values to certain variables.

        Args:
            variable_assignments : A dictionary of (variable name: value) key, val pairs.
            original_expression: Whether or not to evaluate the original expression, by default False.
            functions_map: A map for certain functions.

        Returns:
            TExpr
        """
        return self._backend.substitute(
            self.original_expression if original_expression else self.expression,
            replacements=variable_assignments,
            functions_map=functions_map,
        )

    @property
    @abstractmethod
    def variables(self) -> Iterable[TExpr]:
        """Return the variable parameters in the expression."""

    @property
    @abstractmethod
    def as_individual_terms(self) -> Iterable[TExpr]:
        """Return the expression as an iterable of individual terms."""

    @abstractmethod
    @update_expression
    def substitute(self, expression_to_replace: TExpr, replace_with: TExpr) -> None:
        """Substitute a pattern in the expression with a user-defined replacement."""

    def apply_history_to_routine(self, all_resources: bool = False) -> CompiledRoutine:
        raise NotImplementedError("Applying a sequence of instructions to entire routines is not yet implemented.")

    @abstractmethod
    @update_expression
    def expand(self) -> TExpr:
        """Expand all brackets in the expression."""
