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

arbitrary_z = {
    "name": "arbitrary_z",
    "type": None,
    "ports": [
        {"name": "in", "direction": "input", "size": "n"},
        {"name": "out", "direction": "output", "size": "n"},
    ],
    "resources": [
        {"name": "arbitrary_z", "type": "additive", "value": "ceiling(5*num/2)"},
    ],
    "input_params": ["x", "num"],
    "local_variables": {"n": "x"},
}


def _generate_test(subroutine, input_params, linked_params):
    test_qref = {
        "name": "test_qref",
        "type": None,
        "ports": [
            {"name": "in", "direction": "input", "size": "z"},
            {"name": "out", "direction": "output", "size": "z"},
        ],
    }
    test_qref["children"] = [subroutine]
    test_qref["connections"] = [
        {"source": "in", "target": f"{subroutine['name']}.in"},
        {"source": f"{subroutine['name']}.out", "target": "out"},
    ]
    test_qref["input_params"] = input_params
    test_qref["linked_params"] = linked_params
    test_qref = {"version": "v1", "program": test_qref}
    return qref_to_bartiq(test_qref)


@pytest.mark.parametrize(
    "aggregation_dict, generate_test_fn, remove_decomposed, expected_output",
    [
        (
            {"control_ry": {"rotation": 2, "CNOT": 2}, "rotation": {"T_gates": 50}},
            _generate_test(
                ccry_gate,
                ["z", "num"],
                [{"source": "z", "targets": ["ccry_gate.x"]}, {"source": "num", "targets": ["ccry_gate.num"]}],
            ),
            True,
            Routine(
                name="test_qref",
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
        (  # Example using aggregation dict values with parameters to approximate single-qubit Z-rotations
            # using optimal ancilla-free Clifford+T circuits, as detailed in (arXiv:1403.2975).
            {"arbitrary_z": {"T_gates": "3*log2(1/epsilon) + O(log(log(1/epsilon)))"}},
            _generate_test(
                arbitrary_z,
                ["z", "num"],
                [{"source": "z", "targets": ["arbitrary_z.x"]}, {"source": "num", "targets": ["arbitrary_z.num"]}],
            ),
            True,
            Routine(
                name="test_qref",
                input_params=["z", "num"],
                children={
                    "arbitrary_z": Routine(
                        name="arbitrary_z",
                        type=None,
                        input_params=["x", "num"],
                        ports={
                            "in": {"name": "in", "direction": "input", "size": "n"},
                            "out": {"name": "out", "direction": "output", "size": "n"},
                        },
                        resources={
                            "T_gates": {
                                "name": "T_gates",
                                "type": "additive",
                                "value": "ceiling(5*num/2)*(3*log2(1/epsilon) + O(log(log(1/epsilon))))",
                            },
                        },
                        local_variables={"n": "x"},
                    )
                },
                type=None,
                linked_params={"z": [("arbitrary_z", "x")], "num": [("arbitrary_z", "num")]},
                ports={
                    "in": {"name": "in", "direction": "input", "size": "z"},
                    "out": {"name": "out", "direction": "output", "size": "z"},
                },
                connections=[
                    {"source": "in", "target": "arbitrary_z.in"},
                    {"source": "arbitrary_z.out", "target": "out"},
                ],
            ),
        ),
        (
            {"control_ry": {"rotation": 2, "CNOT": 2}, "rotation": {"T_gates": 50}},
            _generate_test(
                ccry_gate,
                ["z", "num"],
                [{"source": "z", "targets": ["ccry_gate.x"]}, {"source": "num", "targets": ["ccry_gate.num"]}],
            ),
            False,
            Routine(
                name="test_qref",
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
                            "control_ry": {
                                "name": "control_ry",
                                "type": "other",
                                "value": "3*num",
                            },
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
def test_add_aggregated_resources(aggregation_dict, generate_test_fn, remove_decomposed, expected_output):
    result = add_aggregated_resources(generate_test_fn, aggregation_dict, remove_decomposed=remove_decomposed)
    _compare_routines(result, expected_output)


def _compare_routines(routine, expected):
    if hasattr(routine, "resources") and routine.resources:
        for resource_name in routine.resources:
            expanded_expr = sympy.simplify(routine.resources[resource_name].value)
            expected_expr = sympy.simplify(expected.resources[resource_name].value)
            assert expanded_expr.equals(expected_expr)

    for child in routine.children:
        _compare_routines(routine.children[child], expected.children[child])
