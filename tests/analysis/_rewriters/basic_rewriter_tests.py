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
from enum import Enum

import pytest

from bartiq.analysis._rewriters.expression_rewriter import ExpressionRewriter
from bartiq.symbolics.backend import SymbolicBackend


class CommonExpressions(str, Enum):
    """Expressions to test rewriters on."""

    TRIVIAL = "a"
    "Trivial expression; a single symbol."

    SUM_AND_MUL = "a + b + c + d + c*d + a*b"
    "An expression with sums and multiplications."

    MANY_FUNCS = "a*log2(x/n) + b*(max(0, 1+y, 2+x) + Heaviside(aleph, beth))"
    "An expression with different non-trivial functions."

    NESTED_MAX = "max(a, 1 - max(b, 1 - max(c, lamda)))"
    "An expression with nested max functions."


class ExpressionRewriterTests:
    rewriter: type[ExpressionRewriter]
    backend: type[SymbolicBackend]

    def assert_expression_seqs_equal(self, actual, expected):
        assert len(actual) == len(expected) and set(actual) == set(map(self.backend.as_expression, expected))

    @pytest.mark.parametrize(
        "expression, expected_individual_terms",
        [
            [CommonExpressions.TRIVIAL, ["a"]],
            [CommonExpressions.SUM_AND_MUL, ["a", "b", "c", "d", "c*d", "a*b"]],
            [
                CommonExpressions.MANY_FUNCS,
                ["a*log2(x/n)", "b*(Heaviside(aleph, beth) + max(0, x + 2, y + 1))"],
            ],
        ],
    )
    def test_individual_terms(self, expression, expected_individual_terms):
        self.assert_expression_seqs_equal(self.rewriter(expression).individual_terms, expected_individual_terms)

    @pytest.mark.parametrize(
        "expression",
        [
            CommonExpressions.TRIVIAL,
            CommonExpressions.SUM_AND_MUL,
            CommonExpressions.MANY_FUNCS,
            CommonExpressions.NESTED_MAX,
        ],
    )
    def test_free_symbols(self, expression):
        free_symbols_from_rewriter = self.rewriter(expression).free_symbols
        free_symbols_from_backend = self.backend.free_symbols(self.backend.as_expression(expression))
        self.assert_expression_seqs_equal(free_symbols_from_rewriter, free_symbols_from_backend)

    @pytest.mark.parametrize("focus_on, expected_expression", [["a", "a*(b+1)"], ["c", "c*(d+1)"]])
    def test_focus(self, focus_on, expected_expression):

        assert self.rewriter(CommonExpressions.SUM_AND_MUL).focus(focus_on) == self.backend.as_expression(
            expected_expression
        )

    def test_sequence_of_commands(self):
        rewriter = self.rewriter(CommonExpressions.MANY_FUNCS)
        rewriter.evaluate_expression(assignments={"x": 10})
        assert rewriter.expression == self.backend.as_expression(
            "a*log2(10/n) + b*(max(0, 1+y, 12) + Heaviside(aleph, beth))"
        )

        with pytest.raises(ValueError, match="No variable"):
            rewriter.focus("x")
        rewriter.evaluate_expression(assignments={"y": 1})
        assert rewriter.expression == self.backend.as_expression("a*log2(10/n) + b*(Heaviside(aleph, beth) + 12)")
        rewriter.expand()
        assert rewriter.focus("aleph") == self.backend.as_expression("b*Heaviside(aleph, beth)")

    def test_assumptions_update_the_expression_and_are_stored(self):
        rewriter = self.rewriter(CommonExpressions.MANY_FUNCS)
        rewriter.add_assumption("y > 0")
        assert rewriter.focus("y") != self.backend.as_expression("b*(Heaviside(aleph, beth) + Max(x + 2, y + 1))")
        assert str(rewriter.focus("y")) == str(
            self.backend.as_expression("b*(Heaviside(aleph, beth) + Max(x + 2, y + 1))")
        )
