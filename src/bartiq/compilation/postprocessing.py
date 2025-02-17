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
from typing import Any, Callable

from .._routine import CompiledRoutine, Resource, ResourceType
from ..errors import BartiqPostprocessingError
from ..symbolics.backend import SymbolicBackend, T, TExpr
from ..transform import add_aggregated_resources

PostprocessingStage = Callable[[CompiledRoutine[T], SymbolicBackend[T]], CompiledRoutine[T]]

DEFAULT_POSTPROCESSING_STAGES: list[PostprocessingStage] = []


def aggregate_resources(
    aggregation_dict: dict[str, dict[str, Any]], remove_decomposed: bool = True
) -> PostprocessingStage[T]:
    """Returns a postprocessing stage which aggregates resources using `add_aggregated_resources` method.

    This function is just a wrapper around `add_aggregated_resources` method from `bartiq.transform.
    For more details how it works, please see its documentation.

    Args
        aggregation_dict: A dictionary that decomposes resources into more fundamental components along with their
        respective multipliers.
        remove_decomposed : Whether to remove the decomposed resources from the routine.
            Defaults to True.

    """

    def _inner(routine: CompiledRoutine[T], backend: SymbolicBackend[T]) -> CompiledRoutine[T]:
        return add_aggregated_resources(routine, aggregation_dict, remove_decomposed, backend)

    return _inner


def _inflow(routine: CompiledRoutine[T]) -> TExpr[T]:
    return sum(port.size for port in routine.filter_ports(["input", "through"]).values())


def _outflow(routine: CompiledRoutine[T]) -> TExpr[T]:
    return sum(port.size for port in routine.filter_ports(["output", "through"]).values())


def _get_highwater_for_leaf(routine: CompiledRoutine[T], backend: SymbolicBackend[T], ancillae_name: str) -> TExpr[T]:
    local_ancillae = routine.resources[ancillae_name].value if ancillae_name in routine.resources else 0

    match _inflow(routine), _outflow(routine):
        case 0, outflow:
            return outflow + local_ancillae
        case inflow, 0:
            return inflow + local_ancillae
        case inflow, outflow:
            return backend.max(inflow, outflow) + local_ancillae


def _get_highwater_for_non_leaf(
    routine: CompiledRoutine[T], backend: SymbolicBackend[T], resource_name: str, ancillae_name: str
) -> TExpr[T]:
    active_flow = _inflow(routine)
    watermarks: list[TExpr[T]] = [active_flow]

    for child in routine.sorted_children():
        inflow = _inflow(child)
        outflow = _outflow(child)

        watermarks.append(active_flow - inflow + child.resources[resource_name].value)
        active_flow = active_flow - inflow + outflow

    local_ancillae = routine.resources[ancillae_name].value if ancillae_name in routine.resources else 0

    nonzero_watermarks = [watermark for watermark in watermarks if watermark != 0]
    return backend.max(*nonzero_watermarks) + local_ancillae


def add_qubit_highwater(
    routine: CompiledRoutine[T],
    backend: SymbolicBackend[T],
    resource_name: str = "qubit_highwater",
    ancillae_name: str = "local_ancillae",
) -> CompiledRoutine[T]:
    """Add information about qubit highwater to the routine.

    Qubit highwater is the number of qubits needed for a particular subroutine, at the place where it's "widest".
    The resource added by this routine is an upper bound on the actual highwater.

    Args:
        routine: The routine to which the resources will be added.
        backend : Backend instance to use for handling expressions. Defaults to `sympy_backend`.
        resource_name: name for the added resource. Defaults to "qubit_highwater".
        ancillae_name: name for the ancillae used in the routines. Defaults to "local_ancillae".

    Returns:
        The routine with added added the highwater resource.
    """
    if len(routine.children) == 0:
        highwater = _get_highwater_for_leaf(routine, backend, ancillae_name)
    else:
        routine = replace(
            routine,
            children={
                name: add_qubit_highwater(child, backend, resource_name, ancillae_name)
                for name, child in routine.children.items()
            },
        )
        highwater = _get_highwater_for_non_leaf(routine, backend, resource_name, ancillae_name)

    if resource_name in routine.resources:
        raise BartiqPostprocessingError(
            f"Attempted to assign resource {resource_name} to {routine.name}, "
            "which already has a resource with the same name."
        )

    return replace(
        routine,
        resources={
            **routine.resources,
            resource_name: Resource(name=resource_name, value=highwater, type=ResourceType.qubits),
        },
    )
