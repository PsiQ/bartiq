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
from typing import Any, Concatenate, Generic, NamedTuple, ParamSpec, TypeVar, cast

from bartiq import CompiledRoutine
from bartiq.analysis._rewriters.assumptions import Assumption
from bartiq.symbolics.backend import SymbolicBackend, T, TExpr

P = ParamSpec("P")

TRewriter = TypeVar("TRewriter", bound="ExpressionRewriter[Any]")


class Substitution(NamedTuple):
    """A tuple to encapsulate the action of a subtitution."""

    expression_to_replace: str
    replace_with: str
    wild_symbols: tuple[str] = ()


def update_expression(
    function: Callable[Concatenate[TRewriter, P], TExpr[T]],
) -> Callable[Concatenate[TRewriter, P], TExpr[T]]:
    """Decorator for updating the stored expression in ExpressionRewriter."""

    def _inner(self: TRewriter, *args: P.args, **kwargs: P.kwargs) -> TExpr[T]:
        self.expression = function(self, *args, **kwargs)
        return self.expression

    return _inner


def update_linked_params(
    function: callable[[TRewriter, T | str, T | str], TExpr[T]],
) -> Callable[[TRewriter, T | str, T | str], TExpr[T]]:
    def _(self: TRewriter, symbol_or_expr: T | str, replace_with: T | str):
        updated_expression = function(self, symbol_or_expr, replace_with)
        symbols_in_expr = list(map(str, self._backend.as_expression(symbol_or_expr).free_symbols))
        symbols_in_replacement = list(map(str, self._backend.as_expression(replace_with).free_symbols))
        if new_symbols := [x for x in symbols_in_replacement if x not in symbols_in_expr]:
            for ns in new_symbols:
                self.linked_params[ns] = symbols_in_expr
        return updated_expression

    return _


class ExpressionRewriter(ABC, Generic[T]):
    """An abstract base class for rewriting expressions."""

    def __init__(self, expression: T | str, backend: SymbolicBackend[T]):
        self.expression = cast(TExpr[T], backend.as_expression(expression))
        self.original_expression = self.expression
        self._backend = backend

        self.applied_assumptions: tuple[Assumption, ...] = ()
        self.applied_substitutions: tuple[Substitution, ...] = ()

        self.linked_params: dict[T, Iterable[T]] = {}

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
    def focus(self, symbols: str | Iterable[str]) -> TExpr[T]:
        """Return an expression containing terms that involve specific symbols."""

    @abstractmethod
    def _expand(self) -> TExpr[T]:
        pass

    @update_expression
    def expand(self) -> TExpr[T]:
        """Expand all brackets in the expression."""
        return self._expand()

    @abstractmethod
    def _simplify(self) -> TExpr[T]:
        pass

    @update_expression
    def simplify(self) -> TExpr[T]:
        """Run the backend `simplify' functionality, if it exists."""
        return self._simplify()

    @abstractmethod
    def _add_assumption(self, assume: str | Assumption) -> TExpr[T]:
        pass

    @update_expression
    def add_assumption(self, assume: str | Assumption) -> TExpr[T]:
        """Add an assumption on a symbol."""
        valid = self._add_assumption(assume=assume)
        self.applied_assumptions += (Assumption.from_string(assume) if isinstance(assume, str) else assume,)
        return valid

    @update_expression
    def reapply_all_applied_assumptions(self) -> TExpr[T]:
        """Reapply all previously applied assumptions."""
        for assumption in self.applied_assumptions:
            self.expression = self.add_assumption(assume=assumption)
        return self.expression

    def _substitute(self, symbol_or_expr: T | str, replace_with: T | str) -> TExpr[T]:
        self.applied_substitutions += (Substitution(symbol_or_expr, replace_with),)
        return self._backend.substitute(self.expression, replacements={symbol_or_expr: replace_with})

    @update_linked_params
    @update_expression
    def substitute(self, symbol_or_expr: T | str, replace_with: T | str) -> TExpr[T]:
        """Substitute a symbol or subexpression for another symbol or subexpression.
        By default performs a one-to-one mapping, unless wildcard symbols are implemented.
        """
        return self._substitute(symbol_or_expr=symbol_or_expr, replace_with=replace_with)


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
