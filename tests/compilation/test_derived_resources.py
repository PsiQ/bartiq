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

from pathlib import Path

import pytest
import yaml
from qref import SchemaV1

from bartiq import compile_routine
from bartiq.compilation.derived_resources import calculate_highwater


def load_highwater_test_data():
    test_file = Path(__file__).parent / "data/highwater.yaml"
    data = []
    with open(test_file) as f:
        for original, expected in yaml.safe_load(f):
            data.append((SchemaV1(**original), SchemaV1(**expected)))
    return data


HIGHWATER_TEST_DATA = load_highwater_test_data()


@pytest.mark.parametrize("routine, expected_routine", HIGHWATER_TEST_DATA)
def test_compute_highwater(routine, expected_routine, backend):
    derived_resources = [{"name": "qubit_highwater", "type": "qubits", "calculate": calculate_highwater}]
    compiled_routine = compile_routine(routine, derived_resources=derived_resources, backend=backend)
    assert compiled_routine.to_qref() == expected_routine


def test_compute_highwater_with_custom_names(backend):
    input_routine = SchemaV1(
        **{
            "version": "v1",
            "program": {
                "name": "root",
                "type": None,
                "ports": [
                    {"name": "in_0", "direction": "input", "size": "N"},
                    {"name": "out_0", "direction": "output", "size": "N"},
                ],
                "resources": [
                    {"name": "local_ancillae", "type": "qubits", "value": 7},
                    {"name": "custom_ancillae", "type": "qubits", "value": 5},
                    {"name": "qubit_highwater", "type": "qubits", "value": "N+7"},
                ],
            },
        }
    )

    def custom_compute_highwater(routine, backend, resource_name):
        return calculate_highwater(routine, backend, resource_name=resource_name, ancillae_name="custom_ancillae")

    derived_resources = [{"name": "custom_highwater", "type": "qubits", "calculate": custom_compute_highwater}]
    compiled_routine = compile_routine(input_routine, derived_resources=derived_resources, backend=backend).routine

    assert str(compiled_routine.resources["custom_highwater"].value) == "N + 5"


def test_computing_highwater_for_non_chronologically_sorted_routine_raises_warning():
    input_routine = {
        "version": "v1",
        "program": {
            "name": "root",
            "type": None,
            "ports": [
                {"name": "in_0", "direction": "input", "size": "N"},
                {"name": "out_0", "direction": "output", "size": "N"},
            ],
            "children": [
                {
                    "name": "a",
                    "type": "a",
                    "ports": [
                        {"name": "in_0", "direction": "input", "size": "K"},
                        {"name": "out_0", "direction": "output", "size": "K"},
                    ],
                },
                {
                    "name": "b",
                    "type": "b",
                    "ports": [
                        {"name": "in_0", "direction": "input", "size": "K"},
                        {"name": "out_0", "direction": "output", "size": "K"},
                    ],
                },
            ],
            "connections": ["in_0 -> b.in_0", "b.out_0 -> a.in_0", "a.out_0 -> out_0"],
        },
    }
    derived_resources = [{"name": "qubit_highwater", "type": "qubits", "calculate": calculate_highwater}]
    with pytest.warns(
        match=(
            "Order of children in provided routine does not match the topology. Bartiq will use one of topological "
            "orderings as an estimate of chronology, but the computed highwater value might be incorrect."
        )
    ):
        _ = compile_routine(input_routine, derived_resources=derived_resources)


def test_highwater_of_an_empty_routine_is_zero():
    input_routine = {"version": "v1", "program": {"name": "root"}}
    derived_resources = [{"name": "qubit_highwater", "type": "qubits", "calculate": calculate_highwater}]
    compiled_routine = compile_routine(input_routine, derived_resources=derived_resources).routine

    assert compiled_routine.resources["qubit_highwater"].value == 0


def test_additive_derived_resources_are_processed_correctly():
    input_routine = {
        "version": "v1",
        "program": {
            "name": "root",
            "type": None,
            "children": [
                {
                    "name": "a",
                    "type": "a",
                },
                {
                    "name": "b",
                    "type": "b",
                },
                {
                    "name": "c",
                    "type": "c",
                    "resources": [
                        {"name": "test_resource", "type": "additive", "value": 7},
                    ],
                },
            ],
        },
    }

    def add_test_resource(routine, backend):
        if "test_resource" in routine.resources or len(routine.children) != 0:
            return None
        else:
            return 5

    derived_resources = [{"name": "test_resource", "type": "additive", "calculate": add_test_resource}]
    compiled_routine = compile_routine(input_routine, derived_resources=derived_resources).routine

    assert compiled_routine.resources["test_resource"].value == 17
