from dataclasses import replace
from typing import Callable

from .._routine_new import Port, Resource
from ..symbolics.backend import SymbolicBackend, T_expr


def _evaluate_expr(expr: T_expr, inputs: dict[str, T_expr], backend: SymbolicBackend[T_expr]) -> T_expr:
    expr = backend.substitute_all(expr, inputs)
    return value if (value := backend.value_of(expr)) is not None else expr


def evaluate_ports(
    ports: dict[str, Port[T_expr]], inputs: dict[str, T_expr], backend: SymbolicBackend[T_expr]
) -> dict[str, Port[T_expr]]:
    return {name: replace(port, size=_evaluate_expr(port.size, inputs, backend)) for name, port in ports.items()}


def evaluate_resources(
    resources: dict[str, Resource[T_expr]], inputs: dict[str, T_expr], backend: SymbolicBackend[T_expr]
) -> dict[str, Resource[T_expr]]:
    return {
        name: replace(resource, value=_evaluate_expr(resource.value, inputs, backend))
        for name, resource in resources.items()
    }


def _evaluate_and_define_functions(
    expr: T_expr, inputs: dict[str, T_expr], custom_funcs: dict[str, Callable], backend: SymbolicBackend[T_expr]
) -> T_expr:
    expr = backend.substitute_all(expr, inputs)
    for func_name, func in custom_funcs.items():
        expr = backend.define_function(expr, func_name, func)
    return value if (value := backend.value_of(expr)) is not None else expr


def evaluate_ports_v2(
    ports: dict[str, Port[T_expr]],
    inputs: dict[str, T_expr],
    custom_funcs: dict[str, Callable],
    backend: SymbolicBackend[T_expr],
) -> dict[str, Port[T_expr]]:
    return {
        name: replace(port, size=_evaluate_and_define_functions(port.size, inputs, custom_funcs, backend))
        for name, port in ports.items()
    }


def evaluate_resources_v2(
    resources: dict[str, Resource[T_expr]],
    inputs: dict[str, T_expr],
    custom_funcs: dict[str, Callable],
    backend: SymbolicBackend[T_expr],
) -> dict[str, Resource[T_expr]]:
    return {
        name: replace(resource, value=_evaluate_and_define_functions(resource.value, inputs, custom_funcs, backend))
        for name, resource in resources.items()
    }
