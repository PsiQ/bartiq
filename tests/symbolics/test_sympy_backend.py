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
from sympy import cos, exp, pi, sin, sqrt, symbols, sympify

from bartiq.errors import BartiqCompilationError
from bartiq.symbolics import sympy_backend
from bartiq.symbolics.sympy_backend import SympyBackend
from bartiq.symbolics.sympy_interpreter import SPECIAL_FUNCS, Max


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


@pytest.mark.filterwarnings("ignore:The value_of method is deprecated.")
def test_value_of_returns_expr_if_numerical_evaluation_is_not_possible():
    expr = sympy_backend.as_expression("log2(N)")

    assert sympy_backend.value_of(expr) == expr


def test_value_of_raises_deprecation_warning():
    with pytest.warns(DeprecationWarning):
        assert sympy_backend.value_of(10)


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
        ("ceil(log2(N))", False),
        ("ceiling(log2(N))", False),
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
    assert backend.max(*values) == Max(*values)


@pytest.mark.parametrize(
    "expression, expected_output, user_defined",
    [
        (
            "celing(a*log_2(x))/log_10(y) + mlz(x*y/z)*log_10(x*y)",
            [("log_2", "log2"), ("log_10", "log10"), ("celing", "ceiling"), ("mlz", "nlz")],
            [],
        ),
        (
            "ceil(a*log_2(x))/log_10(y) + mlz(x*y/z)*log_10(x*y)",
            [("log_2", "log2"), ("log_10", "log10")],
            ["mlz"],
        ),
    ],
)
def test_find_unknown_functions(backend, expression, expected_output, user_defined):
    input_expr = backend.as_expression(expression)
    assert set(backend.find_undefined_functions(input_expr, user_defined)) == set(expected_output)


def test_sympy_backend_with_sympy_max():
    backend_with_sympy_max = SympyBackend(use_sympy_max=True)
    # These expressions use different max fns
    assert sympy_backend.as_expression("max(0, a)") != backend_with_sympy_max.as_expression("max(0, a)")


def test_max_fn_simplifies_when_using_sympy():
    a = symbols("a", positive=True)
    assert sympy_backend.max(0, a) == Max(0, a)
    assert SympyBackend(use_sympy_max=True).max(0, a) == a


def test_function_mappings_property():
    # As of June 2025, the 'max' function should be the only function overridden
    sympy_backend_with_sympy_max = SympyBackend(use_sympy_max=True)
    assert sympy_backend_with_sympy_max.function_mappings == SPECIAL_FUNCS | {"max": sympy_max}


def test_sum_returns_native_number_if_possible():
    a, b, c = symbols("a, b, c")

    result = sympy_backend.sum(a, b, c, 2.0, -a, -b, -c)

    assert result == 2
    assert isinstance(result, (int, float))


def test_prod_returns_native_number_if_possible():
    a, b, c = symbols("a, b, c")

    result = sympy_backend.prod(a * b, c / b, 1 / a, 2 / c)

    assert result == 2
    assert isinstance(result, (int, float))
