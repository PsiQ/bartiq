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

from collections import defaultdict
from dataclasses import dataclass
from typing import Optional, Union, overload

from .. import Port, PortDirection, Routine
from ..errors import BartiqCompilationError
from ..routing import get_route
from ..symbolics import sympy_backend
from ..symbolics.backend import SymbolicBackend, T_expr
from ._compile import set_input_port_size_to_constant_value
from ._symbolic_function import (
    define_expression_functions,
    evaluate_function_at,
    to_symbolic_function,
    update_routine_with_symbolic_function,
)
from ._utilities import (
    is_non_negative_int,
    is_number_string,
    is_single_parameter,
    parse_value,
    split_equation,
)
from .types import NUMBER_TYPES, FunctionsMap, Number


@dataclass
class _VariableAssignment:
    """Dataclass for variable value assignments."""

    variable: str
    value: Number


@dataclass
class _RegisterSizeAssignment:
    """Dataclass for register size assignments."""

    direction: str
    register: str
    variable: str
    value: Number


Assignment = Union[_VariableAssignment, _RegisterSizeAssignment]
RegisterSizeAssignmentMap = dict[str, list[_RegisterSizeAssignment]]


@overload
def evaluate(routine: Routine, assignments: list[str], *, functions_map: Optional[FunctionsMap] = None) -> Routine:
    pass  # pragma: no cover


@overload
def evaluate(
    routine: Routine,
    assignments: list[str],
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
    return _evaluate(routine=routine, assignments=assignments, backend=backend, functions_map=functions_map)


def _evaluate(
    routine: Routine,
    assignments: list[str],
    *,
    backend: SymbolicBackend[T_expr],
    functions_map: Optional[FunctionsMap],
) -> Routine:
    # We do this to ensure we don't mutate the input object.
    evaluated_routine = Routine(**routine.model_dump())
    parsed_assignments = _parse_assignments(evaluated_routine, assignments)
    for parsed_assignment in parsed_assignments:
        _evaluate_over_assignment(evaluated_routine, parsed_assignment, backend, functions_map)

    return evaluated_routine


def _parse_assignments(routine: Routine, assignments: list[str]) -> list[Assignment]:
    """Splits input register size assignments from input variable assignments."""
    # Parse assignment strings to their variable names and assignment expressions
    assignment_map: dict[str, str] = dict(split_equation(assignment) for assignment in assignments)

    # Resolve input register variable assignments
    size_to_registers_map = _get_input_register_size_per_register(routine)

    # Sort the assignments based on whether they refer to register size variables or not
    parsed_assignments: list[Assignment] = []
    for variable, value_str in assignment_map.items():
        value = parse_value(value_str)
        if variable in routine.input_params or variable in size_to_registers_map:
            if variable in routine.input_params:
                parsed_assignments.append(_VariableAssignment(variable, value))
            if variable in size_to_registers_map:
                registers = size_to_registers_map[variable]
                for register in registers:
                    parsed_assignments.append(_RegisterSizeAssignment(PortDirection.input, register, variable, value))
        else:
            all_params = list(routine.input_params) + list(size_to_registers_map.keys())
            raise BartiqCompilationError(f"Cannot set unknown variable {variable}; known variables are {all_params}.")

    return parsed_assignments


def _get_input_register_size_per_register(routine: Routine) -> dict[str, list[str]]:
    """Returns a dictionary mapping input register size variables to the registers they correspond to."""
    size_to_registers_map = defaultdict(list)

    for port_name, port in routine.input_ports.items():
        size = port.size
        assert size is not None
        assert is_single_parameter(size) or is_non_negative_int(
            size
        ), f"{size} is not a single variable or positive int."
        if isinstance(size, str):
            size_to_registers_map[size].append(port_name)

    return size_to_registers_map


def _evaluate_over_assignment(
    routine: Routine,
    assignment: Assignment,
    backend: SymbolicBackend[T_expr],
    functions_map: Optional[FunctionsMap] = None,
) -> None:
    # A map from routine path to register size assignments
    register_sizes: RegisterSizeAssignmentMap = defaultdict(list)

    # Creates register size assignments for the register sizes of downstream ports from the initial assignment
    if isinstance(assignment, _RegisterSizeAssignment):
        source_port = routine.ports[assignment.register]
        downstream_size_assignments = _get_downstream_register_size_assignments(source_port, assignment.value)
        register_sizes.update(downstream_size_assignments)

    # Walk over the estimate and evaluate each subroutine over the assignment
    for subroutine in routine.walk():
        # Compile a list of assignments that includes the assignments relevant to the current routine
        subroutine_assignments: list[Assignment] = []
        if isinstance(assignment, _VariableAssignment):
            subroutine_assignments.append(assignment)

        # Register size assignments only need to happen at the root
        if isinstance(assignment, _RegisterSizeAssignment) and subroutine.is_root:
            subroutine_assignments.append(assignment)

        # Check for any register size assignments that have been propagated from upstream ports
        if subroutine.absolute_path() in register_sizes:
            subroutine_assignments.extend(register_sizes.pop(subroutine.absolute_path()))

        # Compute the new routine
        evaluated_routine = _evaluate_routine(subroutine, subroutine_assignments, backend, functions_map)

        # Propagate forwards any constant output register sizes
        routine_downstream_register_size_assignments = _propagate_forward_constant_output_register_sizes(
            evaluated_routine
        )
        for path, downstream_assignments in routine_downstream_register_size_assignments.items():
            register_sizes[path].extend(downstream_assignments)

    assert not register_sizes, f"Shouldn't have any more register sizes left to evaluate; found {register_sizes}"


def _get_downstream_register_size_assignments(source_port: Port, value: Number) -> RegisterSizeAssignmentMap:
    register_sizes = defaultdict(list)

    target_route = get_route(source_port, forward=True)

    for target_port in target_route:
        # Skip the first port and any outputs (since they should be set by the assignment of their dependent variables).
        if target_port == source_port or target_port.direction == PortDirection.output:
            continue

        variable = str(target_port.size)
        local_assignment = _RegisterSizeAssignment(target_port.direction, target_port.name, variable, value)
        assert target_port.parent is not None
        register_sizes[target_port.parent.absolute_path()].append(local_assignment)

    return register_sizes


def _propagate_forward_constant_output_register_sizes(
    routine: Routine,
) -> RegisterSizeAssignmentMap:
    register_sizes: RegisterSizeAssignmentMap = defaultdict(list)

    for port in routine.output_ports.values():
        size_str = str(port.size)
        if is_number_string(size_str):
            size_value = parse_value(size_str)
            assert is_non_negative_int(size_value)
            downstream_size_assignments = _get_downstream_register_size_assignments(port, size_value)
            register_sizes.update(downstream_size_assignments)

    return register_sizes


def _evaluate_routine(
    routine: Routine,
    assignments: list[Assignment],
    backend: SymbolicBackend[T_expr],
    functions_map: Optional[FunctionsMap] = None,
) -> Routine:
    for assignment in assignments:
        routine = _evaluate_routine_over_assignment(routine, assignment, backend, functions_map)
    return routine


def _evaluate_routine_over_assignment(
    routine: Routine,
    assignment: Assignment,
    backend: SymbolicBackend[T_expr],
    functions_map: Optional[FunctionsMap] = None,
) -> Routine:
    """Dispatches oeration assignment based upon the assignment type."""
    # First, check that the assignment is to a number
    if not isinstance(assignment.value, NUMBER_TYPES):
        raise BartiqCompilationError(
            f"Can only evaluate variables to numbers; attempted assignment {assignment.variable} = {assignment.value}"
        )
    # Evaluate assignment based on type
    if isinstance(assignment, _VariableAssignment):
        routine = _evaluate_routine_over_assignment_input_variable(routine, assignment, backend, functions_map)
    if isinstance(assignment, _RegisterSizeAssignment):
        assert assignment.direction == PortDirection.input
        routine = _evaluate_routine_over_assignment_input_register_size(routine, assignment, backend, functions_map)

    return routine


def _evaluate_routine_over_assignment_input_variable(
    routine: Routine,
    assignment: _VariableAssignment,
    backend: SymbolicBackend[T_expr],
    functions_map: Optional[FunctionsMap] = None,
) -> Routine:
    """Evaluates a routine over a single input variable assignment."""
    variable = assignment.variable
    value = assignment.value

    # Deal with case when routine doesn't reference input variable
    if variable not in routine.input_params:
        return routine

    # Parse the routine and the assignment
    old_function = to_symbolic_function(routine, backend)

    # Evaluate function over assignment and substitute any user-provided functions
    new_function = define_expression_functions(old_function, functions_map, strict=False)
    new_function = evaluate_function_at(new_function, variable, value, backend)

    update_routine_with_symbolic_function(routine, new_function)
    return routine


def _evaluate_routine_over_assignment_input_register_size(
    routine: Routine,
    assignment: _RegisterSizeAssignment,
    backend: SymbolicBackend[T_expr],
    functions_map: Optional[FunctionsMap] = None,
) -> Routine:
    """Evaluates a routine over a single input register size assignment."""
    register = f"#{assignment.register}"
    value = assignment.value

    old_function = to_symbolic_function(routine, backend)

    new_function = define_expression_functions(old_function, functions_map)
    new_function = set_input_port_size_to_constant_value(new_function, register, value, backend)

    update_routine_with_symbolic_function(routine, new_function)
    return routine
