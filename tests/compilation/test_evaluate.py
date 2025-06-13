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
import re
from pathlib import Path

import pytest
import yaml
from qref import SchemaV1
from qref.schema_v1 import RoutineV1

from bartiq import CompiledRoutine, Routine, compile_routine, evaluate, sympy_backend
from bartiq.errors import BartiqCompilationError
from tests.utilities import (
    load_transitive_resource_data,
    routine_with_passthrough,
    routine_with_two_passthroughs,
)


def load_evaluate_test_data():
    test_files_path = Path(__file__).parent / "data/evaluate/"
    for path in sorted(test_files_path.rglob("*.yaml")):
        with open(path) as f:
            for data in yaml.safe_load(f):
                yield data


EVALUTE_TEST_CASES = load_evaluate_test_data()
TRANSITIVE_RESOURCE_DATA = load_transitive_resource_data()


@pytest.mark.filterwarnings("ignore:Found the following issues with the provided routine")
@pytest.mark.parametrize("input_dict, assignments, expected_dict", EVALUTE_TEST_CASES)
def test_evaluate(input_dict, assignments, expected_dict, backend):
    compiled_routine = CompiledRoutine.from_qref(SchemaV1(**input_dict), backend)
    result = evaluate(compiled_routine, assignments, backend=backend)
    assert result.to_qref() == SchemaV1(**expected_dict)


@pytest.mark.parametrize("_, transitively_compiled, fully_compiled", TRANSITIVE_RESOURCE_DATA)
def test_evaluate_on_transitive_resources_yields_fully_compiled_routine(
    _, transitively_compiled, fully_compiled, backend
):
    transitively_compiled = CompiledRoutine.from_qref(transitively_compiled, backend=backend)
    assert evaluate(transitively_compiled, {}, backend=backend).routine == CompiledRoutine.from_qref(
        fully_compiled, backend
    )


@pytest.mark.parametrize(
    "op, assignments, expected_sizes",
    [
        (routine_with_passthrough(), {"N": 10}, {"out_0": "10"}),
        (routine_with_passthrough(a_out_size="N+2"), {"N": 10}, {"out_0": "12"}),
        (routine_with_two_passthroughs(), {"N": 10, "M": 7}, {"out_0": "10", "out_1": "7"}),
    ],
)
def test_passthroughs(op, assignments, expected_sizes, backend):
    result = compile_routine(op, backend=backend)
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
                        "resources": [{"name": "X", "type": "other", "value": 10}],
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


def test_evaluation_raises_error_when_constraint_is_violated(backend):
    qref_routine = {
        "name": "root",
        "children": [
            {
                "name": "a",
                "ports": [
                    {"name": "in_0", "size": "N", "direction": "input"},
                    {"name": "in_1", "size": "N", "direction": "input"},
                ],
            },
        ],
        "ports": [
            {"name": "in_0", "size": "K", "direction": "input"},
            {"name": "in_1", "size": "M", "direction": "input"},
        ],
        "connections": ["in_0 -> a.in_0", "in_1 -> a.in_1"],
    }

    compiled_routine = compile_routine(RoutineV1(**qref_routine), backend=backend).routine

    expected_error = "The following constraint was violated when compiling root.a: M = K evaluated into 2 = 1."

    with pytest.raises(BartiqCompilationError, match=re.escape(expected_error)):
        _ = evaluate(compiled_routine, {"K": 1, "M": 2}, backend=backend)


@pytest.mark.order(-1)
@pytest.mark.filterwarnings("ignore:Found the following issues")
def test_compile_and_evaluate_double_factorization_routine(backend):
    with open(Path(__file__).parent / "data/df_qref.yaml") as f:
        routine = Routine.from_qref(qref_obj=yaml.safe_load(f), backend=sympy_backend)

    result = compile_routine(routine)

    def return_one(*args):
        return 1

    assignments = {"N_spatial": 10, "R": 54, "M_r": 480, "b_as": 10, "b_givens": 20, "b_mas": 10}
    evaluated_routine = evaluate(
        result.routine,
        assignments=assignments,
        functions_map={"calc_lambda": return_one, "select_elbow_const": return_one},
    ).routine
    expected_resources = {
        "active_volume": 18135184.5,
        "gidney_lelbows": 210527,
        "gidney_relbows": 210527,
        "measurements": 460,
        "ppms": 0,
        "pprs": 72,
        "rotations": 21,
        "t_gates": 145,
        "toffs": 819,
    }

    for resource_name in expected_resources:
        assert expected_resources[resource_name] == evaluated_routine.resources[resource_name].value
