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

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, replace
from graphlib import TopologicalSorter
from typing import Generic, TypeVar

from qref import SchemaV1
from qref.schema_v1 import RoutineV1
from qref.verification import verify_topology

from .._routine import (
    CompiledRoutine,
    Constraint,
    ConstraintStatus,
    Endpoint,
    Port,
    Routine,
    routine_to_qref,
)
from ..errors import BartiqCompilationError
from ..symbolics import sympy_backend
from ..symbolics.backend import ComparisonResult, SymbolicBackend, TExpr
from ._common import evaluate_ports, evaluate_resources
from .preprocessing import DEFAULT_PRECOMPILATION_STAGES, PreprocessingStage

T = TypeVar("T")

ParameterTree = dict[str | None, dict[str, TExpr[T]]]


@dataclass
class CompilationResult(Generic[T]):
    compiled_routine: CompiledRoutine[T]
    _backend: SymbolicBackend[T]

    def to_qref(self) -> SchemaV1:
        return routine_to_qref(self.compiled_routine, self._backend)


@dataclass(frozen=True)
class Context:
    path: str

    def descend(self, next_path: str) -> Context:
        return replace(self, path=".".join((self.path, next_path)))


class ConstraintValidationError(ValueError):
    def __init__(self, original_constraint: Constraint[T], compiled_constraint: Constraint[T]):
        super().__init__(original_constraint, compiled_constraint)


def _compile_constraint(
    constraint: Constraint[T], inputs: dict[str, TExpr[T]], backend: SymbolicBackend[T]
) -> Constraint[T]:
    lhs = backend.substitute_all(constraint.lhs, inputs)
    rhs = backend.substitute_all(constraint.rhs, inputs)

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


def compile_routine(
    routine: SchemaV1 | RoutineV1,
    *,
    backend: SymbolicBackend[T] = sympy_backend,
    precompilation_stages: Iterable[PreprocessingStage[T]] = DEFAULT_PRECOMPILATION_STAGES,
    skip_verification: bool = False,
) -> CompilationResult[T]:
    if not skip_verification:
        if not (verification_result := verify_topology(routine)):
            problems = [problem + "\n" for problem in verification_result.problems]
            raise BartiqCompilationError(
                f"Found the following issues with the provided routine before the compilation started: {problems}",
            )
    root = Routine[T].from_qref(routine, backend)
    for stage in precompilation_stages:
        root = stage(root, backend)
    return CompilationResult(compiled_routine=_compile(root, backend, {}, Context(root.name)), _backend=backend)


def _compile_local_variables(
    local_variables: dict[str, TExpr[T]], inputs: dict[str, TExpr[T]], backend: SymbolicBackend[T]
) -> dict[str, TExpr[T]]:
    predecessors: dict[str, set[str]] = {
        var: set(other_var for other_var in backend.free_symbols_in(expr) if other_var in local_variables)
        for var, expr in local_variables.items()
    }

    compiled_variables: dict[str, TExpr[T]] = {}
    extended_inputs = inputs.copy()
    for variable in TopologicalSorter(predecessors).static_order():
        compiled_value = backend.substitute_all(local_variables[variable], extended_inputs)
        extended_inputs[variable] = compiled_variables[variable] = compiled_value
    return compiled_variables


def _compile_linked_params(
    inputs: dict[str, TExpr[T]], linked_params: dict[str, tuple[tuple[str, str], ...]], backend: SymbolicBackend[T]
) -> ParameterTree[TExpr[T]]:
    parameter_map: ParameterTree[TExpr[T]] = defaultdict(dict)

    for source, targets in linked_params.items():
        evaluated_source = backend.substitute_all(backend.as_expression(source), inputs)
        for child, param in targets:
            parameter_map[child][param] = evaluated_source

    return parameter_map


def _merge_param_trees(tree_1: ParameterTree[T], tree_2: ParameterTree[T]) -> ParameterTree[T]:
    return {k: {**v, **tree_2.get(k, {})} for k, v in tree_1.items()}


def _expand_connections(connections: dict[Endpoint, Endpoint]) -> dict[str | None, dict[str, Endpoint]]:
    tree = defaultdict[str | None, dict[str, Endpoint]](dict)
    for source, target in connections.items():
        tree[source.routine_name][source.port_name] = target

    return tree


def _param_tree_from_compiled_ports(
    connections_map: dict[str, Endpoint], compiled_ports: dict[str, Port[T]]
) -> ParameterTree[TExpr[T]]:
    param_map = defaultdict[str | None, dict[str, TExpr[T]]](dict)
    for source_port, target in connections_map.items():
        param_map[target.routine_name][f"#{target.port_name}"] = compiled_ports[source_port].size
    return param_map


def _compile(
    routine: Routine[T],
    backend: SymbolicBackend[T],
    inputs: dict[str, TExpr[T]],
    context: Context,
) -> CompiledRoutine[T]:
    try:
        new_constraints = [
            compiled_constraint
            for constraint in routine.constraints
            if (compiled_constraint := _compile_constraint(constraint, inputs, backend)).status
            != ConstraintStatus.satisfied
        ]
    except ConstraintValidationError as e:
        raise BartiqCompilationError(
            f"The following constraint was violated when compiling {context.path}: "
            + f"{e.args[0].lhs} = {e.args[0].rhs} evaluated into "
            + f"{e.args[1].lhs} = {e.args[1].rhs}."
        )

    connections_map = _expand_connections(routine.connections)

    local_variables = _compile_local_variables(routine.local_variables, inputs, backend)

    # Parameter map holds all of the assignments as nested dictionary.
    # The first level of nesting is the child name (or None for current routine assignments).
    # The second level maps symbols to the expression that should be substituted for it.
    parameter_map: ParameterTree[T] = {name: {} for name in routine.children}

    # We start by populating it with freshly compiled local variables and inputs
    # {None: {a: 2}, b: {foo: 3, #in_1: N}}
    parameter_map[None] = {**local_variables, **inputs}

    # Invert and merge linked params into parameter_map
    parameter_map = _merge_param_trees(
        parameter_map, _compile_linked_params(parameter_map[None], routine.linked_params, backend)
    )

    compiled_children: dict[str, CompiledRoutine[T]] = {}

    compiled_ports = evaluate_ports(routine.filter_ports(["input", "through"]), parameter_map[None], backend)

    parameter_map = _merge_param_trees(
        parameter_map, _param_tree_from_compiled_ports(connections_map[None], compiled_ports)
    )

    for child in routine.sorted_children():
        compiled_child = _compile(child, backend, parameter_map[child.name], context.descend(child.name))
        compiled_children[child.name] = compiled_child

        parameter_map = _merge_param_trees(
            parameter_map, _param_tree_from_compiled_ports(connections_map[child.name], compiled_child.ports)
        )

    children_variables = {
        f"{cname}.{rname}": resource.value
        for cname, child in compiled_children.items()
        for rname, resource in child.resources.items()
    }

    parameter_map[None] = {**parameter_map[None], **children_variables}

    new_resources = evaluate_resources(routine.resources, parameter_map[None], backend)

    compiled_ports = {
        **compiled_ports,
        **evaluate_ports(routine.filter_ports(["output"]), parameter_map[None], backend),
    }

    new_input_params = sorted(
        (
            set(symbol for expr in inputs.values() for symbol in backend.free_symbols_in(expr))
            if inputs
            else set(routine.input_params)
        ).union(symbol for port in compiled_ports.values() for symbol in backend.free_symbols_in(port.size))
    )

    return CompiledRoutine[T](
        name=routine.name,
        type=routine.type,
        input_params=new_input_params,
        children=compiled_children,
        ports=compiled_ports,
        resources=new_resources,
        constraints=new_constraints,
        connections=routine.connections,
    )
