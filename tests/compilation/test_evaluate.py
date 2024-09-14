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

import sys
from pathlib import Path

import pytest
import yaml
from qref import SchemaV1
from qref.schema_v1 import RoutineV1

from bartiq import CompiledRoutine, compile_routine, evaluate

from ..utilities import routine_with_passthrough, routine_with_two_passthroughs


def load_evaluate_test_data():
    with open(Path(__file__).parent / "data/evaluate_test_data.yaml") as f:
        return yaml.safe_load(f)


EVALUTE_TEST_CASES = load_evaluate_test_data()


@pytest.mark.filterwarnings("ignore:Found the following issues with the provided routine")
@pytest.mark.parametrize("input_dict, assignments, expected_dict", EVALUTE_TEST_CASES)
def test_evaluate(input_dict, assignments, expected_dict, backend):
    compiled_routine = CompiledRoutine.from_qref(SchemaV1(**input_dict), backend)
    result = evaluate(compiled_routine, assignments, backend=backend)
    assert result.to_qref() == SchemaV1(**expected_dict)


@pytest.mark.parametrize(
    "op, assignments, expected_sizes",
    [
        (routine_with_passthrough(), {"N": 10}, {"out_0": "10"}),
        (routine_with_passthrough(a_out_size="N+2"), {"N": 10}, {"out_0": "12"}),
        (routine_with_two_passthroughs(), {"N": 10, "M": 7}, {"out_0": "10", "out_1": "7"}),
    ],
)
def test_passthroughs(op, assignments, expected_sizes, backend):
    result = compile_routine(op)
    evaluated_routine = evaluate(result.routine, assignments=assignments, backend=backend).routine
    for port_name, size in expected_sizes.items():
        assert str(evaluated_routine.ports[port_name].size) == str(size)


def custom_function(a, b):
    if a > 0:
        return a + b
    else:
        return a - b


@pytest.mark.parametrize(
    "input_dict, assignments, functions_map, expected_dict",
    [
        (
            {
                "name": "root",
                "type": "foo",
                "children": [
                    {
                        "name": "a",
                        "type": "a",
                        "resources": [
                            {
                                "name": "X",
                                "type": "other",
                                "value": "2*N + a.unknown_fun(1)",
                            }
                        ],
                        "input_params": ["N"],
                    },
                    {
                        "name": "b",
                        "type": "b",
                        "resources": [
                            {
                                "name": "X",
                                "type": "other",
                                "value": "b.my_f(N, 2) + 3",
                            }
                        ],
                        "input_params": ["N"],
                    },
                ],
                "resources": [{"name": "X", "type": "other", "value": "2*N + b.my_f(N, 2) + 3 + a.unknown_fun(1)"}],
                "input_params": ["N"],
            },
            {"N": 5},
            {"b.my_f": custom_function},
            {
                "name": "root",
                "type": "foo",
                "children": [
                    {
                        "name": "a",
                        "type": "a",
                        "resources": [{"name": "X", "type": "other", "value": "a.unknown_fun(1) + 10"}],
                    },
                    {
                        "name": "b",
                        "type": "b",
                        "resources": [{"name": "X", "type": "other", "value": "10"}],
                    },
                ],
                "resources": [{"name": "X", "type": "other", "value": "a.unknown_fun(1) + 20"}],
            },
        ),
    ],
)
def test_evaluate_with_functions_map(input_dict, assignments, functions_map, expected_dict, backend):
    result = evaluate(
        CompiledRoutine.from_qref(RoutineV1(**input_dict), backend),
        assignments,
        backend=backend,
        functions_map=functions_map,
    )
    assert result.to_qref().program == RoutineV1(**expected_dict)


@pytest.mark.filterwarnings("ignore:Found the following issues")
def test_compile_and_evaluate_double_factorization_routine(backend):
    # Compilation fails on Python 3.9 for the default recursion limit, so we increased it to make this test pass.
    sys.setrecursionlimit(2000)
    with open(Path(__file__).parent / "data/df_qref.yaml") as f:
        routine = SchemaV1(**yaml.safe_load(f))

    result = compile_routine(routine)
    assignments = {"N_spatial": 10, "R": 54, "M": 480, "b": 10, "lamda": 2, "N_givens": 20, "Ksi_l": 10}
    evaluated_routine = evaluate(result.routine, assignments=assignments).routine
    expected_resources = {
        "toffs": 260,
        "t_gates": 216,
        "rotations": 4,
        "measurements": 0,
        "gidney_relbows": 56403,
        "gidney_lelbows": 56403,
    }

    for resource_name in expected_resources:
        assert expected_resources[resource_name] == int(evaluated_routine.resources[resource_name].value)
