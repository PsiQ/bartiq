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

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Callable, Generic, TypeVar

from qref import SchemaV1

from bartiq.errors import BartiqCompilationError

from .._routine import CompiledRoutine, routine_to_qref
from ..symbolics import sympy_backend
from ..symbolics.backend import SymbolicBackend, TExpr
from ._common import (
    ConstraintValidationError,
    Context,
    evaluate_constraints,
    evaluate_ports,
    evaluate_repetition,
    evaluate_resources,
)

T = TypeVar("T")
S = TypeVar("S")


Assignments = Mapping[str, str | TExpr[T]]
FunctionsMap = dict[str, Callable[[TExpr[T]], TExpr[T]]]


@dataclass
class EvaluationResult(Generic[T]):
    """
    Datastructure for storing results of the evaluation.

    Attributes:
        routine: evaluated routine
        _backend: a backend used for manipulating symbolic expressions.
    """

    routine: CompiledRoutine[T]
    _backend: SymbolicBackend[T]

    def to_qref(self) -> SchemaV1:
        """Converts `routine` to QREF using `_backend`."""
        return routine_to_qref(self.routine, self._backend)


def evaluate(
    compiled_routine: CompiledRoutine[T],
    assignments: Assignments[T],
    *,
    backend: SymbolicBackend[T] = sympy_backend,
    functions_map: FunctionsMap[T] | None = None,
) -> EvaluationResult[T]:
    """Substitutes variables into compiled routine.

    Args:
        compiled_routine: a compiled routine to be evaluated.
        assignments: a dictionary mapping a subset of input params of `compiled_routine` either into concrete
            values, or other expressions. Expressions can be provided either as concrete instances of symbolic
            expressions understood by backend, or via strings, e.g. `{"N": 2, "M": "k+3"}.
        backend: a backend used for manipulating symbolic expressions.
        functions_map: a dictionary mapping function names to their concrete implementations.

    Returns:
        A new instance of CompiledRoutine with appropriate substitutions made.
    """
    if functions_map is None:
        functions_map = {}
    parsed_assignments = {
        assignment: backend.parse_constant(backend.as_expression(value)) for assignment, value in assignments.items()
    }
    evaluated_routine = _evaluate_internal(
        compiled_routine, parsed_assignments, backend, functions_map, Context(compiled_routine.name)
    )
    return EvaluationResult(routine=evaluated_routine, _backend=backend)


def _evaluate_internal(
    compiled_routine: CompiledRoutine[T],
    inputs: dict[str, TExpr[T]],
    backend: SymbolicBackend[T],
    functions_map: FunctionsMap[T],
    context: Context,
) -> CompiledRoutine[T]:
    try:
        new_constraints = evaluate_constraints(compiled_routine.constraints, inputs, backend)
    except ConstraintValidationError as e:
        raise BartiqCompilationError(
            f"The following constraint was violated when compiling {context.path}: "
            + f"{e.args[0].lhs} = {e.args[0].rhs} evaluated into "
            + f"{e.args[1].lhs} = {e.args[1].rhs}."
        )
    return replace(
        compiled_routine,
        input_params=sorted(set(compiled_routine.input_params).difference(inputs)),
        ports=evaluate_ports(compiled_routine.ports, inputs, backend, functions_map),
        resources=evaluate_resources(compiled_routine.resources, inputs, backend, functions_map),
        constraints=new_constraints,
        repetition=evaluate_repetition(compiled_routine.repetition, inputs, backend, functions_map),
        children={
            name: _evaluate_internal(
                child, inputs, backend=backend, functions_map=functions_map, context=context.descend(name)
            )
            for name, child in compiled_routine.children.items()
        },
    )
