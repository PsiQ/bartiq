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
from dataclasses import replace
from graphlib import TopologicalSorter
from typing import Any, TypeVar

from bartiq import Resource, ResourceType, Routine
from bartiq.symbolics import sympy_backend
from bartiq.symbolics.backend import SymbolicBackend, TExpr

BACKEND = sympy_backend


T = TypeVar("T")


def add_aggregated_resources(
    routine: Routine[T],
    aggregation_dict: dict[str, dict[str, Any]],
    remove_decomposed: bool = True,
    backend: SymbolicBackend[T] = sympy_backend,
) -> Routine[T]:
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
        remove_decomposed : Whether to remove the decomposed resources from the routine.
            Defaults to True.
        backend : Backend instance to use for handling expressions.
            Defaults to `sympy_backend`.

    Returns:
        Routine: The program with aggregated resources.

    """
    expanded_aggregation_dict = _expand_aggregation_dict(aggregation_dict)
    return _add_aggregated_resources_to_subroutine(routine, expanded_aggregation_dict, remove_decomposed, backend)


def _add_aggregated_resources_to_subroutine(
    subroutine: Routine[T],
    expanded_aggregation_dict: dict[str, dict[str, str | TExpr[T]]],
    remove_decomposed: bool,
    backend: SymbolicBackend[T] = BACKEND,
) -> Routine[T]:
    new_children = {
        name: _add_aggregated_resources_to_subroutine(child, expanded_aggregation_dict, remove_decomposed, backend)
        for name, child in subroutine.children.items()
    }
    if not hasattr(subroutine, "resources") or not subroutine.resources:
        return replace(subroutine, children=new_children)

    aggregated_resources = copy.copy(subroutine.resources)
    for resource_name in subroutine.resources:
        resource_expr = backend.as_expression(subroutine.resources[resource_name].value)
        if resource_name in expanded_aggregation_dict:
            mapping = expanded_aggregation_dict[resource_name]
            for sub_res, multiplier in mapping.items():
                multiplier_expr = backend.as_expression(multiplier)
                if sub_res in aggregated_resources:
                    current_value_expr = backend.as_expression(aggregated_resources[sub_res].value)
                    aggregated_resources[sub_res] = replace(
                        aggregated_resources[sub_res],
                        value=current_value_expr + multiplier_expr * resource_expr,  # type: ignore
                    )
                else:
                    new_resource = Resource[T](
                        name=sub_res,
                        type=subroutine.resources[resource_name].type,
                        value=multiplier_expr * resource_expr,  # type: ignore
                    )
                    aggregated_resources[sub_res] = new_resource
            if remove_decomposed:
                del aggregated_resources[resource_name]
            else:
                aggregated_resources[resource_name] = replace(
                    aggregated_resources[resource_name], type=ResourceType.other
                )

    return replace(subroutine, resources=aggregated_resources, children=new_children)


def _expand_aggregation_dict(
    aggregation_dict: dict[str, dict[str, str | TExpr[T]]], backend: SymbolicBackend[T] = BACKEND
) -> dict[str, dict[str, TExpr[T]]]:
    """Expand the aggregation dictionary to handle nested resources.
    Args:
        aggregation_dict: The input aggregation dictionary.
    Returns:
        Dict[str, Dict[str, Any]]: The expanded aggregation dictionary.
    """
    sorted_resources = _topological_sort(aggregation_dict)
    expanded_dict: dict[str, dict[str, TExpr[T]]] = {}
    for resource in sorted_resources:
        expanded_dict[resource] = _expand_resource(resource, aggregation_dict, expanded_dict, backend)
    return expanded_dict


def _expand_resource(
    resource: str,
    aggregation_dict: dict[str, dict[str, str | TExpr[T]]],
    expanded_dict: dict[str, dict[str, TExpr[T]]],
    backend: SymbolicBackend[T] = BACKEND,
) -> dict[str, TExpr[T]]:
    """Recursively expand resource mapping to handle nested resources and detect circular dependencies.
    Args:
        resource: The resource to expand.
        aggregation_dict: The input aggregation dictionary.
    Returns:
        Dict[str, Any]: The expanded resource mapping.
    """

    expanded_mapping = {k: backend.as_expression(v) for k, v in aggregation_dict[resource].items()}

    for current in list(expanded_mapping):
        # Recursively expand the nested resources
        for sub_res, sub_multiplier in expanded_dict.get(current, {}).items():
            sub_multiplier_expr = backend.as_expression(sub_multiplier)
            expanded_expr = backend.as_expression(expanded_mapping[current]) * sub_multiplier_expr  # type: ignore
            if sub_res in expanded_mapping:
                expanded_mapping[sub_res] = expanded_mapping[sub_res] + expanded_expr  # type: ignore
            else:
                expanded_mapping[sub_res] = expanded_expr

        if current in aggregation_dict:
            del expanded_mapping[current]

    return expanded_mapping


def _topological_sort(aggregation_dict: dict[str, dict[str, Any]]) -> list[str]:
    """Perform a topological sort on the aggregation dictionary to determine the order of resource expansion.
    Args:
        aggregation_dict : The input aggregation dictionary where keys are resource names
                                                      and values are dictionaries of decomposed resources.
    Returns:
        List[str]: The list of resources in topologically sorted order.

    Raises:
        ValueError: If a circular dependency is detected in the aggregation dictionary.
    """

    predecessors: dict[str, set[str]] = {
        var: set(other_var for other_var in dependants if other_var in aggregation_dict)
        for var, dependants in aggregation_dict.items()
    }

    return list(TopologicalSorter(predecessors).static_order())
