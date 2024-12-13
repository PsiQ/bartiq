from dataclasses import replace

from qref.schema_v1 import RoutineV1

from bartiq import compile_routine
from bartiq._routine import Routine
from bartiq.compilation.postprocessing import aggregate_resources


def _get_routine(backend):
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


def test_aggregate_resources_as_postprocessing(backend):
    routine = _get_routine(backend)
    aggregation_dict = {"a": {"op": 1}, "b": {"op": 2}, "c": {"op": 3}}
    postprocessing_stages = [aggregate_resources(aggregation_dict, remove_decomposed=True)]
    compiled_routine = compile_routine(routine, postprocessing_stages=postprocessing_stages, backend=backend).routine
    assert len(compiled_routine.resources) == 1
    assert compiled_routine.resources["op"].value == 22


def test_two_postprocessing_stages(backend):
    routine = _get_routine(backend)

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