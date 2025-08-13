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
from dataclasses import dataclass, field
from typing import cast

from sympy import Add, Expr, Function, Max, Min, Number, Symbol, Wild
from typing_extensions import Self

from bartiq.analysis.rewriters.expression import ExpressionRewriter
from bartiq.analysis.rewriters.utils import (
    Assumption,
    Substitution,
    _unwrap_linked_symbols,
)
from bartiq.symbolics.sympy_backend import SympyBackend
from bartiq.symbolics.sympy_interpreter import Max as CustomMax

_SYMPY_BACKEND = SympyBackend(use_sympy_max=True)


@dataclass
class SympyExpressionRewriter(ExpressionRewriter[Expr]):
    """Rewrite SymPy expressions.

    This class accepts a SymPy expression as input, and provides methods for efficient
    simplification / rewriting of the input expression.
    """

    backend: SympyBackend = field(init=False)

    def __post_init__(self):
        self.backend = _SYMPY_BACKEND
        if isinstance(self.expression, (int, float)):
            self.expression = Number(self.expression)

    @property
    def original(self) -> Self:
        """Return a rewriter with the original expression, and no modifications."""
        return type(self)(expression=self._original_expression, _original_expression=self._original_expression)

    @property
    def free_symbols(self) -> set[Expr]:
        return getattr(self.expression, "free_symbols", set())

    @property
    def individual_terms(self) -> Iterable[Expr]:
        return Add.make_args(self.expression)

    def _expand(self) -> Expr:
        """Expand all brackets in the expression."""
        return self.expression.expand()

    def _simplify(self) -> Expr:
        """Run SymPy's `simplify` method on the expression."""
        return self.expression.simplify()

    def get_symbol(self, symbol_name: str) -> Symbol | None:
        """Get the SymPy Symbol object, given the Symbol's name.

        If the symbol does not exist in the expression, return None.

        Args:
            symbol_name: Name of the symbol.

        Returns:
            A SymPy Symbol object, or None.
        """
        try:
            return next(sym for sym in self.free_symbols if sym.name == symbol_name)
        except StopIteration:
            return None

    def focus(self, symbols: str | Iterable[str]) -> Expr | None:
        """Focus on specific symbol(s), by only showing terms in the expression that include the input symbols.

        Args:
            symbols: symbol name(s) to focus on.

        Returns:
            A SymPy expression whose terms include the input symbols. If none are found, returns None.
        """
        symbols = [symbols] if isinstance(symbols, str) else list(symbols)
        symbols += _unwrap_linked_symbols(self.linked_symbols, symbols)

        variables = set(x for sym in symbols if (x := self.get_symbol(sym)))

        if terms_found := [term for term in self.individual_terms if not term.free_symbols.isdisjoint(variables)]:
            return sum(terms_found).collect(variables)
        return None

    def all_functions_and_arguments(self) -> set[Expr]:
        """Get a set of all unique functions and their arguments in the expression.

        The returned set will include all functions at every level of the expression, i.e.

        All functions and arguments of the following expression:
        ```python
        max(a, 1 - max(b, 1 - max(c, lamda)))
        ```
        would be returned as:
        ```python
        {
            Max(c, lamda),
            Max(b, 1 - Max(c, lamda)),
            Max(a, 1 - Max(b, 1 - Max(c, lamda)))
        }
        ```

        Returns:
            A set of unique functions that exist in the expression.

        """
        return self.expression.atoms(Function, Max, Min)

    def list_arguments_of_function(self, function_name: str) -> list[tuple[Expr, ...] | Expr]:
        """Return a list of arguments X, such that each `function_name(x)` (for x in X) exists in the expression.

        Args:
            function_name: function name to return the arguments of.

        Returns:
            A list of arguments of the input function.
                    If the function takes multiple arguments, they are returned as a tuple in the order they appear.
        """
        return [
            tuple(_arg for _arg in _func.args if (_arg or _arg == 0)) if len(_func.args) > 1 else _func.args[0]
            for _func in self.all_functions_and_arguments()
            if _func.__class__.__name__.lower() == function_name.lower()
        ]

    def _assume(self, assumption: Assumption) -> Expr:
        """Add an assumption to our expression."""
        expression = self.expression

        if reference_symbol := self.get_symbol(symbol_name=assumption.symbol_name):
            replacement = Symbol(assumption.symbol_name, **assumption.symbol_properties)
            expression = expression.subs({reference_symbol: replacement})
            reference_symbol = replacement
        else:
            reference_symbol = (expr := cast(Expr, self.backend.as_expression(assumption.symbol_name))).subs(
                {fs: sym for fs in expr.free_symbols if (sym := self.get_symbol(fs.name))}
            )
        replacement_symbol = Symbol(name="__", **assumption.symbol_properties)
        # This is a hacky way to implement assumptions that relate to nonzero values.
        expression = expression.subs({reference_symbol: replacement_symbol + assumption.value}).subs(
            {replacement_symbol: reference_symbol - assumption.value}
        )
        return expression

    def _substitute(self, substitution: Substitution) -> Expr:
        """Substitute a symbol or expression with another symbol or expression.

        Also permits wildcard substitutions by prefacing a variable with '$'.
        Wildcard symbols are considered to be nonzero.

        Args:
            substitution: A substitution instruction.

        Example::
        ```python
            rewriter = SympyExpressionRewriter(a + b)
            rewriter = rewriter.substitute("a+b", "c")
            print(rewriter.expression) # c
        ```
        and for wildcard substitutions:
        ```python
            rewriter = SympyExpressionRewriter(log(x + 1) + log(y + 4) + log(z + 6))
            rewriter = rewriter.substitute("log($x + $y)", "f(x, y)")
            print(rewriter.expression) # f(1, x) + f(4, y) + f(6, z)
        ```
        More precise control over symbols is possible. Passing in a variable "$N" indicates
        that this symbol should be a _number only_. Any other capital letter (or capitalised word)
        will be flagged as _symbol only_. For example:
        ```python
            rewriter = SympyExpressionRewriter(log(x + 1) + log(y + 4) + log(z + 6))
            rewriter = rewriter.substitute("log($X + $N)", "f(X, N)")
            print(rewriter.expression) # f(x, 1) + f(y, 4) + f(z, 6)
        ```
        Any other symbol will match _anything_ except zero values.
        """

        if substitution.wild:
            return self._wildcard_substitution(substitution)

        _symbol_or_expr = cast(Expr, self.backend.as_expression(substitution.expr))
        _replacement = self.backend.as_expression(substitution.replacement)
        return self.expression.subs(
            _symbol_or_expr.subs({fs: sym for fs in _symbol_or_expr.free_symbols if (sym := self.get_symbol(fs.name))}),
            _replacement,
        )

    def _wildcard_substitution(self, substitution: Substitution) -> Expr:
        """Wildcard substitution in Sympy.

        This performs recursive pattern matching on the expression at every level of the expression tree."""
        NONZERO = lambda x: x != 0
        SYMBOL_ONLY = lambda expr: expr.is_Symbol
        NUMBER_ONLY = lambda expr: expr.is_Number

        def parse_and_sub_wild(expr: str) -> Expr:
            return self.backend.substitute(self.backend.as_expression(expr.replace("$", "")), wildcard_dict)

        wildcard_dict: dict[str, Wild] = {}
        for sym in substitution.wild:
            if sym[0] == "N":
                wildcard_dict[sym] = Wild(sym, properties=[NONZERO, NUMBER_ONLY])
            elif sym[0].isupper():
                wildcard_dict[sym] = Wild(sym, properties=[NONZERO, SYMBOL_ONLY])
            else:
                wildcard_dict[sym] = Wild(sym, properties=[NONZERO])
        pattern = parse_and_sub_wild(substitution.expr)
        replacement = parse_and_sub_wild(substitution.replacement)

        return _replace_subexpression(
            self.expression, pattern, Number(replacement) if isinstance(replacement, (int, float)) else replacement
        )


def sympy_rewriter(expression: str | Expr) -> SympyExpressionRewriter:
    """Initialize a Sympy rewriter instance.

    Args:
        expression: An expression to rewrite, either str or sympy.Expr.

    Returns:
        An instance of the SympyExpressionRewriter.
    """
    if isinstance(expression, Expr):
        expression = expression.replace(CustomMax, Max)

    return SympyExpressionRewriter(
        expression=(expr := _SYMPY_BACKEND.as_expression(expression)), _original_expression=expr
    )


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

    if isinstance(expression, (Symbol, Number)):
        return expression

    def _all_values_numeric(values: Iterable[Expr | Number]) -> bool:
        return all(isinstance(x, Number) for x in values)

    replaced_expr = (
        replacement.subs(matches)
        if (matches := expression.match(pattern)) and not _all_values_numeric(matches.values())
        else expression
    )

    if args := getattr(replaced_expr, "args", None):
        replaced_expr = replaced_expr.__class__(
            *tuple(_replace_subexpression(arg, pattern, replacement) for arg in args)
        )

    return replaced_expr
