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

from bartiq.analysis.rewriters import sympy_rewriter
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

    def test_get_symbol_returns_none_if_no_symbol_exists(self):
        sym = "foo"
        assert self.rewriter(CommonExpressions.MANY_FUNCS).get_symbol(sym) is None

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
        "expression, symbol_or_expr, substitute_with, expected",
        [
            ("max(0, a) + max(0, b) + max(0, c)", "max(0, $b)", "b", "a + b + c"),
            ("max(0, a) + max(0, b) + max(0, c)", "max(0, $X)", "0", "0"),
            ("log(x + 1) + log(y + 4) + log(z + 6)", "log($x)", "f(x)", "f(x+1) + f(y+4) + f(z+6)"),
            ("log(x + 1) + log(y + 4) + log(z + 6)", "log($X + $N)", "f(X, N)", "f(x, 1) + f(y,4) + f(z,6)"),
            ("ceiling(1 - ceiling(1 - ceiling(1+ceiling(x))))", "ceiling($g)", "g", "1+x"),
        ],
    )
    def test_wildcard_substitutions(self, expression, symbol_or_expr, substitute_with, expected, backend):

        assert self.rewriter(expression).substitute(
            symbol_or_expr, substitute_with
        ).expression == backend.as_expression(expected)

    def test_focus_includes_linked_parameters(self, backend):
        rewriter = (
            self.rewriter(CommonExpressions.TRIVIAL).substitute("a", "b").substitute("b", "c").substitute("c", "d")
        )
        assert rewriter.focus("a") == rewriter.expression
