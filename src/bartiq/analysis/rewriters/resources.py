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
"""Resource rewriters allow you to rewrite expressions across entire routines."""
from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from dataclasses import dataclass, replace
from typing import Generic, Protocol, cast

from bartiq import CompiledRoutine
from bartiq.analysis.rewriters.expression import ExpressionRewriter
from bartiq.analysis.rewriters.sympy_expression import sympy_rewriter
from bartiq.analysis.rewriters.utils import (
    Assumption,
    Expand,
    Initial,
    Instruction,
    ReapplyAllAssumptions,
    Simplify,
    Substitution,
)
from bartiq.symbolics.backend import T


class ExpressionRewriterFactory(Protocol[T]):
    """A protocol for generating expression rewriters."""

    def __call__(self, expression: str | T) -> ExpressionRewriter[T]: ...


@dataclass
class ResourceRewriter(Generic[T]):
    """A class for rewriting resource expressions of routines.

    By default, this class only acts on the top level resource. In order to propagate instructions through
    every level of the routine, the method `apply_to_whole_routine` can be called which will return a new
    `CompiledRoutine` object, where the relevant resource in every child (at every level) has the current instructions
    on the rewriter instance applied to its expression.

    Args:
        routine: a CompiledRoutine.
        resource: the resource in the routine we wish to apply rewriting rules to.
        rewriter_factory: A function that returns rewriter instances, by default `sympy_rewriter`.

    Attributes:
        rewriter: A rewriter instance applied to the corresponding resource expression of the input routine.
    """

    routine: CompiledRoutine
    resource: str
    rewriter_factory: ExpressionRewriterFactory[T] = sympy_rewriter

    def __post_init__(self):
        self.rewriter = self.rewriter_factory(self.routine.resources[self.resource].value)

    def __getattr__(self, name: str):
        """Pipe attribute calls to the expression rewriter instance.

        If the attribute is a method that transforms the rewriter, update our rewriter instance and return `self`
        to allow method chaining.
        """
        attr = getattr(self.rewriter, name)

        if callable(attr):

            def wrapper(*args, **kwargs):
                """If the method would transform the rewriter attribute, modify it in place and return
                `self`."""
                result = attr(*args, **kwargs)
                if isinstance(result, ExpressionRewriter):
                    self.rewriter = result
                    return self

                return result

            return wrapper

        return attr

    def apply_to_whole_routine(self) -> CompiledRoutine:
        """Apply all instructions currently on the rewriter instance to all children of the routine.

        Returns:
            A new CompiledRoutine object.
        """
        routine = deepcopy(self.routine)

        def _traverse_routine(routine: CompiledRoutine) -> CompiledRoutine:
            """Recursively traverse the routine, replacing resource values
            starting from the lowest level of children."""
            for _name, child_routine in routine.children.items():
                routine.children[_name] = _traverse_routine(child_routine)
            if self.resource in routine.resources and not isinstance(
                routine.resource_values[self.resource], (int | float)
            ):
                return replace(
                    routine,
                    resources=routine.resources
                    | {
                        self.resource: replace(
                            routine.resources[self.resource],
                            value=_update_expression(
                                self.rewriter_factory,
                                cast(T, routine.resources[self.resource].value),
                                self.rewriter.history(),
                            ),
                        )
                    },
                )

            return routine

        return _traverse_routine(routine=routine)


def _apply_instruction(rewriter: ExpressionRewriter[T], instruction: Instruction) -> ExpressionRewriter[T]:
    """Helper function to apply instructions to a rewriter instance.

    Args:
        rewriter: Rewriter to apply an instruction to.
        instruction: Instruction to apply.

    Raises:
        ValueError: If an unrecognised instruction is passed.

    Returns:
        A new expression rewriter instance.
    """
    match instruction:
        case Initial():
            return rewriter
        case Expand():
            return rewriter.expand()
        case Simplify():
            return rewriter.simplify()
        case Assumption():
            return rewriter.assume(instruction)
        case Substitution():
            return rewriter.substitute(instruction.expr, instruction.replacement)
        case ReapplyAllAssumptions():
            return rewriter.reapply_all_assumptions()
        case _:
            raise ValueError(f"Unrecognised instruction: '{instruction}' has type '{type(instruction)}'.")


def _update_expression(
    rewriter_factory: ExpressionRewriterFactory[T], expression: T, instructions: Iterable[Instruction]
) -> T:
    """Update an expression given a list of rewriting instructions.

    Args:
        expression: The expression to rewrite.
        instructions: A list of instructions to apply.

    Returns:
        A new expression with the given modifications.
    """
    rewriter = rewriter_factory(expression)
    for instr in instructions:
        rewriter = _apply_instruction(rewriter=rewriter, instruction=instr)
    return rewriter.expression
