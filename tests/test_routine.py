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

from bartiq._routine import BaseRoutine, Resource, ResourceType


def test_resource_values():
    # Arrange: create two dummy resources with integer values.
    resources = {
        "res1": Resource(name="res1", type=ResourceType.other, value=5),
        "res2": Resource(name="res2", type=ResourceType.additive, value=10),
    }
    routine = BaseRoutine(
        name="test_routine",
        type=None,
        children={},
        ports={},
        resources=resources,
        connections={},
        children_order=(),
    )

    # Act: retrieve the resource_values.
    values = routine.resource_values

    # Assert: it matches the original resource values.
    assert values == {"res1": 5, "res2": 10}


def test_find_descendants_modes_and_options():
    from bartiq import Routine

    def dummy(name):
        return Routine(
            name=name,
            type=None,
            children={},
            ports={},
            resources={},
            connections={},
            input_params=(),
            linked_params={},
            local_variables={},
            children_order=(),
        )

    root = Routine(
        name="root",
        type=None,
        children={
            "A": Routine(
                name="A",
                type=None,
                children={"X": dummy("X"), "Y": dummy("Y")},
                ports={},
                resources={},
                connections={},
                input_params=(),
                linked_params={},
                local_variables={},
                children_order=("X", "Y"),
            ),
            "B": Routine(
                name="B",
                type=None,
                children={"X": dummy("X"), "Y": dummy("Y"), "Z": dummy("Z")},
                ports={},
                resources={},
                connections={},
                input_params=(),
                linked_params={},
                local_variables={},
                children_order=("X", "Y", "Z"),
            ),
        },
        ports={},
        resources={},
        connections={},
        input_params=(),
        linked_params={},
        local_variables={},
        children_order=("A", "B"),
    )

    # BFS: should find both ["A", "X"] and ["B", "X"], order not guaranteed
    paths_x_bfs = root.find_descendants("X", mode="bfs")
    assert ["A", "X"] in paths_x_bfs
    assert ["B", "X"] in paths_x_bfs

    # max_depth: Z is at depth 2, so should not be found at depth 1
    paths_z_depth1 = root.find_descendants("Z", max_depth=1)
    assert paths_z_depth1 == []

    # DFS: should find all paths to "X"
    results = root.find_descendants("X")
    assert ["A", "X"] in results
    assert ["B", "X"] in results

    # No match
    assert root.find_descendants("Q") == []

    # Single node/leaf: should not find itself as a descendant
    leaf = dummy("Leaf")
    assert leaf.find_descendants("Leaf") == []
