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

import warnings

from sympy import Expr, Function, Poly, Symbol, prod


class BigO:
    def __init__(self, expr: Expr, variable: Symbol | None = None):
        """Class for representing expressions in Big O notation.

        It analyzes given expression and returns all the Big O terms in it.
        If variable is provided, it analyses scaling in this particular variable,
        otherwise it assumes all the symbols are variables.

        Note:
            It's an experimental tool and is meant to facilitate the analysis, but
            it might not produce correct results, especially for more complicated
            expressions. In case of any problems please create an issue on project's GitHub,
            we'd love to hear your feedback on this!

        Args:
            expr: sympy expression we want to analyze
            variable: variable for which we want to performa analysis.
        """
        if variable is None:
            gens = []
        else:
            gens = [variable]
        self.expr = _convert_to_big_O(expr, gens)

    def __add__(self, other):
        if isinstance(other, self.__class__):
            return BigO(_remove_big_O_function(self.expr) + _remove_big_O_function(other.expr))
        else:
            return BigO(_remove_big_O_function(self.expr) + _remove_big_O_function(other))

    def __eq__(self, other):
        return self.expr == other.expr

    def __mul__(self, other):
        if isinstance(other, self.__class__):
            return BigO(_remove_big_O_function(self.expr) * _remove_big_O_function(other.expr))
        else:
            return BigO(_remove_big_O_function(self.expr) * _remove_big_O_function(other))

    def __repr__(self) -> str:
        return f"{self.expr}"


def _remove_big_O_function(expr: Expr) -> Expr:
    args = expr.args
    new_args = []
    for arg in args:
        if isinstance(arg, Function("O")):
            assert len(arg.args) == 1
            new_args.append(arg.args[0])
        else:
            new_args.append(arg)
    return sum(new_args)


def _add_big_o_function(expr: Expr) -> Expr:
    if isinstance(expr, Function("O")):
        return expr
    return Function("O")(expr)


def _convert_to_big_O(expr: Expr, gens: list[Expr] | None = None) -> Expr:
    gens = gens or []
    if len(expr.free_symbols) == 0:
        return _add_big_o_function(1)
    if len(expr.free_symbols) > 1 and len(gens) == 0:
        warnings.warn(
            "Results for using BigO with multiple variables might be unreliable. "
            "For better results please select a variable of interest."
        )
    poly = Poly(expr, *gens)
    leading_terms = _get_leading_terms(poly)
    return sum(map(_add_big_o_function, leading_terms))


def _get_leading_terms(poly):
    terms, _ = zip(*poly.terms())
    leading_terms = []
    for term in terms:
        if not _term_less_than_or_equal_to_all_others(term, leading_terms):
            leading_terms.append(term)

    return [_make_term_expression(poly.gens, leading_term) for leading_term in leading_terms]


def _term_less_than_or_equal_to_all_others(candidate, other_terms):
    if not other_terms:
        return False

    return all(_less_than(candidate, term) for term in other_terms)


def _less_than(term_1, term_2):
    return all(a <= b for a, b in zip(term_1, term_2))


def _make_term_expression(gens, term):
    powers = [gen**order for gen, order in zip(gens, term)]
    return prod(powers)
