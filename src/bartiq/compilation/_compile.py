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

import warnings
from dataclasses import dataclass, replace
from graphlib import TopologicalSorter
from typing import Iterable

from .. import PortDirection, Routine
from .._routine_new import (
    CompilationUnit,
    Constraint,
    ConstraintStatus,
    Port,
    compilation_unit_from_bartiq,
    compilation_unit_to_bartiq,
)
from ..errors import BartiqCompilationError
from ..precompilation.stages_new import (
    DEFAULT_PRECOMPILATION_STAGES,
    PrecompilationStage,
)
from ..symbolics import sympy_backend
from ..symbolics.backend import SymbolicBackend, T_expr
from ..verification import verify_compiled_routine, verify_uncompiled_routine


@dataclass(frozen=True)
class Context:
    path: str

    def descend(self, next_path: str) -> Context:
        return replace(self, path=".".join((self.path, next_path)))


class ConstraintValidationError(ValueError):
    def __init__(self, original_constraint: Constraint[T_expr], compiled_constraint: Constraint[T_expr]):
        super().__init__(original_constraint, compiled_constraint)


def _compile_constraint(
    constraint: Constraint[T_expr], inputs: dict[str, T_expr], backend: SymbolicBackend[T_expr]
) -> Constraint[T_expr]:
    lhs = _substitute_all(constraint.lhs, inputs, backend)
    rhs = _substitute_all(constraint.rhs, inputs, backend)

    comparison = lhs - rhs

    if comparison == 0:
        status = ConstraintStatus.satisfied
    elif backend.is_constant_int(comparison):
        status = ConstraintStatus.violated
    else:
        status = ConstraintStatus.inconclusive

    new_constraint = Constraint(lhs=lhs, rhs=rhs, status=status)

    if new_constraint.status == ConstraintStatus.violated:
        raise ConstraintValidationError(constraint, new_constraint)

    return new_constraint


def _substitute_all(expr: T_expr, substitutions: dict[str, T_expr], backend: SymbolicBackend[T_expr]) -> T_expr:
    actual_symbols = list(backend.free_symbols_in(expr))
    for old, new in substitutions.items():
        if old in actual_symbols:
            expr = backend.substitute(expr, old, new)
    return expr


def compile_routine(
    routine: Routine,
    *,
    backend: SymbolicBackend[T_expr] = sympy_backend,
    precompilation_stages: Iterable[PrecompilationStage[T_expr]] = DEFAULT_PRECOMPILATION_STAGES,
    skip_verification: bool = False,
) -> Routine:
    if not skip_verification:
        verification_result = verify_uncompiled_routine(routine, backend=backend)
        if not verification_result:
            problems = [problem + "\n" for problem in verification_result.problems]
            raise BartiqCompilationError(
                f"Found the following issues with the provided routine before the compilation started: {problems}",
            )

    root_unit = compilation_unit_from_bartiq(routine, backend)
    for stage in precompilation_stages:
        root_unit = stage(root_unit, backend)
    compiled_unit = _compile(root_unit, backend, {}, Context(root_unit.name))
    compiled_routine = compilation_unit_to_bartiq(compiled_unit, backend)
    if not skip_verification:
        verification_result = verify_compiled_routine(compiled_routine, backend=backend)
        if not verification_result:
            warnings.warn(
                "Found the following issues with the provided routine after the compilation has finished:"
                f" {verification_result.problems}",
            )
    return compiled_routine


def _infer_input_map(
    child: CompilationUnit[T_expr],
    inverted_param_links: dict[tuple[str, str], T_expr],
) -> dict[str, T_expr]:
    return {input: value for (child_name, input), value in inverted_param_links.items() if child_name == child.name}


def _compile_local_variables(
    local_variables: dict[str, T_expr], inputs: dict[str, T_expr], backend: SymbolicBackend[T_expr]
) -> dict[str, T_expr]:
    predecessors: dict[str, set[str]] = {
        var: set(other_var for other_var in backend.free_symbols_in(expr) if other_var in local_variables)
        for var, expr in local_variables.items()
    }

    compiled_variables: dict[str, T_expr] = {}
    extended_inputs = inputs.copy()
    for variable in TopologicalSorter(predecessors).static_order():
        compiled_value = _substitute_all(local_variables[variable], extended_inputs, backend)
        extended_inputs[variable] = compiled_variables[variable] = compiled_value
    return compiled_variables


def _compile(
    compilation_unit: CompilationUnit[T_expr],
    backend: SymbolicBackend[T_expr],
    inputs: dict[str, T_expr],
    context: Context,
    is_root: bool = False,
) -> CompilationUnit[T_expr]:
    try:
        new_constraints = [
            compiled_constraint
            for constraint in compilation_unit.constraints
            if (compiled_constraint := _compile_constraint(constraint, inputs, backend)).status
            != ConstraintStatus.satisfied
        ]
    except ConstraintValidationError as e:
        raise BartiqCompilationError(
            f"The following constraint was violated when compiling {context.path}: "
            + f"{e.args[0].lhs} = {e.args[1].rhs} evaluated into "
            + f"{e.args[1].lhs} = {e.args[1].rhs}."
        )
    local_variables = _compile_local_variables(compilation_unit.local_variables, inputs, backend)

    inverted_param_links: dict[str, T_expr] = {
        target: _substitute_all(backend.as_expression(source), {**local_variables, **inputs}, backend)
        for source, targets in compilation_unit.linked_params.items()
        for target in targets
    }

    compiled_children: dict[str, CompilationUnit[T_expr]] = {}
    available_port_sources: dict[str, T_expr] = {}

    compiled_ports: dict[str, Port[T_expr]] = {
        name: replace(port, size=_substitute_all(port.size, {**inputs, **local_variables}, backend))
        for name, port in compilation_unit.ports.items()
        if port.direction != PortDirection.output
    }

    for name, port in compiled_ports.items():
        if (target := compilation_unit.connections.get(name)) is not None:
            available_port_sources[target] = port.size

    for child in compilation_unit.sorted_children():
        compiled_child = _compile(
            child,
            backend,
            {**_infer_input_map(child, inverted_param_links), **available_port_sources},
            context.descend(child.name),
            is_root=False,
        )

        compiled_children[child.name] = compiled_child

        for pname, port in compiled_child.ports.items():
            if target := compilation_unit.connections.get(f"{compiled_child.name}.{pname}"):
                available_port_sources[target] = port.size

    children_variables = {
        f"{cname}.{rname}": resource.value
        for cname, child in compiled_children.items()
        for rname, resource in child.resources.items()
    }

    assignment_map = {**inputs, **children_variables, **local_variables}

    new_resources = {
        name: replace(resource, value=_substitute_all(resource.value, assignment_map, backend))
        for name, resource in compilation_unit.resources.items()
    }

    for name, port in compilation_unit.ports.items():
        if port.direction == "output":
            compiled_ports[port.name] = replace(
                port, size=_substitute_all(port.size, {**inputs, **available_port_sources, **local_variables}, backend)
            )

    input_params = sorted(
        set(symbol for resource in new_resources.values() for symbol in backend.free_symbols_in(resource.value))
        .union(input_param for child in compiled_children.values() for input_param in child.input_params)
        .union(symbol for port in compiled_ports.values() for symbol in backend.free_symbols_in(port.size))
    )
    return replace(
        compilation_unit,
        children=compiled_children,
        input_params=input_params,
        linked_params={},
        ports=compiled_ports,
        resources=new_resources,
        local_variables=local_variables,
        constraints=new_constraints,
    )
