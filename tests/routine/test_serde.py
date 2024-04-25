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

from bartiq._routine import (
    Connection,
    Port,
    PortDirection,
    Resource,
    ResourceType,
    Routine,
)

# flake8: noqa


@pytest.fixture
def expected_dict():
    return {
        "name": "root",
        "type": "root",
        "children": {
            "child_1": {
                "name": "child_1",
                "type": "child_1",
                "ports": {
                    "out_0": {
                        "name": "out_0",
                        "size": {"value": "N", "type": "str"},
                        "direction": "output",
                    }
                },
                "resources": {
                    "N_toffs": {
                        "name": "N_toffs",
                        "type": "additive",
                        "value": {"type": "str", "value": "N - 1"},
                    },
                },
            },
            "child_2": {
                "name": "child_2",
                "type": "child_2",
                "ports": {
                    "in_0": {
                        "name": "in_0",
                        "size": {"value": "N", "type": "str"},
                        "direction": "input",
                    },
                },
                "resources": {
                    "N_toffs": {
                        "name": "N_toffs",
                        "type": "additive",
                        "value": {"type": "str", "value": "N + 1"},
                    },
                },
            },
        },
        "connections": [{"source": "child_1.out_0", "target": "child_2.in_0"}],
    }


@pytest.fixture
def example_routine():
    child_1_port = Port(name="out_0", size="N", direction=PortDirection.output)
    child_2_port = Port(name="in_0", size="N", direction=PortDirection.input)
    connection = Connection(source=child_1_port, target=child_2_port)
    child_1_resource = Resource(name="N_toffs", type=ResourceType.additive, value="N - 1")
    child_2_resource = Resource(name="N_toffs", type=ResourceType.additive, value="N + 1")

    child_1_routine = Routine(
        name="child_1",
        type="child_1",
        ports={"out_0": child_1_port},
        resources={"N_toffs": child_1_resource},
    )
    child_2_routine = Routine(
        name="child_2",
        type="child_2",
        ports={"in_0": child_2_port},
        resources={"N_toffs": child_2_resource},
    )

    my_routine = Routine(
        name="root",
        type="root",
        children={"child_1": child_1_routine, "child_2": child_2_routine},
        connections=[connection],
    )
    return my_routine


def test_routine_serializes_to_expected_dict(expected_dict, example_routine):
    serialized_routine = example_routine.model_dump(exclude_unset=True)
    assert serialized_routine == expected_dict


def test_routine_deserializes_to_expected_object(expected_dict):
    recreated_routine = Routine(**expected_dict)
    assert expected_dict == recreated_routine.model_dump(exclude_unset=True)
