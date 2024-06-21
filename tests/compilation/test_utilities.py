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

import pytest

from bartiq.compilation._utilities import (
    is_constant_int,
    is_non_negative_int,
    is_single_parameter,
    split_equation,
)


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
def test_is_single_parameter(expression, expected):
    assert is_single_parameter(expression) == expected


def _make_constant_int_variations_pass(expression):
    return [
        expression,  # string version
        int(expression),  # int version
    ]


def _make_constant_int_variations_fail(expression):
    return [
        float(expression),  # Float version
        f"{expression}.0",  # Float string version
    ]


IS_CONSTANT_INT_CASES_PASS = [
    *_make_constant_int_variations_pass("0"),
    *_make_constant_int_variations_pass("1"),
    *_make_constant_int_variations_pass("-1"),
    *_make_constant_int_variations_pass("42"),
]
IS_CONSTANT_INT_CASES_FAIL = [
    *_make_constant_int_variations_fail("0"),
    *_make_constant_int_variations_fail("1"),
    *_make_constant_int_variations_fail("-1"),
    *_make_constant_int_variations_fail("42"),
    "x + y",
    "foo",
]


@pytest.mark.parametrize("expression", IS_CONSTANT_INT_CASES_PASS)
def test_is_constant_int_pass(expression):
    assert is_constant_int(expression)


@pytest.mark.parametrize("expression", IS_CONSTANT_INT_CASES_FAIL)
def test_is_constant_int_fail(expression):
    assert not is_constant_int(expression)


@pytest.mark.parametrize(
    "expression, expected",
    [
        # Good positive ints
        (1, True),
        ("1", True),
        (0, True),
        ("0", True),
        # Bad positive ints
        (1.1, False),
        (-1, False),
        (-1.1, False),
        ("1.1", False),
        ("-1", False),
        ("-1.1", False),
    ],
)
def test_is_positive_int(expression, expected):
    assert is_non_negative_int(expression) == expected


@pytest.mark.parametrize(
    "equation, expected_lhs, expected_rhs",
    [
        # Simplest case
        ("a=a", "a", "a"),
        # Simple assigment
        ("a=a + b", "a", "a + b"),
        # Simple equation
        ("a+b=a + c", "a+b", "a + c"),
        # Stripping whitespace
        (" a+b = a + c ", "a+b", "a + c"),
    ],
)
def test_split_equation(equation, expected_lhs, expected_rhs):
    assert split_equation(equation) == (expected_lhs, expected_rhs)


@pytest.mark.parametrize(
    "equation, match",
    [
        # No equals
        ("foo", "Equations must contain a single equals sign; found foo"),
        # Too many equals
        (
            "foo=bar=baz",
            "Equations must contain a single equals sign; found foo=bar=baz",
        ),
        # Bad LHS
        ("=a", "Equations must have both a left- and right-hand side; found =a"),
        # Bad RHS
        ("a=", "Equations must have both a left- and right-hand side; found a="),
        # Bad bad not good
        ("=", "Equations must have both a left- and right-hand side; found ="),
    ],
)
def test_split_equation_fails(equation, match):
    with pytest.raises(ValueError, match=match):
        assert split_equation(equation)
