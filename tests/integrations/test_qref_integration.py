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
from pytest import fixture

from bartiq import Routine
from bartiq.integrations import bartiq_to_qref, qref_to_bartiq

# Note: fixture example_routine has to be synced with
# the example_schema_v1 fixture further in this module.


@fixture
def example_routine():
    return Routine(
        name="root",
        type=None,
        input_params=["N"],
        ports={
            "in_0": {"name": "in_0", "size": "N", "direction": "input"},
            "out_0": {"name": "out_0", "size": "N", "direction": "output"},
            "out_1": {"name": "out_1", "size": 3, "direction": "output"},
        },
        resources={
            "n_qubits": {
                "name": "n_qubits",
                "type": "additive",
                "value": {"value": 30, "type": "int"},
            }
        },
        children={
            "foo": {
                "name": "foo",
                "type": None,
                "input_params": ["M"],
                "local_variables": [
                    "R=ceiling(log_2(M))",
                ],
                "resources": {"T_gates": {"name": "T_gates", "type": "additive", "value": "R ** 2"}},
                "ports": {
                    "in_0": {"name": "in_0", "size": "M", "direction": "input"},
                    "out_0": {"name": "out_0", "size": 3, "direction": "output"},
                },
            },
            "bar": {
                "name": "bar",
                "type": None,
                "input_params": ["N"],
                "ports": {
                    "in_0": {"name": "in_0", "size": "N", "direction": "input"},
                    "out_0": {"name": "out_0", "size": "N", "direction": "output"},
                },
            },
        },
        linked_params={"N": [("foo", "M"), ("bar", "N")]},
        connections=[
            {"source": "in_0", "target": "foo.in_0"},
            {"source": "foo.out_0", "target": "out_0"},
            {"source": "bar.out_0", "target": "out_1"},
        ],
    )


@fixture
def example_serialized_qref_v1_object():
    return {
        "version": "v1",
        "program": {
            "name": "root",
            "children": [
                {
                    "name": "bar",
                    "type": None,
                    "ports": [
                        {"name": "in_0", "direction": "input", "size": "N"},
                        {"name": "out_0", "direction": "output", "size": "N"},
                    ],
                    "input_params": ["N"],
                },
                {
                    "name": "foo",
                    "type": None,
                    "ports": [
                        {"name": "in_0", "direction": "input", "size": "M"},
                        {"name": "out_0", "direction": "output", "size": 3},
                    ],
                    "input_params": ["M"],
                    "local_variables": [
                        "R=ceiling(log_2(M))",
                    ],
                    "resources": [{"name": "T_gates", "type": "additive", "value": "R ** 2"}],
                },
            ],
            "type": None,
            "ports": [
                {"name": "in_0", "direction": "input", "size": "N"},
                {"name": "out_0", "direction": "output", "size": "N"},
                {"name": "out_1", "direction": "output", "size": 3},
            ],
            "resources": [{"name": "n_qubits", "type": "additive", "value": 30}],
            "connections": [
                {"source": "bar.out_0", "target": "out_1"},
                {"source": "foo.out_0", "target": "out_0"},
                {"source": "in_0", "target": "foo.in_0"},
            ],
            "input_params": ["N"],
            "linked_params": [{"source": "N", "targets": ["foo.M", "bar.N"]}],
        },
    }


def test_converting_routine_to_qref_v1_gives_correct_output(example_routine, example_serialized_qref_v1_object):
    assert bartiq_to_qref(example_routine).model_dump(exclude_unset=True) == example_serialized_qref_v1_object


def test_converting_qref_v1_object_to_routine_give_correct_output(example_routine, example_serialized_qref_v1_object):
    assert qref_to_bartiq(example_serialized_qref_v1_object) == example_routine


def test_conversion_from_bartiq_to_qref_raises_an_error_if_version_is_unsupported(example_routine):
    with pytest.raises(ValueError):
        bartiq_to_qref(example_routine, version="v3")
