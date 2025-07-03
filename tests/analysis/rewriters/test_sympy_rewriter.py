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

from bartiq.analysis.rewriters.sympy_rewriter import sympy_rewriter
from bartiq.analysis.rewriters.utils import Substitution
from bartiq.symbolics.sympy_backend import SympyBackend
from tests.analysis.rewriters.basic_rewriter_tests import (
    CommonExpressions,
    ExpressionRewriterTests,
)


class TestSympyExpressionRewriter(ExpressionRewriterTests):

    rewriter = staticmethod(sympy_rewriter)

    @pytest.fixture()
    def backend(self) -> SympyBackend:
        return SympyBackend(use_sympy_max=True)

    def test_simplify(self, backend):
        expr = backend.as_expression("(a*a + b*a)*c + d*(log2(x)**2 + log2(x))")
        assert self.rewriter(expr).simplify().expression == expr.simplify()

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
    def test_all_functions_and_arguments(self, backend, expression, args_and_fns):
        self.assert_expression_seqs_equal(
            backend, self.rewriter(expression).all_functions_and_arguments(), args_and_fns
        )

    @pytest.mark.parametrize(
        "function, expected_args",
        [["log2", ["x/n"]], ["max", [("0", "x+2", "y+1")]], ["Heaviside", [("aleph", "beth")]]],
    )
    def test_list_arguments_of_function(self, backend, function, expected_args):
        args_of_function = set(self.rewriter(CommonExpressions.MANY_FUNCS).list_arguments_of_function(function))
        assert args_of_function == set(
            (tuple(backend.as_expression(x) for x in ex) if isinstance(ex, tuple) else backend.as_expression(ex))
            for ex in expected_args
        )

    def test_expand(self, backend):
        expr = backend.as_expression("(a + b)*c + d*(log2(x) + 5)")
        assert self.rewriter(expr).expand().expression == expr.expand()

    @pytest.mark.parametrize(
        "method, expected_default_value",
        [
            ["free_symbols", set()],
            ["expand", None],
            ["simplify", None],
            ["all_functions_and_arguments", set()],
        ],
    )
    def test_default_return_values_when_expr_is_numeric(self, method, expected_default_value):
        rewriter = self.rewriter("a").substitute("a", 2)
        if callable(x := getattr(rewriter, method)):
            assert x() == expected_default_value or 2
        else:
            assert x == expected_default_value

    @pytest.mark.parametrize(
        "expression, symbol, assumption, simplified_expression, property",
        [
            ("max(0, a)", "a", "a > 0", "a", "is_positive"),
            ("min(0, a)", "a", "a < 0", "a", "is_negative"),
        ],
    )
    def test_add_assumption_simplifies_basic_expressions(
        self, expression, symbol, assumption, simplified_expression, property
    ):
        rewriter = self.rewriter(expression)
        assert getattr(rewriter.get_symbol(symbol), property, None) is None

        rewriter = rewriter.assume(assumption)
        assert str(rewriter.expression) == simplified_expression
        assert getattr(rewriter.get_symbol(symbol), property)

    def test_more_complex_expressions_have_assumptions_applied(self, backend):
        expr = "b*max(1 + log(2*x/5), 5) + c * d"
        rewriter = self.rewriter(expr).assume("log(2*x/5) > 4")
        assert rewriter.expression == backend.as_expression("b*(log(2*x/5) + 1) + c*d")

    @pytest.mark.parametrize(
        "expression, expr_to_replace, replace_with, final_expression",
        [
            [CommonExpressions.TRIVIAL, "a", "b", "b"],
            [CommonExpressions.SUM_AND_MUL, "a + b", "X", "X + c + d + c*d + a*b"],
            [
                CommonExpressions.MANY_FUNCS,
                "a*log2(x/n)",
                "A(x)",
                "A(x) + b*(max(0, 1+y, 2+x) + Heaviside(aleph, beth))",
            ],
            [CommonExpressions.NESTED_MAX, "max(b, 1 - max(c, lamda))", "1-lamda", "max(a, lamda)"],
        ],
    )
    def test_basic_substitutions(self, backend, expression, expr_to_replace, replace_with, final_expression):

        assert self.rewriter(expression).substitute(expr_to_replace, replace_with).expression == backend.as_expression(
            final_expression
        )

    def test_substitutions_are_tracked_correctly(self, backend):
        rewriter = self.rewriter(CommonExpressions.MANY_FUNCS)
        substitutions = (
            ("x/n", "z"),
            ("a*log2(z)", "A"),
            ("Heaviside(aleph, beth)", "h"),
            ("b*(max(0, 1+y, 2+x) + h)", "B"),
        )
        for _expr, _repl in substitutions:
            rewriter = rewriter.substitute(_expr, _repl)

        assert rewriter.expression == backend.as_expression("A+B")
        assert rewriter.substitutions == tuple(Substitution(x, y, rewriter.backend) for x, y in substitutions)
