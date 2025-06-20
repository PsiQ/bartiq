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
"""A rewriter class for SymPy expressions."""

import re
from collections.abc import Iterable
from typing import cast

from sympy import Add, Expr, Function, Max, Min, Number, Symbol, Wild

from bartiq import sympy_backend
from bartiq.analysis._rewriters.assumptions import Assumption
from bartiq.analysis._rewriters.expression_rewriter import (
    ExpressionRewriter,
    ResourceRewriter,
    TExpr,
)
from bartiq.symbolics.sympy_interpreter import Max as CustomMax

WILDCARD_FLAG = "$"


class SympyExpressionRewriter(ExpressionRewriter[Expr]):
    """Rewrite SymPy expressions.

    This class accepts a SymPy expression as input, and provides methods for efficient simplification / rewriting of
    the input expression.

    Args:
        expression: The sympy expression of interest.
    """

    def __init__(self, expression: Expr):
        super().__init__(expression=expression, backend=sympy_backend)
        self.expression = cast(Expr, self.expression).replace(CustomMax, Max)

    @property
    def free_symbols(self) -> set[Expr]:
        return getattr(self.expression, "free_symbols", set())

    @property
    def individual_terms(self) -> Iterable[Expr]:
        return Add.make_args(self.expression)

    def _expand(self) -> TExpr[Expr]:
        """Expand all brackets in the expression."""
        if callable(expand := getattr(self.expression, "expand", None)):
            return expand()
        return self.expression

    def _simplify(self) -> TExpr[Expr]:
        """Run SymPy's `simplify` method on the expression."""
        if callable(simplify := getattr(self.expression, "simplify", None)):
            return simplify()
        return self.expression

    def get_symbol(self, symbol_name: str) -> Symbol:
        """Get the SymPy Symbol object, given the Symbol's name.

        Args:
            symbol_name: Name of the symbol.

        Returns:
            A SymPy Symbol object.

        Raises:
            ValueError: If no Symbol with the input name is in the expression.
        """
        try:
            return next(sym for sym in self.free_symbols if sym.name == symbol_name)
        except StopIteration:
            raise ValueError(f"No variable '{symbol_name}'.")

    def focus(self, symbols: str | Iterable[str]) -> Expr:
        """Focus on specific symbol(s), by only showing terms in the expression that include the input symbols.

        Args:
            symbols: symbol name(s) to focus on.

        Returns:
            A SymPy expression whose terms include the input symbols.
        """
        variables = set(map(self.get_symbol, [symbols] if isinstance(symbols, str) else symbols))
        return sum([term for term in self.individual_terms if not term.free_symbols.isdisjoint(variables)]).collect(
            variables
        )

    def all_functions_and_arguments(self) -> set[Expr]:
        """Get a set of all unique functions and their arguments in the expression.

        The returned set will include all functions at every level of the expression, i.e.

        All functions and arguments of the following expression:
        ```
        max(a, 1 - max(b, 1 - max(c, lamda)))
        ```
        would be returned as:
        ```
        {
            Max(c, lamda),
            Max(b, 1 - Max(c, lamda)),
            Max(a, 1 - Max(b, 1 - Max(c, lamda)))
        }
        ```

        Returns:
            A set of unique functions that exist in the expression.

        """
        if callable(atoms := getattr(self.expression, "atoms", None)):
            return atoms(Function, Max, Min)
        return set()

    def list_arguments_of_function(self, function_name: str) -> list[tuple[Expr, ...] | Expr]:
        """Return a list of arguments X, such that each function_name(x) (for x in X) exists in the expression.

        Args:
            function_name: function name to return the arguments of.

        Returns:
            A list of arguments of the input function. If the function takes multiple arguments,
            they are returned as a tuple in the order they appear.
        """
        return [
            tuple(_arg for _arg in _func.args if (_arg or _arg == 0)) if len(_func.args) > 1 else _func.args[0]
            for _func in self.all_functions_and_arguments()
            if _func.__class__.__name__.lower() == function_name.lower()
        ]

    def _add_assumption(self, assume: str | Assumption) -> TExpr[Expr]:
        """Add an assumption to our expression."""
        if isinstance(self.expression, int | float):
            return self.expression
        assumption = assume if isinstance(assume, Assumption) else Assumption.from_string(assume)
        try:
            # If the Symbol exists, replace it with a Symbol that has the correct properties.
            reference_symbol = self.get_symbol(symbol_name=assumption.symbol_name)
            replacement = _create_symbol_from_assumption(assume=assumption)
            self.expression = self.expression.subs({reference_symbol: replacement})
            reference_symbol = replacement
        except ValueError:
            # If the symbol does _not_ exist, parse the assumption expression.
            reference_symbol = self._backend.as_expression(assumption.symbol_name)

        # This is a hacky way to implement assumptions that relate to nonzero values.
        replacement_symbol = Symbol(name="__", **assumption.symbol_properties)
        self.expression = self.expression.subs({reference_symbol: replacement_symbol + assumption.value}).subs(
            {replacement_symbol: reference_symbol - assumption.value}
        )
        return self.expression

    def _substitute(self, symbol_or_expr: Expr | str, replace_with: Expr | str) -> TExpr[Expr]:
        """Substitute a symbol or expression with another symbol or expression.

        Also permits wildcard substitutions by prefacing a variable with '$'.
        """
        if _has_wildcard(symbol_or_expr):
            return self._wildcard_substitution(symbol_or_expr=symbol_or_expr, replace_with=replace_with)
        return self._backend.substitute(self.expression, {symbol_or_expr: replace_with})

    def _wildcard_substitution(self, symbol_or_expr: str, replace_with: Expr | str) -> TExpr[Expr]:
        wildcard_dict: dict[str, Wild] = {
            sym[1:]: Wild(sym[1:], properties=[lambda x: x != 0]) for sym in _get_wild_characters(symbol_or_expr)
        }
        pattern = (
            self._backend.as_expression(symbol_or_expr.replace(f"{WILDCARD_FLAG}", ""))
            .replace(CustomMax, Max)
            .subs(wildcard_dict)
        )
        replacement = self._backend.substitute(
            self._backend.as_expression(replace_with.replace(f"{WILDCARD_FLAG}", "")).replace(CustomMax, Max),
            wildcard_dict,
        )
        return _replace_subexpression(self.expression, pattern, replacement)


class SympyResourceRewriter(ResourceRewriter[Expr]):
    """A class for rewriting sympy resource expressions in routines.

    By default, this class only acts on the top level resource. In the future, the ability to propagate
    a list of instructions through resources in a routine hierarchy will be made available.
    """

    _rewriter = SympyExpressionRewriter


def _create_symbol_from_assumption(assume: Assumption) -> Symbol:
    return Symbol(assume.symbol_name, **assume.symbol_properties)


def _has_wildcard(expression: str):
    return WILDCARD_FLAG in expression


def _get_wild_characters(expression: str) -> list[str]:
    return re.findall(r"\$[a-zA-Z_][a-zA-Z0-9_]*", expression)


def _replace_subexpression(expression: Expr, pattern: Expr, replacement: Expr) -> Expr:
    """Recursively replace all subexpressions matching `pattern` inside `expression`
    with `replacement`, applying the matched substitutions.

    Args:
        expression: The top-level SymPy expression to process.
        pattern: The pattern expression to match against subexpressions.
        replacement: The expression to replace matches with (uses substitutions).

    Returns:
        The new expression with all matching subexpressions replaced.
    """
    if isinstance(replacement, int | float):
        replacement = Number(replacement)

    def _all_values_numeric(values: Iterable[Expr | Number]) -> bool:
        return all(isinstance(x, Number) for x in values)

    if any(isinstance(expression, t) for t in [Symbol, Number]):
        return expression

    replaced_expr = (
        replacement.subs(matches)
        if (matches := expression.match(pattern)) and not _all_values_numeric(matches.values())
        else expression
    )

    if hasattr(replaced_expr, "args") and replaced_expr.args:
        # new_args = tuple(_replace_subexpression(arg, pattern, replacement) for arg in replaced_expr.args)
        # if new_args != replaced_expr.args:
        replaced_expr = replaced_expr.__class__(
            *tuple(_replace_subexpression(arg, pattern, replacement) for arg in replaced_expr.args)
        )

    return replaced_expr
