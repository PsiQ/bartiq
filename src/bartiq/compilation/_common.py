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

T = TypeVar("T", covariant=True)

FunctionsMap = dict[str, Callable[[TExpr[T]], TExpr[T]]]


def _evaluate_and_define_functions(
    expr: TExpr[T], inputs: dict[str, TExpr[T]], custom_funcs: FunctionsMap[T], backend: SymbolicBackend[T]
) -> TExpr[T]:
    expr = backend.substitute_all(expr, inputs)
    for func_name, func in custom_funcs.items():
        expr = backend.define_function(expr, func_name, func)
    return value if (value := backend.value_of(expr)) is not None else expr


def evaluate_ports(
    ports: dict[str, Port[T]],
    inputs: dict[str, TExpr[T]],
    backend: SymbolicBackend[T],
    custom_funcs: FunctionsMap[T] | None = None,
) -> dict[str, Port[T]]:
    custom_funcs = {} if custom_funcs is None else custom_funcs
    return {
        name: replace(
            port, size=_evaluate_and_define_functions(port.size, inputs, custom_funcs, backend)  # type: ignore
        )
        for name, port in ports.items()
    }


def evaluate_resources(
    resources: dict[str, Resource[T]],
    inputs: dict[str, TExpr[T]],
    backend: SymbolicBackend[T],
    custom_funcs: FunctionsMap[T] | None = None,
) -> dict[str, Resource[T]]:
    custom_funcs = {} if custom_funcs is None else custom_funcs
    return {
        name: replace(
            resource,
            value=_evaluate_and_define_functions(resource.value, inputs, custom_funcs, backend),  # type: ignore
        )
        for name, resource in resources.items()
    }
