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

from bartiq.analysis._rewriters.assumptions import Assumption, Relationals
from bartiq.analysis._rewriters.sympy_rewriter import _create_symbol_from_assumption


@pytest.mark.parametrize(
    "string, expected_attributes",
    [
        ["a>0", ("a", Relationals.GREATER_THAN, 0)],
        ["ceiling(log(a + y) / 4) <= 55", ("ceiling(log(a+y)/4)", Relationals.LESS_THAN_OR_EQUAL_TO, 55)],
    ],
)
def test_from_string(string, expected_attributes):
    from_str = Assumption.from_string(string)
    name, relationship, val = expected_attributes
    assert from_str.symbol_name == name
    assert from_str.relationship == relationship
    assert from_str.value == val


def test_error_raised_if_symbol_on_both_sides_of_relationship():
    with pytest.raises(NotImplementedError, match="Assumption tries to draw a relationship between two variables"):
        Assumption(symbol_name="Y", relationship="<=", value="X")


@pytest.mark.parametrize(
    "assumption, properties_it_has, properties_it_doesnt",
    [
        [
            Assumption(symbol_name="X", relationship=Relationals.GREATER_THAN, value=0),
            ["is_positive"],
            ["is_negative"],
        ],
        [
            Assumption(symbol_name="X", relationship=Relationals.GREATER_THAN_OR_EQUAL_TO, value=5),
            ["is_positive"],
            ["is_negative"],
        ],
        [
            Assumption(symbol_name="X", relationship=Relationals.LESS_THAN, value=0),
            ["is_negative"],
            ["is_positive"],
        ],
    ],
)
def test_symbol_creation_has_correct_properties(assumption, properties_it_has, properties_it_doesnt):
    sym = _create_symbol_from_assumption(assumption)
    for property in properties_it_has:
        assert getattr(sym, property)

    for property in properties_it_doesnt:
        assert not getattr(sym, property)


@pytest.mark.parametrize(
    "assumption, properties_should_be_none",
    [
        [
            Assumption(symbol_name="X", relationship=Relationals.LESS_THAN, value=10),
            ["is_positive", "is_negative"],
        ],
        [
            Assumption(symbol_name="X", relationship=Relationals.GREATER_THAN, value=-10),
            ["is_positive", "is_negative"],
        ],
    ],
)
def test_unknowable_properties_are_none(assumption, properties_should_be_none):
    sym = _create_symbol_from_assumption(assumption)
    for property in properties_should_be_none:
        assert getattr(sym, property) is None
