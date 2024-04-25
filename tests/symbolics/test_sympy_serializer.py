"""
..  Copyright © 2023-2024 PsiQuantum Corp.  All rights reserved.
    PSIQUANTUM CORP. CONFIDENTIAL
    This file includes unpublished proprietary source code of PsiQuantum Corp.
    The copyright notice above does not evidence any actual or intended publication
    of such source code. Disclosure of this source code or any related proprietary
    information is strictly prohibited without the express written permission of
    PsiQuantum Corp.

Tests for sympy serialisation functions.
"""

import pytest
from sympy import Product, Sum, Symbol
from sympy.core.numbers import S as sympy_constants

from bartiq.symbolics.sympy_serializer import serialize_expression

x = Symbol("x")
y = Symbol("y")
z = Symbol("z")
Pi = sympy_constants.Pi
E = sympy_constants.Exp1


@pytest.mark.parametrize(
    "expression, expected_string",
    [
        # Exponentiation
        (x ** (y**z), "x ^ (y ^ z)"),
        # Exponential
        (E, "exp(1)"),
        # Pi
        (Pi, "PI"),
        # Modulo
        (x % y, "Mod(x, y)"),
        # Summation series
        (Sum(x**2, (x, 1, y)), "sum_over(x ^ 2, x, 1, y)"),
        # Product series
        (Product(x**2, (x, 1, y)), "prod_over(x ^ 2, x, 1, y)"),
        # All together now
        (
            Product(Sum(x ** (y**z) + x % y, (x, 1, E)), (y, 1, Pi)),
            "prod_over(sum_over(x ^ (y ^ z) + Mod(x, y), x, 1, exp(1)), y, 1, PI)",
        ),
    ],
)
def test_serialize_expression(expression, expected_string):
    expression_string = serialize_expression(expression)
    assert expression_string == expected_string
