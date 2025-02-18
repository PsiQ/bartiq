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

from dataclasses import replace
from pathlib import Path

import pytest
import yaml
from qref.schema_v1 import RoutineV1, SchemaV1

from bartiq import compile_routine
from bartiq._routine import Routine
from bartiq.compilation.postprocessing import add_qubit_highwater, aggregate_resources


def load_highwater_test_data():
    test_file = Path(__file__).parent / "data/highwater.yaml"
    data = []
    with open(test_file) as f:
        for original, expected in yaml.safe_load(f):
            data.append((SchemaV1(**original), SchemaV1(**expected)))
    return data


HIGHWATER_TEST_DATA = load_highwater_test_data()


def _get_simple_routine(backend):
    qref_routine = RoutineV1(
        name="root",
        type=None,
        children=[
            {
                "name": "child_1",
                "type": None,
                "resources": [
                    {"name": "a", "type": "additive", "value": 1},
                    {"name": "b", "type": "additive", "value": 5},
                ],
            },
            {
                "name": "child_2",
                "type": None,
                "resources": [
                    {"name": "a", "type": "additive", "value": 2},
                    {"name": "b", "type": "additive", "value": 3},
                    {"name": "c", "type": "additive", "value": 1},
                ],
            },
        ],
    )
    return Routine.from_qref(qref_routine, backend)


def test_two_postprocessing_stages(backend):
    routine = _get_simple_routine(backend)

    def stage_1(routine, backend):
        return replace(routine, name=routine.name.upper())

    def stage_2(routine, backend):
        cool_children = routine.children
        for child_name, child in cool_children.items():
            cool_children[child_name] = replace(child, type="cool_kid")
        return replace(routine, children=cool_children)

    postprocessing_stages = [stage_1, stage_2]
    compiled_routine = compile_routine(routine, postprocessing_stages=postprocessing_stages, backend=backend).routine

    assert compiled_routine.name == "ROOT"
    for child in compiled_routine.children.values():
        assert child.type == "cool_kid"


def test_aggregate_resources(backend):
    routine = _get_simple_routine(backend)
    aggregation_dict = {"a": {"op": 1}, "b": {"op": 2}, "c": {"op": 3}}
    postprocessing_stages = [aggregate_resources(aggregation_dict, remove_decomposed=True)]
    compiled_routine = compile_routine(routine, postprocessing_stages=postprocessing_stages, backend=backend).routine
    assert len(compiled_routine.resources) == 1
    assert compiled_routine.resources["op"].value == 22


@pytest.mark.parametrize("routine, expected_routine", HIGHWATER_TEST_DATA)
def test_add_qubit_highwater(routine, expected_routine, backend):
    postprocessing_stages = [add_qubit_highwater]
    compiled_routine = compile_routine(routine, postprocessing_stages=postprocessing_stages, backend=backend)
    assert compiled_routine.to_qref() == expected_routine


def test_add_qubit_highwater_with_custom_names(backend):
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

    def custom_stage(routine, backend):
        return add_qubit_highwater(routine, backend, resource_name="custom_highwater", ancillae_name="custom_ancillae")

    postprocessing_stages = [custom_stage]
    compiled_routine = compile_routine(
        input_routine, postprocessing_stages=postprocessing_stages, backend=backend
    ).routine

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

    with pytest.warns(
        match=(
            "Order of children in provided routine does not match the topology. Bartiq will use one of topological "
            "orderings as an estimate of chronology, but the computed highwater value might be incorrect."
        )
    ):
        _ = compile_routine(input_routine, postprocessing_stages=[add_qubit_highwater])
