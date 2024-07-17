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


def test_attempt_to_rename_builtin_function_fails():
    expr = sympy_backend.as_expression("exp(x)")

    with pytest.raises(BartiqCompilationError):
        sympy_backend.rename_function(expr, "exp", "my_exp")


def test_attempt_to_rename_user_function_to_builtin_function_fails():
    expr = sympy_backend.as_expression("f(a, b, c)")

    with pytest.raises(BartiqCompilationError):
        sympy_backend.rename_function(expr, "f", "exp")


def test_attempt_to_define_builtin_function_fails():
    expr = sympy_backend.as_expression("cos(x)")

    def _f(x):
        return x + 2

    with pytest.raises(BartiqCompilationError):
        sympy_backend.define_function(expr, "cos", _f)
