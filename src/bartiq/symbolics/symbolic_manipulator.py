"""A prototype for manipulation symbolic expressions in sympy."""

from __future__ import annotations

import re
from enum import StrEnum
from collections.abc import Callable
from typing import Optional, Any
import warnings
import sympy
from sympy import Add, Expr, Symbol, Wild, Function
from bartiq.symbolics.sympy_backend import parse_to_sympy, sympy_backend


class _Relationships(StrEnum):
    GREATER_THAN_OR_EQUAL_TO = ">="
    LESS_THAN_OR_EQUAL_TO = "<="
    GREATER_THAN = ">"
    LESS_THAN = "<"
    NOT_EQUAL = "!="


_RELATIONSHIPS = list(_Relationships._value2member_map_.keys())

_SPLIT_BY: str = "(" + ")|(".join(_RELATIONSHIPS) + ")"

# WildCard properties
NONZERO = lambda k: k != 0  # noqa


def update_expression(function: Callable[[Any], Expr]):
    """Decorator for updating the stored expression in GSE."""

    def wrapper(self: GSE, *args, **kwargs):
        flag = kwargs.get("keep", True)
        out = function(self, *args, **kwargs)
        if flag:
            self.expression = out
            success = self._check_expression_update()
            if not success and not self.suppress_warnings:
                warnings.warn("Expression did not change.")
        return out

    return wrapper


class GSE:
    """Prototype class for manipulating gnarly symbolic expressions.

    This class packages a number of methods that can be used to modify
    the input expression to make it simpler, or more readable.

    Parameters
    ----------
    gnarly_symbolic_expression: sympy.Expr
        The top level expression.

    Attributes
    ----------
    expression: Expr
        The current state of the expression, including any modifications that have been applied.
    variables: list[str]
        The variable symbols in the expression.
    individual_terms: tuple[Expr,...]
        The individual terms of an expression returned as a tuple.
    subsititions: dict[Expr, Expr]
        A dictionary of the symbolic subsitutions that have been applied to the expression.
    """

    def _check_expression_update(self) -> bool:
        if len(self._history) == 1:
            return True
        return self._history[-1] != self._history[0]

    def __init__(
        self, gnarly_symbolic_expression: Expr, assumptions: Optional[list[str]] = None, suppress_warnings: bool = True
    ):
        self.gnarly = gnarly_symbolic_expression
        self.gnarly_terms = GSE._individual_terms(self.gnarly)

        self.suppress_warnings = suppress_warnings

        self._expression: Expr = gnarly_symbolic_expression
        self._variables: list[Symbol] = self.gnarly.free_symbols

        self.substitutions: dict[Symbol, Expr | Symbol] = {}
        self._history: list[Expr] = []

        self.assumptions = assumptions or []
        for assuming in self.assumptions:
            self.add_assumption(assume=assuming)

    @staticmethod
    def _individual_terms(expression: Expr) -> tuple[Expr, ...]:
        return Add.make_args(expression)

    def undo(self) -> None:
        """Undo the most recent update to the stored expression.

        Raises:
            IndexError: If there are no steps to undo.
        """
        if len(self._history) == 0:
            raise IndexError("Nothing to undo!")
        self.expression = self._history.pop()
        self._history.pop()

    @property
    def expression(self) -> Expr:
        """Return the current state of the expression.

        Returns:
            Expr
        """
        return self._expression

    @expression.setter
    def expression(self, new: Expr):
        self._history.append(self._expression)
        self._expression = new
        self._variables = new.free_symbols

    @property
    def variables(self) -> list[Symbol]:
        """Return a list of the current variables in the expression.

        Returns:
            list[str]
        """
        return self._variables

    @property
    def individual_terms(self) -> tuple[Expr, ...]:
        """Return the expression as a tuple of its individual terms.

        Returns:
            tuple[Expr, ...]
        """
        return GSE._individual_terms(self.expression)

    def _get_symbol(self, symbol_name: str) -> Symbol:
        """Return a Symbol object given its name.

        Args:
            symbol_name (str): A symbol name.

        Raises:
            ValueError: If a symbol with the given name does not exist.

        Returns:
            Symbol: The relevant symbol object.
        """
        try:
            return next(sym for sym in self.expression.free_symbols if sym.name == symbol_name)
        except StopIteration:
            raise ValueError(f"No variable '{symbol_name}'.")

    @update_expression
    def wildcard_pattern_replacement(
        self, pattern: str, replacement: str, allow_zeroes: bool = False, *, keep: bool = True
    ) -> Expr:
        """Replace a pattern in the expression with another.
        Free variables in the `pattern` kwarg are assumed to be wildcards.

        Args:
            pattern (str): Pattern to replace.
            replacement (str): Replacement pattern.
            allow_zeroes: Allow wildcards to be zero-valued, defaults to False.
            keep (bool, optional): Whether or not to keep the modification. Defaults to True.

        Returns:
            Expr
        """
        wildcard_dict = {
            sym: Wild(str(sym), properties=[] if allow_zeroes else [NONZERO], nonzero=True)
            for sym in parse_to_sympy(pattern).free_symbols
        }
        pattern = parse_to_sympy(pattern).subs(wildcard_dict)
        replacement = parse_to_sympy(replacement).subs(wildcard_dict)
        expr = _replace_subexpression(self.expression, pattern, replacement)
        if keep:
            self.substitutions[replacement] = pattern
        return expr

    @update_expression
    def evaluate_variables(
        self,
        variable_values: dict[str, float],
        gnarly: bool = False,
        functions_map: dict[str, Callable[[Any], int | float]] | None = None,
        *,
        keep: bool = True,
    ) -> Expr:
        """Assign explicit values to certain variables.

        Args:
            variable_values : A dictionary of (variable name: value) key, val pairs.
            gnarly: Whether or not to evaluate the gnarly expression, by default False.
            functions_map: A map for certain functions.
            keep: Whether or not to keep this modification. Defaults to True.

        Returns:
            Expr
        """
        print(self.expression.subs({self._get_symbol(var): val for var, val in variable_values.items()}))
        expr = sympy_backend.substitute(
            self.gnarly if gnarly else self.expression,
            replacements={self._get_symbol(var).name: val for var, val in variable_values.items()},
            functions_map=functions_map,
        )
        return expr

    @update_expression
    def expand(self, keep: bool = True) -> Expr:
        """Aggressively expand parenthesis in the expression.

        Args:
            keep (bool, optional): Whether or not to keep the modification. Defaults to True.

        Returns:
            Expr: An expanded expression.
        """
        return self.expression.expand()

    @update_expression
    def substitute(self, string_literal: str, replacement: str, *, keep: bool = True) -> Expr:
        """Replace a specific string in the expression with another.

        Args:
            string_literal (str): The string to replace.
            replacement (str): Replacment string.
            keep (bool, optional): Whether or not to keep the modification. Defaults to True.

        Returns:
            Expr: _description_
        """
        literal, replacement = map(parse_to_sympy, [string_literal, replacement])
        literal = literal.subs({fs: self._get_symbol(fs.name) for fs in literal.free_symbols})

        expr = self.expression.subs(literal, replacement)
        if keep:
            self.substitutions[replacement] = literal
        return expr

    def highlight_variables(self, variables: str | list[str]) -> Expr:
        """Highlight specific variables in the expression by obfuscating any term that does not include that variable.

        Args:
            variables: A string or list of strings, indiciating the names of the variables to
            highlight.

        Returns:
            Expr: A new expression of the form f(variables) + remaining(!variables)
        """
        if isinstance(variables, str):
            variables = [variables]
        variables = set(map(self._get_symbol, variables))
        variables = variables.union(
            set(sym for sym, orig in self.substitutions.items() if any(x in variables for x in orig.args))
        )
        return Add(*[x for x in self.expression.args if x.free_symbols & variables]).collect(variables)

    @update_expression
    def symplify(self, *, keep: bool = True) -> Expr:
        """Run the built in sympy.simplify function, first on each individual term and then on the whole expression.

        Args:
            keep (bool, optional): Whether or not to keep the modification. Defaults to True.

        Returns:
            Expr: A simplified sympy expression.
        """
        return Add(*[expr.simplify() for expr in self.individual_terms]).simplify()

    @update_expression
    def add_assumption(self, assume: str, *, keep: bool = True) -> Expr:
        """Add an assumption to the expression, which may potentially simplify it.

        An assumption should take the form of
        >>>A ? B
        where
        - A is a variable
        - ? is a relation between A and B, one of '>', '<', '>=', '<=', '!='.
        - B is a reference value, either another variable or a number.


        Args:
            assume (str): A string representative of the assumption, of the form A?B.
            keep (bool, optional): Whether or not to keep the modification. Defaults to True.

        Returns:
            Expr: The expression with the assumption applied. If sympy is unable to use the assumption,
                the expression will look the same.
        """
        if keep and assume not in self.assumptions:
            self.assumptions.append(assume)
        return _apply_assumption(expression=self.expression, assumption=assume)

    @update_expression
    def remove_substitution(self, variable_to_remove: str, *, keep: bool = True) -> Expr:
        """Undo a substitution previously applied to the expression.

        Args:
            variable_to_remove (str): Variable name to remove.
            keep (bool, optional): Whether or not to keep the modification. Defaults to True.

        Returns:
            Expr: Updated expression.
        """
        ref_symbol = self._get_symbol(variable_to_remove)
        return self.expression.subs({ref_symbol: self.substitutions[ref_symbol]})

    def remove_all_substitutions(self, *, keep: bool = True) -> Expr:
        """Remove all (non-wildcard) substitutions.

        Args:
            keep (bool, optional): Whether or not to keep the modification. Defaults to True.

        Returns:
            Expr
        """
        expr = self.expression
        substitutions: list[Symbol | Expr] = [key for key in self.substitutions if not key.is_Wild]
        # TODO: This function does not interact correctly with the decorator
        for sub in substitutions:
            expr = expr.subs({sub: self.substitutions[sub]})
        if keep:
            self.expression = expr
            for key in substitutions:
                self.substitutions.pop(key)
        return expr

    def all_functions_and_arguments(self) -> set[Expr]:
        """Get a set of all functions and their arguments in the expression.

        The returned set will include all functions at every level of the expression, i.e.
        GSE("max(a, 1 - max(b, 1 - max(c, lamda)))).all_functions_and_arguments()
        >>> {
        >>> Max(c, lamda),
        >>> Max(b, 1 - Max(c, lamda)),
        >>> Max(a, 1 - Max(b, 1 - Max(c, lamda)))
        >>> }

        Returns:
            set[Expr]
        """
        return self.expression.atoms(Function, sympy.Max)

    def list_arguments_of_function(self, function_name: str) -> list[tuple[Expr, ...]]:
        """Return a list of all arguments of a named function.

        Args:
            function_name: function name

        Returns:
            list[tuple[Expr, ...]]
        """
        return [
            tuple(_arg for _arg in _func.args if _arg) if len(_func.args) > 1 else _func.args[0]
            for _func in self.all_functions_and_arguments()
            if _func.__class__.__name__.lower() == function_name.lower()
        ]


#####################################################################


def _replace_subexpression(expression: Expr, expr: Expr, repl: Expr) -> Expr:
    """Replace a subexpression within a larger expression.

    Args:
        expression (Expr): Top level expression.
        expr (Expr): Subexpression to replace.
        repl (Expr): Expression to use in place of expr.

    Returns:
        Expr
    """
    if A := expression.match(expr):
        return repl.subs(A)

    if any(isinstance(expression, x) for x in [Symbol, sympy.Number]):
        return expression
    return expression.__class__(
        *[
            repl.subs(A) if (A := arg.match(expr)) else _replace_subexpression(arg, expr, repl)
            for arg in expression.args
        ]
    )


def _apply_assumption(expression: Expr, assumption: str) -> Expr:
    """Apply an assumption to a given expression.

    Args:
        expression (Expr): Expression to add an assumption to.
        assumption (str): Assumption, of the form A ? B.

    Returns:
        Expr
    """
    var, _, value, properties = _parse_assumption(assumption=assumption)
    try:
        reference_symbol: Symbol = next(symbol for symbol in expression.free_symbols if symbol.name == var)
        replacement = Symbol(
            var,
            positive=properties.get("positive"),
            negative=properties.get("negative"),
            nonzero=properties.get("nonzero"),
        )
        expression = expression.subs({reference_symbol: replacement})
        reference_symbol = replacement
    except StopIteration:
        reference_symbol: Expr = parse_to_sympy(var)
        for _sym in reference_symbol.free_symbols:
            reference_symbol = reference_symbol.subs(
                _sym, next(symbol for symbol in expression.free_symbols if symbol.name == _sym.name)
            )

    replacement_symbol = Symbol(
        name="O",
        positive=properties.get("positive"),
        negative=properties.get("negative"),
        nonzero=properties.get("nonzero"),
    )
    expression = expression.subs({reference_symbol: replacement_symbol + value}).subs(
        {replacement_symbol: reference_symbol - value}
    )
    return expression


def _parse_assumption(assumption: str) -> tuple[str, str, int | float, dict[str, bool]]:
    """Parse an assumption, and return useful information about it.

    At present this function just checks if the provided assumption allows for the symbol to be defined
    as positive or negative, and this is provided in a dictionary.

    Args:
        assumption (str): Assumption to parse.

    Raises:
        NotImplementedError: If the reference value in the assumption cannot be evaluated to a numeric value.

    Returns:
        tuple[str, str, int | float, dict[str, bool]]: A tuple of
            (variable name, relationship, reference value, properties)
    """
    var, relationship, value = _unpack_assumption(assumption=assumption)
    try:
        value = eval(value)
    except NameError:
        raise NotImplementedError(
            f"""Assumption tries to draw a relationship between two variables: {var}, {value}.
            At present, this is not possible!"""
        )

    gt: bool = relationship == _Relationships.GREATER_THAN
    gte: bool = relationship == _Relationships.GREATER_THAN_OR_EQUAL_TO

    lt: bool = relationship == _Relationships.LESS_THAN
    lte: bool = relationship == _Relationships.LESS_THAN_OR_EQUAL_TO

    value_positive: bool = value >= 0
    value_negative: bool = value <= 0
    value_non_zero: bool = value != 0

    properties: dict[str, bool] = dict(
        positive=((gt or gte) and value_positive) or None,
        negative=((lt or lte) and value_negative) or None,
        nonzero=(
            (gt and value_positive)
            or (lt and value_negative)
            or (gte and value_positive and value_non_zero)
            or (lte and value_negative and value_non_zero)
        )
        or None,
    )

    return (var, relationship, value, properties)


def _unpack_assumption(assumption: str) -> tuple[str, str, str]:
    """Unpack an assumption into its components.

    An assumption should take the form of
    >>>A ? B
    where
    - A is a variable
    - ? is a relation between A and B, one of '>', '<', '>=', '<=', '!='.
    - B is a reference value, either another variable or a number.

    Args:
        assumption (str): An assumption string.

    Raises:
        ValueError: If an unrecognised relationship is passed.

    Returns:
        tuple[str, str, str]: A tuple of (variable name, relation, reference value)
    """
    var, relationship, value = (x for x in re.split(_SPLIT_BY, assumption.replace(" ", "")) if x)
    if relationship not in _RELATIONSHIPS:
        raise ValueError(f"Relationship {relationship} not in permitted delimiters: {_RELATIONSHIPS}.")
    return var, relationship, value


if __name__ == "__main__":
    expr = parse_to_sympy(
        "55*beth*(-1 + (beth*(lambda - 1)*(n/2 - 1) + beth*(n/2 - 1))/(beth*(n/2 - 1)))*(n/2 - 1) + "
        "2*beth*(lambda - 1)*(n/2 - 1)*(2*ceiling(1.5*beth*(lambda - 1)*(n/2 - 1)) + 1) + 3*beth*(lambda - 1)*(n/2 - 1)"
        "+ 2*beth*(n/2 - 1)*(2*ceiling(1.5*beth*(n/2 - 1)) + 1) + 3*beth*(n/2 - 1) + 1400*beth + 102*lambda + "
        "2*(108*beth + 2816)*(n/2 - 1) + (ceiling(0.75*lambda) + 49)*Max(0, -A + ceiling(M/lambda)) + "
        "(ceiling(0.75*beth*(lambda - 1)*(n/2 - 1) + 0.75*beth*(n/2 - 1)) + 49)*Max(0, -A + ceiling(M/lambda)) "
        "- 4253.5"
    )
    # expr = parse_to_sympy("A + 1")
    gse = GSE(expr)
    gse.add_assumption("A > 0")
    print(expr.subs(None, 1))
