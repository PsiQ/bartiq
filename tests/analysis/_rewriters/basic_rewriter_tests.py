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

from bartiq.analysis._rewriters.assumptions import Assumption
from bartiq.analysis._rewriters.expression_rewriter import (
    ExpressionRewriter,
    Instruction,
)
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

    @pytest.fixture
    def backend(self) -> SymbolicBackend:
        raise NotImplementedError("No `backend` fixture defined.")

    def assert_expression_seqs_equal(self, backend, actual, expected):
        assert len(actual) == len(expected) and set(actual) == set(map(backend.as_expression, expected))

    @pytest.mark.parametrize(
        "expression, expected_individual_terms",
        [
            [CommonExpressions.TRIVIAL, ["a"]],
            [CommonExpressions.SUM_AND_MUL, ["a", "b", "c", "d", "c*d", "a*b"]],
            [
                CommonExpressions.MANY_FUNCS,
                ["a*log2(x/n)", "b*(max(0, 1+y, 2+x) + Heaviside(aleph, beth))"],
            ],
        ],
    )
    def test_individual_terms(self, backend, expression, expected_individual_terms):
        self.assert_expression_seqs_equal(
            backend, self.rewriter(expression).individual_terms, expected_individual_terms
        )

    @pytest.mark.parametrize(
        "expression",
        [
            CommonExpressions.TRIVIAL,
            CommonExpressions.SUM_AND_MUL,
            CommonExpressions.MANY_FUNCS,
            CommonExpressions.NESTED_MAX,
        ],
    )
    def test_free_symbols(self, backend, expression):
        free_symbols_from_rewriter = self.rewriter(expression).free_symbols
        free_symbols_from_backend = backend.free_symbols(backend.as_expression(expression))
        self.assert_expression_seqs_equal(backend, free_symbols_from_rewriter, free_symbols_from_backend)

    @pytest.mark.parametrize("focus_on, expected_expression", [["a", "a*(b+1)"], ["c", "c*(d+1)"]])
    def test_focus(self, backend, focus_on, expected_expression):

        assert self.rewriter(CommonExpressions.SUM_AND_MUL).focus(focus_on) == backend.as_expression(
            expected_expression
        )

    def test_assumptions_are_properly_tracked(self):
        rewriter = self.rewriter(CommonExpressions.SUM_AND_MUL)
        for assumption in ["a>0", "b<0", "c>=0", "d<=10"]:
            rewriter = rewriter.assume(assumption)
        assert rewriter.assumptions == (
            Assumption("a", ">", 0),
            Assumption("b", "<", 0),
            Assumption("c", ">=", 0),
            Assumption("d", "<=", 10),
        )

    def test_history(self):
        init_rewriter = self.rewriter(CommonExpressions.MANY_FUNCS)
        updated_rewriter = init_rewriter.expand().simplify().assume("beth>0")
        assert updated_rewriter.history() == [
            Instruction.Initial,
            Instruction.Expand,
            Instruction.Simplify,
            "Assumption(beth>0)",
        ]

    def test_undo_previous(self):
        init_rewriter = self.rewriter(CommonExpressions.MANY_FUNCS)
        one_step = init_rewriter.expand()
        two_step = one_step.simplify()
        three_step = two_step.assume("beth>0")
        assert three_step.undo_previous() == two_step
        assert three_step.undo_previous(2) == one_step
        assert three_step.undo_previous(3) == init_rewriter
        assert one_step.undo_previous() == init_rewriter

    def test_original(self):
        initial = self.rewriter(CommonExpressions.TRIVIAL)
        assert initial.expand().simplify().assume("a>0").original == initial

    def test_undo_previous_raises_error_if_arg_too_large(self):
        with pytest.raises(ValueError, match="Attempting to undo too many operations!"):
            self.rewriter(CommonExpressions.MANY_FUNCS).expand().simplify().assume("a > 0").undo_previous(6)

    @pytest.mark.parametrize("invalid_int_arg", [0, -1])
    def test_undo_previous_raises_error_if_invalid_integer_arg(self, invalid_int_arg):
        with pytest.raises(ValueError, match="Can't undo fewer than one previous command."):
            self.rewriter(CommonExpressions.TRIVIAL).expand().simplify().undo_previous(invalid_int_arg)

    def test_reapply_all_assumptions(self):
        rewriter = self.rewriter(CommonExpressions.MANY_FUNCS)
        rewriter_1 = rewriter.assume("x>0").assume("y>0").assume("beth>0")
        assert rewriter_1.reapply_all_assumptions()._previous == (Instruction.ReapplyAllAssumptions, rewriter_1)
