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
from numbers import Number
from typing import Generic, Self, cast

from bartiq import CompiledRoutine
from bartiq.analysis._rewriters.assumptions import Assumption
from bartiq.symbolics.backend import SymbolicBackend, T, TExpr


class Instruction(str, Enum):
    Expand = "Expand"
    Simplify = "Simplify"
    Assumption = "Assumption"
    AllAssumptions = "AllAssumptions"


@dataclass
class ExpressionRewriter(ABC, Generic[T]):
    """An abstract base class for rewriting expressions."""

    expression: T | str
    backend: SymbolicBackend[T]
    assumptions: tuple[Assumption, ...] = ()
    linked_params: dict[T, Iterable[T]] = field(default_factory=dict)
    original_expression: T | str = ""
    _previous: tuple[Instruction, Self] = (None, None)

    def __post_init__(self):
        self.expression = cast(TExpr[T], self.backend.as_expression(self.expression))
        if self.original_expression == "":
            self.original_expression = self.expression

    def _repr_latex_(self) -> str | None:
        if hasattr(self.expression, "_repr_latex_"):
            return self.expression._repr_latex_()
        return None

    def show_history(self) -> tuple[Instruction | None, ...]:
        previous_instructions = []
        current = self
        while current is not None:
            previous_instructions.append(current._previous[0])
            current = current._previous[1]
        return tuple(previous_instructions)

    def revert_to(self, before: Instruction | str) -> Self:
        current = self
        current_instr, previous_instance = current._previous
        if current_instr is None:
            raise ValueError(f"No instruction '{before}' found in the history.")
        if current_instr == before:
            return previous_instance
        return previous_instance.revert_to(before=before)

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
    def _add_assumption(self, assumption: str | Assumption) -> TExpr[T]:
        pass

    def add_assumption(self, assumption: str | Assumption) -> Self:
        """Add an assumption for a symbol."""
        return replace(
            self,
            expression=self._add_assumption(assumption=assumption),
            assumptions=self.assumptions
            + (Assumption.from_string(assumption) if isinstance(assumption, str) else assumption,),
            _previous=(Instruction.Assumption(assumption), self),
        )

    def reapply_all_applied_assumptions(self) -> Self:
        """Reapply all previously applied assumptions."""
        expression = self.expression
        for assumption in self.assumptions:
            expression = self._add_assumption(assumption=assumption)
        replace(self, expression=expression, _previous=(Instruction.AllAssumptions, self))


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
