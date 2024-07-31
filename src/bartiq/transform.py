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

import sympy

from bartiq import Resource, Routine
from bartiq.compilation.types import Number
from bartiq.symbolics import sympy_backend
from bartiq.verification import verify_uncompiled_routine

BACKEND = sympy_backend


def add_aggregated_resources(aggregation_dict: Dict[str, Dict[str, Any]], routine: Routine, backend=BACKEND) -> Routine:
    """
    Add aggregated resources to bartiq routine based on the aggregation dictionary.

    Args:
        aggregation_dict: A dictionary that decomposes resources into more fundamental components along with their
        respective multipliers. The multipliers can be numeric values or strings representing expressions.
                          Example:
                          {
                              "swap": {"CNOT": 3},
                              "arbitrary_z": {"T_gates": "3*log_2(1/epsilon) + O(log(log(1/epsilon)))"},
                              ...
                          }
        routine: The program to which the resources will be added.

    Returns:
        Routine: The program with aggregated resources.

    Raises:
        TypeError: If the input types are not valid bartiq routine.
    """
    try:
        verify_uncompiled_routine(routine, backend=backend)
    except Exception as e:
        raise TypeError("Must apply to a valid bartiq routine.") from e

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
        resource_expr = backend.as_expression(subroutine.resources[resource_name].value)
        if resource_name in expanded_aggregation_dict:
            mapping = expanded_aggregation_dict[resource_name]
            for sub_res, multiplier in mapping.items():
                multiplier_expr = backend.as_expression(multiplier)
                if sub_res in aggregated_resources:
                    current_value_expr = backend.as_expression(aggregated_resources[sub_res].value)
                    aggregated_resources[sub_res].value = str(current_value_expr + multiplier_expr * resource_expr)
                else:
                    new_resource = Resource(
                        name=sub_res,
                        type=subroutine.resources[resource_name].type,
                        value=str(multiplier_expr * resource_expr),
                    )
                    aggregated_resources[sub_res] = new_resource

            del aggregated_resources[resource_name]

    subroutine.resources = aggregated_resources
    return subroutine


def _expand_aggregation_dict(aggregation_dict: Dict[str, Dict[str, Any]], backend=BACKEND) -> Dict[str, Dict[str, Any]]:
    """
    Expand the aggregation dictionary to handle nested resources.
    Args:
        aggregation_dict: The input aggregation dictionary.
    Returns:
        Dict[str, Dict[str, Any]]: The expanded aggregation dictionary.
    """
    if not isinstance(aggregation_dict, dict):
        raise TypeError("aggregation_dict must be a dictionary.")

    expanded_dict = {}
    for resource in aggregation_dict.keys():
        expanded_dict[resource] = _expand_resource(resource, aggregation_dict, set())
    return expanded_dict


def _expand_resource(
    resource: str, aggregation_dict: Dict[str, Dict[str, Any]], visited: set, backend=BACKEND
) -> Dict[str, Any]:
    """
    Recursively expand resource mapping to handle nested resources and detect circular dependencies.
    Args:
        resource: The resource to expand.
        aggregation_dict: The input aggregation dictionary.
        visited: A set of currently visited resources to detect circular dependencies.
    Returns:
        Dict[str, Any]: The expanded resource mapping.
    """
    if resource in visited:
        raise ValueError(f"Circular dependency detected: {' -> '.join(visited)} -> {resource}")

    # Add current resource to the visited set
    visited.add(resource)

    # If the resource is not in the aggregation dictionary, return an empty dictionary
    if resource not in aggregation_dict:
        visited.remove(resource)
        return {}

    # Sympify the mapping values for the current resource
    expanded_mapping = {
        k: sympy.simplify(v) if not isinstance(v, Number) else v for k, v in aggregation_dict[resource].items()
    }

    expanded_mapping = {k: backend.as_expression(v) for k, v in aggregation_dict[resource].items()}

    res_to_expand = list(expanded_mapping.keys())

    while res_to_expand:
        current = res_to_expand.pop(0)
        if current in aggregation_dict:
            # Recursively expand the nested resources
            sub_mapping = _expand_resource(current, aggregation_dict, visited.copy())
            for sub_res, sub_multiplier in sub_mapping.items():
                if sub_res in expanded_mapping:
                    expanded_mapping[sub_res] = (
                        backend.parse(expanded_mapping[sub_res]) + expanded_mapping[current] * sub_multiplier
                    )
                else:
                    expanded_mapping[sub_res] = expanded_mapping[current] * sub_multiplier
                    res_to_expand.append(sub_res)
            del expanded_mapping[current]

    # Remove the current resource from the visited set
    visited.remove(resource)
    return expanded_mapping
