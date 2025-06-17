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

from collections.abc import Iterable
from typing import cast

from sympy import Add, Expr, Function, Max, Min, Symbol

from bartiq import sympy_backend
from bartiq.analysis._rewriters.assumptions import SympyAssumption
from bartiq.analysis._rewriters.expression_rewriter import (
    ExpressionRewriter,
    ResourceRewriter,
    TExpr,
)
from bartiq.symbolics.sympy_interpreter import Max as CustomMax


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

    def _add_assumption(self, assume: str | SympyAssumption) -> TExpr[Expr]:
        """Add an assumption to our expression."""
        assumption = assume if isinstance(assume, SympyAssumption) else SympyAssumption.from_string(assume)
        try:
            # If the Symbol exists, replace it with a Symbol that has the correct properties.
            reference_symbol = self.get_symbol(symbol_name=assumption.symbol_name)
            replacement = assumption.to_symbol()
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


class SympyResourceRewriter(ResourceRewriter[Expr]):
    """A class for rewriting sympy resource expressions in routines.

    By default, this class only acts on the top level resource. In the future, the ability to propagate
    a list of instructions through resources in a routine hierarchy will be made available.
    """

    _rewriter = SympyExpressionRewriter
