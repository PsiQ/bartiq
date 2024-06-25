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

from dataclasses import dataclass

from qref.verification import verify_topology

from . import Routine
from .integrations.qref import bartiq_to_qref
from .symbolics.backend import SymbolicBackend


@dataclass
class VerificationOutput:
    """Dataclass containing the output of the verification."""

    problems: list[str]

    @property
    def is_valid(self):
        """If true, no issues has been found in the process of verification."""
        return len(self.problems) == 0

    def __bool__(self) -> bool:
        return self.is_valid


def verify_routine_topology(routine: Routine) -> VerificationOutput:
    """Verifies whether the routine has correct topology.

    It uses QREF's `verify_topology` method.

    Args:
        routine: Routine to be verified.
    """
    qref_routine = bartiq_to_qref(routine)
    return VerificationOutput(problems=verify_topology(qref_routine).problems)


def verify_uncompiled_routine(routine: Routine, backend: SymbolicBackend) -> VerificationOutput:
    """Verifies whether an uncompiled routine has correct format.

    This function checks:

    - routine's topology
    - whether parameter linking is correct
    - if all the expressions in the routine can be parsed by a provided backend

    Args:
        routine: Routine to be verified.
        backend: Backend used for verification

    Returns:
        verified stuff
    """
    topology_verification_output = verify_routine_topology(routine)
    parameter_linking_problems = _verify_parameter_linking(routine)
    expression_parsing_problems = _verify_expressions_parsable(routine, backend)

    return VerificationOutput(
        problems=topology_verification_output.problems + parameter_linking_problems + expression_parsing_problems
    )


def _verify_parameter_linking(routine: Routine) -> list[str]:
    for subroutine in routine.walk():
        wrong_key_problems = [
            f"{key} is present in linked_params, but not in input_params."
            for key in subroutine.linked_params
            if key not in subroutine.input_params
        ]

        wrong_input_param_problems = []
        for parent_param, links in subroutine.linked_params.items():
            for link in links:
                path = link[0]
                input_param = link[1]
                descendant = subroutine.find_descendant(path)
                if input_param not in descendant.input_params:
                    wrong_input_param_problems.append(
                        f"There is a link defined between {parent_param} and {link}, "
                        f"but subroutine {path} does not have input_param: {input_param}."
                    )
    return wrong_key_problems + wrong_input_param_problems


def _verify_expressions_parsable(routine: Routine, backend: SymbolicBackend) -> list[str]:
    problems = []
    for subroutine in routine.walk():
        resource_problems = [
            _verify_expression(backend, resource, resource.value, "resource", subroutine.absolute_path())
            for resource in subroutine.resources.values()
        ]
        local_variable_problems = [
            _verify_expression(
                backend, local_variable, local_variable.split("=")[1], "local_variable", subroutine.absolute_path()
            )
            for local_variable in subroutine.local_variables
        ]
        port_problems = [
            _verify_expression(backend, port, port.size, "port size", subroutine.absolute_path())
            for port in subroutine.ports.values()
        ]
        problems = resource_problems + local_variable_problems + port_problems
    problems = [problem for problem in problems if problem is not None]
    return problems


def _verify_expression(backend, original_object, value, object_type, path):
    try:
        backend.as_expression(value)
    except:  # noqa: E722
        return f"Couldn't parse {object_type}: {original_object} of subroutine: {path}."


def verify_compiled_routine(routine: Routine, backend: SymbolicBackend) -> VerificationOutput:
    """Verifies whether a compiled routine has correct format.

    This function checks:

    - routine's topology
    - if all the expression contain only parameters defined at the top level
    - if all the linked_params are empty

    Args:
        routine: Routine to be verified.
        backend: Backend used for verification
    """
    topology_verification_output = verify_routine_topology(routine)
    local_params_problems = _verify_no_local_params(routine, backend)
    linked_param_problems = _verify_linked_params_removed(routine)

    return VerificationOutput(
        problems=topology_verification_output.problems + linked_param_problems + local_params_problems
    )


def _verify_no_local_params(routine: Routine, backend: SymbolicBackend) -> list[str]:
    port_params = [
        symbol
        for port in routine.input_ports.values()
        if port.size is not None
        for symbol in backend.free_symbols_in(backend.as_expression(port.size))
    ]

    local_variables = [local_variable.split("=")[0] for local_variable in routine.local_variables]
    input_params = [input_param for input_param in routine.input_params]
    root_params = set(input_params + port_params + local_variables)

    problems = []

    for subroutine in routine.walk():
        resource_expressions = [resource.value for resource in subroutine.resources.values()]
        port_expressions = [port.size for port in subroutine.ports.values() if port.size is not None]
        local_param_expressions = [local_variable.split("=")[1] for local_variable in subroutine.local_variables]

        expressions = resource_expressions + port_expressions + local_param_expressions

        symbol_problems = []
        for expression in expressions:
            symbols = backend.free_symbols_in(backend.as_expression(expression))
            symbol_problems = [
                f"Symbol {symbol} found in subroutine: {subroutine.absolute_path()}, which is not among "
                f"top level params: {root_params}."
                for symbol in symbols
                if symbol not in root_params
            ]
        input_param_problems = [
            f"Input param {input_param} found in subroutine: {subroutine.absolute_path()}, which is not among "
            f"top level params: {root_params}."
            for input_param in subroutine.input_params
            if input_param not in root_params
        ]
        problems += symbol_problems + input_param_problems

    return problems


def _verify_linked_params_removed(routine: Routine) -> list[str]:
    problems = [
        f"Expected linked_params to be removed, found: {subroutine.linked_params}" f" in {subroutine.absolute_path()}."
        for subroutine in routine.walk()
        if len(subroutine.linked_params) != 0
    ]
    return problems
