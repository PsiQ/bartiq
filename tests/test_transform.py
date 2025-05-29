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

import warnings

import pytest
import sympy
from qref.schema_v1 import RoutineV1

from bartiq import Resource, ResourceType, Routine
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


def _assert_circuit_volume_by_index(
    routine,
    expected_volumes,
    should_exist,
    name_of_circuit_volume="circuit_volume",
    name_of_qubit_highwater="qubit_highwater",
):
    """
    Checks circuit_volume for parent and children by index in expected_volumes.
    expected_volumes: [parent, child1, child2, ...]
    """
    nodes = [routine] + list(routine.children.values())
    for idx, node in enumerate(nodes):
        expected_volume = expected_volumes[idx]
        if should_exist and expected_volume is not None:
            assert name_of_circuit_volume in node.resources
            # Use the parameterized name for qubit_highwater
            assert name_of_qubit_highwater in node.resources
            assert sympy.simplify(node.resources[name_of_circuit_volume].value - sympy.sympify(expected_volume)) == 0
        else:
            assert name_of_circuit_volume not in node.resources


@pytest.mark.parametrize(
    "parent_resources,children_resources,expected_volumes,should_exist,custom_t,custom_qh",
    [
        # Custom resource names, all present
        (
            {"my_t": Resource("my_t", ResourceType.additive, 7), "my_qh": Resource("my_qh", ResourceType.other, 3)},
            [
                {"my_t": Resource("my_t", ResourceType.additive, 2), "my_qh": Resource("my_qh", ResourceType.other, 5)},
            ],
            [21, 10],
            True,
            "my_t",
            "my_qh",
        ),
        # Custom resource names, child missing qubit highwater
        (
            {"my_t": Resource("my_t", ResourceType.additive, 7), "my_qh": Resource("my_qh", ResourceType.other, 3)},
            [
                {"my_t": Resource("my_t", ResourceType.additive, 2)},
            ],
            [21, None],
            True,
            "my_t",
            "my_qh",
        ),
        # Custom resource names, parent missing qubit highwater
        ({"my_t": Resource("my_t", ResourceType.additive, 7)}, [], [None], False, "my_t", "my_qh"),
        # Deeply nested children, all present
        (
            {"agg": Resource("agg", ResourceType.additive, 2), "qhw": Resource("qhw", ResourceType.other, 4)},
            [
                {"agg": Resource("agg", ResourceType.additive, 3), "qhw": Resource("qhw", ResourceType.other, 5)},
                {"agg": Resource("agg", ResourceType.additive, 1), "qhw": Resource("qhw", ResourceType.other, 2)},
            ],
            [8, 15, 2],
            True,
            "agg",
            "qhw",
        ),
    ],
)
def test_add_circuit_volume_custom_names_and_children(
    parent_resources, children_resources, expected_volumes, should_exist, custom_t, custom_qh, backend
):
    from bartiq import CompiledRoutine
    from bartiq.transform import add_circuit_volume

    children = {}
    for i, res in enumerate(children_resources):
        children[f"child{i + 1}"] = CompiledRoutine(
            name=f"child{i + 1}",
            type=None,
            input_params=(),
            children={},
            ports={},
            resources=res,
            constraints=(),
            connections={},
            repetition=None,
            children_order=(),
        )
    parent = CompiledRoutine(
        name="parent",
        type=None,
        input_params=(),
        children=children,
        ports={},
        resources=parent_resources,
        constraints=(),
        connections={},
        repetition=None,
        children_order=tuple(children.keys()),
    )

    result = add_circuit_volume(
        parent, name_of_aggregated_t=custom_t, name_of_qubit_highwater=custom_qh, backend=backend
    )
    _assert_circuit_volume_by_index(
        result,
        expected_volumes,
        should_exist,
        name_of_circuit_volume="circuit_volume",
        name_of_qubit_highwater=custom_qh,
    )


def test_add_circuit_volume_warns_on_missing_resources(backend):
    from bartiq import CompiledRoutine
    from bartiq.transform import add_circuit_volume

    parent_resources = {"agg": Resource("agg", ResourceType.additive, 2)}
    parent = CompiledRoutine(
        name="parent",
        type=None,
        input_params=(),
        children={},
        ports={},
        resources=parent_resources,
        constraints=(),
        connections={},
        repetition=None,
        children_order=(),
    )
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        _ = add_circuit_volume(parent, name_of_aggregated_t="agg", name_of_qubit_highwater="qhw", backend=backend)
        assert any("Missing required resources" in str(warn.message) for warn in w)
