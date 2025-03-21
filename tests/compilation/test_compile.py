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
from bartiq.errors import BartiqCompilationError, BartiqPreprocessingError
from bartiq.compilation.derived_resources import calculate_highwater


def load_compile_test_data():
    test_files_path = Path(__file__).parent / "data/compile/"
    for path in sorted(test_files_path.rglob("*.yaml")):
        with open(path) as f:
            for original, expected in yaml.safe_load(f):
                yield (SchemaV1(**original), SchemaV1(**expected))


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
            routine, preprocessing_stages=[introduce_port_variables], backend=backend, skip_verification=True
        )


@pytest.mark.parametrize(
    "routine, expected_lhs, expected_rhs",
    [
        (
            {
                "name": "root",
                "type": "dummy",
                "children": [
                    {
                        "name": "a",
                        "type": "dummy",
                        "ports": [
                            {"name": "in_0", "direction": "input", "size": "N"},
                            {"name": "in_1", "direction": "input", "size": "2 ** N"},
                        ],
                    }
                ],
                "ports": [
                    {"name": "in_0", "size": "K", "direction": "input"},
                    {"name": "in_1", "size": "K", "direction": "input"},
                ],
                "connections": ["in_0 -> a.in_0", "in_1 -> a.in_1"],
            },
            "K",
            "2 ** K",
        ),
        (
            {
                "name": "root",
                "type": "dummy",
                "children": [
                    {
                        "name": "a",
                        "type": "dummy",
                        "ports": [
                            {"name": "in_0", "direction": "input", "size": "N"},
                            {"name": "in_1", "direction": "input", "size": "f(g(N)) + N + 1"},
                        ],
                    }
                ],
                "ports": [
                    {"name": "in_0", "size": "K", "direction": "input"},
                    {"name": "in_1", "size": "K", "direction": "input"},
                ],
                "connections": ["in_0 -> a.in_0", "in_1 -> a.in_1"],
            },
            "K",
            "f(g(K)) + K + 1",
        ),
    ],
)
def test_compilation_introduces_constraints_stemming_from_relation_between_port_sizes(
    routine, expected_lhs, expected_rhs, backend
):

    compiled_routine = compile_routine(routine, backend=backend).routine

    constraint = compiled_routine.children["a"].constraints[0]
    assert constraint.lhs == backend.as_expression(expected_lhs)
    assert constraint.rhs == backend.as_expression(expected_rhs)


def test_compilation_fails_if_input_ports_has_size_depending_on_undefined_variable(backend):
    routine = {
        "name": "root",
        "type": "dummy",
        "children": [
            {"name": "a", "type": "dummy", "ports": [{"name": "in_0", "direction": "input", "size": "N + M"}]}
        ],
        "ports": [{"name": "in_0", "direction": "input", "size": "K"}],
        "connections": ["in_0 -> a.in_0"],
    }

    with pytest.raises(
        BartiqPreprocessingError, match=r"Size of the port in_0 depends on symbols \['M', 'N'\] which are undefined."
    ):
        compile_routine(routine, backend=backend)



def load_highwater_test_data():
    test_file = Path(__file__).parent / "data/highwater.yaml"
    data = []
    with open(test_file) as f:
        for original, expected in yaml.safe_load(f):
            data.append((SchemaV1(**original), SchemaV1(**expected)))
    return data


HIGHWATER_TEST_DATA = load_highwater_test_data()

@pytest.mark.parametrize("routine, expected_routine", HIGHWATER_TEST_DATA)
def test_compute_highwater(routine, expected_routine, backend):
    derived_resources = [{"name": "qubit_highwater", "type": "qubits", "generator": calculate_highwater}]
    compiled_routine = compile_routine(routine, derived_resources=derived_resources, backend=backend)
    assert compiled_routine.to_qref() == expected_routine


def test_compute_highwater_with_custom_names(backend):
    input_routine = SchemaV1(
        **{
            "version": "v1",
            "program": {
                "name": "root",
                "type": None,
                "ports": [
                    {"name": "in_0", "direction": "input", "size": "N"},
                    {"name": "out_0", "direction": "output", "size": "N"},
                ],
                "resources": [
                    {"name": "local_ancillae", "type": "qubits", "value": 7},
                    {"name": "custom_ancillae", "type": "qubits", "value": 5},
                    {"name": "qubit_highwater", "type": "qubits", "value": "N+7"},
                ],
            },
        }
    )

    def custom_compute_highwater(routine, backend, resource_name):
        return calculate_highwater(routine, backend, resource_name=resource_name, ancillae_name="custom_ancillae")

    derived_resources = [{"name": "custom_highwater", "type": "qubits", "generator": custom_compute_highwater}]
    compiled_routine = compile_routine(
        input_routine, derived_resources=derived_resources, backend=backend
    ).routine

    assert str(compiled_routine.resources["custom_highwater"].value) == "N + 5"


def test_computing_highwater_for_non_chronologically_sorted_routine_raises_warning():
    input_routine = {
        "version": "v1",
        "program": {
            "name": "root",
            "type": None,
            "ports": [
                {"name": "in_0", "direction": "input", "size": "N"},
                {"name": "out_0", "direction": "output", "size": "N"},
            ],
            "children": [
                {
                    "name": "a",
                    "type": "a",
                    "ports": [
                        {"name": "in_0", "direction": "input", "size": "K"},
                        {"name": "out_0", "direction": "output", "size": "K"},
                    ],
                },
                {
                    "name": "b",
                    "type": "b",
                    "ports": [
                        {"name": "in_0", "direction": "input", "size": "K"},
                        {"name": "out_0", "direction": "output", "size": "K"},
                    ],
                },
            ],
            "connections": ["in_0 -> b.in_0", "b.out_0 -> a.in_0", "a.out_0 -> out_0"],
        },
    }
    derived_resources = [{"name": "qubit_highwater", "type": "qubits", "generator": calculate_highwater}]
    with pytest.warns(
        match=(
            "Order of children in provided routine does not match the topology. Bartiq will use one of topological "
            "orderings as an estimate of chronology, but the computed highwater value might be incorrect."
        )
    ):
        _ = compile_routine(input_routine, derived_resources=derived_resources)


def test_highwater_of_an_empty_routine_is_zero():
    input_routine = {"version": "v1", "program": {"name": "root"}}
    derived_resources = [{"name": "qubit_highwater", "type": "qubits", "generator": calculate_highwater}]
    compiled_routine = compile_routine(input_routine, derived_resources=derived_resources).routine

    assert compiled_routine.resources["qubit_highwater"].value == 0
