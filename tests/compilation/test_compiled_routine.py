# Copyright 2025 PsiQuantum, Corp.
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
from qref import SchemaV1

from bartiq import Routine, compile_routine
from bartiq.symbolics.sympy_backend import SympyBackend


def get_simple_input_schema(inp_val1, inp_val2):
    schema_v1 = SchemaV1(
        program={
            "name": "root",
            "resources": [
                {"name": "success_rate", "type": "multiplicative", "value": inp_val1},
                {"name": "other_resource", "type": "additive", "value": inp_val2},
            ],
        },
        version="v1",
    )
    return schema_v1


def get_input_schema_with_children(inp_val1, inp_val2):
    schema_v1 = SchemaV1(
        program={
            "name": "root",
            "children": [
                {
                    "name": "child1",
                    "resources": [
                        {"name": "success_rate", "type": "multiplicative", "value": inp_val1},
                    ],
                },
                {
                    "name": "child2",
                    "resources": [
                        {"name": "success_rate", "type": "multiplicative", "value": inp_val2},
                    ],
                },
            ],
        },
        version="v1",
    )
    return schema_v1


@pytest.mark.parametrize(
    ["input_schema", "expected"],
    [
        (get_simple_input_schema(20.0, 30.0), True),
        (get_simple_input_schema("example_val", 30.0), False),
        (get_simple_input_schema(20.0, "example_val"), False),
        (get_input_schema_with_children(20.0, 30.0), True),
        (get_input_schema_with_children("example_val", 30.0), False),
        (get_input_schema_with_children(20.0, "example_val"), False),
    ],
)
def test_is_numeric(input_schema, expected):
    backend = SympyBackend()
    routine_from_qref = Routine.from_qref(input_schema, backend=backend)
    c_routine = compile_routine(routine_from_qref)
    assert c_routine.routine.is_numeric() == expected
