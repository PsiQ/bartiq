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
from typing import Generic

from typing_extensions import Self

from bartiq.analysis.rewriters.utils import (
    Assumption,
    Expand,
    Initial,
    Instruction,
    ReapplyAllAssumptions,
    Simplify,
    Substitution,
)
from bartiq.symbolics.backend import SymbolicBackend, T, TExpr


@dataclass
class ExpressionRewriter(ABC, Generic[T]):
    """An abstract base class for rewriting expressions."""

    expression: T
    _original_expression: T
    backend: SymbolicBackend[T]
    linked_params: dict[str, Iterable[str]] = field(default_factory=dict)
    _previous: tuple[Instruction, Self | None] = (Initial(), None)

    def _repr_latex_(self) -> str | None:
        if hasattr(self.expression, "_repr_latex_"):
            return self.expression._repr_latex_()
        return None

    @property
    def assumptions(self) -> tuple[Assumption, ...]:
        return tuple(instr for instr in self.history() if isinstance(instr, Assumption))

    @property
    def substitutions(self) -> tuple[Substitution, ...]:
        return tuple(instr for instr in self.history() if isinstance(instr, Substitution))

    @property
    def original(self) -> Self:
        """Return a rewriter with the original expression, and no modifications."""
        return type(self)(
            expression=self._original_expression, _original_expression=self._original_expression, backend=self.backend
        )

    def _unwrap_history(self) -> list[tuple[Instruction, ExpressionRewriter[T] | None]]:
        """Unwrap the history of the rewriter into a list of previous (instruction, rewriter) tuples.

        The history is ordered backwards in time; the first element in each tuple (an instruction)
        was applied to the second element (a rewriter) to result in the rewriter in the _previous_ tuple:
        ```python
            self._unwrap_history()
            >>> [
            >>> (instruction_n-1, rewriter_n-1),
            >>> (instruction_n-2, rewriter_n-2),
            >>> ...,
            >>> (instruction_0, rewriter_0),
            >>> (Initial, None)
            >>> ]
        ```
        That is, `instruction_j` applied to `rewriter_j` results in `rewriter_j+1`,
        `instruction_j+1` applied to `rewriter_j+1` results in `rewriter_j+2`, and so on.

        Returns:
            A list of instructions and rewriters they have been applied to.
        """
        previous = []
        current: ExpressionRewriter[T] | None = self
        while current is not None:
            previous.append(current._previous)
            current = current._previous[1]
        return previous

    def history(self) -> list[Instruction]:
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
        return self.backend.substitute(self.expression, replacements=assignments, functions_map=functions_map)

    @property
    @abstractmethod
    def free_symbols(self) -> Iterable[T]:
        """Return the free symbols in the expression."""

    @property
    @abstractmethod
    def individual_terms(self) -> Iterable[T]:
        """Return the expression as an iterable of individual terms."""

    @abstractmethod
    def focus(self, symbols: str | Iterable[str]) -> T:
        """Return an expression containing terms that involve specific symbols."""

    @abstractmethod
    def _expand(self) -> T: ...

    def expand(self) -> Self:
        """Expand all brackets in the expression."""
        return replace(self, expression=self._expand(), _previous=(Expand(), self))

    @abstractmethod
    def _simplify(self) -> T: ...

    def simplify(self) -> Self:
        """Run the backend `simplify' functionality, if it exists."""
        return replace(self, expression=self._simplify(), _previous=(Simplify(), self))

    @abstractmethod
    def _assume(self, assumption: Assumption) -> T: ...

    def assume(self, assumption: str | Assumption) -> Self:
        """Add an assumption for a symbol."""
        assumption = Assumption.from_string(assumption) if isinstance(assumption, str) else assumption
        return replace(
            self,
            expression=self._assume(assumption=assumption),
            _previous=(assumption, self),
        )

    def reapply_all_assumptions(self) -> Self:
        """Reapply all previously applied assumptions."""
        current = self
        for assumption in self.assumptions:
            current = current.assume(assumption=assumption)
        return replace(self, expression=current.expression, _previous=(ReapplyAllAssumptions(), self))

    @abstractmethod
    def _substitute(self, substitution: Substitution) -> T: ...

    def substitute(self, symbol_or_expr: str, replace_with: str) -> Self:
        """Substitute a symbol or subexpression for another symbol or subexpression.
        By default performs a one-to-one mapping, unless wildcard symbols are implemented.
        """
        substitution: Substitution = Substitution(
            symbol_or_expr=symbol_or_expr, replacement=replace_with, backend=self.backend
        )
        return replace(
            self,
            expression=self._substitute(substitution=substitution),
            linked_params=(
                self.linked_params | substitution._get_linked_parameters()
                if not substitution.wild
                else self.linked_params
            ),
            _previous=(substitution, self),
        )
