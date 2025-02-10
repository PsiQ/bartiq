import pytest
from qref.schema_v1 import RoutineV1

from bartiq._routine import Routine, routine_to_qref
from bartiq.compilation.preprocessing import PreprocessingStage, propagate_child_resources, propagate_linked_params


def _apply_stage(qref_obj: RoutineV1, stage: PreprocessingStage, backend) -> RoutineV1:
    routine = Routine.from_qref(qref_obj, backend)
    preprocessed_routine = stage(routine, backend)
    return routine_to_qref(preprocessed_routine, backend).program


def test_propagating_child_resources(backend):
    routine = RoutineV1(
        name="root",
        type=None,
        children=[
            {
                "name": "a",
                "type": None,
                "resources": [
                    {"name": "N_toffs", "type": "additive", "value": 1},
                    {"name": "N_meas", "type": "additive", "value": 5},
                    {"name": "success_prob", "type": "multiplicative", "value": 0.9},
                ],
            },
            {
                "name": "b",
                "type": None,
                "resources": [
                    {"name": "N_toffs", "type": "additive", "value": 2},
                    {"name": "N_rots", "type": "additive", "value": 3},
                    {"name": "N_x", "type": "other", "value": 1},
                    {"name": "success_prob", "type": "multiplicative", "value": 0.9},
                ],
            },
        ],
        resources=[{"name": "N_meas", "type": "additive", "value": "a.N_meas"}],
    )

    routine_with_resources = _apply_stage(routine, propagate_child_resources, backend)

    expected_resources = [
        {"name": "N_meas", "type": "additive", "value": "a.N_meas"},
        {"name": "N_rots", "type": "additive", "value": "b.N_rots"},
        {"name": "N_toffs", "type": "additive", "value": "a.N_toffs + b.N_toffs"},
        {"name": "success_prob", "type": "multiplicative", "value": "a.success_prob*b.success_prob"},
    ]

    expected_routine = RoutineV1.model_validate({**routine.model_dump(), "resources": expected_resources})

    assert routine_with_resources == expected_routine


LINKED_PARAM_CASES = [
    (
        {
            "name": "root",
            "type": None,
            "children": [
                {
                    "name": "a",
                    "type": None,
                    "children": [
                        {
                            "name": "b",
                            "type": None,
                            "resources": [{"name": "z", "type": "other", "value": "x+y"}],
                            "input_params": ["x", "y"],
                        },
                    ],
                    "resources": [{"name": "v", "type": "other", "value": "w+b.z"}],
                    "input_params": ["w"],
                },
            ],
            "resources": [{"name": "u", "type": "other", "value": "a.v+5"}],
            "input_params": ["w_a", "x_ab", "y_ab"],
            "linked_params": [
                {"source": "w_a", "targets": ["a.w"]},
                {"source": "x_ab", "targets": ["a.b.x"]},
                {"source": "y_ab", "targets": ["a.b.y"]},
            ],
        },
        {
            "root": {
                "w_a": (("a", "w"),),
                "x_ab": (("a", "b.x"),),
                "y_ab": (("a", "b.y"),),
            },
            "root.a": {
                "b.x": (("b", "x"),),
                "b.y": (("b", "y"),),
            },
        },
    ),
    (
        {
            "name": "root",
            "type": None,
            "children": [
                {
                    "name": "a",
                    "type": None,
                    "children": [
                        {
                            "name": "b",
                            "type": None,
                            "children": [
                                {
                                    "name": "c",
                                    "type": None,
                                    "resources": [{"name": "z", "type": "other", "value": "x+y"}],
                                    "input_params": ["x", "y"],
                                }
                            ],
                            "resources": [{"name": "z", "type": "other", "value": "c.z+y"}],
                            "input_params": ["y"],
                        },
                        {
                            "name": "d",
                            "type": None,
                            "resources": [{"name": "z", "type": "other", "value": "x+y"}],
                            "input_params": ["x", "y"],
                        },
                    ],
                    "resources": [{"name": "z", "type": "other", "value": "b.z + d.z"}],
                },
            ],
            "resources": [{"name": "z", "type": "other", "value": "a.z+5"}],
            "input_params": ["x_abc", "y_abc", "y_ab", "x_ad", "y_ad"],
            "linked_params": [
                {"source": "x_abc", "targets": ["a.b.c.x"]},
                {"source": "y_abc", "targets": ["a.b.c.y"]},
                {"source": "y_ab", "targets": ["a.b.y"]},
                {"source": "x_ad", "targets": ["a.d.x"]},
                {"source": "y_ad", "targets": ["a.d.y"]},
            ],
        },
        {
            "root": {
                "x_abc": (("a", "b.c.x"),),
                "x_ad": (("a", "d.x"),),
                "y_ab": (("a", "b.y"),),
                "y_abc": (("a", "b.c.y"),),
                "y_ad": (("a", "d.y"),),
            },
            "root.a": {
                "b.c.x": (("b", "c.x"),),
                "d.x": (("d", "x"),),
                "b.y": (("b", "y"),),
                "b.c.y": (("b", "c.y"),),
                "d.y": (("d", "y"),),
            },
            "root.a.b": {"c.x": (("c", "x"),), "c.y": (("c", "y"),)},
        },
    ),
]


@pytest.mark.parametrize("input_dict, expected_linked_params", LINKED_PARAM_CASES)
def test_precompile_propagates_linked_params(input_dict, expected_linked_params, backend):
    input_routine = Routine.from_qref(RoutineV1(**input_dict), backend)

    preprocessed_routine = propagate_linked_params(input_routine, backend)

    for path, linked_params in expected_linked_params.items():
        routine = preprocessed_routine
        for part in path.split(".")[1:]:
            routine = routine.children[part]

        assert routine.linked_params == linked_params
