import numpy as np
from bartiq import sympy_backend
from bartiq.numerics.grid_eval import IterativeEvaluator, make_evaluator_for_expressions
from sympy import lambdify, cos, sin
import pytest


@pytest.mark.parametrize("vectorize", [True, False])
def test_evaluator_correctly_substitutes_parameter_values(vectorize):
    exprs = {
        "foo": sympy_backend.as_expression("x ** 2 + y + z"),
        "bar": sympy_backend.as_expression("(x + y) ** 2 + sin(z)")
    }

    foo = lambda x, y, z: float(x ** 2 + y + z)
    bar = lambda x, y, z: float((x +  y) ** 2 + np.sin(z))
    grid = {"x": [1, 2], "y": [5, 6], "z": [0, 1]}

    expected = [
        ({"x": x, "y": y, "z": z}, {"foo": foo(x, y, z), "bar": bar(x, y, z)})
        for x in grid["x"] for y in grid["y"] for z in grid["z"]
    ]

    evaluator = make_evaluator_for_expressions(exprs, inputs=["x", "y", "z"], vectorize=vectorize)

    assert list(evaluator.evaluate(grid)) == expected


@pytest.mark.parametrize("vectorize", [True, False])
def test_iterative_evaluator_correctly_substitutes_custom_functions(vectorize):
    exprs = {
        "foo": sympy_backend.as_expression("x ** 2 + y + f(z)"),
        "bar": sympy_backend.as_expression("(x + y) ** 2 + g(z)")
    }
    functions_map = {"f": lambda z: z + 1, "g": lambda z: cos(z)}

    foo = lambda x, y, z: float(x ** 2 + y + z + 1)
    bar = lambda x, y, z: float((x +  y) ** 2 + np.cos(z))
    grid = {"x": [1, 2], "y": [5, 6], "z": [0, 1]}

    expected = [
        ({"x": x, "y": y, "z": z}, {"foo": foo(x, y, z), "bar": bar(x, y, z)})
        for x in grid["x"] for y in grid["y"] for z in grid["z"]
    ]

    evaluator = make_evaluator_for_expressions(exprs, inputs=["x", "y", "z"], functions_map=functions_map, vectorize=vectorize)

    assert list(evaluator.evaluate(grid)) == expected
