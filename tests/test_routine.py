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
