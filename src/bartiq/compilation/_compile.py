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
import inspect
import os
import warnings
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from enum import Flag, auto
from graphlib import TopologicalSorter
from typing import Generic, Protocol

from qref import SchemaV1
from qref.functools import ensure_routine
from qref.schema_v1 import RoutineV1
from qref.verification import verify_topology
from typing_extensions import TypedDict, TypeIs

from bartiq._routine import (
    CompiledRoutine,
    Endpoint,
    Port,
    Resource,
    ResourceType,
    Routine,
    routine_to_qref,
)
from bartiq.compilation._common import (
    ConstraintValidationError,
    Context,
    evaluate_constraints,
    evaluate_ports,
    evaluate_resources,
)
from bartiq.compilation.postprocessing import (
    DEFAULT_POSTPROCESSING_STAGES,
    PostprocessingStage,
)
from bartiq.compilation.preprocessing import (
    DEFAULT_PREPROCESSING_STAGES,
    PreprocessingStage,
)
from bartiq.errors import BartiqCompilationError
from bartiq.repetitions import Repetition
from bartiq.symbolics import sympy_backend
from bartiq.symbolics.backend import SymbolicBackend, T, TExpr
from bartiq.verification import verify_uncompiled_repetitions

REPETITION_ALLOW_ARBITRARY_RESOURCES_ENV = "BARTIQ_REPETITION_ALLOW_ARBITRARY_RESOURCES"

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
# processed should have size set to N.
ParameterTree = dict[str | None, dict[str, TExpr[T]]]


class CompilationFlags(Flag):
    """A collection of compilation flags to modify `compile_routine` functionality."""

    EXPAND_RESOURCES = auto()
    """Expand resource values into full, rather than transitive, expressions."""

    SKIP_VERIFICATION = auto()
    """Skip the verification step on the routine."""


class Calculate(Protocol[T]):

    def __call__(self, routine: CompiledRoutine[T], backend: SymbolicBackend[T]) -> TExpr[T] | None:
        pass


class CalculateWithName(Protocol[T]):

    def __call__(self, routine: CompiledRoutine[T], backend: SymbolicBackend[T], resource_name: str) -> TExpr[T] | None:
        pass


class DerivedResources(TypedDict, Generic[T]):
    """Contains information needed to calculate derived resources."""

    name: str
    type: str
    calculate: Calculate[T] | CalculateWithName[T]


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
    postprocessing_stages: Iterable[PostprocessingStage[T]] = DEFAULT_POSTPROCESSING_STAGES,
    derived_resources: Iterable[DerivedResources] = (),
    compilation_flags: CompilationFlags | None = None,
) -> CompilationResult[T]:
    """Performs symbolic compilation of a given routine.

    In this context, compilation means transforming a routine defined in terms of routine-local variables into
    one defined in terms of global input parameters.

    Args:
        routine: routine to be compiled.
        backend: a backend used for manipulating symbolic expressions.
        preprocessing_stages: functions used for preprocessing of a given routine to make sure it can be correctly
            compiled by Bartiq.
        postprocessing_stages: functions used for postprocessing of a given routine after compilation is done.
        derived_resources: iterable with dictionaries describing how to calculate derived resources.
            Each dictionary should contain the derived resource's name, type
            and the function mapping a routine to the value of resource.
        compilation_flags: bitwise combination of compilation flags to tailor the compilation process; access these
            through the `CompilationFlags` object. By default None.
    """
    compilation_flags = compilation_flags or CompilationFlags(0)
    if CompilationFlags.SKIP_VERIFICATION not in compilation_flags and not isinstance(routine, Routine):
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

    for pre_stage in preprocessing_stages:
        root = pre_stage(root, backend)
    compiled_routine = _compile(
        routine=root,
        backend=backend,
        inputs={},
        context=Context(root.name),
        derived_resources=derived_resources,
        compilation_flags=compilation_flags,
    )
    for post_stage in postprocessing_stages:
        compiled_routine = post_stage(compiled_routine, backend)
    return CompilationResult(routine=compiled_routine, _backend=backend)


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
) -> ParameterTree[T]:
    parameter_map: ParameterTree[T] = defaultdict(dict)

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
) -> ParameterTree[T]:
    param_map = defaultdict[str | None, dict[str, TExpr[T]]](dict)
    for source_port, target in connections_map.items():
        param_map[target.routine_name][f"#{target.port_name}"] = compiled_ports[source_port].size
    return param_map


def _process_repeated_resources(
    repetition: Repetition[T],
    resources: dict[str, Resource[T]],
    children: Sequence[CompiledRoutine[T]],
    backend: SymbolicBackend[T],
) -> dict[str, Resource[T]]:
    if len(children) != 1:
        raise BartiqCompilationError("Routine with repetition can only have one child.")
    import copy

    # Ensure that routine with repetition only contains resources that we will later overwrite
    child_resources = copy.copy(children[0].resources)
    if parent_resources_not_in_child := resources.keys() - child_resources.keys():
        raise BartiqCompilationError(
            """Routine with repetition does not share the same resources as its child."""
            f"""\nFollowing resources are in the parent, but not the child: {parent_resources_not_in_child}"""
        )
    if incorrectly_named_resources := [
        x
        for resource in resources.values()
        if (x := backend.serialize(resource.value)) != f"{children[0].name}.{resource.name}"
    ]:
        raise BartiqCompilationError(
            """Routine with repetition should have resource names like `child_name.resource_name."""
            f"""\nFound the following incorrectly named resources {incorrectly_named_resources}"""
        )

    new_resources = {}
    for resource in child_resources.values():
        replacement_value = backend.as_expression(f"{children[0].name}.{resource.name}")
        if resource.type == ResourceType.additive:
            new_value = repetition.sequence_sum(replacement_value, backend)
        elif resource.type == ResourceType.multiplicative:
            new_value = repetition.sequence_prod(replacement_value, backend)
        elif resource.type == ResourceType.qubits and repetition.sequence.type == "constant":
            # NOTE: Actually this could also be `new_value = resource.value`.
            # The reason it's not, is that in such case local_ancillae are counted twice
            # in calculate_highwater.
            continue
        elif ast.literal_eval(os.environ.get(REPETITION_ALLOW_ARBITRARY_RESOURCES_ENV, "False")):
            new_value = replacement_value
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
    derived_resources: Iterable[DerivedResources] = (),
    compilation_flags: CompilationFlags = CompilationFlags(0),  # CompilationsFlags(0) corresponds to no flags
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
        compiled_child = _compile(
            routine=child,
            backend=backend,
            inputs=parameter_map[child.name],
            context=context.descend(child.name),
            derived_resources=derived_resources,
            compilation_flags=compilation_flags,
        )
        compiled_children[child.name] = compiled_child
        parameter_map = _merge_param_trees(
            parameter_map, _param_tree_from_compiled_ports(connections_map[child.name], compiled_child.ports)
        )

    if CompilationFlags.EXPAND_RESOURCES in compilation_flags:
        children_variables = {
            f"{cname}.{rname}": resource.value
            for cname, child in compiled_children.items()
            for rname, resource in child.resources.items()
        }
        parameter_map[None] = {**parameter_map[None], **children_variables}

    resources = {**routine.resources, **_generate_arithmetic_resources(routine.resources, compiled_children, backend)}
    repetition = routine.repetition

    if routine.repetition is not None:
        resources = _process_repeated_resources(
            routine.repetition, resources, list(compiled_children.values()), backend
        )
        repetition = routine.repetition.substitute_symbols(parameter_map[None], backend=backend)

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

    new_resources = evaluate_resources(resources, parameter_map[None], backend)

    compiled_routine = CompiledRoutine[T](
        name=routine.name,
        type=routine.type,
        input_params=new_input_params,
        children=compiled_children,
        ports=compiled_ports,
        resources=new_resources,
        constraints=new_constraints,
        connections=routine.connections,
        repetition=repetition,
        children_order=routine.children_order,
    )

    tmp_routine = (
        compiled_routine
        if CompilationFlags.EXPAND_RESOURCES in compilation_flags
        else _introduce_placeholder_child_resources(compiled_routine, backend)
    )
    tmp_routine = _add_derived_resources(tmp_routine, backend, derived_resources)

    return replace(compiled_routine, resources=tmp_routine.resources)


def _accepts_resource_name(func: Calculate[T] | CalculateWithName[T]) -> TypeIs[CalculateWithName[T]]:
    return "resource_name" in inspect.signature(func).parameters


def _introduce_placeholder_resources(
    compiled_routine: CompiledRoutine[T], backend: SymbolicBackend[T]
) -> CompiledRoutine[T]:
    return replace(
        compiled_routine,
        resources={
            name: replace(res, value=backend.as_expression(f"{compiled_routine.name}.{name}"))
            for name, res in compiled_routine.resources.items()
        },
    )


def _introduce_placeholder_child_resources(
    compiled_routine: CompiledRoutine[T], backend: SymbolicBackend[T]
) -> CompiledRoutine[T]:
    return replace(
        compiled_routine,
        children={
            cname: _introduce_placeholder_resources(child, backend)
            for cname, child in compiled_routine.children.items()
        },
    )


def _add_derived_resources(
    routine: CompiledRoutine[T],
    backend: SymbolicBackend[T],
    derived_resources: Iterable[DerivedResources[T]] = (),
) -> CompiledRoutine[T]:
    for specs in derived_resources:
        name = specs["name"]
        type = specs["type"]
        calculate = specs["calculate"]

        value = (
            calculate(routine, backend, resource_name=name)
            if _accepts_resource_name(calculate)
            else calculate(routine, backend)
        )

        if value is not None:
            resource = Resource(name, type=ResourceType(type), value=value)
            routine = replace(
                routine,
                resources={
                    **routine.resources,
                    name: resource,
                },
            )
    return routine


def _generate_arithmetic_resources(
    resources: dict[str, Resource[T]], compiled_children: dict[str, CompiledRoutine[T]], backend: SymbolicBackend[T]
) -> dict[str, Resource[T]]:
    """Returns resources dict with sum/prod of all the additive/multiplicative resources of the children.

    Since additive/multiplicative resources follow simple rules (value of a resource is equal to sum/product of
    the resources of it's children), we can just have it defined for appropriate leaves and then "bubble them up".
    This step generates such resources for the parent.

    Args:
        resources: routine's resources
        compiled_children: children from which the resources need to be derived.
        backend: a backend used for manipulating symbolic expressions.

    Returns:
        A dictionary containing generated resources
    """
    child_additive_resources_map: defaultdict[str, set[str]] = defaultdict(set)
    child_multiplicative_resources_map: defaultdict[str, set[str]] = defaultdict(set)

    for child in compiled_children.values():
        for resource in child.resources.values():
            if resource.type == ResourceType.additive:
                child_additive_resources_map[resource.name].add(child.name)
            if resource.type == ResourceType.multiplicative:
                child_multiplicative_resources_map[resource.name].add(child.name)

    additive_resources: dict[str, Resource[T]] = {
        res_name: Resource(
            name=res_name,
            type=ResourceType.additive,
            value=backend.sum(*[backend.as_expression(f"{child_name}.{res_name}") for child_name in children]),
        )
        for res_name, children in child_additive_resources_map.items()
        if res_name not in resources
    }

    multiplicative_resources: dict[str, Resource[T]] = {
        res_name: Resource(
            name=res_name,
            type=ResourceType.multiplicative,
            value=backend.prod(*[backend.as_expression(f"{child_name}.{res_name}") for child_name in children]),
        )
        for res_name, children in child_multiplicative_resources_map.items()
        if res_name not in resources
    }
    return {**additive_resources, **multiplicative_resources}
