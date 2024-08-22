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

import math

import pytest
import sympy
from sympy.abc import x, y

from bartiq.analysis import BigO, minimize


@pytest.mark.parametrize(
    "expr,variable,expected",
    [
        (
            x**y + y**x + x * y + x**2 * y + 3 + x * y**2 + x + y + 1,
            None,
            BigO(x**y) + BigO(y**x) + BigO(x * y**2) + BigO(x**2 * y),
        ),
        (
            x * y + x**2 * y + 3 + x * y**3 + x + y + 1,
            x,
            BigO(x**2),
        ),
        (
            x * y + x**2 * y + 3 + x * y**3 + x + y + 1,
            y,
            BigO(y**3),
        ),
        (
            sympy.sympify("f(x) + y"),
            y,
            BigO(y),
        ),
        (
            sympy.sympify("log(x) + y**2 + y"),
            None,
            BigO(sympy.sympify("log(x)")) + BigO(y**2),
        ),
    ],
)
def test_BigO(expr, variable, expected):
    assert BigO(expr, variable) == expected


def test_BigO_throws_warning_for_multiple_variables():
    with pytest.warns(
        match="Results for using BigO with multiple variables might be unreliable. "
        "For better results please select a variable of interest."
    ):
        BigO(x**y + y**x + x * y + x**2 * y + 3 + x * y**2 + x + y + 1)


def test_adding_BigO_expressions():
    assert BigO(x) + BigO(x) == BigO(x)
    assert BigO(x) * BigO(x) == BigO(x**2)
    assert BigO(2 * y + 17) + BigO(x - 1) == BigO(x) + BigO(y)
    assert BigO(x, variable=y) + BigO(y, variable=x) == BigO(sympy.sympify(1))


@pytest.mark.parametrize(
    "expr,gens,expected",
    [
        (
            x**0.5,
            x,
            BigO(x**0.5),
        ),
        (
            sympy.log(x) + sympy.log(x) * x,
            x,
            BigO(sympy.log(x) * x),
        ),
        (
            sympy.log(x) + sympy.log(x) * x,
            x,
            BigO(sympy.log(x) * x),
        ),
    ],
)
def test_failing_big_O_cases(expr, gens, expected):
    pytest.xfail()


@pytest.mark.parametrize(
    "cost_expression, param, optimizer_kwargs, initial_params, expected_optimal_value, expected_minimum_cost",
    [
        # Adjusted test case for minimizing the cosine function
        ("cos(x)", "x", {"learning_rate": 0.5, "max_iter": 10000, "tolerance": 1e-6}, 3.0, math.pi, -1.0),
    ],
)
def test_minimize(
    cost_expression, param, optimizer_kwargs, initial_params, expected_optimal_value, expected_minimum_cost
):

    result = minimize(
        expression=cost_expression,
        param=param,
        initial_params=initial_params,
        optimizer="gradient_descent",
        optimizer_kwargs=optimizer_kwargs,
    )

    assert abs(result["optimal_value"] - expected_optimal_value) < 1e-6
    assert abs(result["minimum_cost"] - expected_minimum_cost) < 1e-6
