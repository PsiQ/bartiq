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


import copy
from typing import Any, Dict

from bartiq import Resource, Routine
from bartiq.symbolics import sympy_backend
from bartiq.verification import verify_uncompiled_routine

BACKEND = sympy_backend


def add_aggregated_resources(aggregation_dict: Dict[str, Dict[str, Any]], routine: Routine, backend=BACKEND) -> Routine:
    """
    Add aggregated resources to bartiq routine based on the aggregation dictionary.

    Args:
        aggregation_dict: The aggregation dictionary.
        routine: The program to which the resources will be added.

    Returns:
        Routine: The program with aggregated resources.

    Raises:
        TypeError: If the input types are not valid bartiq routine.
    """
    if not verify_uncompiled_routine(routine, backend=backend):
        raise TypeError("Must apply to a valid bartiq routine.")

    expanded_aggregation_dict = _expand_aggregation_dict(aggregation_dict)
    for subroutine in routine.walk():
        _add_aggregated_resources_to_subroutine(expanded_aggregation_dict, subroutine)
    return routine


def _add_aggregated_resources_to_subroutine(
    expanded_aggregation_dict: Dict[str, Dict[str, Any]], subroutine: Routine, backend=BACKEND
) -> Routine:
    if not hasattr(subroutine, "resources") or not subroutine.resources:
        return subroutine

    aggregated_resources = copy.copy(subroutine.resources)
    for resource_name in subroutine.resources:
        resource_expr = backend.parse(subroutine.resources[resource_name].value)
        if resource_name in expanded_aggregation_dict:
            mapping = expanded_aggregation_dict[resource_name]
            for sub_res, multiplier in mapping.items():
                if sub_res in aggregated_resources:
                    current_value_expr = backend.parse(aggregated_resources[sub_res].value)
                    aggregated_resources[sub_res].value = str(current_value_expr + multiplier * resource_expr)
                else:
                    new_resource = Resource(
                        name=sub_res,
                        type=subroutine.resources[resource_name].type,
                        value=str(multiplier * resource_expr),
                    )
                    aggregated_resources[sub_res] = new_resource

            del aggregated_resources[resource_name]

    subroutine.resources = aggregated_resources
    return subroutine


def _expand_aggregation_dict(aggregation_dict: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    expanded_dict = {}
    for resource in aggregation_dict:
        expanded_dict[resource] = _expand_resource(resource, aggregation_dict)
    return expanded_dict


def _expand_resource(resource: str, aggregation_dict: Dict[str, Dict[str, Any]], backend=BACKEND) -> Dict[str, Any]:
    expanded_mapping = {}
    to_expand = [(resource, 1)]
    visited = set()

    while to_expand:
        current, multiplier = to_expand.pop()
        if current in visited:
            raise ValueError(f"Circular dependency detected: {' -> '.join(visited)} -> {current}")

        visited.add(current)

        if current not in aggregation_dict:
            if current in expanded_mapping:
                expanded_mapping[current] += multiplier
            else:
                expanded_mapping[current] = multiplier
            visited.remove(current)
            continue

        for sub_res, sub_multiplier in aggregation_dict[current].items():
            sub_multiplier = backend.as_expression(sub_multiplier) * multiplier
            if sub_res in expanded_mapping:
                expanded_mapping[sub_res] += sub_multiplier
            else:
                expanded_mapping[sub_res] = sub_multiplier
                to_expand.append((sub_res, sub_multiplier))

        visited.remove(current)

    return expanded_mapping

    # Remove the current resource from the visited set
    visited.remove(resource)
    return expanded_mapping
