from __future__ import annotations
from typing import TypeAlias, TypeVar, Any
from collections.abc import Iterable, Callable

from bartiq import CompiledRoutine, sympy_backend
from bartiq.symbolics.backend import SymbolicBackend

from abc import ABC, abstractmethod

from sympy import Basic, Expr, Add, Symbol, sympify
from enum import Enum, auto


class InstructionTypes(Enum):
    """A collection of different instructions used during symbolic manipulation."""

    SIMPLIFY = auto()
    "Call the backend `simplify` functionality."
    EXPAND = auto()
    "Expand all brackets in the expression."
    EVALUATE = auto()
    "Evaluate the expression, either fully or partially."


def update_expression(function: Callable[[Any], Expr]):
    """Decorator for updating the stored expression in Manipulator."""

    def wrapper(self: Manipulator, *args, **kwargs):
        self.expression = function(self, *args, **kwargs)
        return self.expression

    return wrapper


class Manipulator(ABC):
    """A base class for symbolic manipulation, or simplification, tools.

    Args:
        routine: A compiled routine object.
        resource: A string indicating the resource we wish to act on.
        backend: Optional argument indicating the symbolic backend required, by default sympy_backend.
    """

    def __init__(self, routine: CompiledRoutine, resource: str, backend: SymbolicBackend):
        self.routine = routine
        self._expr = self.routine.resources[resource].value
        self.original_expression = self._expr

        self._backend = backend

    @property
    def expression(self) -> Expr:
        """Return the current form of the expression."""
        return self._expr

    @expression.setter
    def expression(self, other: Expr):
        self._expr = other

    @update_expression
    def evaluate_expression(
        self,
        variable_assignments: dict[str, float],
        original_expression: bool = False,
        functions_map: dict[str, Callable[[Any], int | float]] | None = None,
    ) -> Expr:
        """Assign explicit values to certain variables.

        Args:
            variable_assignments : A dictionary of (variable name: value) key, val pairs.
            original_expression: Whether or not to evaluate the original expression, by default False.
            functions_map: A map for certain functions.

        Returns:
            Expr
        """
        return self._backend.substitute(
            self.original_expression if original_expression else self.expression,
            replacements=variable_assignments,
            functions_map=functions_map,
        )

    @property
    @abstractmethod
    def variables(self) -> Iterable[Expr]:
        """Return the variable parameters in the expression."""

    @property
    @abstractmethod
    def as_individual_terms(self) -> Iterable[Expr]:
        """Return the expression as an iterable of individual terms."""

    @abstractmethod
    @update_expression
    def substitute(self, expression_to_replace: Expr, replace_with: Expr) -> None:
        """Substitute a pattern in the expression with a user-defined replacement."""

    def apply_history_to_routine(self, all_resources: bool = False) -> CompiledRoutine:
        raise NotImplementedError("Applying a sequence of instructions to entire routines is not yet implemented.")

    @abstractmethod
    @update_expression
    def expand(self) -> Expr:
        """Expand all brackets in the expression."""


class SympyManipulation(Manipulator):
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


if __name__ == "__main__":
    import dill

    with open("brno.dill", "rb") as f:
        routine = dill.load(f)
    c = SympyManipulation(routine=routine, resource="active_volume")
    print(c.variables)
    c.expression = routine.resources["t_gates"].value
    print(c.variables)
