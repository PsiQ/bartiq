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
import pytest

from bartiq.symbolics.ast_parser import _preprocess


@pytest.mark.parametrize(
    "expression, expected_expression",
    [
        ("#in_0", "Port(in_0)"),
        ("a.#out_1", "a.Port(out_1)"),
        ("root.child.#port_0", "root.child.Port(port_0)"),
        ("~.n_toffs", "wildcard().n_toffs"),
        ("a~", "wildcard(a)"),
        ("b.test~.highwater", "b.wildcard(test).highwater"),
    ],
)
def test_preprocessing_expression_gives_one_with_incompatible_syntax_replaced(expression, expected_expression):
    assert _preprocess(expression) == expected_expression
