"""
..  Copyright © 2023-2024 PsiQuantum Corp.  All rights reserved.
    PSIQUANTUM CORP. CONFIDENTIAL
    This file includes unpublished proprietary source code of PsiQuantum Corp.
    The copyright notice above does not evidence any actual or intended publication
    of such source code. Disclosure of this source code or any related proprietary
    information is strictly prohibited without the express written permission of
    PsiQuantum Corp.

Tests for the SympyExpression implementation.
"""

import pytest
from sympy import E
from sympy import Max as sympy_max
from sympy import Min as sympy_min
from sympy import Number, Symbol, Wild, cos, exp, log, pi, sin, sqrt, symbols, sympify

from bartiq.errors import BartiqCompilationError
from bartiq.symbolics import sympy_backend
from bartiq.symbolics.sympy_backends import _LOG2_EXPR, _correct_base2_logs, _postprocess


@pytest.mark.parametrize(
    "expression, expected",
    [
        # Good ints
        (sympify("0"), True),
        (sympify("1"), True),
        (sympify("-1"), True),
        (sympify("42"), True),
        (sympify("1 + 1"), True),
        # Bad ints
        (sympify("x"), False),
        (sympify("x + 1"), False),
    ],
)
def test_is_sympy_int(expression, expected):
    assert sympy_backend.is_constant_int(expression) == expected


@pytest.mark.parametrize(
    "expression_str, expected",
    [
        # Known constants
        ("pi", pi),
        ("PI", pi),
        ("e", E),
        ("E", E),
        # Expressions with constants
        ("2 * pi", 2 * pi),
        ("e + 1", E + 1),
        ("sqrt(-cos(3*pi))", sqrt(-cos(3 * pi))),
        # Mixed case
        ("2 * PI", 2 * pi),
        ("sin(-0.25*e)", sin(-0.25 * E)),
        ("-exp(Pi / 4)", -exp(pi / 4)),
        # No constants
        ("x", sympify("x")),
        ("x + y", sympify("x + y")),
    ],
)
def test_parse_constant(expression_str, expected):
    expr = sympy_backend.as_expression(expression_str)
    expr = sympy_backend.parse_constant(expr)
    assert expr == expected


def test_value_of_returns_none_if_numerical_evaluation_is_not_possible():
    expr = sympy_backend.as_expression("log2(N)")

    assert sympy_backend.value_of(expr) is None


def test_attempt_to_define_builtin_function_fails():
    expr = sympy_backend.as_expression("cos(x)")

    def _f(x):
        return x + 2

    with pytest.raises(BartiqCompilationError):
        sympy_backend.substitute(expr, {}, {"cos": _f})


@pytest.mark.parametrize(
    "expression, expected",
    [
        # Good params
        ("x", True),
        ("lambda", True),
        ("one", True),
        ("some.path.to.param", True),
        ("some.path.to.#port.param", True),
        # Bad params
        ("x + y", False),
        ("1", False),
        ("3.141", False),
        ("N+1", False),
        ("ceil(log_2(N))", False),
        (None, False),
    ],
)
def test_single_parameters_are_correctly_recognized(expression, expected):
    assert sympy_backend.is_single_parameter(sympy_backend.as_expression(expression)) == expected


@pytest.mark.parametrize(
    "expression_str, expected_value", [("N", "N"), ("k * j + i", "i + j*k"), ("2.5", 2.5), ("4", 4)]
)
def test_expressions_are_correctly_converted_to_native_types_based_on_their_category(
    expression_str, expected_value, backend
):
    expr = backend.as_expression(expression_str)

    native_value = backend.as_native(expr)

    assert isinstance(native_value, type(expected_value))  # Needed because e.g. 4.0 == 4, value is not enough
    assert native_value == expected_value


@pytest.mark.parametrize(
    "func_name, arg_str, expected_native_result",
    [("ceil", 2, 2), ("sin", "PI", 0), ("sin", "x", "sin(x)"), ("sin", "PI/6", 0.5)],
)
def test_functions_obtained_from_backend_can_be_called_to_obtain_new_expressions(
    func_name, arg_str, expected_native_result, backend
):
    func = backend.func(func_name)
    arg = backend.as_expression(arg_str)

    result = func(arg)

    assert backend.as_native(result) == expected_native_result


@pytest.mark.parametrize(
    "expression_str, variables, functions, expected_native_result",
    [
        ("8", {}, {"f": lambda x: x + 10}, 8),
        # Note: existence of function "g" is crucial in the examples below, even if it is not used explicitly
        # These examples triggered issue #143: https://github.com/PsiQ/bartiq/issues/143
        ("f(x)", {"x": 5}, {"f": lambda x: int(x) + 5, "g": lambda x: x}, 10),
        ("f(x)+10", {}, {"f": lambda x: 2, "g": lambda x: int(x) ** 2}, 12),
    ],
)
def test_function_definition_succeeds_even_if_expression_becomes_constant(
    expression_str, variables, functions, expected_native_result, backend
):
    expr = backend.as_expression(expression_str)

    new_expr = backend.substitute(expr, variables, functions)

    assert backend.as_native(new_expr) == expected_native_result


def test_defining_functions_is_invariant_under_input_order(backend):
    def f(x):
        return int(x) + 1

    def g(x):
        return x**2

    expr = backend.as_expression("f(g(x))")

    result_1 = backend.substitute(expr, {"x": 3}, {"f": f, "g": g})
    result_2 = backend.substitute(expr, {"x": 3}, {"g": g, "f": f})

    assert result_1 == 10
    assert result_2 == 10


def test_min_max_works_for_numerical_values(backend):
    values = [-5, 0, 1, 23.4]
    assert backend.min(*values) == min(*values)
    assert backend.max(*values) == max(*values)


def test_min_max_works_for_symbols(backend):
    values = symbols("a, b, c")
    assert backend.min(*values) == sympy_min(*values)
    assert backend.max(*values) == sympy_max(*values)


def test_log2_expression():
    A, B = Wild("A"), Wild("B")
    assert {B: "X", A: "Y"} == {key: val.name for key, val in _LOG2_EXPR.match(A * log(B) / log(2)).items()}


@pytest.mark.parametrize(
    "_input, expected_output",
    [
        (Symbol("Ksi_L"), Symbol("Ksi_L")),
        (Symbol("X1"), Symbol("X1")),
        (Number("5645421.2343545"), Number("5645421.2343545")),
        (Number("0"), Number("0")),
    ],
)
def test_correct_base2_logs_ignores_symbol_and_number(_input, expected_output):
    assert _correct_base2_logs(_input) == expected_output


ex1 = sympify("P*(a*log(x)/log(2) + L*(log(2)*log(y) + log(L)/log(2))) + log(y)/log(10) + 1/log(2)")
ex1_morphed = sympify("P*(L*(log(2)*log(y) + log2(L)) + a*log2(x)) + log(y)/log(10) + 1/log(2)")

ex2 = sympify("ceiling(log(x)/log(2))")
ex2_morphed = sympify("ceiling(log2(x))")

ex3 = sympify("P*(1/log(2))")


@pytest.mark.parametrize(
    "_input, expected_output",
    [
        (ex1, ex1_morphed),
        (ex2, ex2_morphed),
        (ex3, ex3),
    ],
)
def test_correct_base2_logs_morphs_expressions_as_expected(_input, expected_output):
    assert sympify(str(_correct_base2_logs(_input))) == expected_output


@pytest.mark.parametrize(
    "_input, expected_output",
    [
        (ex1, ex1_morphed),
        (ex2, ex2_morphed),
        (ex3, ex3),
    ],
)
def test_postprocess_morphs_expressions_as_expected(_input, expected_output):
    assert sympify(str(_postprocess(_input))) == expected_output
