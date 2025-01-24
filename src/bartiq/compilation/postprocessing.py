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
from graphlib import TopologicalSorter
from typing import Any, Callable, TypeVar

from .._routine import CompiledRoutine, Resource, ResourceType
from ..errors import BartiqPostprocessingError
from ..symbolics.backend import SymbolicBackend
from ..transform import add_aggregated_resources

T = TypeVar("T")

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
        return add_aggregated_resources(routine, aggregation_dict, remove_decomposed, backend)  # TODO: Konrad mypy

    return _inner


def _get_highwater_for_leaf(routine: CompiledRoutine[T], backend: SymbolicBackend[T], ancillae_name: str) -> T:
    input_ports = routine.filter_ports("input")
    output_ports = routine.filter_ports("output")
    through_ports = routine.filter_ports("through")
    input_sum = sum([port.size for port in input_ports.values()])
    output_sum = sum([port.size for port in output_ports.values()])
    through_sum = sum([port.size for port in through_ports.values()])
    local_ancillae = routine.resources[ancillae_name].value if ancillae_name in routine.resources else 0
    values_for_max = []
    if input_sum != 0:
        values_for_max.append(input_sum)
    if output_sum != 0:
        values_for_max.append(output_sum)
    if len(values_for_max) == 0:
        values_for_max = [0]
    return backend.max(*values_for_max) + through_sum + local_ancillae


def _get_graph_of_children(routine) -> dict[str, set[str]]:
    predecessor_map: dict[str, set[str]] = {name: set() for name in routine.children}
    for source, target in routine._inner_connections.items():
        assert target.routine_name is not None and source.routine_name is not None  # Assert to satisfy typechecker
        predecessor_map[target.routine_name].add(source.routine_name)
    return predecessor_map


class UnionFind:
    def __init__(self):
        self.subsets = {}

    def load_graph(self, graph):
        for node, connections in graph.items():
            self.add_item(node, connections)

    def find(self, node):
        for i, subset in self.subsets.items():
            if node in subset:
                return i
        else:
            return None

    def add_item(self, node, connections):
        if len(connections) == 0:
            self.subsets[len(self.subsets)] = [node]
            return
        ids_list = []
        for other_node in connections:
            id = self.find(other_node)
            if id is not None:
                ids_list.append(id)
            if len(ids_list) == 2:
                self.union(ids_list[0], ids_list[1])
                ids_list.remove(ids_list[1])

        if len(ids_list) == 0:
            self.subsets[len(self.subsets)] = [node]
        elif len(ids_list) == 1:
            self.subsets[ids_list[0]].append(node)
        else:
            raise Exception("Shouldn't happen.")

    def union(self, id_1, id_2):
        new_subset = self.subsets[id_1] + self.subsets[id_2]
        del self.subsets[id_2]
        self.subsets[id_1] = new_subset


class PassThrough:
    def __init__(self, name, value, resource_name):
        self.name = name
        self.resources = {resource_name: Resource(resource_name, value=value, type=ResourceType("qubits"))}


def _divide_into_disconnected_graphs(graph):
    uf = UnionFind()
    uf.load_graph(graph)
    graphs = [{k: graph[k] for k in subset} for subset in uf.subsets.values()]
    return graphs


def _divide_into_layers(graph):
    layers_mapping = {}
    reverse_layers_mapping = defaultdict(list)

    for node in TopologicalSorter(graph).static_order():
        layer_id = max([layers_mapping[k] for k in graph.get(node, [])], default=-1) + 1
        layers_mapping[node] = layer_id
        reverse_layers_mapping[layer_id].append(node)
    return reverse_layers_mapping


def _fill_in_layers(routine, layers, resource_name):
    import copy

    modified_children = copy.copy(routine.children)

    def find_layer(layers, name):
        if name is None:
            return None
        for layer_id, values in layers.items():
            if name in values:
                return layer_id
        else:
            return None

    passthrough_counter = 0
    for endpoint_1, endpoint_2 in routine.connections.items():
        layer_1 = find_layer(layers, endpoint_1.routine_name)
        layer_2 = find_layer(layers, endpoint_2.routine_name)
        if layer_1 is None or layer_2 is None:
            pass
        elif layer_2 - layer_1 > 1:
            for layer_id in range(layer_1 + 1, layer_2):
                name = f"{endpoint_1.routine_name}_to_{endpoint_2.routine_name}_passthrough_{passthrough_counter}"
                modified_children[name] = PassThrough(
                    name,
                    routine.children[endpoint_1.routine_name].ports[endpoint_1.port_name].size,
                    resource_name=resource_name,
                )
                layers[layer_id].append(name)
                passthrough_counter += 1
        elif layer_2 - layer_1 == 1:
            pass
        else:
            raise BartiqPostprocessingError("Connections between layers are not allowed.")

    return modified_children, layers


def _get_highwater_for_non_leaf(
    routine: CompiledRoutine[T], backend: SymbolicBackend[T], resource_name: str, ancillae_name: str
) -> T:

    full_graph = _get_graph_of_children(routine)
    graphs = _divide_into_disconnected_graphs(full_graph)
    costs = []
    cost_per_graph = []

    for graph in graphs:
        costs = []
        layers = _divide_into_layers(graph)
        modified_children, modified_layers = _fill_in_layers(routine, layers, resource_name)
        for layer in modified_layers.values():
            cost = 0
            for child in layer:
                cost += modified_children[child].resources["qubit_highwater"].value
            if cost != 0:
                costs.append(cost)
        cost_per_graph.append(backend.max(*costs))

    passthrough_cost = 0
    for endpoint_1, endpoint_2 in routine.connections.items():
        if endpoint_1.routine_name is None and endpoint_2.routine_name is None:
            passthrough_cost += routine.ports[endpoint_1.port_name].size

    local_ancillae = routine.resources[ancillae_name].value if ancillae_name in routine.resources else 0
    return sum(cost_per_graph) + local_ancillae + passthrough_cost


def _update_children_highwater(routine: CompiledRoutine[T], backend: SymbolicBackend[T]) -> CompiledRoutine[T]:
    for child in routine.children.values():
        child = add_qubit_highwater(child, backend)
    return routine


def add_qubit_highwater(
    routine: CompiledRoutine[T],
    backend: SymbolicBackend[T],
    resource_name: str = "qubit_highwater",
    ancillae_name: str = "local_ancillae",
) -> CompiledRoutine[T]:
    """Add information about qubit highwater to the routine.

    Qubit highwater is the number of qubits needed for a particular subroutine, at the place where it's "widest".

    Args:
        routine: The routine to which the resources will be added.
        backend : Backend instance to use for handling expressions. Defaults to `sympy_backend`.
        resource_name: name for the added resource. Defaults to `qubit_highwater`.
        ancillae_name: name for the ancillae used in the routines. Defaults to `local_ancillae`.

    Returns:
        The routine with added `qubit_highwater` field.
    """
    if len(routine.children) == 0:
        highwater = _get_highwater_for_leaf(routine, backend, ancillae_name)
    else:
        routine = _update_children_highwater(routine, backend)
        highwater = _get_highwater_for_non_leaf(routine, backend, resource_name, ancillae_name)

    if resource_name in routine.resources:
        raise BartiqPostprocessingError(
            f"Attempted to assign resource {resource_name} to {routine.name}, "
            "which already has a resource with the same name."
        )
    else:
        routine.resources[resource_name] = Resource(name=resource_name, value=highwater, type=ResourceType("qubits"))
        # routine.resources["highwater"] = Resource(name="highwater", value=highwater, type=ResourceType("qubits"))
    return routine
