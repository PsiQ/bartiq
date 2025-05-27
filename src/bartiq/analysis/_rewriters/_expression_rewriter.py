from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Mapping
from typing import Any, Generic, ParamSpec, TypeAlias

from bartiq import CompiledRoutine
from bartiq.symbolics.backend import SymbolicBackend, T

Expr: TypeAlias = T | str
P = ParamSpec("P")


def update_expression(function: Callable[P, str | Expr[T]]) -> Callable[P, Expr[T]]:
    """Decorator for updating the stored expression in ExpressionRewriter."""

    def _inner(self: ExpressionRewriter, *args: P.args, **kwargs: P.kwargs) -> Expr[T]:
        self.expression = function(self, *args, **kwargs)
        return self.expression

    return _inner


class ExpressionRewriter(ABC, Generic[T]):
    """An abstract base class for rewriting expressions."""

    def __init__(self, expression: Expr[T], backend: SymbolicBackend[T]):
        self._expr = backend.as_expression(expression)
        self.original_expression = self._expr
        self._backend = backend

    @property
    def expression(self) -> T:
        """Return the current form of the expression."""
        return self._expr

    @expression.setter
    def expression(self, other: T):
        self._expr = other

    @update_expression
    def evaluate_expression(
        self,
        variable_assignments: dict[Expr[T], float],
        original_expression: bool = False,
        functions_map: Mapping[str, Callable[[Any], int | float]] | None = None,
    ) -> T:
        """Assign explicit values to certain variables.

        Args:
            variable_assignments : A dictionary of (variable: value) key, val pairs.
            original_expression: Whether or not to evaluate the original expression, by default False.
            functions_map: A map for certain functions.
        """
        return self._backend.substitute(
            self.original_expression if original_expression else self.expression,
            replacements=variable_assignments,
            functions_map=functions_map,
        )

    @property
    @abstractmethod
    def variables(self) -> Iterable[T]:
        """Return the variable parameters in the expression."""

    @property
    @abstractmethod
    def as_individual_terms(self) -> Iterable[T]:
        """Return the expression as an iterable of individual terms."""

    @abstractmethod
    @update_expression
    def expand(self) -> T:
        """Expand all brackets in the expression."""

    @abstractmethod
    def focus(self, variables: str | Iterable[str]) -> T:
        """Return an expression containing terms that involve specific variables."""


class ResourceRewriter:
    """A class for rewriting resource expressions in entire routines.

    Args:
        routine: a CompiledRoutine object with symbolic resources.
        resource: the resource in the routine we wish to apply rewriting rules to.
    """

    _rewriter: type[ExpressionRewriter[T]]

    def __init__(self, routine: CompiledRoutine, resource: str):
        self.routine = routine
        self.resource = resource
        if resource not in self.routine.resources:
            raise ValueError(f"Routine {routine.name} has no resource {self.resource}.")
        self.top_level_expression = self.routine.resources[self.resource].value

        self.rewriter = self._rewriter(expression=self.top_level_expression)

    def __getattr__(self, name: str):
        return getattr(self.rewriter, name)
