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

import re
from copy import copy
from typing import Any, Callable, Iterable, Optional

from .. import Connection, Resource, ResourceType, Routine
from ..compilation._symbolic_function import infer_subcosts
from ..errors import BartiqPrecompilationError
from ..symbolics.backend import SymbolicBackend

DefaultsMap = dict[Optional[str], Iterable[Callable[[Any], None]]]


def remove_non_root_container_input_register_sizes(routine: Routine, _backend: SymbolicBackend) -> None:
    """Removes any non-root container inputer register sizes defined."""
    # Only run for non-root containers
    if routine.is_leaf or routine.is_root:
        return

    for port in routine.input_ports.values():
        port.size = None


def add_default_properties(
    routine: Routine,
    _backend: SymbolicBackend,
    defaults: Optional[DefaultsMap] = None,
) -> None:
    """Adds a default resources/port sizes to a routine based on its type."""
    defaults = defaults or _get_defaults()

    for default_modifier in defaults.get(routine.type, []):
        default_modifier(routine)


def _get_defaults():
    """Returns a dictionary of functions to add default values for ports or resources keyed by routine type."""
    return {
        "merge": (_add_register_sizes_to_merge,),
    }


def _add_register_sizes_to_merge(routine):
    """Adds appropriate register sizes to the merge routine."""
    assert len(routine.output_ports) == 1, "Merge routine should always have one output port"
    input_ports = routine.input_ports
    output_port = next(iter(routine.output_ports.values()))
    if output_port.size is not None:
        return

    new_size = None
    for in_port_name, in_port in input_ports.items():
        if in_port.size is None:
            in_port.size = "N_" + in_port_name
        if new_size is None:
            new_size = in_port.size
        else:
            new_size += f"+{in_port.size}"
    output_port.size = new_size


def add_default_additive_costs(routine: Routine, _backend: SymbolicBackend) -> None:
    """Adds an additive resources to routine if any of the children contains them.

    If given routine:
    - has children,
    - children have defined some additive resources
    - is missing some these resources,
    it adds the resource which is sum of the costs in subroutines.
    """
    if routine.is_leaf:
        return

    resources_to_add = set(
        [
            resource.name
            for child in routine.children.values()
            for resource in child.resources.values()
            if resource.type == ResourceType.additive
        ]
    )
    for new_resource in resources_to_add:
        if new_resource not in routine.resources:
            routine.resources[new_resource] = Resource(
                name=new_resource,
                type=ResourceType.additive,
                parent=routine,
                value=f"sum(~.{new_resource})",
            )


def unroll_wildcarded_costs(routine: Routine, backend: SymbolicBackend) -> None:
    """Unrolls wildcarded expressions in the resources using information from its children.
    Right now it supports only non-nested expressions.
    """
    subcosts = infer_subcosts(routine, backend)
    wildcard_subcosts = {}

    for subcost in subcosts:
        if "~" in subcost:
            subcost_parts = subcost.split(".")
            if len(subcost_parts) > 2:
                raise BartiqPrecompilationError("Wildcard parsing supported only for expressions without nesting.")
            pattern = subcost_parts[0].replace("~", ".*")
            cost_type = subcost_parts[1]

            if "~" in cost_type:
                raise BartiqPrecompilationError("Cost cannot contain wildcard symbol.")
            matching_strings = []
            for child_name in routine.children.keys():
                if re.search(pattern, child_name):
                    child_resources = routine.children[child_name].resources
                    for resource in child_resources.values():
                        if resource.name == cost_type:
                            matching_strings.append(child_name)
                            break
            wildcard_subcosts[subcost] = [string + "." + cost_type for string in matching_strings]

    new_costs = {}
    for resource in routine.resources.values():
        resource_expr = resource.value
        if isinstance(resource_expr, str) and "~" in resource_expr:
            new_cost_expression = resource_expr
            for pattern_to_replace in wildcard_subcosts:
                if pattern_to_replace in resource_expr:
                    substitution = ",".join(wildcard_subcosts[pattern_to_replace])
                    new_cost_expression = new_cost_expression.replace(pattern_to_replace, substitution)
            if resource_expr != new_cost_expression:
                new_costs[resource.name] = new_cost_expression

    for resource_name in routine.resources:
        if resource_name in new_costs:
            routine.resources[resource_name].value = new_costs[resource_name]


class AddPassthroughPlaceholder:
    def __init__(self) -> None:
        """Contrary to other precompilation methods, this one is stateful (and therefore implemented as a class),
        to ensure unique name and register size for each passhtrough.
        """
        self.index = 0

    def add_passthrough_placeholders(self, routine: Routine, _backend: SymbolicBackend) -> None:
        """Detects when a passthrough occurs in given routine and removes it.
        Passthroughs are problematic for the compilation process and are removed by adding
        "identity routines". This changes the topology of the routine, but it functionally stays the same.

        NOTE: To work properly it needs to be used before remove_non_root_container_input_register_sizes.
        """
        connections_to_remove = []
        connections_to_add = []
        for i, connection in enumerate(copy(routine.connections)):
            # Detecting passthrough
            if (connection.source.parent is routine) and (connection.target.parent is routine):
                new_routine = _get_passthrough_routine(self.index)
                new_routine.parent = routine
                if new_routine.name in routine.children:
                    raise BartiqPrecompilationError(
                        f"Cannot add passthrough named {new_routine.name}, as child with such name already exists."
                    )
                else:
                    # NOTE: We need to set the whole dictionary, rather than just mutating the dictionary,
                    # as otherwise serializing this using `exclude_unset` will still consider this field
                    # as unset. This is a prime example why mutability might be problematic in hard to predict ways.
                    # routine.children[new_routine.name] = new_routine # <- this causes problems
                    routine.children = {**routine.children, new_routine.name: new_routine}
                connections_to_remove.append(i)
                connections_to_add.append(
                    Connection(source=connection.source, target=new_routine.ports["in_0"], parent=routine)
                )
                connections_to_add.append(
                    Connection(source=new_routine.ports["out_0"], target=connection.target, parent=routine)
                )
                self.index += 1

        for index in connections_to_remove[::-1]:
            routine.connections.pop(index)

        routine.connections.extend(connections_to_add)


def _get_passthrough_routine(index):
    return Routine(
        **{
            "name": f"passthrough_{index}",
            "type": "passthrough",
            "ports": {
                "in_0": {"name": "in_0", "direction": "input", "size": f"P_{index}"},
                "out_0": {"name": "out_0", "direction": "output", "size": f"P_{index}"},
            },
        }
    )
