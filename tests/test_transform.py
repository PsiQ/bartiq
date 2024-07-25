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
from sympy.abc import x, y
from qref import SchemaV1  # Assuming the functions and class are in qref module

from bartiq.transform import _expand_aggregation_dict, expand_aggregation_resources, add_aggregated_resources


@pytest.mark.parametrize(
    "aggregation_dict, expected",
    [
        (
            {'A': {'B': 2, 'C': 3}, 'B': {'C': 4, 'D': 5}, 'C': {'D': 6}},
            {'A': {'D': 76}, 'B': {'D': 29}, 'C': {'D': 6}},
        ),
    ],
)
def test_expand_aggregation_dict(aggregation_dict, expected):
    assert _expand_aggregation_dict(aggregation_dict) == expected

@pytest.mark.parametrize(
    "aggregation_dict, expected",
    [
        (
            {'A': {'B': 2, 'C': 'x-y'}, 'B': {'C': 4, 'D': 5}, 'C': {'D': '3*z'}},
            {'A': {'D': '3*z*(x - y + 8) + 10'}, 'B': {'D': '12*z+5'}, 'C': {'D': '3*z'}},
        ),
    ],
)
def test_expand_aggregation_dict_symbol(aggregation_dict, expected):
    result = _expand_aggregation_dict(aggregation_dict)
    for key in expected:
        for sub_key in expected[key]:
            assert sympy.simplify(result[key][sub_key]) == sympy.simplify(expected[key][sub_key])