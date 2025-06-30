# Copyright 2025 PsiQuantum, Corp.
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
"""Base classes for rewriting symbolic expressions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Mapping
from numbers import Number
from typing import Any, Concatenate, Generic, ParamSpec, TypeVar, cast

from bartiq import CompiledRoutine
from bartiq.analysis._rewriters.assumptions import Assumption
from bartiq.symbolics.backend import SymbolicBackend, T, TExpr

P = ParamSpec("P")

TRewriter = TypeVar("TRewriter", bound="ExpressionRewriter[Any]")


def update_expression(
    function: Callable[Concatenate[TRewriter, P], TExpr[T]],
) -> Callable[Concatenate[TRewriter, P], TExpr[T]]:
    """Decorator for updating the stored expression in ExpressionRewriter."""

    def _inner(self: TRewriter, *args: P.args, **kwargs: P.kwargs) -> TExpr[T]:
        self.expression = function(self, *args, **kwargs)
        return self.expression

    return _inner


class ExpressionRewriter(ABC, Generic[T]):
    """An abstract base class for rewriting expressions."""

    def __init__(self, expression: T | str, backend: SymbolicBackend[T]):
        self.expression = cast(TExpr[T], backend.as_expression(expression))
        self.original_expression = self.expression
        self._backend = backend

        self.applied_assumptions: tuple[Assumption, ...] = ()

    def evaluate_expression(
        self,
        assignments: Mapping[str, Number],
        functions_map: Mapping[str, Callable[[TExpr[T]], TExpr[T]]] | None = None,
        original_expression: bool = False,
    ) -> Number:
        """Assign explicit values to variables.

        This function does not store the result! Will be refactored in a future PR for a cleaner interface.

        Args:
            assignments : A dictionary of (variable: value) key, val pairs.
            original_expression: Whether or not to evaluate the original expression, by default False.
            functions_map: A map for certain functions.

        Returns:
            A fully or partially evaluated expression.
        """
        if not all(isinstance(x, Number) for x in assignments.values()) or set(assignments.keys()) != self.free_symbols:
            raise ValueError("You must pass in numeric values for all symbols in the expression. ")
        return cast(
            Number,
            self._backend.substitute(
                self.original_expression if original_expression else self.expression,
                replacements=assignments,  # type: ignore
                # TODO: Remove this in future PR.
                functions_map=functions_map,
            ),
        )

    @property
    @abstractmethod
    def free_symbols(self) -> Iterable[T]:
        """Return the free symbols in the expression."""

    @property
    @abstractmethod
    def individual_terms(self) -> Iterable[T]:
        """Return the expression as an iterable of individual terms."""

    @abstractmethod
    def _expand(self) -> TExpr[T]:
        pass

    @update_expression
    def expand(self) -> TExpr[T]:
        """Expand all brackets in the expression."""
        return self._expand()

    @abstractmethod
    def focus(self, symbols: str | Iterable[str]) -> TExpr[T]:
        """Return an expression containing terms that involve specific symbols."""

    @abstractmethod
    def _simplify(self) -> TExpr[T]:
        pass

    @update_expression
    def simplify(self) -> TExpr[T]:
        """Run the backend `simplify' functionality, if it exists."""
        return self._simplify()

    @abstractmethod
    def _assume(self, assumption: str | Assumption) -> TExpr[T]:
        pass

    @update_expression
    def assume(self, assumption: str | Assumption) -> TExpr[T]:
        """Add an assumption for a symbol."""
        expr_with_assumption_applied = self._assume(assumption=assumption)
        self.applied_assumptions += (Assumption.from_string(assumption) if isinstance(assumption, str) else assumption,)
        return expr_with_assumption_applied

    @update_expression
    def reapply_all_assumptions(self) -> TExpr[T]:
        """Reapply all previously applied assumptions."""
        for assumption in self.applied_assumptions:
            self.expression = self.assume(assumption=assumption)
        return self.expression


class ResourceRewriter(Generic[T]):
    """A class for rewriting resource expressions of routines.

    By default, this class only acts on the top level resource. In the future, the ability to propagate
    a list of instructions through resources in a routine hierarchy will be made available.

    Args:
        routine: a CompiledRoutine object with symbolic resources.
        resource: the resource in the routine we wish to apply rewriting rules to.
    """

    _rewriter: Callable[[T | str], ExpressionRewriter[T]]

    def __init__(self, routine: CompiledRoutine, resource: str):
        self.routine = routine
        self.resource = resource
        if resource not in self.routine.resources:
            raise ValueError(f"Routine {routine.name} has no resource {self.resource}.")
        self.top_level_expression = cast(T | str, self.routine.resources[self.resource].value)

        self.rewriter = self._rewriter(self.top_level_expression)

    def __getattr__(self, name: str):
        return getattr(self.rewriter, name)
