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
"""Here we provide functionality to allow you to apply rewriters to CompiledRoutine resource expressions."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from typing import Protocol

from bartiq import CompiledRoutine
from bartiq.analysis.rewriters.expression import ExpressionRewriter
from bartiq.analysis.rewriters.sympy_expression import sympy_rewriter
from bartiq.analysis.rewriters.utils import Instruction
from bartiq.compilation._common import Resource
from bartiq.symbolics import sympy_backend
from bartiq.symbolics.backend import SymbolicBackend, T
from bartiq.transform import postorder_transform


class ExpressionRewriterFactory(Protocol[T]):
    """A protocol for generating expression rewriters."""

    def __call__(self, expression: int | float | T) -> ExpressionRewriter[T]:
        """Create an expression rewriter for the given expression."""
        ...


@postorder_transform
def _rewrite_routine_resources_single(
    routine: CompiledRoutine[T],
    backend: SymbolicBackend[T],  # Only needed to ensure compatibility with @postorder_transform
    resources: Iterable[str],
    instructions: list[Instruction],
    rewriter_factory: ExpressionRewriterFactory[T],
) -> CompiledRoutine[T]:
    """Internal function that applies rewriting to a single routine node.

    This function is decorated with @postorder_transform so it will be applied
    to all nodes in the routine hierarchy in postorder fashion.
    """

    # Check if we need to rewrite any resources in this routine
    resources_to_rewrite = resources & routine.resources.keys()
    if not resources_to_rewrite:
        return routine

    new_resource_dict: dict[str, Resource] = {}
    for resource_name in resources_to_rewrite:
        # Only rewrite if the resource value is not a simple numeric value
        if not isinstance(routine.resource_values[resource_name], (int, float)):
            new_resource_dict[resource_name] = replace(
                routine.resources[resource_name],
                value=rewriter_factory(routine.resources[resource_name].value)
                .with_instructions(instructions)
                .expression,
            )

    if new_resource_dict:
        return replace(routine, resources=routine.resources | new_resource_dict)

    return routine


def rewrite_routine_resources(
    routine: CompiledRoutine[T],
    resources: str | Iterable[str],
    instructions: list[Instruction],
    rewriter_factory: ExpressionRewriterFactory[T] = sympy_rewriter,
) -> CompiledRoutine[T]:
    """Rewrite the resources of a CompiledRoutine object with a given list of instructions.

    Args:
        routine: A CompiledRoutine object.
        resources: Resource name(s) to apply the instructions to.
        instructions: A list of rewriter instructions to apply.
        rewriter_factory: A factory function that instantiates a rewriter. By default sympy_rewriter.

    Returns:
        A new CompiledRoutine object.
    """
    # Convert resources to a set for efficient lookup
    if isinstance(resources, str):
        resources = [resources]

    # Use the postorder transform function with all resources at once
    return _rewrite_routine_resources_single(routine, sympy_backend, resources, instructions, rewriter_factory)
