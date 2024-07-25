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


def _expand_aggregation_dict(aggregation_dict: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Expand the aggregation dictionary to handle nested resources.

    Args:
        aggregation_dict (Dict[str, Dict[str, Any]]): The input aggregation dictionary.

    Returns:
        Dict[str, Dict[str, Any]]: The expanded aggregation dictionary.
    """
    expanded_dict = {}
    for resource, mapping in aggregation_dict.items():
        expanded_mapping = {k: sympy.sympify(v) for k, v in mapping.items()}
        to_expand = list(mapping.keys())
        while to_expand:
            current = to_expand.pop(0)
            if current in aggregation_dict:
                sub_mapping = {k: sympy.sympify(v) for k, v in aggregation_dict[current].items()}
                for sub_res, sub_multiplier in sub_mapping.items():
                    if sub_res in expanded_mapping:
                        expanded_mapping[sub_res] = (
                            sympy.sympify(expanded_mapping[sub_res]) + expanded_mapping[current] * sub_multiplier
                        )
                    else:
                        expanded_mapping[sub_res] = expanded_mapping[current] * sub_multiplier
                        to_expand.append(sub_res)
                del expanded_mapping[current]
        expanded_dict[resource] = expanded_mapping
    return expanded_dict


def add_aggregated_resources(aggregation_dict: Dict[str, Dict[str, Any]], subroutine: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add aggregated resources to the subroutine based on the aggregation dictionary.

    Args:
        aggregation_dict (Dict[str, Dict[str, Any]]): The aggregation dictionary.
        subroutine (Dict[str, Any]): The subroutine to which the resources will be added.

    Returns:
        Dict[str, Any]: The subroutine with aggregated resources.

    """
    expanded_aggregation_dict = _expand_aggregation_dict(aggregation_dict)
    if "resources" not in subroutine:
        raise ValueError("No resources defined")
    # Initialize a dictionary for aggregated resources
    aggregated_resources = {res["name"]: copy.deepcopy(res) for res in subroutine["resources"]}

    # Iterate over the original resources in the program
    for resource in copy.deepcopy(subroutine["resources"]):
        resource_name = resource["name"]
        resource_expr = sympy.sympify(resource["value"])

        if resource_name in expanded_aggregation_dict:
            mapping = expanded_aggregation_dict[resource_name]
            for sub_res, multiplier in mapping.items():
                if sub_res in aggregated_resources:
                    aggregated_resources[sub_res]["value"] = (
                        sympy.sympify(aggregated_resources[sub_res]["value"]) + multiplier * resource_expr
                    )
                else:
                    aggregated_resources[sub_res] = {
                        "name": sub_res,
                        "type": "additive",
                        "value": multiplier * resource_expr,
                    }
            del aggregated_resources[resource_name]

    subroutine["resources"] = list(aggregated_resources.values())

    return subroutine
