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
from typing import Any, Callable, Dict, List, Optional, Tuple, TypedDict, Union

from sympy import Expr, Function, Poly, Symbol, prod  # type: ignore

from bartiq.symbolics import sympy_backend

Backend = sympy_backend

try:
    from scipy.optimize import minimize as scipy_minimize  # type: ignore

    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


class BigO:
    def __init__(self, expr: Expr, variable: Symbol | None = None):
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


def _convert_to_big_O(expr: Expr, gens: list[Expr] | None = None) -> Expr:
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
    x0: Optional[float]
    bounds: Optional[Tuple[float, float]]
    learning_rate: Optional[float]
    max_iter: Optional[int]
    tolerance: Optional[float]


class ScipyOptimizerKwargs(TypedDict, total=False):
    args: Tuple[Any, ...]
    method: Optional[str]
    jac: Optional[Union[Callable, str, bool]]
    hess: Optional[Union[Callable, str]]
    hessp: Optional[Callable]
    constraints: Union[Dict[str, Any], List[Dict[str, Any]]]
    callback: Optional[Callable]
    options: Optional[Dict[str, Any]]


class Optimizer:
    @staticmethod
    def gradient_descent(
        cost_func: Callable[[float], float],
        x0: Optional[float] = None,
        bounds: Optional[Tuple[float, float]] = None,
        learning_rate: float = 1e-6,
        max_iter: int = 1000,
        tolerance: float = 1e-8,
        momentum: float = 0.9,
    ) -> Dict[str, Any]:
        """
        Perform gradient descent optimization to find the minimum of the expression with respect to the specified
        parameter.

        Parameters:
            cost_func: The objective cost function to be minimized.
            x0: The starting point for the optimization. If None, a random value is
            selected.
            bounds: A tuple specifying the (min, max) range for the parameter value.
            Default is None (no bounds).
            learning_rate: The step size for each iteration. Default is 1e-6.
            max_iter: The maximum number of iterations to perform. Default is 1000.
            tolerance: The tolerance level for stopping criteria. Default is 1e-8.
            momentum: The momentum factor to control the influence of previous updates.

        Returns:
            Dict: A dictionary containing the final value of the parameter and the history of values
            during optimization.
        """
        if x0 is None:
            x0 = random.uniform(*bounds) if bounds else random.uniform(-1, 1)

        if bounds and not (bounds[0] <= x0 <= bounds[1]):
            raise ValueError(f"Initial value {x0} is out of bounds {bounds}.")

        current_value = x0
        velocity = 0.0

        x_history = [current_value]

        for i in range(max_iter):
            gradient = Optimizer._numerical_gradient(cost_func, current_value)

            velocity = momentum * velocity - learning_rate * gradient
            next_value = current_value + velocity

            if bounds:
                next_value = max(min(next_value, bounds[1]), bounds[0])
                if next_value == bounds[0] or next_value == bounds[1]:
                    x_history.append(next_value)
                    current_value = next_value
                    break

            if abs(gradient) < tolerance:
                break

            x_history.append(next_value)

            current_value = next_value

        else:
            raise RuntimeError("Maximum iterations reached without convergence.")

        return {"optimal_value": current_value, "minimum_cost": cost_func(current_value), "x_history": x_history}

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
    optimizer: str = "gradient_descent",
    optimizer_kwargs: Optional[OptimizerKwargs] = None,
    scipy_kwargs: Optional[ScipyOptimizerKwargs] = None,
    backend=Backend,
) -> Dict[str, Any]:
    """Find the optimal parameter value that minimizes a given expression.

    To visualize `minimize` results using a plotting library like `matplotlib`:

    1. Plot `x_history` (parameter values) on the x-axis.
    2. Plot `minimum_cost` on the y-axis.

    """

    if optimizer_kwargs is None:
        optimizer_kwargs = {}
    if scipy_kwargs is None:
        scipy_kwargs = {}

    expression = backend.as_expression(expression)

    def cost_func_callable(x) -> float:
        if not isinstance(x, (int, float)):
            x = x[0]

        substituted_expr = backend.substitute(expression, {param: x})
        result = backend.value_of(substituted_expr)
        return float(result)

    if optimizer == "gradient_descent":
        x0 = optimizer_kwargs.get("x0")
        bounds = optimizer_kwargs.get("bounds")

        if bounds:
            lower_bound, upper_bound = bounds
            bounds = (
                float(lower_bound) if lower_bound is not None else float("-inf"),
                float(upper_bound) if upper_bound is not None else float("inf"),
            )

        optimization_result = Optimizer.gradient_descent(
            cost_func=cost_func_callable,
            x0=x0,
            bounds=bounds,
            learning_rate=optimizer_kwargs.get("learning_rate") or 0.000001,
            max_iter=optimizer_kwargs.get("max_iter") or 10000,
            tolerance=optimizer_kwargs.get("tolerance") or 1e-8,
        )

    elif optimizer == "scipy":

        if SCIPY_AVAILABLE:
            if not optimizer_kwargs.get("x0"):
                raise ValueError("SciPy optimization requires an initial value 'x0'.")

            x0 = optimizer_kwargs.get("x0")
            bounds = optimizer_kwargs.get("bounds")
            bounds_scipy = [bounds] if isinstance(bounds, tuple) else bounds
            tol_scipy = optimizer_kwargs.get("tolerance")

            scipy_result = scipy_minimize(
                fun=cost_func_callable,
                x0=x0,
                args=scipy_kwargs.get("args", ()),
                method=scipy_kwargs.get("method"),
                jac=scipy_kwargs.get("jac"),
                hess=scipy_kwargs.get("hess"),
                hessp=scipy_kwargs.get("hessp"),
                bounds=bounds_scipy,
                constraints=scipy_kwargs.get("constraints", ()),
                tol=tol_scipy,
                callback=scipy_kwargs.get("callback"),
                options=scipy_kwargs.get(
                    "options",
                    {
                        "maxiter": optimizer_kwargs.get("max_iter"),
                        "disp": True,
                    },
                ),
            )
            optimization_result = {
                "optimal_value": float(scipy_result.x.item()) if scipy_result.x.size == 1 else scipy_result.x,
                "minimum_cost": float(scipy_result.fun),
                "x_history": [x0] + scipy_result.x.tolist() if scipy_result.x.size > 1 else [x0, scipy_result.x.item()],
            }

        else:
            raise ImportError("Scipy is not installed. Please install scipy to use the 'scipy' optimizer.")

    else:
        raise ValueError(f"Unknown optimizer: {optimizer}")

    return optimization_result
