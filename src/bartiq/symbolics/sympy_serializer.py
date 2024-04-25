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
