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
from bartiq import Routine
from bartiq.integrations import qref_to_bartiq
from bartiq.transform import add_aggregated_resources

ccry_gate = {
    "name": "ccry_gate",
    "type": None,
    "ports": [
        {"name": "in", "direction": "input", "size": "n"},
        {"name": "out", "direction": "output", "size": "n"},
    ],
    "resources": [
        {"name": "CNOT", "type": "additive", "value": "2*num"},
        {"name": "control_ry", "type": "additive", "value": "3*num"},
    ],
    "input_params": ["x", "num"],
    "local_variables": {"n": "x"},
}


def generate_test_1():
    test_1_qref = {
        "name": "test_1_qref",
        "type": None,
        "ports": [
            {"name": "in", "direction": "input", "size": "z"},
            {"name": "out", "direction": "output", "size": "z"},
        ],
    }
    test_1_qref["children"] = [ccry_gate]
    test_1_qref["connections"] = [
        {"source": "in", "target": "ccry_gate.in"},
        {"source": "ccry_gate.out", "target": "out"},
    ]
    test_1_qref["input_params"] = ["z", "num"]
    test_1_qref["linked_params"] = [
        {"source": "z", "targets": ["ccry_gate.x"]},
        {"source": "num", "targets": ["ccry_gate.num"]},
    ]
    test_1_qref = {"version": "v1", "program": test_1_qref}
    test_1 = qref_to_bartiq(test_1_qref)
    return test_1


@pytest.mark.parametrize(
    "aggregation_dict, test_1, expected_output",
    [
        (
            {"control_ry": {"rotation": 2, "CNOT": 2}, "rotation": {"T_gates": 50}},
            generate_test_1(),
            Routine(
                name="test_1_qref",
                input_params=["z", "num"],
                children={
                    "ccry_gate": Routine(
                        name="ccry_gate",
                        type=None,
                        input_params=["x", "num"],
                        ports={
                            "in": {"name": "in", "direction": "input", "size": "n"},
                            "out": {"name": "out", "direction": "output", "size": "n"},
                        },
                        resources={
                            "CNOT": {"name": "CNOT", "type": "additive", "value": "8*num"},
                            "T_gates": {"name": "control_ry", "type": "additive", "value": "300*num"},
                        },
                        local_variables={"n": "x"},
                    )
                },
                type=None,
                linked_params={"z": [("ccry_gate", "x")], "num": [("ccry_gate", "num")]},
                ports={
                    "in": {"name": "in", "direction": "input", "size": "z"},
                    "out": {"name": "out", "direction": "output", "size": "z"},
                },
                connections=[
                    {"source": "in", "target": "ccry_gate.in"},
                    {"source": "ccry_gate.out", "target": "out"},
                ],
            ),
        ),
    ],
)
def test_add_aggregated_resources(aggregation_dict, test_1, expected_output):
    result = add_aggregated_resources(aggregation_dict, test_1)

    def compare_resources(routine, expected):
        if hasattr(routine, "resources") and routine.resources:
            for resource_name in routine.resources:
                assert routine.resources[resource_name].value == expected.resources[resource_name].value
            for child in routine.children:
                compare_resources(child, expected)

    compare_resources(result, expected_output)
