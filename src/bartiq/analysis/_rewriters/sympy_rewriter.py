from collections.abc import Iterable
from bartiq import sympy_backend
from bartiq.analysis._rewriters._expression_rewriter import ExpressionRewriter, ResourceRewriter, update_expression
from sympy import Symbol, Expr, Add, Function, Max, Basic


class SympyExpressionRewriter(ExpressionRewriter[Basic]):
    """A class to rewrite SymPy expressions.

    Args:
        expression: The sympy expression to rewrite.
    """

    def __init__(self, expression: Expr):
        super().__init__(expression=expression, backend=sympy_backend)

    @property
    def variables(self) -> set[Basic]:
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

        Returns:
            Symbol
        """
        try:
            return next(sym for sym in self.variables if sym.name == symbol_name)
        except StopIteration:
            raise ValueError(f"No variable '{symbol_name}'.")

    def focus(self, variables: str | Iterable[str]) -> Expr:
        """Return terms that involve only those variables passed.

        Args:
            variables: a symbol name, or iterable of symbol names, to focus on.

        Returns:
            Expr
        """
        variables = set(map(self.get_symbol, [variables] if isinstance(variables, str) else variables))
        return sum([term for term in self.as_individual_terms if term.free_symbols & variables]).collect(variables)

    def all_functions_and_arguments(self) -> set[Expr]:
        """Get a set of all functions and their arguments in the expression.

        The returned set will include all functions at every level of the expression, i.e.

        All functions and arguments of the following expression:
        >>> max(a, 1 - max(b, 1 - max(c, lamda)))

        iokolwould be returned as:
        >>> {
        >>> Max(c, lamda),
        >>> Max(b, 1 - Max(c, lamda)),
        >>> Max(a, 1 - Max(b, 1 - Max(c, lamda)))
        >>> }

        Returns:
            set[Expr]
        """
        return self.expression.atoms(Function, Max)

    def list_arguments_of_function(self, function_name: str) -> list[tuple[Expr, ...] | Expr]:
        """Return a list of all arguments of a named function.

        Args:
            function_name: function name

        Returns:
            list[tuple[Expr, ...]]
        """
        return [
            tuple(_arg for _arg in _func.args if (_arg or _arg == 0)) if len(_func.args) > 1 else _func.args[0]
            for _func in self.all_functions_and_arguments()
            if _func.__class__.__name__.lower() == function_name.lower()
        ]


class SympyResourceRewriter(ResourceRewriter):
    """A class for rewriting sympy expressions across entire routines."""

    _rewriter = SympyExpressionRewriter
