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

import pytest
import sympy
from bartiq.transform import _expand_aggregation_dict, add_aggregated_resources


@pytest.mark.parametrize(
    "aggregation_dict, expected",
    [
        (
            {
                "B": {"C": 4, "D": 5},
                "C": {"D": 6},
                "A": {"B": 2, "C": 3},
            },
            {
                "B": {"D": 29},
                "C": {"D": 6},
                "A": {"D": 76},
            },
        ),
    ],
)
def test_expand_aggregation_dict(aggregation_dict, expected):
    assert _expand_aggregation_dict(aggregation_dict) == expected


@pytest.mark.parametrize(
    "aggregation_dict, expected",
    [
        (
            {"B": {"C": 4, "D": 5}, "C": {"D": "3*z"}, "A": {"B": 2, "C": "x-y"}},
            {"B": {"D": "12*z+5"}, "A": {"D": "3*z*(x - y + 8) + 10"}, "C": {"D": "3*z"}},
        ),
    ],
)
def test_expand_aggregation_dict_symbol(aggregation_dict, expected):
    result = _expand_aggregation_dict(aggregation_dict)

    for resource in result:
        for sub_res in result[resource]:
            expanded_expr = sympy.simplify(result[resource][sub_res])
            expected_expr = sympy.simplify(expected[resource][sub_res])
            assert expanded_expr.equals(expected_expr)


"""
subroutine_1 = {
    "name": "subroutine_1",
    "type": None,
    "ports": [
        {"name": "in", "direction": "input", "size": "R"},
        {"name": "out", "direction": "output", "size": "R"},
    ],
    "resources": [
        {"name": "A", "type": "additive", "value": "2*x"},
        {"name": "B", "type": "additive", "value": "3"},
    ],
    "input_params": ["x"],
    "local_variables": {"R": "x+1"},
}

subroutine_2 = {
    "name": "subroutine_2",
    "type": None,
    "ports": [
        {"name": "in", "direction": "input", "size": "R"},
        {"name": "out", "direction": "output", "size": "R"},
    ],
    "resources": [
        {"name": "A", "type": "additive", "value": "ceil(x/4)"},
        {"name": "B", "type": "additive", "value": "1"},
    ],
    "input_params": ["x"],
    "local_variables": {"R": "x+1"},
}

subroutine_3 = {
    "name": "subroutine_3",
    "type": None,
    "ports": [
        {"name": "in", "direction": "input", "size": "R"},
        {"name": "out", "direction": "output", "size": "R"},
    ],
    "resources": [
        {"name": "A", "type": "additive", "value": "sqrt(x/4)"},
        {"name": "B", "type": "additive", "value": "1"},
    ],
    "input_params": ["x"],
    "local_variables": {"R": "x"},
}


# Test for add_aggregated_resources with correct values
@pytest.mark.parametrize(
    "aggregation_dict, subroutine, expected",
    [
        (
            {"A": {"B": "x*y + z"}, "B": {"C": "2*z"}},
            subroutine_1,
            {
                "name": "subroutine_1",
                "type": None,
                "ports": [
                    {"name": "in", "direction": "input", "size": "R"},
                    {"name": "out", "direction": "output", "size": "R"},
                ],
                "resources": [
                    {"name": "C", "type": "additive", "value": "6*z+2*x*(x*y+z)*(2*z)"},
                ],
                "input_params": ["x"],
                "local_variables": {"R": "x+1"},
            },
        ),
        (
            {"A": {"C": "x*y"}, "B": {"D": "2*x + y"}, "C": {"D": "3*z"}},
            subroutine_2,
            {
                "name": "subroutine_2",
                "type": None,
                "ports": [
                    {"name": "in", "direction": "input", "size": "R"},
                    {"name": "out", "direction": "output", "size": "R"},
                ],
                "resources": [
                    {"name": "D", "type": "additive", "value": "3*ceil(x/4)*x*y*z + (2*x + y)"},
                ],
                "input_params": ["x"],
                "local_variables": {"R": "x+1"},
            },
        ),
    ],
)
def test_add_aggregated_resources(aggregation_dict, subroutine, expected):
    aggregated_subroutine = add_aggregated_resources(aggregation_dict, subroutine)

    aggregated_resources = aggregated_subroutine["resources"]
    expected_resources = expected["resources"]

    aggregated_names = [res["name"] for res in aggregated_resources]
    expected_names = [res["name"] for res in expected_resources]

    assert aggregated_names == expected_names

    for resource in aggregated_resources:
        for expected_resource in expected_resources:
            if expected_resource["name"] == resource["name"]:
                assert sympy.simplify(resource["value"]) == sympy.simplify(expected_resource["value"])
                assert resource["type"] == expected_resource["type"]


@pytest.mark.parametrize(
    "error_aggregation_dict, error_subroutine, error_expected",
    [
        (
            {"A": {"B": "x*y + z"}},
            subroutine_3,
            {
                "name": "subroutine_3",
                "type": None,
                "ports": [
                    {"name": "in", "direction": "input", "size": "R"},
                    {"name": "out", "direction": "output", "size": "R"},
                ],
                "resources": [
                    {"name": "B", "type": "multiadditive", "value": "sqrt(x/4) * (x*y + z)+90"},
                    {"name": "wrong", "type": "additive", "value": "3"},
                ],
                "input_params": ["x"],
                "local_variables": {"R": "x"},
            },
        ),
    ],
)
def test_add_aggregated_resources_errors(error_aggregation_dict, error_subroutine, error_expected):
    aggregated_subroutine = add_aggregated_resources(error_aggregation_dict, error_subroutine)

    aggregated_resources = aggregated_subroutine["resources"]
    expected_resources = error_expected["resources"]

    aggregated_names = [res["name"] for res in aggregated_resources]
    expected_names = [res["name"] for res in expected_resources]

    assert aggregated_names != expected_names

    for resource in aggregated_resources:
        for expected_resource in expected_resources:
            if expected_resource["name"] == resource["name"]:
                assert sympy.simplify(resource["value"]) != sympy.simplify(expected_resource["value"])
                assert resource["type"] != expected_resource["type"]
"""
