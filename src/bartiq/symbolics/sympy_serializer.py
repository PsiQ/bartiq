"""
..  Copyright © 2023-2024 PsiQuantum Corp.  All rights reserved.
    PSIQUANTUM CORP. CONFIDENTIAL
    This file includes unpublished proprietary source code of PsiQuantum Corp.
    The copyright notice above does not evidence any actual or intended publication
    of such source code. Disclosure of this source code or any related proprietary
    information is strictly prohibited without the express written permission of
    PsiQuantum Corp.

Module for serialising sympy expressions so that they're compatible with our sympy interpreter.
"""

from typing import Any

from sympy import Expr
from sympy.printing.precedence import precedence
from sympy.printing.str import StrPrinter


class BartiqPrinter(StrPrinter):
    """Printer for symbolic Bartiq expressions strings."""

    def _print_Exp1(self, expr: Any) -> str:
        return "exp(1)"

    def _print_Sum(self, expr: Any) -> str:
        return self._print_over_sequence(expr, "sum_over")

    def _print_Product(self, expr: Any) -> str:
        return self._print_over_sequence(expr, "prod_over")

    def _print_over_sequence(self, expr: Any, sequence: str) -> str:
        function, symbols = expr.args
        symbol_args_str = ", ".join(self._print(symbol) for symbol in symbols)
        return f"{sequence}({self._print(function)}, {symbol_args_str})"

    def _print_Pi(self, expr: Any) -> str:
        return "PI"

    def _print_Pow(self, expr: Any, rational: Any = ...) -> str:
        PREC = precedence(expr)
        base, exponent = expr.args
        base_str = self._print(self.parenthesize(expr.base, PREC))
        exp_str = self._print(self.parenthesize(expr.exp, PREC))
        return f"{base_str} ^ {exp_str}"


def serialize_expression(expr: Expr) -> str:
    """Takes a sympy expression and serializes it to a Bartiq-parseable expression."""
    return BartiqPrinter().doprint(expr)
