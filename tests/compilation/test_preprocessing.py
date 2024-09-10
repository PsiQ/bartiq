from qref.schema_v1 import RoutineV1

from bartiq._routine_new import CompilationUnit, routine_to_qref
from bartiq.compilation.preprocessing import (
    PreprocessingStage,
    add_default_additive_resources,
)


def _apply_stage(qref_obj: RoutineV1, stage: PreprocessingStage, backend) -> RoutineV1:
    routine = CompilationUnit.from_qref(qref_obj, backend)
    preprocessed_routine = stage(routine, backend)
    return routine_to_qref(preprocessed_routine, backend).program


def test_adding_additive_resources(backend):
    routine = RoutineV1(
        name="root",
        type=None,
        children=[
            {
                "name": "a",
                "type": None,
                "resources": [
                    {"name": "N_toffs", "type": "additive", "value": "1"},
                    {"name": "N_meas", "type": "additive", "value": "5"},
                ],
            },
            {
                "name": "b",
                "type": None,
                "resources": [
                    {"name": "N_toffs", "type": "additive", "value": "2"},
                    {"name": "N_rots", "type": "additive", "value": "3"},
                    {"name": "N_x", "type": "other", "value": "1"},
                ],
            },
        ],
        resources=[{"name": "N_meas", "type": "additive", "value": "a.N_meas"}],
    )

    routine_with_resources = _apply_stage(routine, add_default_additive_resources, backend)

    expected_resources = [
        {"name": "N_meas", "type": "additive", "value": "a.N_meas"},
        {"name": "N_rots", "type": "additive", "value": "b.N_rots"},
        {"name": "N_toffs", "type": "additive", "value": "a.N_toffs + b.N_toffs"},
    ]

    expected_routine = RoutineV1.model_validate({**routine.model_dump(), "resources": expected_resources})

    assert routine_with_resources == expected_routine
