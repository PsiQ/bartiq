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
from collections import defaultdict
from typing import Any, Dict, List, Set

from bartiq import Resource, Routine
from bartiq.symbolics import sympy_backend
from bartiq.verification import verify_uncompiled_routine

BACKEND = sympy_backend


def add_aggregated_resources(routine: Routine, aggregation_dict: Dict[str, Dict[str, Any]], backend=BACKEND) -> Routine:
    """Add aggregated resources to bartiq routine based on the aggregation dictionary.

    Args:
        routine: The program to which the resources will be added.
        aggregation_dict: A dictionary that decomposes resources into more fundamental components along with their
        respective multipliers. The multipliers can be numeric values or strings representing valid bartiq expressions.
                          Example:
                          {
                              "swap": {"CNOT": 3},
                              "arbitrary_z": {"T_gates": "3*log2(1/epsilon) + O(log(log(1/epsilon)))"},
                              ...
                          }

    Returns:
        Routine: The program with aggregated resources.

    """
    verify_uncompiled_routine(routine, backend=backend)

    expanded_aggregation_dict = _expand_aggregation_dict(aggregation_dict)
    for subroutine in routine.walk():
        _add_aggregated_resources_to_subroutine(subroutine, expanded_aggregation_dict)
    return routine


def _add_aggregated_resources_to_subroutine(
    subroutine: Routine, expanded_aggregation_dict: Dict[str, Dict[str, Any]], backend=BACKEND
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
    """Expand the aggregation dictionary to handle nested resources.
    Args:
        aggregation_dict: The input aggregation dictionary.
    Returns:
        Dict[str, Dict[str, Any]]: The expanded aggregation dictionary.
    """
    if not isinstance(aggregation_dict, dict):
        raise TypeError("aggregation_dict must be a dictionary.")

    sorted_resources = _topological_sort(aggregation_dict)

    expanded_dict = {}
    for resource in sorted_resources:
        if resource in aggregation_dict:
            expanded_dict[resource] = _expand_resource(resource, aggregation_dict)
    return expanded_dict


def _expand_resource(resource: str, aggregation_dict: Dict[str, Dict[str, Any]], backend=BACKEND) -> Dict[str, Any]:
    """Recursively expand resource mapping to handle nested resources and detect circular dependencies.
    Args:
        resource: The resource to expand.
        aggregation_dict: The input aggregation dictionary.
    Returns:
        Dict[str, Any]: The expanded resource mapping.
    """

    expanded_mapping = {k: backend.as_expression(v) for k, v in aggregation_dict[resource].items()}

    res_to_expand = list(expanded_mapping.keys())

    for current in res_to_expand[:]:
        if current in aggregation_dict:
            # Recursively expand the nested resources
            sub_mapping = _expand_resource(current, aggregation_dict, backend)
            for sub_res, sub_multiplier in sub_mapping.items():
                sub_multiplier_expr = backend.as_expression(sub_multiplier)
                expanded_expr = backend.as_expression(expanded_mapping[current]) * sub_multiplier_expr
                if sub_res in expanded_mapping:
                    expanded_mapping[sub_res] = str(backend.as_expression(expanded_mapping[sub_res]) + expanded_expr)
                else:
                    expanded_mapping[sub_res] = str(expanded_expr)
                    res_to_expand.append(sub_res)

            del expanded_mapping[current]

    return expanded_mapping


def _topological_sort(aggregation_dict: Dict[str, Dict[str, Any]]) -> List[str]:
    """Perform a topological sort on the aggregation dictionary to determine the order of resource expansion.
    Args:
        aggregation_dict : The input aggregation dictionary where keys are resource names
                                                      and values are dictionaries of decomposed resources.
    Returns:
        List[str]: The list of resources in topologically sorted order.

    Raises:
        ValueError: If a circular dependency is detected in the aggregation dictionary.
    """

    def dfs(res):
        # Helper function to perform DFS
        if res in visiting:
            raise ValueError(f"Circular dependency detected: {' -> '.join(visiting[visiting.index(res):])} -> {res}")

        if res not in visited:
            visiting.append(res)
            for neighbor in default_agg_dict[res]:
                dfs(neighbor)
            visiting.remove(res)
            visited.add(res)
            result.append(res)

    visited: Set[str] = set()
    visiting: List[str] = []
    result: List[str] = []
    default_agg_dict: Dict[str, Any] = defaultdict(list, aggregation_dict)

    resources = list(default_agg_dict.keys())
    for res in resources:
        if res not in visited:
            dfs(res)

    return result
