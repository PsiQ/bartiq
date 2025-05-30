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

import pytest
from qref.schema_v1 import RoutineV1

from bartiq import Routine, compile_routine
from bartiq.compilation import CompilationFlags
from bartiq.compilation.preprocessing import introduce_port_variables
from bartiq.errors import BartiqCompilationError, BartiqPreprocessingError
from tests.utilities import load_compile_test_data, load_transitive_resource_data

COMPILE_TEST_DATA = load_compile_test_data()
COMPILE_TEST_DATA_TRANSITIVE_RESOURCES = load_transitive_resource_data()


@pytest.mark.parametrize("routine, expected_routine", COMPILE_TEST_DATA)
def test_compile_with_no_transitive_resources(routine, expected_routine, backend):
    compiled_routine = compile_routine(
        routine, backend=backend, compilation_flags=CompilationFlags.EXPAND_RESOURCES
    ).to_qref()
    assert compiled_routine == expected_routine


@pytest.mark.parametrize("routine, compiled_transitive, _", COMPILE_TEST_DATA_TRANSITIVE_RESOURCES)
def test_compile_with_transitive_resources(routine, compiled_transitive, _, backend):
    compiled_routine = compile_routine(routine, backend=backend).to_qref()
    assert compiled_routine == compiled_transitive


def f_1_simple(x):
    return x + 1


def f_2_conditional(x):
    if x > 1:
        return -x
    return x


def f_3_optional_inputs(a, b=2, c=3):
    return a + b * c


@pytest.mark.parametrize(
    "compilation_flags, expected_resource_value",
    [[None, "a.X + b.X + c.X"], [CompilationFlags.EXPAND_RESOURCES, "2*O(1) + f(1, 2, 3) + g(7) + 5"]],
)
def test_compiling_correctly_propagates_global_functions(compilation_flags, expected_resource_value):
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

    result = compile_routine(routine, compilation_flags=compilation_flags)
    # resources[0] is the only resource X
    assert result.to_qref().program.resources[0].value == expected_resource_value


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
            routine,
            preprocessing_stages=[introduce_port_variables],
            backend=backend,
            compilation_flags=CompilationFlags.SKIP_VERIFICATION,
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


N_CHILDREN = 1000


# Note: we will serialize the obtained value and compare it to the f-strings below. Theoretically,
# we could instead parse the strings and compare them to the actual values - but in practice this would
# mess up the parser because of the recursion limit.
# Also note: these strings are specific to sympy.
@pytest.mark.order(-1)
@pytest.mark.timeout(300)
@pytest.mark.parametrize(
    "compilation_flags, expected_t_count, expected_foo",
    [
        [CompilationFlags.EXPAND_RESOURCES, f"{N_CHILDREN}*n", f"n ^ {N_CHILDREN}"],
        [
            None,
            " + ".join(sorted(f"child_{x}.t_count" for x in range(N_CHILDREN))),
            "*".join(sorted(f"child_{x}.foo" for x in range(N_CHILDREN))),
        ],
    ],
)
def test_compilation_works_as_expected_in_presence_of_large_number_of_children(
    backend, compilation_flags, expected_t_count, expected_foo
):
    # This test does not check correctness, but rather serves as litmus paper detecting performance
    # regression. See https://github.com/PsiQ/bartiq/issues/181

    qref_def = {
        "version": "v1",
        "program": {
            "name": "root",
            "type": "root",
            "input_params": ["n"],
            "children": [
                {
                    "name": f"child_{i}",
                    "resources": [
                        {"type": "additive", "name": "t_count", "value": "n"},
                        {"type": "multiplicative", "name": "foo", "value": "n"},
                    ],
                }
                for i in range(N_CHILDREN)
            ],
        },
    }

    routine = Routine.from_qref(qref_def, backend)
    compilation_result = compile_routine(routine, backend=backend, compilation_flags=compilation_flags).routine
    assert (
        list(compilation_result.resources) == ["t_count", "foo"]
        and backend.serialize(compilation_result.resources["t_count"].value) == expected_t_count
        and backend.serialize(compilation_result.resources["foo"].value) == expected_foo
    )
