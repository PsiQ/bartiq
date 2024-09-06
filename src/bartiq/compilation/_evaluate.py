# Copyright 2024 PsiQuantum, Corp.
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

from dataclasses import replace
from typing import Mapping, Optional, TypeVar, overload

from bartiq.compilation._common import evaluate_ports_v2, evaluate_resources_v2

from .. import Routine
from .._routine_new import (
    CompiledRoutine,
    compiled_routine_from_bartiq,
    compiled_routine_to_bartiq,
)
from ..symbolics import sympy_backend
from ..symbolics.backend import SymbolicBackend, T_expr
from .types import FunctionsMap, Number

T = TypeVar("T")
S = TypeVar("S")


Assignments = Mapping[str, str | Number | T_expr]


@overload
def evaluate(
    routine: Routine,
    asignments: Assignments[T_expr],
    *,
    functions_map: Optional[FunctionsMap] = None,
) -> Routine:
    pass  # pragma: no cover


@overload
def evaluate(
    routine: Routine,
    assignments: Assignments[T_expr],
    *,
    backend: SymbolicBackend[T_expr],
    functions_map: Optional[FunctionsMap] = None,
) -> Routine:
    pass  # pragma: no cover


def evaluate(routine, assignments, *, backend=sympy_backend, functions_map=None) -> Routine:
    """Evaluates an estimate of a series of variable assignments.

    Args:
        routine: Routine to evaluate. Note: this must have been compiled already.
        assignments: A list of variable assignments, such as ``['x = 10', 'y = 3.141']``.
        backend: A backend used for manipulating symbolic expressions.
        functions_map: A dictionary with string keys and callable functions as values. If any of the routines contains
            a function matching the key in this dict, it will be replaced by calling corresponding value of this dict.

    Returns:
        A new estimate with variables assigned to the desired values.
    """
    return _evaluate(
        compiled_routine=routine,
        assignments=assignments,
        backend=backend,
        functions_map=functions_map,
    )


def _evaluate(
    compiled_routine: CompiledRoutine[T_expr],
    assignments: list[str],
    *,
    backend: SymbolicBackend[T_expr],
    functions_map: Optional[FunctionsMap],
) -> Routine:
    if functions_map is None:
        functions_map = {}
    parsed_assignments = {
        assignment: backend.parse_constant(backend.as_expression(value)) for assignment, value in assignments.items()
    }
    evaluated_routine = _evaluate_internal(compiled_routine, parsed_assignments, backend, functions_map)
    return evaluated_routine


def _evaluate_internal(
    compiled_routine: CompiledRoutine[T_expr],
    inputs: dict[str, T_expr],
    backend: SymbolicBackend[T_expr],
    functions_map: Optional[FunctionsMap],
) -> CompiledRoutine[T_expr]:
    return replace(
        compiled_routine,
        input_params=sorted(set(compiled_routine.input_params).difference(inputs)),
        ports=evaluate_ports_v2(compiled_routine.ports, inputs, functions_map, backend),
        resources=evaluate_resources_v2(compiled_routine.resources, inputs, functions_map, backend),
        children={
            name: _evaluate_internal(child, inputs, backend=backend, functions_map=functions_map)
            for name, child in compiled_routine.children.items()
        },
    )


def _make_assignments_dict(assignments: list[str], backend: SymbolicBackend[T_expr]) -> dict[str, T_expr]:
    assignment_map: dict[str, T_expr] = {}
    for assignment in assignments:
        lhs, rhs = assignment.split("=")
        assignment_map[lhs.strip()] = backend.as_expression(rhs.strip())
    return assignment_map
