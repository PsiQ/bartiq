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

import ast
import os
import warnings
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from graphlib import TopologicalSorter
from typing import Generic, TypeVar

from qref import SchemaV1
from qref.functools import ensure_routine
from qref.schema_v1 import RoutineV1
from qref.verification import verify_topology

from .._routine import (
    CompiledRoutine,
    Endpoint,
    Port,
    Repetition,
    Resource,
    Routine,
    routine_to_qref,
)
from ..errors import BartiqCompilationError
from ..symbolics import sympy_backend
from ..symbolics.backend import SymbolicBackend, TExpr
from ..verification import verify_uncompiled_repetitions
from ._common import (
    ConstraintValidationError,
    Context,
    evaluate_constraints,
    evaluate_ports,
    evaluate_resources,
)
from .preprocessing import DEFAULT_PREPROCESSING_STAGES, PreprocessingStage

REPETITION_ALLOW_ARBITRARY_RESOURCES_ENV = "BARTIQ_REPETITION_ALLOW_ARBITRARY_RESOURCES"

T = TypeVar("T")

# ParameterTree is a structure we use to build up our knowledge about
# parameters during successive compilation stages.
# In the context of any given rouine, non-None keys store dictionaries
# mapping children's variables into the values that have to be
# substituted into them.
# For instance, consider, the following parameter tree:
# {"a": {"x": N, "y": 2}, "b": {"x": 3"}}
# It means, that when processing "a" we should substitue x=N
# and y=2, and when processing child "b" we should substitute x=3.
# A special key None represents routine currently being compiled.
# For instance, the following parameter tree:
# {None: {"#out_0": N}}
# tells us that the output port of the routine currently being
# procesed should have size set to N.
ParameterTree = dict[str | None, dict[str, TExpr[T]]]


@dataclass
class CompilationResult(Generic[T]):
    """
    Datastructure for storing results of the compilation.

    Attributes:
        routine: compiled routine
        _backend: a backend used for manipulating symbolic expressions.

    """

    routine: CompiledRoutine[T]
    _backend: SymbolicBackend[T]

    def to_qref(self) -> SchemaV1:
        """Converts `routine` to QREF using `_backend`."""
        return routine_to_qref(self.routine, self._backend)


def compile_routine(
    routine: SchemaV1 | RoutineV1 | Routine[T],
    *,
    backend: SymbolicBackend[T] = sympy_backend,
    preprocessing_stages: Iterable[PreprocessingStage[T]] = DEFAULT_PREPROCESSING_STAGES,
    skip_verification: bool = False,
) -> CompilationResult[T]:
    """Performs symbolic compilation of a given routine.

    In this context, compilation means transforming a routine defined in terms of routine-local variables into
    one defined in terms of global input parameters.

    Args:
        routine: routine to be compiled.
        backend: a backend used for manipulating symbolic expressions.
        preprocessing_stages: functions used for preprocessing of a given routine to make sure it can be correctly
            compiled by Bartiq.
        skip_verification: a flag indicating whether verification of the routine should be skipped.


    """
    if not skip_verification and not isinstance(routine, Routine):
        problems = []
        if not (topology_verification_result := verify_topology(routine)):
            problems += [problem + "\n" for problem in topology_verification_result.problems]
        if not (repetitions_verification_result := verify_uncompiled_repetitions(routine)):
            problems += [problem + "\n" for problem in repetitions_verification_result.problems]
        if len(problems) > 0:
            raise BartiqCompilationError(
                f"Found the following issues with the provided routine before the compilation started: \n {problems}",
            )
    root = routine if isinstance(routine, Routine) else Routine[T].from_qref(ensure_routine(routine), backend)

    for stage in preprocessing_stages:
        root = stage(root, backend)
    return CompilationResult(routine=_compile(root, backend, {}, Context(root.name)), _backend=backend)


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
        compiled_value = backend.substitute(local_variables[variable], extended_inputs)
        extended_inputs[variable] = compiled_variables[variable] = compiled_value
    return compiled_variables


def _compile_linked_params(
    inputs: dict[str, TExpr[T]], linked_params: dict[str, tuple[tuple[str, str], ...]], backend: SymbolicBackend[T]
) -> ParameterTree[TExpr[T]]:
    parameter_map: ParameterTree[TExpr[T]] = defaultdict(dict)

    for source, targets in linked_params.items():
        evaluated_source = backend.substitute(backend.as_expression(source), inputs)
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


def _process_repeated_resources(
    repetition: Repetition,
    resources: dict[str, Resource],
    children: Sequence[CompiledRoutine[T]],
    backend: SymbolicBackend[T],
) -> dict[str, Resource]:
    assert len(children) == 1, "Routine with repetition can only have one child."
    new_resources = {}
    child_resources = children[0].resources

    # Ensure that routine with repetition only contains resources that we will later overwrite
    for resource_name, resource in resources.items():
        assert resource_name in child_resources
        assert backend.serialize(resource.value) == f"{children[0].name}.{resource.name}"
    for resource in child_resources.values():
        if resource.type == "additive":
            new_value = repetition.sequence_sum(resource.value, backend)
        elif resource.type == "multiplicative":
            new_value = repetition.sequence_prod(resource.value, backend)
        elif ast.literal_eval(os.environ.get(REPETITION_ALLOW_ARBITRARY_RESOURCES_ENV, "False")):
            new_value = resource.value
            warnings.warn(
                f'Can\'t process resource "{resource.name}" of type "{resource.type}" in repetitive structure.'
                "Passing its value as is without modifications. "
                f"To change the behaviour, set {REPETITION_ALLOW_ARBITRARY_RESOURCES_ENV} env to False."
            )
        else:
            raise BartiqCompilationError(
                f'Can\'t process resource "{resource.name}" of type "{resource.type}" in repetitive structure.'
            )

        new_resource = replace(resource, value=new_value)
        new_resources[resource.name] = new_resource
    return new_resources


def _compile(
    routine: Routine[T],
    backend: SymbolicBackend[T],
    inputs: dict[str, TExpr[T]],
    context: Context,
) -> CompiledRoutine[T]:
    try:
        new_constraints = evaluate_constraints(routine.constraints, inputs, backend)
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

    resources = routine.resources
    repetition = routine.repetition

    if routine.repetition is not None:
        resources = _process_repeated_resources(
            routine.repetition, resources, list(compiled_children.values()), backend
        )
        repetition = routine.repetition.substitute_symbols(parameter_map[None], backend=backend)

    new_resources = evaluate_resources(resources, parameter_map[None], backend)

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
        repetition=repetition,
    )
