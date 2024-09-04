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

from bartiq import compile_routine
from bartiq._routine import Routine
from bartiq.compilation._symbolic_function import (
    SymbolicFunction,
    define_expression_functions,
)
from bartiq.errors import BartiqCompilationError
from bartiq.integrations.qref import qref_to_bartiq
from bartiq.precompilation.stages_new import introduce_port_variables
from bartiq.symbolics import sympy_backend

BACKEND = sympy_backend


def load_compile_test_data():
    with open(Path(__file__).parent / "data/compile_test_data_new_qref.yaml") as f:
        return [(qref_to_bartiq(original), qref_to_bartiq(expected)) for original, expected in yaml.safe_load(f)]


COMPILE_TEST_DATA = load_compile_test_data()


@pytest.mark.filterwarnings("ignore:Found the following issues with the provided routine")
@pytest.mark.parametrize("routine, expected_routine", COMPILE_TEST_DATA)
def test_compile(routine, expected_routine):
    compiled_routine = compile_routine(routine, skip_verification=True)
    assert compiled_routine == expected_routine


def f_1_simple(x):
    return x + 1


def f_2_conditional(x):
    if x > 1:
        return -x
    return x


def f_3_optional_inputs(a, b=2, c=3):
    return a + b * c


DEFINED_EXPRESSION_FUNCTIONS_TEST_DATA = [
    # Testing function which can be interpreted symbolically
    (
        SymbolicFunction.assemble(["a", "b"], {"x": "f(a) + f(b)"}, BACKEND),
        {"f": f_1_simple},
        {"x": "a + b + 2"},
    ),
    # Testing function which cannot be interpreted symbolically due to having a condition
    (
        SymbolicFunction.assemble(["a"], {"x": "f(a) + a"}, BACKEND),
        {"f": f_2_conditional},
        {"x": "a + f(a)"},
    ),
    # Testing function with multiple inputs, some with default values ["x = a**2 + 2*a + 3*b"]
    (
        SymbolicFunction.assemble(["a", "b"], {"x": "f(a, b) + f(a, a, a)"}, BACKEND),
        {"f": f_3_optional_inputs},
        {"x": "a ^ 2 + 2*a + 3*b"},
    ),
    # Testing nested calls of a simple function
    (
        SymbolicFunction.assemble(["a"], {"x": "f(f(f(a)))"}, BACKEND),
        {"f": f_1_simple},
        {"x": "a + 3"},
    ),
]


@pytest.mark.parametrize("function, functions_map, expected_output_expressions", DEFINED_EXPRESSION_FUNCTIONS_TEST_DATA)
def test_defined_expression_functions(function, functions_map, expected_output_expressions):
    new_function = define_expression_functions(function=function, functions_map=functions_map)
    assert function.inputs == new_function.inputs
    for output_symbol, output_variable in new_function.outputs.items():
        for expression_function_name, expression_function_callable in functions_map.items():
            assert output_variable.expression_functions[expression_function_name] == expression_function_callable
        new_evaluated_expression = output_variable.evaluated_expression
        assert expected_output_expressions[output_symbol] == new_evaluated_expression


def mad_max(a, b):
    return a + b


@pytest.mark.parametrize(
    "function, functions_map, expected_error",
    [
        (
            SymbolicFunction.assemble(["a", "b"], {"x": "max(a, b)"}, BACKEND),
            {"max": mad_max},
            "Attempted to redefine built-in function max",
        )
    ],
)
def test_defined_expression_functions_errors(function, functions_map, expected_error):
    with pytest.raises(BartiqCompilationError, match=re.escape(expected_error)):
        new_function = define_expression_functions(function=function, functions_map=functions_map)
        for output_variable in new_function.outputs.values():
            output_variable.evaluated_expression


def test_compiling_correctly_propagates_global_functions():
    routine = Routine(
        name="root",
        type="dummy",
        resources={"X": {"name": "X", "value": "a.X + b.X + c.X", "type": "other"}},
        children={
            "a": Routine(
                name="a",
                type="dummy",
                resources={"X": {"name": "X", "value": "O(1) + 5", "type": "other"}},
            ),
            "b": Routine(
                name="b",
                type="dummy",
                resources={"X": {"name": "X", "value": "O(1)", "type": "other"}},
            ),
            "c": Routine(
                name="c",
                type="dummy",
                resources={"X": {"name": "X", "value": "g(7) + f(1, 2, 3)", "type": "other"}},
            ),
        },
    )

    compiled_routine = compile_routine(routine)

    assert compiled_routine.resources["X"].value == "2*O(1) + f(1, 2, 3) + g(7) + 5"


COMPILE_ERRORS_TEST_CASES = [
    # Attempt to assign inconsistent constant register sizes
    (
        Routine(
            name="root",
            type="dummy",
            children={
                "a": {
                    "name": "a",
                    "type": "dummy",
                    "ports": {"in_bar": {"name": "in_bar", "direction": "input", "size": 2}},
                }
            },
            ports={"in_foo": {"name": "in_foo", "direction": "input", "size": 1}},
            connections=[{"source": "in_foo", "target": "a.in_bar"}],
        ),
        "The following constraint was violated when compiling root.a: #in_bar = 2 evaluated into 1 = 2.",
    ),
    # Attempt to connect two different sizes to routine which has both inputs of the same size
    (
        Routine(
            name="root",
            type="dummy",
            children={
                "a": {
                    "name": "a",
                    "type": "dummy",
                    "ports": {"out_0": {"name": "out_0", "direction": "output", "size": 1}},
                },
                "b": {
                    "name": "b",
                    "type": "dummy",
                    "ports": {"out_0": {"name": "out_0", "direction": "output", "size": 2}},
                },
                "c": {
                    "name": "c",
                    "type": "dummy",
                    "ports": {
                        "out_0": {"name": "out_0", "direction": "output", "size": "2*N"},
                        "in_0": {"name": "in_0", "direction": "input", "size": "N"},
                        "in_1": {"name": "in_1", "direction": "input", "size": "N"},
                    },
                },
            },
            connections=[
                {"source": "a.out_0", "target": "c.in_0"},
                {"source": "b.out_0", "target": "c.in_1"},
            ],
        ),
        "The following constraint was violated when compiling root.c: #in_1 = #in_0 evaluated into 2 = 1",
    ),
]


@pytest.mark.parametrize("routine, expected_error", COMPILE_ERRORS_TEST_CASES)
def test_compile_errors(routine, expected_error):
    with pytest.raises(BartiqCompilationError, match=re.escape(expected_error)):
        compile_routine(routine, precompilation_stages=[introduce_port_variables], skip_verification=True)
