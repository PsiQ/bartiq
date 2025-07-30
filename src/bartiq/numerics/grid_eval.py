from collections.abc import Iterable
from functools import singledispatch
from itertools import product
from typing import Protocol


import numpy as np
from sympy import Expr, lambdify


from bartiq import evaluate, sympy_backend



class Evaluator(Protocol):

    def evaluate(self, param_grid: dict[str, Iterable[int] | Iterable[float]]) -> Iterable[dict[str, int | float], dict[str, int | float]]:
        pass


class IterativeEvaluator:

    def __init__(self, function_dict, params):
        self.function_dict = function_dict
        self.params = params

    def evaluate(self, param_grid: dict[str, Iterable[int] | Iterable[float]]) -> Iterable[dict[str, int | float], dict[str, int | float]]:
        assert list(self.params) == list(param_grid)
        grid_values = [param_grid[k] for k in self.params]

        for param_values in product(*grid_values):
            yield dict(zip(self.params, param_values)), {name: function(param_values) for name, function in self.function_dict.items()}


class MeshEvaluator:

    def __init__(self, function_dict, params):
        self.function_dict = function_dict
        self.params = params

    def evaluate(self, param_grid):
        assert list(self.params) == list(param_grid)
        grid_values = [param_grid[k] for k in self.params]

        mesh = np.meshgrid(*grid_values, indexing="ij")

        func_values = {name: function(mesh) for name, function in self.function_dict.items()}
        return zip(
            [dict(zip(self.params, values)) for values in product(*grid_values)],
            [{key: float(value) for key, value in zip(func_values, values)} for values in zip(*(func_values[k].flat for k in func_values))]
        )


def make_evaluator(compiled_routine, functions_map=None) -> Evaluator:
    params = sorted(compiled_routine.input_params)
    return make_evaluator_for_expressions({name: res.value for name, res in compiled_routine.resources.items()}, params, functions_map)


def make_evaluator_for_expressions(expressions: dict[str, Expr], inputs: Iterable[str], functions_map=None, vectorize=False):
    functions_map = functions_map or {}
    substituted = {name: sympy_backend.substitute(expr, {}, functions_map=functions_map) for name, expr in expressions.items()}
    lambdify_inputs = [tuple(inputs)]

    evaluator_cls = IterativeEvaluator if not vectorize else MeshEvaluator
    return evaluator_cls(
        {name: lambdify(lambdify_inputs, expr) for name, expr in substituted.items()},
        inputs
    )











