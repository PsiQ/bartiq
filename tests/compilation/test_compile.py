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

from bartiq import compile_routine
from bartiq.compilation.preprocessing import introduce_port_variables
from bartiq.errors import BartiqCompilationError


def load_compile_test_data():
    with open(Path(__file__).parent / "data/compile_test_data.yaml") as f:
        return [(SchemaV1(**original), SchemaV1(**expected)) for original, expected in yaml.safe_load(f)]


COMPILE_TEST_DATA = load_compile_test_data()


@pytest.mark.filterwarnings("ignore:Found the following issues with the provided routine")
@pytest.mark.parametrize("routine, expected_routine", COMPILE_TEST_DATA)
def test_compile(routine, expected_routine, backend):
    compiled_routine = compile_routine(routine, skip_verification=False, backend=backend).to_qref()
    assert compiled_routine == expected_routine


def f_1_simple(x):
    return x + 1


def f_2_conditional(x):
    if x > 1:
        return -x
    return x


def f_3_optional_inputs(a, b=2, c=3):
    return a + b * c


def test_compiling_correctly_propagates_global_functions():
    routine = RoutineV1(
        name="root",
        type="dummy",
        resources=[{"name": "X", "value": "a.X + b.X + c.X", "type": "other"}],
        children=[
            RoutineV1(
                name="a",
                type="other",
                resources=[{"name": "X", "value": "O(1) + 5", "type": "other"}],
            ),
            RoutineV1(
                name="b",
                type="other",
                resources=[{"name": "X", "value": "O(1)", "type": "other"}],
            ),
            RoutineV1(
                name="c",
                type="other",
                resources=[{"name": "X", "value": "g(7) + f(1, 2, 3)", "type": "other"}],
            ),
        ],
    )

    result = compile_routine(routine)

    # resources[0] is the only resource X
    assert result.to_qref().program.resources[0].value == "2*O(1) + f(1, 2, 3) + g(7) + 5"


COMPILE_ERRORS_TEST_CASES = [
    # Attempt to assign inconsistent constant register sizes
    (
        RoutineV1(
            name="root",
            type="dummy",
            children=[{"name": "a", "type": "dummy", "ports": [{"name": "in_bar", "direction": "input", "size": 2}]}],
            ports=[{"name": "in_foo", "direction": "input", "size": 1}],
            connections=[{"source": "in_foo", "target": "a.in_bar"}],
        ),
        "The following constraint was violated when compiling root.a: #in_bar = 2 evaluated into 1 = 2.",
    ),
    # Attempt to connect two different sizes to routine which has both inputs of the same size
    (
        RoutineV1(
            name="root",
            type="dummy",
            children=[
                {
                    "name": "a",
                    "type": "dummy",
                    "ports": [{"name": "out_0", "direction": "output", "size": 1}],
                },
                {
                    "name": "b",
                    "type": "dummy",
                    "ports": [{"name": "out_0", "direction": "output", "size": 2}],
                },
                {
                    "name": "c",
                    "type": "dummy",
                    "ports": [
                        {"name": "out_0", "direction": "output", "size": "2*N"},
                        {"name": "in_0", "direction": "input", "size": "N"},
                        {"name": "in_1", "direction": "input", "size": "N"},
                    ],
                },
            ],
            connections=[
                {"source": "a.out_0", "target": "c.in_0"},
                {"source": "b.out_0", "target": "c.in_1"},
            ],
        ),
        "The following constraint was violated when compiling root.c: #in_1 = #in_0 evaluated into 2 = 1",
    ),
]


@pytest.mark.parametrize("routine, expected_error", COMPILE_ERRORS_TEST_CASES)
def test_compile_errors(routine, expected_error, backend):
    with pytest.raises(BartiqCompilationError, match=re.escape(expected_error)):
        compile_routine(
            routine, precompilation_stages=[introduce_port_variables], backend=backend, skip_verification=True
        )
