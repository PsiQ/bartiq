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
from dataclasses import replace
from typing import Callable, TypeVar

from .._routine import Port, Resource
from ..symbolics.backend import SymbolicBackend, TExpr

T = TypeVar("T")


def _evaluate_expr(expr: TExpr[T], inputs: dict[str, TExpr[T]], backend: SymbolicBackend[T]) -> TExpr[T]:
    expr = backend.substitute_all(expr, inputs)
    return value if (value := backend.value_of(expr)) is not None else expr


def evaluate_ports(
    ports: dict[str, Port[T]], inputs: dict[str, TExpr[T]], backend: SymbolicBackend[T]
) -> dict[str, Port[T]]:
    return {name: replace(port, size=_evaluate_expr(port.size, inputs, backend)) for name, port in ports.items()}


def evaluate_resources(
    resources: dict[str, Resource[T]], inputs: dict[str, TExpr[T]], backend: SymbolicBackend[T]
) -> dict[str, Resource[T]]:
    return {
        name: replace(resource, value=_evaluate_expr(resource.value, inputs, backend))
        for name, resource in resources.items()
    }


def _evaluate_and_define_functions(
    expr: TExpr[T], inputs: dict[str, TExpr[T]], custom_funcs: dict[str, Callable], backend: SymbolicBackend[T]
) -> TExpr[T]:
    expr = backend.substitute_all(expr, inputs)
    for func_name, func in custom_funcs.items():
        expr = backend.define_function(expr, func_name, func)
    return value if (value := backend.value_of(expr)) is not None else expr


def evaluate_ports_v2(
    ports: dict[str, Port[T]],
    inputs: dict[str, TExpr[T]],
    custom_funcs: dict[str, Callable],
    backend: SymbolicBackend[T],
) -> dict[str, Port[T]]:
    return {
        name: replace(port, size=_evaluate_and_define_functions(port.size, inputs, custom_funcs, backend))
        for name, port in ports.items()
    }


def evaluate_resources_v2(
    resources: dict[str, Resource[T]],
    inputs: dict[str, TExpr[T]],
    custom_funcs: dict[str, Callable],
    backend: SymbolicBackend[T],
) -> dict[str, Resource[T]]:
    return {
        name: replace(resource, value=_evaluate_and_define_functions(resource.value, inputs, custom_funcs, backend))
        for name, resource in resources.items()
    }
