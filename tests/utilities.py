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

from pathlib import Path

import yaml
from qref.schema_v1 import RoutineV1, SchemaV1


def routine_with_passthrough(a_out_size="N"):
    """Routine with a passthrough, used for testing."""
    return RoutineV1(
        name="root",
        input_params=["N"],
        ports=[
            {"name": "in_0", "direction": "input", "size": "N"},
            {"name": "out_0", "direction": "output", "size": None},
        ],
        children=[
            RoutineV1(
                name="a",
                type=None,
                ports=[
                    {"name": "in_0", "direction": "input", "size": "N"},
                    {"name": "out_0", "direction": "output", "size": f"{a_out_size}"},
                ],
            ),
            RoutineV1(
                name="b",
                type=None,
                ports=[
                    {"name": "in_0", "direction": "input", "size": None},
                    {"name": "out_0", "direction": "output", "size": None},
                ],
                connections=[{"source": "in_0", "target": "out_0"}],
            ),
            RoutineV1(
                name="c",
                type=None,
                ports=[
                    {"name": "in_0", "direction": "input", "size": None},
                    {"name": "out_0", "direction": "output", "size": None},
                ],
                connections=[{"source": "in_0", "target": "out_0"}],
            ),
        ],
        connections=[
            {"source": "in_0", "target": "a.in_0"},
            {"source": "a.out_0", "target": "b.in_0"},
            {"source": "b.out_0", "target": "c.in_0"},
            {"source": "c.out_0", "target": "out_0"},
        ],
        type=None,
    )


def routine_with_two_passthroughs():
    """Routine with a two passthroughs, used for testing."""
    return RoutineV1(
        name="root",
        type=None,
        input_params=["N"],
        ports=[
            {"name": "in_0", "direction": "input", "size": "N"},
            {"name": "in_1", "direction": "input", "size": "M"},
            {"name": "out_0", "direction": "output", "size": None},
            {"name": "out_1", "direction": "output", "size": None},
        ],
        children=[
            RoutineV1(
                name="a",
                type=None,
                ports=[
                    {"name": "in_0", "direction": "input", "size": "N"},
                    {"name": "out_0", "direction": "output", "size": "N"},
                ],
            ),
            RoutineV1(
                name="b",
                type=None,
                ports=[
                    {"name": "in_0", "direction": "input", "size": "N"},
                    {"name": "out_0", "direction": "output", "size": "N"},
                ],
            ),
            RoutineV1(
                name="c",
                type=None,
                ports=[
                    {"name": "in_0", "direction": "input", "size": None},
                    {"name": "in_1", "direction": "input", "size": None},
                    {"name": "out_0", "direction": "output", "size": None},
                    {"name": "out_1", "direction": "output", "size": None},
                ],
                connections=[
                    {"source": "in_0", "target": "out_0"},
                    {"source": "in_1", "target": "out_1"},
                ],
            ),
        ],
        connections=[
            {"source": "in_0", "target": "a.in_0"},
            {"source": "in_1", "target": "b.in_0"},
            {"source": "a.out_0", "target": "c.in_0"},
            {"source": "b.out_0", "target": "c.in_1"},
            {"source": "c.out_0", "target": "out_0"},
            {"source": "c.out_1", "target": "out_1"},
        ],
    )


FILE = Path(__file__)
TEST_DATA_FILEPATH = Path("/".join(FILE.parts[: FILE.parts.index("tests") + 1])) / "compilation/data/compile/"


def load_compile_test_data():
    for path in [x for x in sorted(TEST_DATA_FILEPATH.rglob("*.yaml")) if "transitive" not in x.stem]:
        with open(path) as f:
            for original, expected in yaml.safe_load(f):
                yield (SchemaV1(**original), SchemaV1(**expected))


def load_transitive_resource_data():
    with open(TEST_DATA_FILEPATH / "transitive_resources.yaml") as f:
        for original, compiled_transitive, full_compiled_routine in yaml.safe_load(f):
            yield (SchemaV1(**original), SchemaV1(**compiled_transitive), SchemaV1(**full_compiled_routine))
