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
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Generic, NamedTuple, cast

from typing_extensions import Self

from bartiq import CompiledRoutine
from bartiq.analysis._rewriters.assumptions import Assumption
from bartiq.symbolics.backend import SymbolicBackend, T, TExpr


class Substitution(NamedTuple):
    """A tuple to encapsulate the action of a subtitution."""

    expression_to_replace: str
    replace_with: str
    wild_symbols: tuple[str, ...] = ()


class Instruction(str, Enum):
    """A collection of rewriter mutating instructions."""

    Initial = "initial"
    """The initial instance of a rewriter."""

    Expand = "expand"
    """Expand all brackets in an expression."""

    Simplify = "simplify"
    """Simplify an expression."""

    ReapplyAllAssumptions = "reapply_all_assumptions"
    """Reapply all assumptions previously applied."""


@dataclass
class ExpressionRewriter(ABC, Generic[T]):
    """An abstract base class for rewriting expressions."""

    expression: TExpr[T] | str
    backend: SymbolicBackend[T]
    assumptions: tuple[Assumption, ...] = ()
    substitutions: tuple[Substitution, ...] = ()
    linked_params: dict[T, Iterable[T]] = field(default_factory=dict)
    original_expression: TExpr[T] | str = ""
    _previous: tuple[Instruction | Substitution | str, Self | None] = (Instruction.Initial, None)

    def __post_init__(self):
        self.expression = cast(T, self.backend.as_expression(self.expression))
        if self.original_expression == "":
            self.original_expression = self.expression

    def _repr_latex_(self) -> str | None:
        if hasattr(self.expression, "_repr_latex_"):
            return self.expression._repr_latex_()
        return None

    @property
    def original(self) -> Self:
        """Return a rewriter with the original expression, and no modifications."""
        return type(self)(expression=self._original_expression, backend=self.backend)

    def _unwrap_history(self) -> list[tuple[Instruction | str, ExpressionRewriter[T] | None]]:
        previous = []
        current: ExpressionRewriter[T] | None = self
        while current is not None:
            previous.append(current._previous)
            current = current._previous[1]
        return previous

    def history(self) -> list[Instruction | str]:
        """Show a chronological history of all rewriter-transforming commands that have resulted in this
        instance of the rewriter.

        Returns:
            A list of chronologically ordered `Instructions`, where index 0 corresponds to initialisation.
        """
        instructions, _ = zip(*self._unwrap_history())
        return list(instructions[::-1])

    def undo_previous(self, num_operations_to_undo: int = 1) -> Self:
        """Undo a number of previous operations.

        Rewinds the rewriter back to a previous instance.

        Args:
            num_operations_to_undo: The number of previous steps to undo, by default 1.

        Returns:
            A previous instance of the rewriter.
        """
        _, previous_instances = zip(*self._unwrap_history())
        if num_operations_to_undo > (x := len(previous_instances) - 1):
            raise ValueError(f"Attempting to undo too many operations! Only {x} transforming commands in history.")
        if num_operations_to_undo < 1:
            raise ValueError("Can't undo fewer than one previous command.")
        return previous_instances[num_operations_to_undo - 1] or self.original

    def evaluate_expression(
        self,
        assignments: Mapping[str, TExpr[T]],
        functions_map: Mapping[str, Callable[[TExpr[T]], TExpr[T]]] | None = None,
    ) -> TExpr[T]:
        """Temporarily evaluate the expression.

        This method does _not_ store the result, and employs the 'substitute' method of the given backend.

        Args:
            assignments: A mapping of symbols to numeric values or expressions.
            functions_map: A mapping for user-defined functions in the expressions. By default None.
        """
        return self.backend.substitute(
            cast(TExpr[T], self.expression), replacements=assignments, functions_map=functions_map
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

    def expand(self) -> Self:
        """Expand all brackets in the expression."""
        return replace(self, expression=self._expand(), _previous=(Instruction.Expand, self))

    @abstractmethod
    def _simplify(self) -> TExpr[T]:
        pass

    def simplify(self) -> Self:
        """Run the backend `simplify' functionality, if it exists."""
        return replace(self, expression=self._simplify(), _previous=(Instruction.Simplify, self))

    @abstractmethod
    def _assume(self, assumption: str | Assumption) -> TExpr[T]:
        pass

    def assume(self, assumption: str | Assumption) -> Self:
        """Add an assumption for a symbol."""
        assumption = Assumption.from_string(assumption) if isinstance(assumption, str) else assumption
        return replace(
            self,
            expression=self._assume(assumption=assumption),
            assumptions=self.assumptions + (assumption,),
            _previous=(str(assumption), self),
        )

    def reapply_all_assumptions(self) -> Self:
        """Reapply all previously applied assumptions."""
        expression = self.expression
        for assumption in self.assumptions:
            expression = self.assume(assumption=assumption).expression
        return replace(self, expression=expression, _previous=(Instruction.ReapplyAllAssumptions, self))

    def _substitute(self, symbol_or_expr: str, replace_with: str) -> TExpr[T]:
        self.substitutions += (Substitution(symbol_or_expr, replace_with),)
        return self.backend.substitute(
            cast(TExpr[T], self.expression), replacements={symbol_or_expr: self.backend.as_expression(replace_with)}
        )

    def substitute(self, symbol_or_expr: str, replace_with: str) -> Self:
        """Substitute a symbol or subexpression for another symbol or subexpression.
        By default performs a one-to-one mapping, unless wildcard symbols are implemented.
        """
        return replace(
            self,
            expression=self._substitute(symbol_or_expr=symbol_or_expr, replace_with=replace_with),
            _previous=(Substitution(symbol_or_expr, replace_with), self),
        )


@dataclass
class ResourceRewriter(Generic[T]):
    """A class for rewriting resource expressions of routines.

    By default, this class only acts on the top level resource. In the future, the ability to propagate
    a list of instructions through resources in a routine hierarchy will be made available.

    Args:
        routine: a CompiledRoutine object with symbolic resources.
        resource: the resource in the routine we wish to apply rewriting rules to.
    """

    routine: CompiledRoutine
    resource: str
    _rewriter: ExpressionRewriter[T]

    def __post_init__(self):
        if self.resource not in self.routine.resources:
            raise ValueError(f"Routine {self.routine.name} has no resource {self.resource}.")
        self.top_level_expression = cast(T | str, self.routine.resources[self.resource].value)

        self.rewriter = self._rewriter(self.top_level_expression)

    def __getattr__(self, name: str):
        return getattr(self.rewriter, name)
