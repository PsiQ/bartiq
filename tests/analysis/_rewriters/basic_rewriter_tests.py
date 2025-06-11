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

from bartiq.analysis._rewriters.expression_rewriter import ExpressionRewriter
from bartiq.symbolics.backend import SymbolicBackend


class ExpressionRewriterTests:
    rewriter: type[ExpressionRewriter]
    backend: type[SymbolicBackend]

    @pytest.fixture(scope="function")
    def trivial(self) -> ExpressionRewriter:
        return self.rewriter("a")

    @pytest.fixture(scope="function")
    def sum_and_mul(self) -> ExpressionRewriter:
        return self.rewriter("a + b + c + d + c*d + a*b")

    @pytest.fixture(scope="function")
    def many_funcs(self) -> ExpressionRewriter:
        return self.rewriter("a*log2(x/n) + b*(max(0, 1+y, 2+x) + Heaviside(aleph, beth))")

    @pytest.fixture(scope="function")
    def nested_max(self) -> ExpressionRewriter:
        return self.rewriter("max(a, 1 - max(b, 1 - max(c, lamda)))")

    def test_trivial(trivial):
        assert trivial.evaluate_expression({"a": 10}) == 10

    @pytest.mark.parametrize(
        "expression, individual_terms",
        [
            ["trivial", ["a"]],
            ["sum_and_mul", ["a", "b", "c", "d", "c*d", "a*b"]],
            [
                "many_funcs",
                ["a*log2(x/n)", "b*(max(0, 1+y, 2+x) + Heaviside(aleph, beth))"],
            ],
        ],
    )
    def test_individual_terms(self, expression, individual_terms, request):
        assert set(request.getfixturevalue(expression).individual_terms) == set(
            map(self.backend.as_expression, individual_terms)
        )

    @pytest.mark.parametrize("fixture", ["trivial", "sum_and_mul", "many_funcs", "nested_max"])
    def test_free_symbols(self, fixture, request):
        rewriter = request.getfixturevalue(fixture)
        assert set(rewriter.free_symbols) == set(
            map(self.backend.as_expression, self.backend.free_symbols(rewriter.expression))
        )

    @pytest.mark.parametrize("focus_on, expected_expression", [["a", "a*(b+1)"], ["c", "c*(d+1)"]])
    def test_focus(self, focus_on, expected_expression, sum_and_mul):
        assert sum_and_mul.focus(focus_on) == self.backend.as_expression(expected_expression)
