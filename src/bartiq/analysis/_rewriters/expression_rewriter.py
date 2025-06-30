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

# from numbers import Number as NumberT
from typing import Generic, Self, cast

from bartiq import CompiledRoutine
from bartiq.analysis._rewriters.assumptions import Assumption
from bartiq.symbolics.backend import SymbolicBackend, T, TExpr


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
    linked_params: dict[T, Iterable[T]] = field(default_factory=dict)
    original_expression: TExpr[T] | str = ""
    _previous: tuple[Instruction | str, Self | None] = (Instruction.Initial, None)

    def __post_init__(self):
        self.expression = cast(T, self.backend.as_expression(self.expression))
        if self.original_expression == "":
            self.original_expression = self.expression

    def _repr_latex_(self) -> str | None:
        if hasattr(self.expression, "_repr_latex_"):
            return self.expression._repr_latex_()
        return None

    def show_history(self) -> list[Instruction | str]:
        """Show a chronological history of all mutating commands that have resulted in this instance of the rewriter.

        Returns:
            A list of chronologically ordered `Instructions`, where index 0 corresponds to initialisation.
        """
        previous_instructions: list[Instruction | str] = []
        current: ExpressionRewriter[T] | None = self
        while current is not None:
            previous_instructions.append(current._previous[0])
            current = current._previous[1]
        return previous_instructions[::-1]

    def revert_to(self, before: Instruction | str) -> Self:
        """Revert to a previous instance of the rewriter.

        The history of the rewriter is stored as a list of (Instruction, Previous Instance) tuples, where the
        `Instruction` has mutated the `Previous Instance` to create the current instance. Thus, the keyword argument
        in this method, `before`, accepts an `Instruction` argument and will return the corresponding instance
        _prior_ to that instruction.

        Args:
            before: Rewind before the most recent application of a certain `Instruction`.

        """
        current = self
        current_instr, previous_instance = current._previous
        if current_instr is Instruction.Initial:
            raise ValueError(f"No instruction '{before}' found in the history.")
        assert previous_instance is not None
        if current_instr == before:
            return previous_instance
        return previous_instance.revert_to(before=before)

    def evaluate_expression(
        self,
        assignments: Mapping[str, TExpr[T]],
        functions_map: Mapping[str, Callable[[TExpr[T]], TExpr[T]]] | None = None,
        original_expression: bool = False,
    ) -> TExpr[T]:
        """Evaluate the current expression.

        Uses the 'substitute' method of the given backend.

        Args:
            assignments: A mapping of symbols to numeric values or expressions.
            functions_map: A mapping for user-defined functions in the expressions. By default None.
            original_expression: Flag indicating whether or not to evaluate the original, unmodified expression.
                                By default False.

        """
        return self.backend.substitute(
            cast(TExpr[T], self.original_expression if original_expression else self.expression),
            replacements=assignments,
            functions_map=functions_map,
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

    def reapply_all_applied_assumptions(self) -> Self:
        """Reapply all previously applied assumptions."""
        expression = self.expression
        for assumption in self.assumptions:
            expression = self._assume(assumption=assumption)
        return replace(self, expression=expression, _previous=(Instruction.ReapplyAllAssumptions, self))


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
