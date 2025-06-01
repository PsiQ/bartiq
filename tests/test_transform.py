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
from qref.schema_v1 import RoutineV1

from bartiq import Routine
from bartiq.transform import add_aggregated_resources, add_circuit_volume

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
    return test_qref


@pytest.mark.parametrize(
    "aggregation_dict, input_qref, remove_decomposed, expected_output",
    [
        (
            {"control_ry": {"rotation": 2, "CNOT": 2}, "rotation": {"T_gates": 50}},
            _generate_test(
                ccry_gate,
                ["z", "num"],
                [{"source": "z", "targets": ["ccry_gate.x"]}, {"source": "num", "targets": ["ccry_gate.num"]}],
            ),
            True,
            {
                "name": "test_qref",
                "input_params": ["z", "num"],
                "children": [
                    {
                        "name": "ccry_gate",
                        "type": None,
                        "input_params": ["x", "num"],
                        "ports": [
                            {"name": "in", "direction": "input", "size": "n"},
                            {"name": "out", "direction": "output", "size": "n"},
                        ],
                        "resources": [
                            {"name": "CNOT", "type": "additive", "value": "8*num"},
                            {"name": "T_gates", "type": "additive", "value": "300*num"},
                        ],
                        "local_variables": {"n": "x"},
                    }
                ],
                "type": None,
                "linked_params": [
                    {"source": "z", "targets": ["ccry_gate.x"]},
                    {"source": "num", "targets": ["ccry_gate.num"]},
                ],
                "ports": [
                    {"name": "in", "direction": "input", "size": "z"},
                    {"name": "out", "direction": "output", "size": "z"},
                ],
                "connections": [
                    {"source": "in", "target": "ccry_gate.in"},
                    {"source": "ccry_gate.out", "target": "out"},
                ],
            },
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
            {
                "name": "test_qref",
                "input_params": ["z", "num"],
                "children": [
                    {
                        "name": "arbitrary_z",
                        "type": None,
                        "input_params": ["x", "num"],
                        "ports": [
                            {"name": "in", "direction": "input", "size": "n"},
                            {"name": "out", "direction": "output", "size": "n"},
                        ],
                        "resources": [
                            {
                                "name": "T_gates",
                                "type": "additive",
                                "value": "ceiling(5*num/2)*(3*log2(1/epsilon) + O(log(log(1/epsilon))))",
                            },
                        ],
                        "local_variables": {"n": "x"},
                    }
                ],
                "type": None,
                "linked_params": [
                    {"source": "z", "targets": ["arbitrary_z.x"]},
                    {"source": "num", "targets": ["arbitrary_z.num"]},
                ],
                "ports": [
                    {"name": "in", "direction": "input", "size": "z"},
                    {"name": "out", "direction": "output", "size": "z"},
                ],
                "connections": [
                    {"source": "in", "target": "arbitrary_z.in"},
                    {"source": "arbitrary_z.out", "target": "out"},
                ],
            },
        ),
        (
            {"control_ry": {"rotation": 2, "CNOT": 2}, "rotation": {"T_gates": 50}},
            _generate_test(
                ccry_gate,
                ["z", "num"],
                [{"source": "z", "targets": ["ccry_gate.x"]}, {"source": "num", "targets": ["ccry_gate.num"]}],
            ),
            False,
            {
                "name": "test_qref",
                "input_params": ["z", "num"],
                "children": [
                    {
                        "name": "ccry_gate",
                        "type": None,
                        "input_params": ["x", "num"],
                        "ports": [
                            {"name": "in", "direction": "input", "size": "n"},
                            {"name": "out", "direction": "output", "size": "n"},
                        ],
                        "resources": [
                            {"name": "CNOT", "type": "additive", "value": "8*num"},
                            {"name": "T_gates", "type": "additive", "value": "300*num"},
                            {
                                "name": "control_ry",
                                "type": "other",
                                "value": "3*num",
                            },
                        ],
                        "local_variables": {"n": "x"},
                    }
                ],
                "type": None,
                "linked_params": [
                    {"source": "z", "targets": ["ccry_gate.x"]},
                    {"source": "num", "targets": ["ccry_gate.num"]},
                ],
                "ports": [
                    {"name": "in", "direction": "input", "size": "z"},
                    {"name": "out", "direction": "output", "size": "z"},
                ],
                "connections": [
                    {"source": "in", "target": "ccry_gate.in"},
                    {"source": "ccry_gate.out", "target": "out"},
                ],
            },
        ),
    ],
)
def test_add_aggregated_resources(aggregation_dict, input_qref, remove_decomposed, expected_output, backend):
    routine = Routine.from_qref(RoutineV1(**input_qref), backend)
    result = add_aggregated_resources(routine, aggregation_dict, remove_decomposed=remove_decomposed)
    _compare_routines(result, Routine.from_qref(RoutineV1(**expected_output), backend))


def _compare_routines(routine, expected):
    if hasattr(routine, "resources") and routine.resources:
        for resource_name in routine.resources:
            expanded_expr = sympy.simplify(routine.resources[resource_name].value)
            expected_expr = sympy.simplify(expected.resources[resource_name].value)
            assert expanded_expr.equals(expected_expr)

    for child in routine.children:
        _compare_routines(routine.children[child], expected.children[child])


def test_add_circuit_volume_simple(backend):
    from bartiq import CompiledRoutine, Resource, ResourceType

    # Create a simple routine with required resources
    routine = CompiledRoutine(
        name="test",
        type=None,
        input_params=[],
        children={},
        ports={},
        resources={
            "aggregated_t_gates": Resource("aggregated_t_gates", ResourceType.additive, 5),
            "qubit_highwater": Resource("qubit_highwater", ResourceType.qubits, 3),
        },
        connections={},
        children_order=(),
    )
    out = add_circuit_volume(routine, backend=backend)
    assert "circuit_volume" in out.resources
    assert backend.value_of(out.resources["circuit_volume"].value) == 15


def test_add_circuit_volume_with_children(backend):
    from bartiq import CompiledRoutine, Resource, ResourceType
    from bartiq.transform import add_circuit_volume

    # Create a child routine with required resources
    child = CompiledRoutine(
        name="child",
        type=None,
        input_params=[],
        children={},
        ports={},
        resources={
            "aggregated_t_gates": Resource("aggregated_t_gates", ResourceType.additive, 2),
            "qubit_highwater": Resource("qubit_highwater", ResourceType.qubits, 4),
        },
        connections={},
        children_order=(),
    )
    # Create a parent routine with required resources and the child
    parent = CompiledRoutine(
        name="parent",
        type=None,
        input_params=[],
        children={"child": child},
        ports={},
        resources={
            "aggregated_t_gates": Resource("aggregated_t_gates", ResourceType.additive, 3),
            "qubit_highwater": Resource("qubit_highwater", ResourceType.qubits, 5),
        },
        connections={},
        children_order=("child",),
    )
    out = add_circuit_volume(parent, backend=backend)
    assert "circuit_volume" in out.resources
    assert backend.value_of(out.resources["circuit_volume"].value) == 15
    assert "circuit_volume" in out.children["child"].resources
    assert backend.value_of(out.children["child"].resources["circuit_volume"].value) == 8

    # Test with custom resource names
    child2 = CompiledRoutine(
        name="child2",
        type=None,
        input_params=[],
        children={},
        ports={},
        resources={
            "custom_t": Resource("custom_t", ResourceType.additive, 7),
            "custom_highwater": Resource("custom_highwater", ResourceType.qubits, 2),
        },
        connections={},
        children_order=(),
    )
    out2 = add_circuit_volume(
        child2, name_of_aggregated_t="custom_t", name_of_qubit_highwater="custom_highwater", backend=backend
    )
    assert "circuit_volume" in out2.resources
    assert backend.value_of(out2.resources["circuit_volume"].value) == 14
