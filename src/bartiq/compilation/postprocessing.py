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

from collections.abc import Iterable
from dataclasses import replace
from graphlib import TopologicalSorter
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


def _sum_port_sizes(routine: CompiledRoutine[T], direction: str) -> TExpr[T]:
    return sum([port.size for port in routine.filter_ports([direction]).values()])


def _get_highwater_for_leaf(routine: CompiledRoutine[T], backend: SymbolicBackend[T], ancillae_name: str) -> TExpr[T]:
    input_sum = _sum_port_sizes(routine, "input")
    output_sum = _sum_port_sizes(routine, "output")
    through_sum = _sum_port_sizes(routine, "through")
    local_ancillae = routine.resources[ancillae_name].value if ancillae_name in routine.resources else 0
    result: TExpr[T] = through_sum + local_ancillae

    match input_sum, output_sum:
        case 0, output_sum:
            result += output_sum
        case input_sum, 0:
            result += input_sum
        case input_sum, output_sum:
            result += backend.max(input_sum, output_sum)

    return result


def _get_graph_of_children(routine: CompiledRoutine[T]) -> dict[str | None, set[str]]:
    predecessor_map: dict[str | None, set[str]] = {name: set() for name in routine.children}
    terminal_nodes = set(routine.children)
    for source, target in routine.inner_connections.items():
        predecessor_map[target.routine_name].add(source.routine_name)
        if source.routine_name in terminal_nodes:
            terminal_nodes.remove(source.routine_name)

    # The additional node is so that at the end of processing we always trigger sync
    return {None: set(terminal_nodes), **predecessor_map}


_TreeNode = tuple[str | None, ...]
_Tree = dict[_TreeNode, _TreeNode]


def _least_common_ancestor(nodes: Iterable[_TreeNode], tree: _Tree) -> _TreeNode:
    paths: list[tuple[_TreeNode, ...]] = [_path_to_root(node, tree) for node in nodes]

    result = (None,)
    for components in zip(*paths):
        if len(set(components)) == 1:
            result = components[0]
        else:
            break
    return result


def _is_root(node: _TreeNode):
    return node == (None,)


def _path_to_root(node: _TreeNode, tree: dict[_TreeNode, _TreeNode]) -> tuple[_TreeNode, ...]:
    if _is_root(node):
        return (node,)
    else:
        return _path_to_root(tree[node], tree) + (node,)


def _get_highwater_for_non_leaf(
    routine: CompiledRoutine[T], backend: SymbolicBackend[T], resource_name: str, ancillae_name: str
) -> T:
    highwater_map: dict[_TreeNode, TExpr[T]] = {
        (name,): child.resources[resource_name].value for name, child in routine.children.items()
    }

    tree: _Tree = {}

    graph = _get_graph_of_children(routine)

    passthrough_index = 0

    for child in TopologicalSorter(graph).static_order():
        ancestors = [node for node in tree if any(predecessor in node for predecessor in graph[child])]

        # Starting nodes are connected to source node represented by (None,)
        if not ancestors:
            tree[(child,)] = (None,)
        # Children with one incoming connections are simply connected to their ancestor
        elif len(ancestors) == 1:
            tree[(child,)] = ancestors[0]
        # Everything else is connected to several nodes and hence has to trigger
        # a summation.
        else:
            # Least common ancestor is the lowest level node that is a (not necessarily direct)
            # ancestor of all ancestors at once - this is the cut of point after which we need
            # to sum.
            lca: _TreeNode = _least_common_ancestor(ancestors, tree)
            # Keys to fix are additional keys that we will have to re-connect once we sum over
            # parallel chains going from lca to current child.
            keys_to_fix = set[_TreeNode]()
            chains = []
            for node in ancestors:
                chain = []
                # We collect all nodes between current child and the lca. Note that this chain
                # can be empty (e.g. child is "D" and connections are A -> B, A -> D, B -> D.
                # in such a case the lca is (A,) and the chains are [(B,)] and [])
                while node != lca:
                    chain.append(node)
                    node = tree[node]

                # In case when the chain is nonempty, the flow between lca and current child
                # is encoded in the components of the chain. However, in the case of an
                # empty chain we have to compute this flow manually by summing size of
                # the edges connecting child to lca. We have to compensate for it somehow,
                # and to this end we introduce an artifical passthrough.
                if not chain:
                    new_passthrough = f"Passthrough_{passthrough_index}"
                    passthrough_index += 1

                    highwater_map[(new_passthrough,)] = sum(
                        (
                            routine.children[start.routine_name].ports[start.port_name].size
                            for start, end in routine.inner_connections.items()
                            if start.routine_name in lca and end.routine_name == child
                        ),
                        start=0,
                    )
                    tree[(new_passthrough,)] = lca
                    chain = [(new_passthrough,)]

                # All children in a chain have to be removed, because we are combining them
                # into a new node.
                for x in chain:
                    del tree[x]

                chains.append(chain)

                # All offsprings of nodes in chain that don't participate in the merge
                # have to be re-connected to the new, combined node that we'll create.
                keys_to_fix |= set(key for key in tree if key in tree[key] in chain)

            # New node is labelled by combining all the participating tuples.
            # Here we see introducing passthrough (as opposed to only compensating by adding a flow)
            # is crucial, as otherwise the new_node could have a label that duplicates one of the
            # existing labels.
            new_node = sum((node for chain in chains for node in chain), start=())
            # The new node has highwater equal to sum of highwaters of all chains.
            highwater_map[new_node] = sum(
                backend.max(*[highwater_map[node] for node in chain]) for chain in chains if chain
            )

            # Finally, re-connect the keys that need it.
            for key in keys_to_fix:
                tree[key] = new_node

            # New node is a direct descendad of the lca.
            tree[new_node] = lca
            # And the new child is a direct descendant of the new node.
            tree[(child,)] = new_node

    # We added an artificial node to trigger a final summation, after which the tree is
    # actually linear. However, this node should not be taken account when computing
    # the final highwater (it's not even in highwater_map) and so we remove it.
    del tree[(None,)]

    # There are some qubits that are not captured by the above procedure, because they don't
    # pass through any of children. We adjust for this now. Note that it doesn't matter
    # which endpoint we take size from, as all those connections are necessary passthrough.
    passthrough_cost: TExpr[T] = sum(
        routine.ports[endpoint_1.port_name].size
        for endpoint_1, endpoint_2 in routine.connections.items()
        if endpoint_1.routine_name is None and endpoint_2.routine_name is None
    )

    # Include local ancillae as well.
    local_ancillae = routine.resources[ancillae_name].value if ancillae_name in routine.resources else 0

    # And finally combine the results.
    children_highwater = backend.max(*[highwater_map[key] for key in tree])
    return children_highwater + local_ancillae + passthrough_cost


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
