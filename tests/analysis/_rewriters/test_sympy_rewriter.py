# Copyright 2025 PsiQuantum, Corp.
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
import sympy

from bartiq.analysis._rewriters.sympy_rewriter import SympyExpressionRewriter
from bartiq.symbolics.sympy_backend import SympyBackend
from tests.analysis._rewriters.basic_rewriter_tests import (
    CommonExpressions,
    ExpressionRewriterTests,
)


class TestSympyExpressionRewriter(ExpressionRewriterTests):
    rewriter = SympyExpressionRewriter
    backend = SympyBackend(use_sympy_max=True)

    def test_simplify(self):
        expr = self.backend.as_expression("(a*a + b*a)*c + d*(log2(x)**2 + log2(x))")
        assert self.rewriter(expr).simplify() == expr.simplify()

    @pytest.mark.parametrize(
        "expression, symbol_names",
        [
            [CommonExpressions.TRIVIAL, ["a"]],
            [CommonExpressions.SUM_AND_MUL, ["a", "b", "c", "d"]],
            [
                CommonExpressions.MANY_FUNCS,
                ["a", "x", "n", "b", "y", "aleph", "beth"],
            ],
        ],
    )
    def test_get_symbol(self, expression, symbol_names):
        for name in symbol_names:
            assert self.rewriter(expression).get_symbol(name) == sympy.Symbol(name)

    def test_get_symbol_raises_error_if_no_symbol_exists(self):
        sym = "foo"

        with pytest.raises(ValueError, match=f"No variable '{sym}'."):
            self.rewriter(CommonExpressions.MANY_FUNCS).get_symbol(sym)

    @pytest.mark.parametrize(
        "expression, args_and_fns",
        [
            [CommonExpressions.TRIVIAL, []],
            [CommonExpressions.MANY_FUNCS, ["log2(x/n)", "max(0, 1+y, 2+x)", "Heaviside(aleph, beth)"]],
            [
                CommonExpressions.NESTED_MAX,
                ["max(c, lamda)", "max(b, 1-max(c, lamda))", "max(a, 1-max(b, 1-max(c, lamda)))"],
            ],
        ],
    )
    def test_all_functions_and_arguments(self, expression, args_and_fns):
        self.assert_expression_seqs_equal(self.rewriter(expression).all_functions_and_arguments(), args_and_fns)

    @pytest.mark.parametrize(
        "function, expected_args",
        [["log2", ["x/n"]], ["max", [("0", "x+2", "y+1")]], ["Heaviside", [("aleph", "beth")]]],
    )
    def test_list_arguments_of_function(self, function, expected_args):
        args_of_function = set(self.rewriter(CommonExpressions.MANY_FUNCS).list_arguments_of_function(function))
        assert args_of_function == set(
            (
                tuple(self.backend.as_expression(x) for x in ex)
                if isinstance(ex, tuple)
                else self.backend.as_expression(ex)
            )
            for ex in expected_args
        )

    def test_expand(self):
        expr = self.backend.as_expression("(a + b)*c + d*(log2(x) + 5)")
        assert self.rewriter(expr).expand() == expr.expand()
