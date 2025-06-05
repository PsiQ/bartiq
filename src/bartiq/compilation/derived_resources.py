# Copyright 2024-2025 PsiQuantum, Corp.
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

from warnings import warn

from .._routine import CompiledRoutine
from ..symbolics.backend import SymbolicBackend, T, TExpr


def _inflow(routine: CompiledRoutine[T], backend: SymbolicBackend[T]) -> TExpr[T]:
    return backend.sum(*[port.size for port in routine.filter_ports(["input", "through"]).values()])


def _outflow(routine: CompiledRoutine[T], backend: SymbolicBackend[T]) -> TExpr[T]:
    return backend.sum(*[port.size for port in routine.filter_ports(["output", "through"]).values()])


def calculate_highwater(
    routine: CompiledRoutine[T],
    backend: SymbolicBackend[T],
    resource_name: str = "qubit_highwater",
    ancillae_name: str = "local_ancillae",
) -> TExpr[T] | None:
    """Calculates qubit highwater for a given routine.

    Qubit highwater is the number of qubits needed for a particular subroutine, at the place where it's "widest".
    The resource added by this routine is an upper bound of the actual highwater.

    Args:
        routine: The routine to which the resources will be added.
        backend : Backend instance to use for handling expressions. Defaults to `sympy_backend`.
        resource_name: name for the added resource. Defaults to "qubit_highwater".
        ancillae_name: name for the ancillae used in the routines. Defaults to "local_ancillae".

    Returns:
        The routine with added added the highwater resource.
    """
    active_flow = _inflow(routine, backend)
    outflow = _outflow(routine, backend)
    watermarks: list[TExpr[T]] = [active_flow]

    if routine.children_order != routine.sorted_children_order:
        warn(
            "Order of children in provided routine does not match the topology. Bartiq will use one of topological "
            "orderings as an estimate of chronology, but the computed highwater value might be incorrect."
        )

    for child in routine.sorted_children():
        inflow = _inflow(child, backend)
        outflow = _outflow(child, backend)

        watermarks.append(active_flow - inflow + child.resources[resource_name].value)
        active_flow = active_flow - inflow + outflow

    watermarks.append(_outflow(routine, backend))
    local_ancillae = routine.resources[ancillae_name].value if ancillae_name in routine.resources else 0

    nonzero_watermarks = [watermark for watermark in watermarks if watermark != 0]

    return backend.max(*nonzero_watermarks) + local_ancillae if nonzero_watermarks else local_ancillae
