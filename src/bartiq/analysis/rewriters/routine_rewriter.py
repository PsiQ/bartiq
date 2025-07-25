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
"""Here we provide functionality to allow you to apply rewriters to CompiledRoutine resource expressions"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from typing import Protocol, cast

from bartiq import CompiledRoutine
from bartiq.analysis.rewriters.expression import ExpressionRewriter
from bartiq.analysis.rewriters.sympy_expression import sympy_rewriter
from bartiq.analysis.rewriters.utils import Instruction
from bartiq.symbolics.backend import T


class ExpressionRewriterFactory(Protocol[T]):
    """A protocol for generating expression rewriters."""

    def __call__(self, expression: str | T) -> ExpressionRewriter[T]: ...


def rewrite_routine_resources(
    routine: CompiledRoutine,
    resources: str | Iterable[str],
    instructions: list[Instruction],
    rewriter_factory: ExpressionRewriterFactory = sympy_rewriter,
) -> CompiledRoutine:
    """Rewrite the resources of a CompiledRoutine object with a given list of instructions.

    Args:
        routine: A CompiledRoutine object.
        resources: Resource name(s) to apply the instructions to.
        instructions: A list of rewriter instructions to apply.
        rewriter_factory: A factory function that instantiates a rewriter. By default sympy_rewriter.

    Returns:
        A new CompiledRoutine object.
    """

    def _traverse_routine(routine: CompiledRoutine, resource: str) -> CompiledRoutine:
        """Recursively traverse the routine, replacing resource values
        starting from the lowest level of children."""
        for child_routine in routine.children.values():
            return _traverse_routine(child_routine, resource)
        if resource in routine.resources and not isinstance(routine.resource_values[resource], (int | float)):
            return replace(
                routine,
                resources=routine.resources
                | {
                    resource: replace(
                        routine.resources[resource],
                        value=rewriter_factory(cast(T, routine.resources[resource].value)).with_instruction_set(
                            instructions
                        ),
                    )
                },
            )

        return routine

    if isinstance(resources, str):
        return _traverse_routine(routine, resources)

    for resource in resources:
        routine = _traverse_routine(routine, resource)
    return routine
