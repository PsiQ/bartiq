"""A prototype for manipulation symbolic expressions in sympy."""

from __future__ import annotations
import sympy
import re
from typing import Optional
from sympy import Add, Symbol, Expr, Wild
from bartiq.symbolics.sympy_backends import parse_to_sympy

from enum import StrEnum
from functools import lru_cache


class _Relationships(StrEnum):
    GREATER_THAN = ">"
    LESS_THAN = "<"
    GREATER_THAN_OR_EQUAL_TO = ">="
    LESS_THAN_OR_EQUAL_TO = "<="
    NOT_EQUAL = "!="


_RELATIONSHIPS = list(_Relationships._value2member_map_.keys())

_SPLIT_BY: str = "(" + ")|(".join(_RELATIONSHIPS) + ")"


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

    def __init__(self, gnarly_symbolic_expression: Expr, assumptions: Optional[list[str]] = None):
        self.gnarly = gnarly_symbolic_expression
        self.gnarly_terms = GSE._individual_terms(self.gnarly)

        self._expression: Expr = gnarly_symbolic_expression
        self._variables: list[Symbol] = self.gnarly.free_symbols

        self.substitutions: dict[Symbol, Expr | Symbol] = {}
        self._history: list[Expr] = []

        self.assumptions = assumptions or []
        for assuming in self.assumptions:
            self.add_assumption(assume=assuming)

    @staticmethod
    def _individual_terms(expression: Expr) -> tuple[Expr, ...]:
        return sympy.Add.make_args(expression)

    def undo(self):
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
    def variables(self) -> list[str]:
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

    @lru_cache
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
            symbol = next(sym for sym in self.expression.free_symbols if sym.name == symbol_name)
            return symbol
        except StopIteration:
            raise ValueError(f"No variable '{symbol_name}'.")

    def wildcard_pattern_replacement(self, pattern: str, replacement: str, keep_modification: bool = True) -> Expr:
        """Replace a pattern in the expression with another.
        Free variables in the `pattern` kwarg are assumed to be wildcards.

        Args:
            pattern (str): Pattern to replace.
            replacement (str): Replacement pattern.
            keep_modification (bool, optional): Whether or not to keep the modification. Defaults to True.

        Returns:
            Expr
        """
        wildcard_dict = {
            sym: Wild(str(sym), properties=[lambda k: k != 0]) for sym in parse_to_sympy(pattern).free_symbols
        }
        pattern = parse_to_sympy(pattern).subs(wildcard_dict)
        replacement = parse_to_sympy(replacement).subs(wildcard_dict)
        expr = _replace_subexpression(self.expression, pattern, replacement)
        if keep_modification:
            self.expression = expr
            self.substitutions[replacement] = pattern
        return expr

    def evaluate_variables(self, variable_values: dict[str, float], keep_modification: bool = True) -> Expr:
        """Assign explicit values to certain variables.

        Args:
            variable_values : A dictionary of (variable name: value) key, val pairs.
            keep_modification: Whether or not to keep this modification. Defaults to True.

        Returns:
            Expr
        """
        expr = self.expression.subs({self._get_symbol(var): val for var, val in variable_values.items()})
        if keep_modification:
            self.expression = expr
        return expr

    def expand(self, keep_modification: bool = True) -> Expr:
        """Aggressively expand parenthesis in the expression.

        Args:
            keep_modification (bool, optional): Whether or not to keep the modification. Defaults to True.

        Returns:
            Expr: An expanded expression.
        """
        expr = self.expression.expand()
        if keep_modification:
            self.expression = expr
        return expr

    def simplify_logs(self, keep_modification: bool = True) -> Expr:
        """Simplify the log terms in the expression, i.e. replace log(x)/log(2) with log2(x).

        Args:
            keep_modification (bool, optional): Whether or not to keep the modification. Defaults to True.

        Returns:
            Expr
        """
        expr = self.wildcard_pattern_replacement("a*log(x)/log(2)", "a*log2(x)")
        if keep_modification:
            self.expression = expr
        return expr

    def substitute(self, string_literal: str, replacement: str, keep_modification: bool = True) -> Expr:
        """Replace a specific string in the expression with another.

        Args:
            string_literal (str): The string to replace.
            replacement (str): Replacment string.
            keep_modification (bool, optional): Whether or not to keep the modification. Defaults to True.

        Returns:
            Expr: _description_
        """
        literal, replacement = map(parse_to_sympy, [string_literal, replacement])
        literal = literal.subs({fs: self._get_symbol(fs.name) for fs in literal.free_symbols})

        expr = self.expression.subs(literal, replacement)
        if keep_modification:
            self.expression = expr
            self.substitutions[replacement] = literal
        return expr

    def highlight_variables(self, variables: str | list[str]) -> Expr:
        """Highlight specific variables in the expression by obfuscating any term that does not include that variable.

        Args:
            variables (str | list[str]): A string or list of strings, indiciating the names of the variables to
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

    def symplify(self, keep_modification: bool = True) -> Expr:
        """Run the built in sympy.simplify function, first on each individual term and then on the whole expression.

        Args:
            keep_modification (bool, optional): Whether or not to keep the modification. Defaults to True.

        Returns:
            Expr: A simplified sympy expression.
        """
        expr = Add(*[expr.simplify() for expr in self.individual_terms]).simplify()
        if keep_modification:
            self.expression = expr
        return expr

    def add_assumption(self, assume: str, keep_modification: bool = True) -> Expr:
        """Add an assumption to the expression, which may potentially simplify it.

        An assumption should take the form of
        >>>A ? B
        where
        - A is a variable
        - ? is a relation between A and B, one of '>', '<', '>=', '<=', '!='.
        - B is a reference value, either another variable or a number.


        Args:
            assume (str): A string representative of the assumption, of the form A?B.
            keep_modification (bool, optional): Whether or not to keep the modification. Defaults to True.

        Returns:
            Expr: The expression with the assumption applied. If sympy is unable to use the assumption,
                the expression will look the same.
        """
        expr = _apply_assumption(expression=self.expression, assumption=assume)
        if keep_modification:
            self.expression = expr
            if assume not in self.assumptions:
                self.assumptions.append(assume)
        return expr

    def remove_substitution(self, variable_to_remove: str, keep_modification: bool = True) -> Expr:
        """Undo a substitution previously applied to the expression.

        Args:
            variable_to_remove (str): Variable name to remove.
            keep_modification (bool, optional): Whether or not to keep the modification. Defaults to True.

        Returns:
            Expr: Updated expression.
        """
        ref_symbol = self._get_symbol(variable_to_remove)
        expr = self.expression.subs({ref_symbol: self.substitutions[ref_symbol]})
        if keep_modification:
            self.expression = expr
        return expr

    def remove_all_substitutions(self, keep_modification: bool = True) -> Expr:
        expr = self.expression
        for sub in [key for key in self.substitutions if not key.is_Wild]:
            expr = expr.subs({sub: self.substitutions.pop(sub)})
        if keep_modification:
            self.expression = expr
        return expr


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
    var, relation, value, properties = _parse_assumption(assumption=assumption)
    try:
        reference_symbol: Symbol = next(symbol for symbol in expression.free_symbols if symbol.name == var)
    except StopIteration:
        reference_symbol: Expr = parse_to_sympy(var)

    replacement_symbol = Symbol(
        name="O",
        positive=(relation in [_Relationships.GREATER_THAN, _Relationships.GREATER_THAN_OR_EQUAL_TO]) and (value >= 0),
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
    properties: dict[str, bool] = {}
    try:
        reference_value = eval(value)
        properties.update(
            dict(
                positive=(
                    (relationship in [_Relationships.GREATER_THAN, _Relationships.GREATER_THAN_OR_EQUAL_TO])
                    and reference_value >= 0
                ),
                negative=(
                    ((relationship in [_Relationships.LESS_THAN, _Relationships.LESS_THAN_OR_EQUAL_TO]))
                    and reference_value <= 0
                ),
            ),
        )

        return (var, relationship, reference_value, properties)
    except NameError:
        raise NotImplementedError(
            f"""Assumption tries to draw a relationship between two variables: {var}, {value}.
            At present, this is not possible!"""
        )


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
