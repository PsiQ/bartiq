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
from dataclasses import dataclass
from enum import Enum, auto
from graphlib import TopologicalSorter
from typing import Generic, Literal, cast

from qref import SchemaV1
from qref.functools import AnyQrefType, ensure_routine
from qref.schema_v1 import ParamLinkV1, PortV1, ResourceV1, RoutineV1
from typing_extensions import Self, TypedDict, TypeVar

from .repetitions import Repetition, repetition_from_qref, repetition_to_qref
from .symbolics.backend import SymbolicBackend, T, TExpr

S = TypeVar("S", default=str | None)


class ResourceType(str, Enum):
    """Class for representing types of resources."""

    additive = "additive"
    multiplicative = "multiplicative"
    qubits = "qubits"
    other = "other"


class PortDirection(str, Enum):
    """Class for representing port direction."""

    input = "input"
    output = "output"
    through = "through"


class ConstraintStatus(Enum):
    inconclusive = auto()
    satisfied = auto()
    violated = auto()


@dataclass(frozen=True)
class Constraint(Generic[T]):
    lhs: TExpr[T]
    rhs: TExpr[T]
    status: ConstraintStatus = ConstraintStatus.inconclusive


@dataclass(frozen=True)
class Port(Generic[T]):
    name: str
    direction: str
    size: TExpr[T]


@dataclass(frozen=True)
class Resource(Generic[T]):
    name: str
    type: ResourceType
    value: TExpr[T]


@dataclass(frozen=True)
class Endpoint(Generic[S]):
    routine_name: S
    port_name: str


class _CommonRoutineParams(TypedDict, Generic[T]):
    name: str
    type: str | None
    input_params: Iterable[str]
    ports: dict[str, Port[T]]
    resources: dict[str, Resource[T]]
    repetition: Repetition[T] | None
    connections: dict[Endpoint, Endpoint]


@dataclass(frozen=True, kw_only=True)
class BaseRoutine(Generic[T]):
    name: str
    type: str | None
    children: dict[str, Self]
    ports: dict[str, Port[T]]
    resources: dict[str, Resource[T]]
    connections: dict[Endpoint, Endpoint]
    repetition: Repetition[T] | None = None
    constraints: Iterable[Constraint[T]] = ()
    children_order: tuple[str, ...] = ()

    def __post_init__(self):
        if len(self.children_order) != len(self.children) or set(self.children_order) != set(self.children):
            raise ValueError(
                "Attempted to construct a routine with child order not matching actual children. "
                + f"The order given is {self.children_order}, but the names of children are {list(self.children)}."
            )

    @property
    def resource_values(self) -> dict[str, TExpr[T]]:
        return {k: v.value for k, v in self.resources.items()}

    @property
    def inner_connections(self) -> dict[Endpoint[str], Endpoint[str]]:
        return cast(
            dict[Endpoint[str], Endpoint[str]],
            {
                source: target
                for source, target in self.connections.items()
                if source.routine_name is not None and target.routine_name is not None
            },
        )

    @property
    def sorted_children_order(self) -> Iterable[str]:
        predecessor_map: dict[str, set[str]] = {name: set() for name in self.children}
        for source, target in self.inner_connections.items():
            predecessor_map[target.routine_name].add(source.routine_name)

        visited = set[str]()

        is_sorted = True

        for child in self.children_order:
            if any(pred not in visited for pred in predecessor_map[child]):
                is_sorted = False
                break
            visited.add(child)

        return self.children_order if is_sorted else TopologicalSorter(predecessor_map).static_order()

    def sorted_children(self) -> Iterable[Self]:
        return [self.children[child_name] for child_name in self.sorted_children_order]


@dataclass(frozen=True, kw_only=True)
class Routine(BaseRoutine[T]):
    input_params: Iterable[str]
    linked_params: dict[str, tuple[tuple[str, str], ...]]
    local_variables: dict[str, TExpr[T]]

    def filter_ports(self, directions: Iterable[str]) -> dict[str, Port[T]]:
        """Returns all the ports with given directions"""
        return {port_name: port for port_name, port in self.ports.items() if port.direction in directions}

    @classmethod
    def from_qref(cls, qref_obj: AnyQrefType, backend: SymbolicBackend[T]) -> Routine[T]:
        """Load Routine from a QREF definition, using specified backend for parsing expressions."""
        program = ensure_routine(qref_obj)
        children = {child.name: cls.from_qref(child, backend) for child in program.children}
        return Routine[T](
            children=children,
            local_variables={var: backend.as_expression(expr) for var, expr in program.local_variables.items()},
            linked_params={
                str(param.source): tuple(((split := target.rsplit(".", 1))[0], split[1]) for target in param.targets)
                for param in program.linked_params
            },
            children_order=tuple(children),
            **_common_routine_dict_from_qref(qref_obj, backend),
        )

    def to_qref(self, backend: SymbolicBackend[T]) -> SchemaV1:
        """Exports Routine to QREF.

        Args:
            backend: backend used to serialize the symbolic expressions.

        Returns:
            QREF object representing provided routine.

        """
        return SchemaV1(version="v1", program=_routine_to_qref_program(self, backend))


@dataclass(frozen=True, kw_only=True)
class CompiledRoutine(BaseRoutine[T]):
    input_params: Iterable[str]

    def filter_ports(self, directions: Iterable[str]) -> dict[str, Port[T]]:
        """Returns all the ports with given directions"""
        return {port_name: port for port_name, port in self.ports.items() if port.direction in directions}

    @classmethod
    def from_qref(cls, qref_obj: AnyQrefType, backend: SymbolicBackend[T]) -> CompiledRoutine[T]:
        """Load CompiledRoutine from a QREF definition, using specified backend for parsing expressions."""
        program = ensure_routine(qref_obj)
        children = {child.name: cls.from_qref(child, backend) for child in program.children}
        return CompiledRoutine[T](
            children=children,
            children_order=tuple(children),
            **_common_routine_dict_from_qref(qref_obj, backend),
        )

    def to_qref(self, backend: SymbolicBackend[T]) -> SchemaV1:
        """Exports Routine to QREF.

        Args:
            backend: backend used to serialize the symbolic expressions.

        Returns:
            QREF object representing provided routine.

        """
        return SchemaV1(version="v1", program=_routine_to_qref_program(self, backend))


def _common_routine_dict_from_qref(qref_obj: AnyQrefType, backend: SymbolicBackend[T]) -> _CommonRoutineParams[T]:
    program = ensure_routine(qref_obj)
    return {
        "name": program.name,
        "type": program.type,
        "ports": {port.name: _port_from_qref(port, backend) for port in program.ports},
        "input_params": program.input_params,
        "resources": {resource.name: _resource_from_qref(resource, backend) for resource in program.resources},
        "repetition": repetition_from_qref(program.repetition, backend),
        "connections": {
            _endpoint_from_qref(conn.source): _endpoint_from_qref(conn.target) for conn in program.connections
        },
    }


def _port_from_qref(port: PortV1, backend: SymbolicBackend[T]) -> Port[T]:
    size = f"#{port.name}" if port.size is None else port.size
    return Port(name=port.name, direction=port.direction, size=backend.as_expression(str(size)))


def _resource_from_qref(resource: ResourceV1, backend: SymbolicBackend[T]) -> Resource[T]:
    assert resource.value is not None, f"Resource {resource.name} has value of None, and this cannot be compiled."
    return Resource(name=resource.name, type=ResourceType(resource.type), value=backend.as_expression(resource.value))


def _endpoint_from_qref(endpoint: str) -> Endpoint:
    return Endpoint(*endpoint.split(".")) if "." in endpoint else Endpoint(None, endpoint)


def _port_to_qref(port: Port[T], backend: SymbolicBackend[T]) -> PortV1:
    return PortV1(
        name=port.name,
        size=backend.as_native(port.size),
        direction=cast(Literal["input", "output", "through"], port.direction),
    )


def _resource_to_qref(resource: Resource[T], backend: SymbolicBackend[T]) -> ResourceV1:
    return ResourceV1(name=resource.name, type=resource.type.value, value=backend.as_native(resource.value))


def _endpoint_to_qref(endpoint: Endpoint) -> str:
    return endpoint.port_name if endpoint.routine_name is None else f"{endpoint.routine_name}.{endpoint.port_name}"


def _linked_params_to_qref(linked_params: dict) -> list[ParamLinkV1]:
    return [
        ParamLinkV1(source=source, targets=[f"{target[0]}.{target[1]}" for target in targets])
        for source, targets in linked_params.items()
    ]


def routine_to_qref(routine: Routine[T] | CompiledRoutine[T], backend: SymbolicBackend[T]) -> SchemaV1:
    """Exports a Routine or CompiledRoutine object to QREF.

    Args:
        routine: routine to be exported.
        backend: backend used to serialize the symbolic expressions.

    Returns:
        QREF object representing provided routine.

    """
    return SchemaV1(version="v1", program=_routine_to_qref_program(routine, backend))


def _routine_to_qref_program(routine: Routine[T] | CompiledRoutine[T], backend: SymbolicBackend[T]) -> RoutineV1:
    kwargs = (
        {
            "linked_params": _linked_params_to_qref(routine.linked_params),
            "local_variables": {var: backend.serialize(expr) for var, expr in routine.local_variables.items()},
        }
        if isinstance(routine, Routine)
        else {}
    )

    return RoutineV1(
        name=routine.name,
        type=routine.type,
        input_params=routine.input_params,
        children=[_routine_to_qref_program(child, backend) for child in routine.children.values()],
        ports=[_port_to_qref(port, backend) for port in routine.ports.values()],
        resources=[_resource_to_qref(resource, backend) for resource in routine.resources.values()],
        connections=[
            {"source": _endpoint_to_qref(source), "target": _endpoint_to_qref(target)}
            for source, target in routine.connections.items()
        ],
        repetition=repetition_to_qref(routine.repetition, backend),
        **kwargs,
    )
