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
import sympy
from typing import Union
from qref import SchemaV1


def _expand_aggregation_dict(aggregation_dict: dict) -> dict:
    # Expand the aggregation_dict to handle nested calls
    expanded_dict = {}
    for key, mapping in aggregation_dict.items():
        expanded_mapping = {k: sympy.sympify(v) for k, v in mapping.items()}
        to_expand = list(mapping.keys())
        while to_expand:
            current = to_expand.pop(0)
            if current in aggregation_dict:
                sub_mapping = {k: sympy.sympify(v) for k, v in aggregation_dict[current].items()}
                for sub_key, sub_multiplier in sub_mapping.items():
                    if sub_key in expanded_mapping:
                        expanded_mapping[sub_key] = (
                            sympy.sympify(expanded_mapping[sub_key]) + expanded_mapping[current] * sub_multiplier
                        )
                    else:
                        expanded_mapping[sub_key] = expanded_mapping[current] * sub_multiplier
                        to_expand.append(sub_key)
                del expanded_mapping[current]
        expanded_dict[key] = expanded_mapping
    return expanded_dict


def add_aggregated_resources(aggregation_dict: dict, subroutine: dict) -> dict:
    expanded_aggregation_dict = _expand_aggregation_dict(aggregation_dict)
    if "resources" not in subroutine:
        raise ValueError("No resources defined")
    # Initialize a dictionary for aggregated resources
    aggregated_resources = {res["name"]: copy.deepcopy(res) for res in subroutine["resources"]}

    # Iterate over the original resources in the program
    for resource in copy.deepcopy(subroutine["resources"]):
        resource_name = resource["name"]
        resource_expr = sympy.sympify(resource["value"])

        # Check if the resource should be aggregated
        if resource_name in expanded_aggregation_dict:
            mapping = expanded_aggregation_dict[resource_name]
            for key, multiplier in mapping.items():
                if key in aggregated_resources:
                    aggregated_resources[key]["value"] = (
                        sympy.sympify(aggregated_resources[key]["value"]) + multiplier * resource_expr
                    )
                else:
                    aggregated_resources[key] = {"name": key, "type": "additive", "value": multiplier * resource_expr}
            del aggregated_resources[resource_name]

    subroutine["resources"] = list(aggregated_resources.values())

    return subroutine
