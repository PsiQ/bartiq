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

from collections.abc import Iterable
from dataclasses import dataclass, replace
from typing import Callable, TypeVar

from .._routine import Constraint, ConstraintStatus, Port, Repetition, Resource
from ..symbolics.backend import ComparisonResult, SymbolicBackend, TExpr

T = TypeVar("T", covariant=True)

FunctionsMap = dict[str, Callable[[TExpr[T]], TExpr[T]]]


@dataclass(frozen=True)
class Context:
    path: str

    def descend(self, next_path: str) -> Context:
        return replace(self, path=".".join((self.path, next_path)))


class ConstraintValidationError(ValueError):
    """Raised when a constraint in the compilation process is violated."""

    def __init__(self, original_constraint: Constraint[T], compiled_constraint: Constraint[T]):
        super().__init__(original_constraint, compiled_constraint)


def evaluate_ports(
    ports: dict[str, Port[T]],
    inputs: dict[str, TExpr[T]],
    backend: SymbolicBackend[T],
    custom_funcs: FunctionsMap[T] | None = None,
) -> dict[str, Port[T]]:
    custom_funcs = {} if custom_funcs is None else custom_funcs
    return {
        name: replace(port, size=backend.substitute(port.size, inputs, custom_funcs))  # type: ignore
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
            value=backend.substitute(resource.value, inputs, custom_funcs),  # type: ignore
        )
        for name, resource in resources.items()
    }


def evaluate_repetition(
    repetition: Repetition[T] | None,
    inputs: dict[str, TExpr[T]],
    backend: SymbolicBackend[T],
    custom_funcs: FunctionsMap[T] | None = None,
) -> Repetition[T] | None:
    if repetition is not None:
        return repetition.substitute_symbols(inputs, backend, functions_map=custom_funcs)
    else:
        return None


def _evaluate_constraint(
    constraint: Constraint[T], inputs: dict[str, TExpr[T]], backend: SymbolicBackend[T], custom_funcs: FunctionsMap[T]
) -> Constraint[T]:
    lhs = backend.substitute(constraint.lhs, inputs, custom_funcs)
    rhs = backend.substitute(constraint.rhs, inputs, custom_funcs)

    if (comparison_result := backend.compare(lhs, rhs)) == ComparisonResult.equal:
        status = ConstraintStatus.satisfied
    elif comparison_result == ComparisonResult.unequal:
        status = ConstraintStatus.violated
    else:
        status = ConstraintStatus.inconclusive

    new_constraint = Constraint(lhs=lhs, rhs=rhs, status=status)

    if new_constraint.status == ConstraintStatus.violated:
        raise ConstraintValidationError(constraint, new_constraint)

    return new_constraint


def evaluate_constraints(
    constraints: Iterable[Constraint[T]],
    inputs: dict[str, TExpr[T]],
    backend: SymbolicBackend[T],
    custom_funcs: FunctionsMap[T] | None = None,
) -> Iterable[Constraint[T]]:
    custom_funcs = {} if custom_funcs is None else custom_funcs
    return tuple(
        _evaluate_constraint(constraint, inputs, backend, custom_funcs)
        for constraint in constraints
        if constraint.status != ConstraintStatus.satisfied
    )
