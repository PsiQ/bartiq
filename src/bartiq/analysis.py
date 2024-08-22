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

import random
import warnings
from typing import Callable, Dict, Optional, Tuple, TypedDict, Union

from sympy import Expr, Function, Poly, Symbol, lambdify, prod, symbols

from bartiq.symbolics import sympy_backend

Backend = sympy_backend


class BigO:
    def __init__(self, expr: Expr, variable: Optional[Symbol] = None):
        """Class for representing expressions in Big O notation.

        It analyzes given expression and returns all the Big O terms in it.
        If variable is provided, it analyses scaling in this particular variable,
        otherwise it assumes all the symbols are variables.

        Note:
            It's an experimental tool and is meant to facilitate the analysis, but
            it might not produce correct results, especially for more complicated
            expressions. In case of any problems please create an issue on project's GitHub,
            we'd love to hear your feedback on this!

        Args:
            expr: sympy expression we want to analyze
            variable: variable for which we want to performa analysis.
        """
        if variable is None:
            gens = []
        else:
            gens = [variable]
        self.expr = _convert_to_big_O(expr, gens)

    def __add__(self, other):
        if isinstance(other, self.__class__):
            return BigO(_remove_big_O_function(self.expr) + _remove_big_O_function(other.expr))
        else:
            return BigO(_remove_big_O_function(self.expr) + _remove_big_O_function(other))

    def __eq__(self, other):
        return self.expr == other.expr

    def __mul__(self, other):
        if isinstance(other, self.__class__):
            return BigO(_remove_big_O_function(self.expr) * _remove_big_O_function(other.expr))
        else:
            return BigO(_remove_big_O_function(self.expr) * _remove_big_O_function(other))

    def __repr__(self) -> str:
        return f"{self.expr}"


def _remove_big_O_function(expr: Expr) -> Expr:
    args = expr.args
    new_args = []
    for arg in args:
        if isinstance(arg, Function("O")):
            assert len(arg.args) == 1
            new_args.append(arg.args[0])
        else:
            new_args.append(arg)
    return sum(new_args)


def _add_big_o_function(expr: Expr) -> Expr:
    if isinstance(expr, Function("O")):
        return expr
    return Function("O")(expr)


def _convert_to_big_O(expr: Expr, gens: Optional[list[Expr]] = None) -> Expr:
    gens = gens or []
    if len(expr.free_symbols) == 0:
        return _add_big_o_function(1)
    if len(expr.free_symbols) > 1 and len(gens) == 0:
        warnings.warn(
            "Results for using BigO with multiple variables might be unreliable. "
            "For better results please select a variable of interest."
        )
    poly = Poly(expr, *gens)
    leading_terms = _get_leading_terms(poly)
    return sum(map(_add_big_o_function, leading_terms))


def _get_leading_terms(poly):
    terms, _ = zip(*poly.terms())
    leading_terms = []
    for term in terms:
        if not _term_less_than_or_equal_to_all_others(term, leading_terms):
            leading_terms.append(term)

    return [_make_term_expression(poly.gens, leading_term) for leading_term in leading_terms]


def _term_less_than_or_equal_to_all_others(candidate, other_terms):
    if not other_terms:
        return False

    return all(_less_than(candidate, term) for term in other_terms)


def _less_than(term_1, term_2):
    return all(a <= b for a, b in zip(term_1, term_2))


def _make_term_expression(gens, term):
    powers = [gen**order for gen, order in zip(gens, term)]
    return prod(powers)


class OptimizerKwargs(TypedDict, total=False):
    initial_value: Optional[Union[float, int]]
    bounds: Optional[Tuple[float, float]]
    learning_rate: float
    max_iter: int
    tolerance: float
    initial_params: Optional[Union[float, int]]


class Optimizer:
    @staticmethod
    def gradient_descent(
        cost_func: Callable[[float], float],
        initial_value: Optional[float] = None,
        bounds: Optional[Tuple[float, float]] = None,
        learning_rate: float = 0.01,
        max_iter: int = 1000,
        tolerance: float = 1e-6,
    ) -> Dict[str, object]:
        """
        Perform gradient descent optimization to find the minimum of the expression with respect to the specified
        parameter.

        Parameters:
            cost_func: The objective cost function to be minimized.
            initial_value: The starting point for the optimization. If None, a random value is
            selected.
            bounds: A tuple specifying the (min, max) range for the parameter value.
            Default is None (no bounds).
            learning_rate: The step size for each iteration. Default is 0.01.
            max_iter: The maximum number of iterations to perform. Default is 1000.
            tolerance: The tolerance level for stopping criteria. Default is 1e-6.

        Returns:
            Dict: A dictionary containing the final value of the parameter and the history of values
            during optimization.
        """
        if initial_value is None:
            initial_value = random.uniform(*bounds) if bounds else random.uniform(-1, 1)

        if bounds and not (bounds[0] <= initial_value <= bounds[1]):
            raise ValueError(f"Initial value {initial_value} is out of bounds {bounds}.")

        current_value = initial_value
        x_history = [current_value]

        for i in range(max_iter):
            gradient = Optimizer._numerical_gradient(cost_func, current_value)
            next_value = current_value - learning_rate * gradient

            if bounds:
                next_value = max(min(next_value, bounds[1]), bounds[0])
                if next_value == bounds[0] or next_value == bounds[1]:
                    print(f"Bounds reached at iteration {i + 1}.")
                    x_history.append(next_value)
                    break

            x_history.append(next_value)

            if abs(gradient) < tolerance:
                print(f"Convergence reached after {i + 1} iterations.")
                break

            current_value = next_value
        else:
            raise RuntimeError("Maximum iterations reached without convergence.")

        return {"optimal_value": current_value, "x_history": x_history}

    @staticmethod
    def _numerical_gradient(f: Callable[[float], float], value: float, epsilon: float = 1e-8) -> float:
        """
        Calculate the numerical gradient of the function f at a given point using finite difference.

        Parameters:
            f: The objective function to be minimized.
            value: The point at which to compute the gradient.
            epsilon: A small number to calculate the finite difference. Default is 1e-8.

        Returns:
            float: The estimated gradient of the function at the given point.
        """
        return (f(value + epsilon) - f(value - epsilon)) / (2 * epsilon)


def minimize(
    expression: str,
    param: str,
    optimizer: str,
    optimizer_kwargs: Optional[OptimizerKwargs] = None,
    backend=Backend,
) -> Dict[str, object]:
    """
    Find the optimal parameter value that minimizes a given expression.

    Parameters:
        expression: The cost function to be optimized, provided as a string expression.
        param: The parameter to be optimized, provided as a string.
        optimizer: The name of the optimizer to use.
        initial_params: The initial guess for the parameter. Default is None.
        optimizer_kwargs: Additional arguments for the optimizer. Default is None.
        backend: Backend to process the expression.

    Returns:
        Dict: A dictionary containing the optimal value of the parameter (`optimal_value`),
              the corresponding minimum cost (`minimum_cost`), and the history of parameter values
              (`x_history`).

    Raises:
        ValueError: If the specified optimizer is unknown.
    """
    if optimizer_kwargs is None:
        optimizer_kwargs = {}

    param_symbol = symbols(param)
    cost_func = backend.as_expression(expression)
    cost_func_callable = lambdify(param_symbol, cost_func)

    if optimizer == "gradient_descent":
        initial_value = float(optimizer_kwargs.get("initial_value", optimizer_kwargs.get("initial_params", None)))
        bounds = optimizer_kwargs.get("bounds", None)
        learning_rate = float(optimizer_kwargs.get("learning_rate", 0.01))
        max_iter = float(optimizer_kwargs.get("max_iter", 1000))
        tolerance = float(optimizer_kwargs.get("tolerance", 1e-6))

        optimization_result = Optimizer.gradient_descent(
            cost_func=cost_func_callable,
            initial_value=initial_value,
            bounds=bounds,
            learning_rate=learning_rate,
            max_iter=max_iter,
            tolerance=tolerance,
        )
        opt_value = optimization_result["optimal_value"]
        x_history = optimization_result["x_history"]
        min_cost = cost_func_callable(opt_value)
    else:
        raise ValueError(f"Unknown optimizer: {optimizer}")

    return {"optimal_value": opt_value, "minimum_cost": min_cost, "x_history": x_history}
