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
    test_files_path = Path(__file__).parent / "data/highwater/"
    for path in sorted(test_files_path.rglob("*.yaml")):
        with open(path) as f:
            for original, expected in yaml.safe_load(f):
                yield (SchemaV1(**original), SchemaV1(**expected))


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


# TODO: Should we just test post functions separately, or in compilation?
@pytest.mark.parametrize("routine, expected_routine", HIGHWATER_TEST_DATA)
def test_add_qubit_highwater(routine, expected_routine, backend):
    postprocessing_stages = [add_qubit_highwater]
    compiled_routine = compile_routine(routine, postprocessing_stages=postprocessing_stages, backend=backend)
    # from qref.experimental.rendering import to_graphviz
    # gv_obj = to_graphviz(compiled_routine.to_qref())
    # gv_obj.render(f"stuff", format="png")

    assert compiled_routine.to_qref() == expected_routine

