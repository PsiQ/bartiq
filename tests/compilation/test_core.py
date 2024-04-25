"""
..  Copyright © 2022-2024 PsiQuantum Corp.  All rights reserved.
    PSIQUANTUM CORP. CONFIDENTIAL
    This file includes unpublished proprietary source code of PsiQuantum Corp.
    The copyright notice above does not evidence any actual or intended publication
    of such source code. Disclosure of this source code or any related proprietary
    information is strictly prohibited without the express written permission of
    PsiQuantum Corp.

Tests for the bartiq.compilation._symbolic_function module.
"""

import re

import pytest

from bartiq.compilation._symbolic_function import (
    SymbolicFunction,
    _get_renamed_inputs_and_outputs,
    _merge_functions,
    _serialize_variables,
    compile_functions,
    rename_variables,
)
from bartiq.errors import BartiqCompilationError
from bartiq.symbolics.variables import DependentVariable, IndependentVariable

# Note: in the following test cases, the expected outputs (last param)
# is a dictionary mapping variable name to a serialized dependent variable
# Hence, in the test case the values have to be deserialzied using
# DependentVariable.from_str
# This is by design, because the test case is parametrized with a backend.
FROM_STR_TEST_CASES = [
    # Null case
    (
        [],  # Inputs
        [],  # Outputs
        {},  # Expected inputs
        {},  # Expected outputs
    ),
    # Input-only case
    (
        ["a", "b", "c"],  # Inputs
        [],  # Outputs
        {  # Expected inputs
            "a": IndependentVariable("a"),
            "b": IndependentVariable("b"),
            "c": IndependentVariable("c"),
        },
        {},  # Expected outputs
    ),
    # Output-only case
    (
        [],  # Inputs
        ["a = 1", "b = 2"],  # Outputs
        {},  # Expected inputs
        {  # Expected outputs
            "a": "a = 1",
            "b": "b = 2",
        },
    ),
    # Full case
    (
        ["x", "y"],  # Inputs
        ["a = x + y", "b = x - y"],  # Outputs
        {  # Expected inputs
            "x": IndependentVariable("x"),
            "y": IndependentVariable("y"),
        },
        {  # Expectged outputs
            "a": "a = x + y",
            "b": "b = x - y",
        },
    ),
]


@pytest.mark.parametrize("inputs, outputs, expected_inputs, expected_outputs", FROM_STR_TEST_CASES)
def test_SymbolicFunction_from_str(inputs, outputs, expected_inputs, expected_outputs, backend):
    expected_outputs = {k: DependentVariable.from_str(v, backend) for k, v in expected_outputs.items()}
    function = SymbolicFunction.from_str(inputs, outputs, backend)
    assert function.inputs == expected_inputs
    assert function.outputs == expected_outputs

    # Test round-trip
    round_trip_inputs, round_trip_outputs = function.to_str()
    assert round_trip_inputs == inputs
    assert round_trip_outputs == outputs


EQUALITY_TEST_CASES = [
    # Null case
    (
        ([], []),
        ([], []),
    ),
    # Permuted inputs
    (
        (["a", "b"], []),
        (["b", "a"], []),
    ),
    # Permuted outputs
    (
        ([], ["a = 42", "b = 24"]),
        ([], ["b = 24", "a = 42"]),
    ),
    # Permuted inputs and outputs
    (
        (["a", "b"], ["c = a", "d = b"]),
        (["b", "a"], ["d = b", "c = a"]),
    ),
    # Addition vs multiplication
    (
        (["a"], ["b = a + a"]),
        (["a"], ["b = 2 * a"]),
    ),
]


@pytest.mark.parametrize("function_1, function_2", EQUALITY_TEST_CASES)
def test_SymbolicFunction_equality(function_1, function_2, backend):
    function_1 = SymbolicFunction.from_str(*function_1, backend)
    function_2 = SymbolicFunction.from_str(*function_2, backend)

    assert function_1 == function_2


ERRORS_TEST_CASES = [
    # Output references unknown variables
    (([], ["b = a"]), BartiqCompilationError, "Expressions must not contain unknown variables"),
    # No duplicate inputs
    ((["a", "a"], []), BartiqCompilationError, "Variable list contains repeated symbol"),
    # No duplicate outputs
    (([], ["a = 0", "a = 1"]), BartiqCompilationError, "Variable list contains repeated symbol"),
    # Outputs cannot share names with inputs
    ((["a"], ["a = 0"]), BartiqCompilationError, "Outputs must not reuse input symbols"),
]


@pytest.mark.parametrize("function, exception, match", ERRORS_TEST_CASES)
def test_SymbolicFunction_errors(function, exception, match, backend):
    with pytest.raises(exception, match=match):
        SymbolicFunction.from_str(*function, backend)


MERGE_FUNCTIONS_TEST_CASES = [
    # Null case
    (
        ([], []),
        ([], []),
        ([], []),
    ),
    # Constant function from two unconnected functions
    (
        (["a"], []),
        ([], ["b = 42"]),
        (["a"], ["b = 42"]),
    ),
    # Constant function from connected functions
    (
        (["a"], ["b = a + 1"]),
        (["b"], ["c = 42"]),
        (["a"], ["c = 42"]),
    ),
    #  Null outer function from non-null functions
    (
        ([], ["a = 42"]),
        (["a"], []),
        ([], []),
    ),
    # Trivial case 1
    (
        (["a"], ["b = a"]),
        ([], []),
        (["a"], ["b = a"]),
    ),
    # Trivial case 2
    (
        ([], []),
        (["a"], ["b = a"]),
        (["a"], ["b = a"]),
    ),
    # Simple linear case
    (
        (["a"], ["b = a"]),
        (["b"], ["c = b"]),
        (["a"], ["c = a"]),
    ),
    # Tensor of two functions
    (
        (["a"], ["b = a + 1"]),
        (["c"], ["d = c + 2"]),
        (["a", "c"], ["b = a + 1", "d = c + 2"]),
    ),
    # Simple single-variable addition
    (
        (["x"], ["y = x + 1"]),
        (["y"], ["z = y + 1"]),
        (["x"], ["z = x + 2"]),
    ),
    # Nested functions
    (
        (["x"], ["y = f(x)"]),
        (["y"], ["z = g(y)"]),
        (["x"], ["z = g(f(x))"]),
    ),
    # Both functions introduce new variables
    (
        (["a", "b"], ["c = a + b"]),
        (["c", "d"], ["e = c + d"]),
        (["a", "b", "d"], ["e = a + b + d"]),
    ),
    # Both functions define outputs
    (
        (["a"], ["b = f(a)", "c = g(a)"]),
        (["b"], ["d = h(b)"]),
        (["a"], ["c = g(a)", "d = h(f(a))"]),
    ),
    # Automatic simplification (woooooahhh!)
    (
        (["x"], ["y = log(x)"]),
        (["y"], ["z = exp(y)"]),
        (["x"], ["z = x"]),
    ),
    # Allow for merged functions to take same inputs
    (
        (["x"], []),
        (["x"], []),
        (["x"], []),
    ),
    # Allow for merged functions to take same outputs if they have the same expressions
    (
        ([], ["x = 0"]),
        ([], ["x = 0"]),
        ([], ["x = 0"]),
    ),
]


@pytest.mark.parametrize("base_func, target_func, expected_func", MERGE_FUNCTIONS_TEST_CASES)
def test_merge_functions(base_func, target_func, expected_func, backend):
    base_func = SymbolicFunction.from_str(*base_func, backend)
    target_func = SymbolicFunction.from_str(*target_func, backend)
    expected_func = SymbolicFunction.from_str(*expected_func, backend)

    assert _merge_functions(base_func, target_func) == expected_func


MERGE_FUNCTION_ERRORS_TEST_CASES = [
    # Target function has output already defined as base input
    (
        (["y"], ["z = g(y)"]),
        (["x"], ["y = f(x)"]),
        "Target function outputs must not reference base function inputs when merging",
    ),
    # Functions have same output symbols, but different expressions
    (
        ([], ["x = 1"]),
        ([], ["x = 0"]),
        "Merging functions may only have same outputs if the outputs share the same expression",
    ),
]


@pytest.mark.parametrize("base_func, target_func, match", MERGE_FUNCTION_ERRORS_TEST_CASES)
def test_merge_functions_errors(base_func, target_func, match, backend):
    base_func = SymbolicFunction.from_str(*base_func, backend)
    target_func = SymbolicFunction.from_str(*target_func, backend)

    with pytest.raises(BartiqCompilationError, match=match):
        _merge_functions(base_func, target_func)


COMPILE_FUNCTIONS_TEST_CASES = [
    # Null case
    (
        [],
        ([], []),
    ),
    # Nuller case
    (
        [
            ([], []),
        ],
        ([], []),
    ),
    # Nullest case
    (
        [
            ([], []),
            ([], []),
        ],
        ([], []),
    ),
    # The "Dude, I heard you like functions..." case
    (
        [
            (["a"], ["b = f(a)"]),
            (["b"], ["c = g(b)"]),
            (["c"], ["d = h(c)"]),
        ],
        (["a"], ["d = h(g(f(a)))"]),
    ),
    # Expanding outputs case (via generating binary number additions)
    (
        [
            (["a"], ["b0 = a + 0", "b1 = a + 1"]),
            (["b0"], ["c00 = b0 + 0", "c10 = b0 + 2"]),
            (["b1"], ["c01 = b1 + 0", "c11 = b1 + 2"]),
        ],
        (["a"], ["c00 = a + 0", "c01 = a + 1", "c10 = a + 2", "c11 = a + 3"]),
    ),
    # Decreasing inputs case (via log-tree adder)
    (
        [
            (["a000", "a001"], ["b00 = a000 + a001"]),
            (["a010", "a011"], ["b01 = a010 + a011"]),
            (["a100", "a101"], ["b10 = a100 + a101"]),
            (["a110", "a111"], ["b11 = a110 + a111"]),
            (["b00", "b01"], ["c0 = b00 + b01"]),
            (["b10", "b11"], ["c1 = b10 + b11"]),
            (["c0", "c1"], ["d = c0 + c1"]),
        ],
        (
            ["a000", "a001", "a010", "a011", "a100", "a101", "a110", "a111"],
            ["d = a000 + a001 + a010 + a011 + a100 + a101 + a110 + a111"],
        ),
    ),
]


@pytest.mark.parametrize("functions, expected_function", COMPILE_FUNCTIONS_TEST_CASES)
def test_compile_functions(functions, expected_function, backend):
    functions = list(map(lambda func: SymbolicFunction.from_str(*func, backend), functions))
    expected_function = SymbolicFunction.from_str(*expected_function, backend)

    assert compile_functions(functions) == expected_function


RENAME_VARIABLES_TEST_CASES = [
    # Null case
    (
        ([], []),
        {},
        ([], []),
    ),
    # Renaming inputs
    (
        (["a", "b", "c"], []),
        {"a": "x", "c": "y"},
        (["x", "b", "y"], []),
    ),
    # Renaming outputs
    (
        ([], ["a = 42", "b = 3.141", "c = 101"]),
        {"a": "x", "c": "y"},
        ([], ["x = 42", "b = 3.141", "y = 101"]),
    ),
    # Renaming inputs and outputs
    (
        (["a", "b", "c"], ["d = a + b", "e = b + c"]),
        {"a": "x", "c": "y", "e": "z"},
        (["x", "b", "y"], ["d = x + b", "z = b + y"]),
    ),
]


@pytest.mark.parametrize("function, variable_map, expected_function", RENAME_VARIABLES_TEST_CASES)
def test_rename_variables(function, variable_map, expected_function, backend):
    function = SymbolicFunction.from_str(*function, backend)
    expected_function = SymbolicFunction.from_str(*expected_function, backend)

    assert rename_variables(function, variable_map) == expected_function


RENAME_INPUTS_AND_OUTPUTS_TEST_CASES = [
    # Ensure non-duplication of inputs
    (
        (["a", "b"], []),
        {"a": "b"},
        (["b"], []),
    ),
    # Ensure non-duplication of outputs
    (
        ([], ["x = 1", "y = 1"]),
        {"x": "y"},
        ([], ["y = 1"]),
    ),
    # Ensure simultaneous non-duplication of outputs
    (
        (["a", "b"], ["x = a", "y = b"]),
        {"a": "b", "x": "y"},
        (["b"], ["y = b"]),
    ),
    # Renaming inputs and outputs
    (
        (["a", "b", "c"], ["d = a + b", "e = b + c"]),
        {"a": "x", "c": "x", "e": "z"},
        (["x", "b"], ["d = b + x", "z = b + x"]),
    ),
    # Renaming with cycle
    (
        (["a", "b", "c"], ["d = a + b", "e = b + c"]),
        {"a": "x", "c": "x", "x": "z", "z": "a"},
        (["a", "b"], ["d = a + b", "e = a + b"]),
    ),
]


@pytest.mark.parametrize("function, variable_map, expected_results", RENAME_INPUTS_AND_OUTPUTS_TEST_CASES)
def test_rename_inputs_and_outputs(function, variable_map, expected_results, backend):
    function = SymbolicFunction.from_str(*function, backend)
    new_inputs, new_outputs = _get_renamed_inputs_and_outputs(function, variable_map)
    serialized_inputs = _serialize_variables(new_inputs)
    serialized_outputs = _serialize_variables(new_outputs)

    expected_inputs, expected_outputs = expected_results
    assert serialized_inputs == expected_inputs
    assert serialized_outputs == expected_outputs


RENAME_INPUTS_AND_OUTPUTS_ERRORS_TEST_CASES: list[tuple[tuple, dict, str]] = [
    # Output renaming would cause a conflict
    (([], ["x = 1", "y = 2"]), {"x": "y"}, "Cannot rename output variable"),
]


@pytest.mark.parametrize("function, variable_map, expected_error", RENAME_INPUTS_AND_OUTPUTS_ERRORS_TEST_CASES)
def test_rename_inputs_and_outputs_errors(function, variable_map, expected_error, backend):
    function = SymbolicFunction.from_str(*function, backend)

    with pytest.raises(BartiqCompilationError, match=re.escape(expected_error)):
        _get_renamed_inputs_and_outputs(function, variable_map)
