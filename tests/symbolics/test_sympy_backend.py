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
from sympy import E, cos, exp, pi, sin, sqrt, sympify

from bartiq.errors import BartiqCompilationError
from bartiq.symbolics import sympy_backend


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
        sympy_backend.define_function(expr, "cos", _f)


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
