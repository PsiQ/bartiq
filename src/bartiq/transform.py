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
from typing import Any, Dict, Union

import sympy
from qref import SchemaV1

def add_aggregated_resources(
    aggregation_dict: Dict[str, Dict[str, Any]], qref_obj: Union[SchemaV1, dict]
) -> Union[SchemaV1, dict]:
    """
    Add aggregated resources to qref program based on the aggregation dictionary.

    Args:
        aggregation_dict (Dict[str, Dict[str, Any]]): The aggregation dictionary.
        qref_obj (Union[Dict[str, Any], Any]): The program to which the resources will be added.

    Returns:
        Union[SchemaV1, dict]: The program with aggregated resources.

    Raises:
        TypeError: If the input types are not valid qref object.
    """
    if not SchemaV1.model_validate(qref_obj):
        raise TypeError("Must apply to a qref object.")

    expanded_aggregation_dict = _expand_aggregation_dict(aggregation_dict)
    qref_obj["program"] = _process_program(expanded_aggregation_dict, qref_obj["program"])
    return qref_obj


def _add_aggregated_resources_to_subroutine(
    expanded_aggregation_dict: Dict[str, Dict[str, Any]], subroutine: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Add aggregated resources to the subroutine based on the aggregation dictionary.

    Args:
        expanded_aggregation_dict (Dict[str, Dict[str, Any]]): The expanded aggregation dictionary.
        subroutine (Dict[str, Any]): The subroutine to which the resources will be added.

    Returns:
        Dict[str, Any]: The subroutine with aggregated resources.
    """
    if "resources" not in subroutine:
        return subroutine

    # Initialize a dictionary for aggregated resources
    aggregated_resources = {res["name"]: copy.deepcopy(res) for res in subroutine["resources"]}
    # Iterate over the original resources in the subroutine
    for resource in subroutine["resources"]:
        resource_name = resource["name"]
        resource_type = resource["type"]

        try:
            resource_expr = sympy.sympify(resource["value"])
        except (sympy.SympifyError, TypeError) as e:
            raise ValueError(f"Invalid resource value: {resource['value']}") from e

        if resource_name in expanded_aggregation_dict:
            mapping = expanded_aggregation_dict[resource_name]
            for sub_res, multiplier in mapping.items():
                if sub_res in aggregated_resources and resource_type == "additive":
                    aggregated_resources[sub_res]["value"] = (
                        sympy.sympify(aggregated_resources[sub_res]["value"]) + multiplier * resource_expr
                    )
                else:
                    aggregated_resources[sub_res] = {
                        "name": sub_res,
                        "type": resource_type,
                        "value": multiplier * resource_expr,
                    }
            del aggregated_resources[resource_name]

    subroutine["resources"] = list(aggregated_resources.values())
    return subroutine

def _process_program(expanded_aggregation_dict: Dict[str, Dict[str, Any]], program: Dict[str, Any]) -> Dict[str, Any]:
    program = _add_aggregated_resources_to_subroutine(expanded_aggregation_dict, program)
    if "children" in program:
        program["children"] = [_process_program(expanded_aggregation_dict, child) for child in program["children"]]

    return program


def _expand_aggregation_dict(aggregation_dict: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Expand the aggregation dictionary to handle nested resources.

    Args:
        aggregation_dict (Dict[str, Dict[str, Any]]): The input aggregation dictionary.

    Returns:
        Dict[str, Dict[str, Any]]: The expanded aggregation dictionary.
    """
    expanded_dict = {}
    for resource in aggregation_dict.keys():
        expanded_dict[resource] = _expand_resource(resource, aggregation_dict, set())
    return expanded_dict

def _expand_resource(resource: str, aggregation_dict: Dict[str, Dict[str, Any]], visited: set) -> Dict[str, Any]:
    """
    Recursively expand resource mapping to handle nested resources and detect circular dependencies.

    Args:
        resource (str): The resource to expand.
        aggregation_dict (Dict[str, Dict[str, Any]]): The input aggregation dictionary.
        visited (set): A set of currently visited resources to detect circular dependencies.

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
    expanded_mapping = {k: sympy.sympify(v) for k, v in aggregation_dict[resource].items()}
    res_to_expand = list(expanded_mapping.keys())

    while res_to_expand:
        current = res_to_expand.pop(0)
        if current in aggregation_dict:
            # Recursively expand the nested resources
            sub_mapping = _expand_resource(current, aggregation_dict, visited.copy())
            for sub_res, sub_multiplier in sub_mapping.items():
                if sub_res in expanded_mapping:
                    expanded_mapping[sub_res] = (
                        sympy.sympify(expanded_mapping[sub_res]) + expanded_mapping[current] * sub_multiplier
                    )
                else:
                    expanded_mapping[sub_res] = expanded_mapping[current] * sub_multiplier
                    res_to_expand.append(sub_res)
            del expanded_mapping[current]

    # Remove the current resource from the visited set
    visited.remove(resource)
    return expanded_mapping

