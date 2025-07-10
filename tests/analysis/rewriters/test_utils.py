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
from sympy import Symbol

from bartiq.analysis.rewriters.utils import (
    WILDCARD_SYMBOL,
    Assumption,
    Comparators,
    Substitution,
)


class TestAssumption:
    @pytest.mark.parametrize(
        "string, expected_attributes",
        [
            ["a>0", ("a", Comparators.GREATER_THAN, 0)],
            ["ceiling(log(a + y) / 4) <= 55", ("ceiling(log(a+y)/4)", Comparators.LESS_THAN_OR_EQUAL_TO, 55)],
        ],
    )
    def test_from_string(self, string, expected_attributes):
        from_str = Assumption.from_string(string)
        name, comparator, val = expected_attributes
        assert from_str.symbol_name == name
        assert from_str.comparator == comparator
        assert from_str.value == val

    def test_error_raised_if_symbol_on_both_sides_of_comparator(self):
        with pytest.raises(NotImplementedError, match="Assumption tries to draw a comparison between two variables"):
            Assumption.from_string("X<=Y")

    def test_error_raised_if_invalid_string(self):
        with pytest.raises(ValueError, match="Invalid assumption!"):
            Assumption.from_string("Y&4")

    @pytest.mark.parametrize(
        "assumption, properties_it_has, properties_it_doesnt",
        [
            [
                Assumption(symbol_name="X", comparator=Comparators.GREATER_THAN_OR_EQUAL_TO, value=0),
                ["is_nonnegative"],
                ["is_nonpositive", "is_negative", "is_positive"],
            ],
            [
                Assumption(symbol_name="X", comparator=Comparators.GREATER_THAN_OR_EQUAL_TO, value=1),
                ["is_nonnegative", "is_positive"],
                ["is_nonpositive", "is_negative"],
            ],
            [
                Assumption(symbol_name="X", comparator=Comparators.GREATER_THAN, value=0),
                ["is_nonnegative", "is_positive"],
                ["is_nonpositive", "is_negative"],
            ],
            [
                Assumption(symbol_name="X", comparator=Comparators.LESS_THAN_OR_EQUAL_TO, value=0),
                ["is_nonpositive"],
                ["is_nonnegative", "is_positive", "is_negative"],
            ],
            [
                Assumption(symbol_name="X", comparator=Comparators.LESS_THAN_OR_EQUAL_TO, value=-1),
                ["is_nonpositive", "is_negative"],
                ["is_nonnegative", "is_positive"],
            ],
            [
                Assumption(symbol_name="X", comparator=Comparators.LESS_THAN, value=0),
                ["is_nonpositive", "is_negative"],
                ["is_nonnegative", "is_positive"],
            ],
        ],
    )
    def test_symbol_from_assumptions_has_correct_properties(self, assumption, properties_it_has, properties_it_doesnt):
        sym = Symbol(assumption.symbol_name, **assumption.symbol_properties)
        for property in properties_it_has:
            assert getattr(sym, property)

        for property in properties_it_doesnt:
            assert not getattr(sym, property)

    @pytest.mark.parametrize(
        "assumption, properties_should_be_none",
        [
            [
                Assumption(symbol_name="X", comparator=Comparators.LESS_THAN, value=10),
                ["is_nonnegative", "is_nonpositive", "is_positive", "is_negative"],
            ],
            [
                Assumption(symbol_name="X", comparator=Comparators.GREATER_THAN, value=-10),
                ["is_nonpositive", "is_nonnegative", "is_negative", "is_positive"],
            ],
        ],
    )
    def test_unknowable_properties_are_none(self, assumption, properties_should_be_none):
        sym = Symbol(assumption.symbol_name, **assumption.symbol_properties)
        for property in properties_should_be_none:
            assert getattr(sym, property) is None

    def test_assumption_raises_error_for_invalid_value_in_str(self):
        with pytest.raises(ValueError, match="Invalid entry for `value` field."):
            Assumption.from_string(r"x>{'a':1}")


def test_wildcard_symbol_didnt_change():
    assert WILDCARD_SYMBOL == "$"


class TestSubstitutions:
    @pytest.mark.parametrize(
        "symbol, replace_with, expected_wild_chars",
        [
            ("$x", "y", ("x",)),
            ("$x + $y + $Z", "", ("x", "y", "Z")),
            ("max($x, y) + log2($z + f) - Heaviside($F, l)", "", ("x", "z", "F")),
        ],
    )
    def test_wild_characters_are_defined_correctly(self, symbol, replace_with, expected_wild_chars, backend):
        assert Substitution(symbol, replace_with, backend).wild == expected_wild_chars

    @pytest.mark.parametrize(
        "symbol, replacement, linked_params",
        [
            ("x", "y", {"y": ("x",)}),
            ("max(a, b, c)", "X(b, c)", {}),
            ("max(a, b, c)", "g(x, y)", {"x": ("a", "b", "c"), "y": ("a", "b", "c")}),
        ],
    )
    def test_get_linked_parameters(self, symbol, replacement, linked_params, backend):
        compare_dicts(Substitution(symbol, replacement, backend).linked_params, linked_params)


def compare_dicts(dict1, dict2):
    assert dict1.keys() == dict2.keys()
    for key in dict1.keys():
        assert set(dict1[key]) == set(dict2[key])
