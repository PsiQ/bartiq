from collections.abc import Iterable

from bartiq import sympy_backend
from bartiq.analysis._symbolic_manipulator import Manipulator, update_expression

from sympy import Expr, Add, Symbol


class SympyManipulator(Manipulator):
    """A class for manipulating and simplifying SymPy expressions."""

    def __init__(self, routine, resource):
        super().__init__(routine=routine, resource=resource, backend=sympy_backend)

    @property
    def variables(self) -> set[Symbol]:
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
            symbol_name: Name ofthe symbol.

        Raises:
            ValueError: If no Symbol with the input name is in the expression.

        Returns:
            Symbol
        """
        try:
            return next(sym for sym in self.variables if sym.name == symbol_name)
        except StopIteration:
            raise ValueError(f"No variable '{symbol_name}'.")

    @update_expression
    def substitute(self, pattern_to_replace: Expr, replace_with: Expr):
        raise NotImplementedError("Substitutions not yet implemented.")

    def focus(self, variables: str | Iterable[str]) -> Expr:
        """Return an expression that only contains terms containing specific variables.

        Args:
            variables: a symbol name, or iterable of symbol names, to focus on.

        Returns:
            Expr
        """
        variables = set(map(self.get_symbol, [variables] if isinstance(variables, str) else variables))
        return self.expression.__class__(*[x for x in self.expression.args if x.free_symbols & variables]).collect(
            variables
        )


if __name__ == "__main__":
    import dill

    with open("brno.dill", "rb") as f:
        routine = dill.load(f)
    c = SympyManipulat(routine=routine, resource="active_volume")
    print(c.variables)
    c.expression = routine.resources["t_gates"].value
    print(c.variables)
