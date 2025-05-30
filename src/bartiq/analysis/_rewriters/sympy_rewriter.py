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

from sympy import Add, Basic, Expr, Function, Max, Symbol

from bartiq import sympy_backend
from bartiq.analysis._rewriters.expression_rewriter import (
    ExpressionRewriter,
    ResourceRewriter,
    update_expression,
)


class SympyExpressionRewriter(ExpressionRewriter[Basic]):
    """Rewrite SymPy expressions.

    Args:
        expression: The sympy expression to rewrite.
    """

    def __init__(self, expression: Expr):
        super().__init__(expression=expression, backend=sympy_backend)

    @property
    def free_symbols_in(self) -> set[Basic]:
        return self.expression.free_symbols

    @property
    def as_individual_terms(self) -> Iterable[Expr]:
        return Add.make_args(self.expression)

    @update_expression
    def expand(self) -> Expr:
        """Expand all brackets in the expression."""
        return self.expression.expand()

    @update_expression
    def simplify(self) -> Expr:
        """Run SymPy's `simplify` method on the expression."""
        return self.expression.simplify()

    def get_symbol(self, symbol_name: str) -> Symbol:
        """Get the SymPy Symbol object, given the Symbol's name.

        Args:
            symbol_name: Name of the symbol.

        Raises:
            ValueError: If no Symbol with the input name is in the expression.
        """
        try:
            return next(sym for sym in self.free_symbols_in if sym.name == symbol_name)
        except StopIteration:
            raise ValueError(f"No variable '{symbol_name}'.")

    def focus(self, symbols: str | Iterable[str]) -> Expr:
        """Return a reduced version of the expression, where only terms that include the input symbols are shown.

        Args:
            symbols: symbol name(s) to focus on.
        """
        variables = set(map(self.get_symbol, [symbols] if isinstance(symbols, str) else symbols))
        return sum([term for term in self.as_individual_terms if term.free_symbols & variables]).collect(variables)

    def all_functions_and_arguments(self) -> set[Expr]:
        """Get a set of all unique functions and their arguments in the expression.

        The returned set will include all functions at every level of the expression, i.e.

        All functions and arguments of the following expression:
        >>> max(a, 1 - max(b, 1 - max(c, lamda)))

        would be returned as:
        >>> {
        >>> Max(c, lamda),
        >>> Max(b, 1 - Max(c, lamda)),
        >>> Max(a, 1 - Max(b, 1 - Max(c, lamda)))
        >>> }
        """
        return self.expression.atoms(Function, Max)

    def list_arguments_of_function(self, function_name: str) -> list[tuple[Expr, ...] | Expr]:
        """Return a list of arguments X, such that each function_name(x) (for x in X) exists in the expression.

        Args:
            function_name: function name to return the arguments of.
        """
        return [
            tuple(_arg for _arg in _func.args if (_arg or _arg == 0)) if len(_func.args) > 1 else _func.args[0]
            for _func in self.all_functions_and_arguments()
            if _func.__class__.__name__.lower() == function_name.lower()
        ]


class SympyResourceRewriter(ResourceRewriter):
    """A class for rewriting sympy resource expressions in routines.

    By default, this class only acts on the top level resource. In the future, the ability to propagate
    a list of instructions through resources in a routine hierarchy will be made available.
    """

    _rewriter = SympyExpressionRewriter
