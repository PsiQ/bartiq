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

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from functools import cached_property
from typing import Any, Callable, Generic, Optional

from typing_extensions import Self

from ..compilation._utilities import parse_value
from ..compilation.types import NUMBER_TYPES, Number
from ..errors import BartiqCompilationError
from .backend import SymbolicBackend, T_expr


class VariableError(Exception):
    """Error class for errors associated with variables."""


@dataclass(frozen=True)
class IndependentVariable:
    """A independent variable variable with no determined expression value."""

    symbol: str
    value: Optional[Number] = None
    description: Optional[str] = None

    def __post_init__(self):
        if not isinstance(self.symbol, str):
            raise BartiqCompilationError(
                f"Input variable symbols must be strings; found {self.symbol} with type {type(self.symbol)}."
            )
        if self.value is not None and not isinstance(self.value, NUMBER_TYPES):
            raise BartiqCompilationError(
                f"Input variable value type must be one of {NUMBER_TYPES}; found "
                f"{self.value} with type {type(self.value)}."
            )

    def with_new_value(self, value: Number) -> Self:
        """Set the value of the variable."""
        # Raise an error if there's already a value set and this one doesn't agree with it
        if self.value is not None and self.value != value:
            raise VariableError(f"Cannot set variable {self} to value {value}; already has value {self.value}")

        return replace(self, value=value)

    def rename_symbol(self, symbol: str) -> Self:
        """Returns a new independent variable with the symbol renamed."""
        return replace(self, symbol=symbol)

    @classmethod
    def from_str(cls, string) -> IndependentVariable:
        """Generates a :class:`~.IndependentVariable` instance from a string.

        Accepts the following cases:
        1. A single symbol, e.g. ``'x'``.
        2. A symbol with a value, e.g. ``'x = 4'``.
        3. A symbol with a description, e.g. ``'x (my favourite variable)'``.
        4. A symbol with a value and description, e.g. ``'x = 4 (my favourite variable)'``.

        Args:
            string: the variable string to be evaluated

        Returns:
            A new independent variable.
        """
        symb = r"([\w\.#]+)"
        desc = r"\((.+)\)"
        ws = r"\s*"
        val = r"(\w+)"

        # Case 1: symbol, value, description
        if match := re.fullmatch(f"{ws}{symb}{ws}={ws}{val}{ws}{desc}{ws}", string):
            symbol, value_str, description = match.groups()
            value = parse_value(value_str)

        # Case 2: symbol, value
        elif match := re.fullmatch(f"{ws}{symb}{ws}={ws}{val}{ws}", string):
            symbol, value_str = match.groups()
            value = parse_value(value_str)
            description = None

        # Case 3: symbol, description
        elif match := re.fullmatch(f"{ws}{symb}{ws}{desc}{ws}", string):
            symbol, description = match.groups()
            value = None

        # Case 4: symbol
        elif match := re.fullmatch(f"{ws}{symb}{ws}", string):
            (symbol,) = match.groups()
            value, description = None, None

        else:
            raise BartiqCompilationError(
                f"Failed to parse input string {string} for independent variable; "
                "must be of format 'symbol', 'symbol (description)', 'symbol = value', or 'symbol = value (description)"
            )

        return cls(symbol, value=value, description=description)

    def __str__(self) -> str:
        return _variable_to_str(self.symbol, self.value, self.description)

    def __repr__(self) -> str:
        attrs = ["value", "description"]
        kwargs_strs = _compile_kwargs_strs(self, attrs)
        args_str = ", ".join([self.symbol, *kwargs_strs])
        return f"IndependentVariable({args_str})"


def _compile_kwargs_strs(obj: Any, attrs: list[str]) -> list[str]:
    kwargs = {attr: getattr(obj, attr) for attr in attrs}
    return [f"{attr}={value}" for attr, value in kwargs.items() if value is not None]


@dataclass(frozen=True)
class DependentVariable(Generic[T_expr]):
    """A dependent variable variable which is a function of some other set of variables."""

    symbol: str
    expression: T_expr
    backend: SymbolicBackend[T_expr]
    expression_variables: dict[str, IndependentVariable] = field(default_factory=dict)
    expression_functions: dict[str, Optional[Callable]] = field(default_factory=dict)
    description: Optional[str] = None

    def __post_init__(self):
        # Fill in the blanks and cover your ass
        self._infer_missing_expression_variables()
        self._add_unknown_expression_functions()
        self._validate_expression_variables()
        self._validate_expression_functions()

    @cached_property
    def value(self) -> Optional[Number]:
        """Calculates the value of the variable if all expression variables are set."""
        # Deal with uncalculable case.
        has_undefined_variable = any(
            expression_variable.value is None for expression_variable in self.expression_variables.values()
        )
        has_undefined_function = any(
            expression_function is None for expression_function in self.expression_functions.values()
        )
        if has_undefined_variable or has_undefined_function:
            return None

        # Evaluate expression
        evaluated_expression = self._evaluate_expression()
        assert evaluated_expression is not None

        return self.backend.value_of(evaluated_expression)

    def _evaluate_expression(self) -> T_expr:
        """Evaluates the expression over all known variable values and defined functions."""
        # Evaluate all expression variable values
        evaluated_expression = self.expression
        for expression_symbol, expression_variable in self.expression_variables.items():
            if expression_variable.value is not None:
                evaluated_expression = self.backend.substitute(
                    evaluated_expression, expression_symbol, expression_variable.value
                )

        # Evaluate all functions
        for (
            expression_function_name,
            expression_function_callable,
        ) in self.expression_functions.items():
            if expression_function_callable:
                evaluated_expression = self.backend.define_function(
                    evaluated_expression, expression_function_name, expression_function_callable
                )

        return evaluated_expression

    def _infer_missing_expression_variables(self) -> None:
        """Goes through the expression and adds any independent variables the user missed."""
        backend_expression_variables = self.backend.free_symbols_in(self.expression)
        for backend_expression_variable in backend_expression_variables:
            if backend_expression_variable not in self.expression_variables:
                new_expression_variable = IndependentVariable(symbol=backend_expression_variable)
                self.expression_variables[backend_expression_variable] = new_expression_variable

    def _validate_expression_variables(self) -> None:
        """Ensures that the tracked expression variables match those of the backend."""
        user_expression_variables = set(self.expression_variables)
        backend_expression_variables = set(self.backend.free_symbols_in(self.expression))
        if backend_expression_variables != user_expression_variables:
            raise BartiqCompilationError(
                "User-supplied expression variables are not consistent with backend expression variables; "
                f"expected {user_expression_variables}, but backend found {backend_expression_variables}."
            )

    def _add_unknown_expression_functions(self) -> None:
        """Goes through the expression and tracks any functions the user left undefined."""
        backend_expression_functions = self.backend.functions_in(self.expression)
        for backend_expression_function in backend_expression_functions:
            self.expression_functions.setdefault(backend_expression_function)

    def _validate_expression_functions(self) -> None:
        """Ensures that the tracked expression functions match those of the backend."""
        user_expression_functions = set(self.expression_functions)
        backend_expression_functions = set(self.backend.functions_in(self.expression))
        if user_expression_functions != backend_expression_functions:
            raise BartiqCompilationError(
                f"Tracked are not consistent with backend functions for expression {self.expression}; "
                f"expected {user_expression_functions}, but backend found {backend_expression_functions}. "
            )

    @cached_property
    def evaluated_expression(self) -> str:
        """Returns the output variable's evaluated expression string.

        NOTE: here "evaluated" refers to the expression with known numeric values and function definitions substituted.
        """
        return self.backend.serialize(self._evaluate_expression())

    def substitute(self, variable: str, expression: str | Number) -> Self:
        """Substitutes a subvariable that occurs in the variable's expression with a new expression or value."""
        # Deal with trivial case
        if variable not in self.expression_variables:
            return self

        if isinstance(expression, NUMBER_TYPES):
            expression = str(expression)
        elif not isinstance(expression, str):
            raise TypeError(f"Substitution expression must be a string; found {expression} of type {type(expression)}.")

        # Catch any naughty business
        if variable == self.symbol:
            raise BartiqCompilationError(
                f"Cannot apply substitution to dependent variable's LHS; "
                f"Attempted to rename {variable} to {expression} for dependent variable {self}."
            )
        if expression == self.symbol:
            raise BartiqCompilationError(
                "Cannot substitute a variable in a dependent variable's RHS with the LHS variable; "
                f"Attempted to rename {variable} to {expression} for dependent variable {self}."
            )

        # Create the new expression
        new_expression = self.backend.substitute(self.expression, variable, self.backend.as_expression(expression))

        # Compile the variables for the new expression
        old_expression_variables = self.expression_variables
        new_expression_variables = {}
        for symbol in self.backend.free_symbols_in(new_expression):
            if symbol in old_expression_variables:
                new_expression_variables[symbol] = old_expression_variables[symbol]
            else:
                new_expression_variables[symbol] = IndependentVariable(symbol)

        return replace(self, expression=new_expression, expression_variables=new_expression_variables)

    def substitute_series(self, substitution_map: dict[str, str | Number]) -> Self:
        """Applies a series of substitutions."""
        new_variable = self
        for symbol, expression in substitution_map.items():
            new_variable = new_variable.substitute(symbol, str(expression))
        return new_variable

    def rename_function(self, old_function: str, new_function: str) -> Self:
        """Renames a function within the dependent variable's expression."""
        assert new_function != self.symbol and new_function not in self.backend.free_symbols_in(self.expression)

        new_expression = self.backend.rename_function(self.expression, old_function, new_function)
        old_expression_functions = self.expression_functions.copy()
        if old_function in self.expression_functions:
            expression_function = old_expression_functions.pop(old_function)
            new_expression_functions = {
                **old_expression_functions,
                new_function: expression_function,
            }
            return replace(self, expression=new_expression, expression_functions=new_expression_functions)
        else:
            return self

    def rename_symbol(self, symbol: str) -> Self:
        """Returns a new dependent variable with, but with a new symbol."""
        return replace(self, symbol=symbol)

    @property
    def is_constant_int(self) -> bool:
        """Returns whether the variable is a constant integer or not."""
        return self.backend.is_constant_int(self.expression)

    def define_function(
        self,
        function_name: str,
        function_callable: Callable,
    ) -> Self:
        """Define an undefined expression function.

        Args:
            function_name: The name of the expression function being defined.
            function_callable: The definition of the function.

        Returns:
            A new dependent variable with functions specified.
        """
        # Check for pre-defined function overwrites
        if predefined_function_callable := self.expression_functions.get(function_name):
            raise BartiqCompilationError(
                f"Attempted to overwrite defined function {function_name} with {function_callable}; "
                f"function {function_name} already defined as {predefined_function_callable}."
            )

        # Check for built-in function overwrites
        if function_name in (reserved := self.backend.reserved_functions()):
            raise BartiqCompilationError(
                f"Attempted to redefine built-in function {function_name} as {function_callable}; "
                f"known built-in functions are {reserved}"
            )

        new_expression_functions = self.expression_functions.copy()
        # Check for definitions of unknown functions
        if function_name in self.expression_functions:
            new_expression_functions[function_name] = function_callable

        return replace(self, expression_functions=new_expression_functions)

    @classmethod
    def from_str(cls, string: str, backend: SymbolicBackend[T_expr]) -> DependentVariable[T_expr]:
        """Generates a :class:`~.DependentVariable` instance from a string.

        NOTE: ``from_str`` doesn't currently allow for defining descriptions, since this interferes with expression
        parsing.

        Accepts the following cases:
        1. A symbol with an expression, e.g. ``'x = y + z'``.

        Args:
            string: the variable string to be evaluated
            backend: Backend used for parsing and later manipulating symbolic expressions.

        Returns:
            A new dependent variable.
        """
        symb = r"([\w\.#]+)"
        expr = r"(.+)"
        ws = r"\s*"

        # Case 1: symbol, expression
        if match := re.fullmatch(f"{ws}{symb}{ws}={ws}{expr}{ws}", string):
            symbol, expression = match.groups()

        else:
            raise BartiqCompilationError(
                f"Failed to parse input string {string} for dependent variable; "
                "must be of format 'symbol = expression' or 'symbol = expression (description)'"
            )

        return cls(symbol, backend.as_expression(expression), backend)

    def __str__(self) -> str:
        return _variable_to_str(self.symbol, self.value, self.description, expression=str(self.expression))

    def __repr__(self) -> str:
        attrs = ["value", "description"]
        kwargs_strs = _compile_kwargs_strs(self, attrs)
        args_str = ", ".join(map(str, [self.symbol, self.expression, *kwargs_strs]))
        return f"DependentVariable({args_str})"

    def __eq__(self, other: Any) -> bool:
        return (
            isinstance(other, type(self))
            and self.symbol == other.symbol
            and self.expression == other.expression
            and self.value == other.value
            and self.description == other.description
        )


def _variable_to_str(
    symbol: str,
    value: Optional[Number],
    description: Optional[str],
    expression: Optional[str] = None,
) -> str:
    """Serialises a variable to a string."""
    string = symbol
    if expression:
        string += f" = {expression}"
    # NOTE: only include value at the end if the variable has one and it's not exactly the same as the expression
    # E.g. we want to be able to do x = y + z = 1 but don't want x = 1 = 1
    if value and str(value) != expression:
        string += f" = {value}"
    if description:
        string += f" ({description})"

    return string
