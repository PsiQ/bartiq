from typing import Type

import pytest

from bartiq.analysis._rewriters.sympy_rewriter import ExpressionRewriter
from bartiq.symbolics.backend import SymbolicBackend


class ExpressionRewriterTests:
    rewriter: Type[ExpressionRewriter]
    backend = Type[SymbolicBackend]

    @pytest.fixture(scope="class")
    def trivial(self):
        return self.rewriter("a")

    @pytest.fixture(scope="class")
    def sum_and_mul(self):
        return self.rewriter("a + b + c + d + c*d + a*b")

    @pytest.fixture(scope="class")
    def many_funcs(self):
        return self.rewriter("a*log2(x/n) + b*(max(1+y, 2+x) + Heaviside(aleph, beth))")

    @pytest.fixture(scope="class")
    def nested_max(self):
        return self.rewriter("max(a, 1 - max(b, 1 - max(c, lamda)))")

    @pytest.mark.parametrize(
        "expression, individual_terms",
        [
            ["trivial", ["a"]],
            ["sum_and_mul", ["a", "b", "c", "d", "c*d", "a*b"]],
            [
                "many_funcs",
                ["a*log2(x/n)", "b*(max(1+y, 2+x) + Heaviside(aleph, beth))"],
            ],
        ],
    )
    def test_as_individual_terms(self, expression, individual_terms, request):
        assert set(request.getfixturevalue(expression).as_individual_terms) == set(
            map(self.backend.as_expression, individual_terms)
        )

    @pytest.mark.parametrize("fixture", ["trivial", "sum_and_mul", "many_funcs", "nested_max"])
    def test_variables(self, fixture, request):
        rewriter = request.getfixturevalue(fixture)
        assert rewriter.variables == rewriter.expression.free_symbols

    def test_expand(self):
        expr = self.backend.as_expression("(a + b)*c + d*(log2(x) + 5)")
        assert self.rewriter(expr).expand() == expr.expand()

    @pytest.mark.parametrize("focus_on, expected_expression", [["a", "a*(b+1)"], ["c", "c*(d+1)"]])
    def test_focus(self, focus_on, expected_expression, sum_and_mul):
        assert sum_and_mul.focus(focus_on) == self.backend.as_expression(expected_expression)
