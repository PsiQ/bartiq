"""
..  Copyright © 2023-2024 PsiQuantum Corp.  All rights reserved.
    PSIQUANTUM CORP. CONFIDENTIAL
    This file includes unpublished proprietary source code of PsiQuantum Corp.
    The copyright notice above does not evidence any actual or intended publication
    of such source code. Disclosure of this source code or any related proprietary
    information is strictly prohibited without the express written permission of
    PsiQuantum Corp.

Classes used internally for representing compiled and uncompiled routines.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum, auto
from graphlib import TopologicalSorter
from typing import Generic, Literal, cast

from qref import SchemaV1
from qref.schema_v1 import ConnectionV1, PortV1, ResourceV1, RoutineV1
from typing_extensions import Self, TypedDict

from .symbolics.backend import SymbolicBackend, T_expr


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
class Constraint(Generic[T_expr]):
    lhs: T_expr
    rhs: T_expr
    status: ConstraintStatus = ConstraintStatus.inconclusive


@dataclass(frozen=True)
class Port(Generic[T_expr]):
    name: str
    direction: str
    size: T_expr


@dataclass(frozen=True)
class Resource(Generic[T_expr]):
    name: str
    type: ResourceType
    value: T_expr


@dataclass(frozen=True)
class Endpoint:
    routine_name: str | None
    port_name: str


class _CommonRoutineParams(TypedDict):
    name: str
    type: str | None
    input_params: Iterable[str]
    ports: dict[str, Port[T_expr]]
    resources: dict[str, Resource[T_expr]]
    connections: dict[Endpoint, Endpoint]


@dataclass(frozen=True)
class Routine(Generic[T_expr]):
    name: str
    type: str | None
    input_params: Iterable[str]
    linked_params: dict[str, tuple[tuple[str, str], ...]]
    local_variables: dict[str, T_expr]
    children: dict[str, Self]
    ports: dict[str, Port[T_expr]]
    resources: dict[str, Resource[T_expr]]
    connections: dict[Endpoint, Endpoint]
    constraints: Iterable[Constraint[T_expr]] = ()

    @property
    def inner_connections(self) -> dict[Endpoint, Endpoint]:
        return {
            source: target
            for source, target in self.connections.items()
            if source.routine_name is not None and target.routine_name is not None
        }

    def sorted_children(self) -> Iterable[Self]:
        predecessor_map: dict[str, set[str]] = {name: set() for name in self.children}
        for source, target in self.inner_connections.items():
            assert target.routine_name is not None and source.routine_name is not None  # Assert to satisfy typechecker
            predecessor_map[target.routine_name].add(source.routine_name)

        return [self.children[name] for name in TopologicalSorter(predecessor_map).static_order()]

    def filter_ports(self, directions: Iterable[str]) -> dict[str, Port[T_expr]]:
        return {port_name: port for port_name, port in self.ports.items() if port.direction in directions}

    @classmethod
    def from_qref(
        cls: type[Routine[T_expr]], qref_obj: SchemaV1 | RoutineV1, backend: SymbolicBackend[T_expr]
    ) -> Routine[T_expr]:
        program = qref_obj.program if isinstance(qref_obj, SchemaV1) else qref_obj
        return Routine[T_expr](
            children={child.name: cls.from_qref(child, backend) for child in program.children},
            local_variables={var: backend.as_expression(expr) for var, expr in program.local_variables.items()},
            linked_params={
                str(param.source): tuple(_rsplit_once(target) for target in param.targets)
                for param in program.linked_params
            },
            **_common_routine_dict_from_qref(qref_obj, backend),
        )


def _common_routine_dict_from_qref(
    qref_obj: SchemaV1 | RoutineV1, backend: SymbolicBackend[T_expr]
) -> _CommonRoutineParams[T_expr]:
    program = qref_obj.program if isinstance(qref_obj, SchemaV1) else qref_obj
    return {
        "name": program.name,
        "type": program.type,
        "ports": {port.name: _port_from_qref(port, backend) for port in program.ports},
        "input_params": tuple(program.input_params),
        "resources": {resource.name: _resource_from_qref(resource, backend) for resource in program.resources},
        "connections": {
            _endpoint_from_qref(conn.source): _endpoint_from_qref(conn.target) for conn in program.connections
        },
    }


def _rsplit_once(target: str) -> tuple[str, str]:
    parts = target.rsplit(".", 1)
    assert len(parts) == 2, f"Expected a string with at least one dot, got {target}."
    return (parts[0], parts[1])


def _port_from_qref(port: PortV1, backend: SymbolicBackend[T_expr]) -> Port[T_expr]:
    if port.size is None:
        size = f"#{port.name}"
    else:
        size = port.size
    return Port(name=port.name, direction=port.direction, size=backend.as_expression(size))


def _resource_from_qref(resource: ResourceV1, backend: SymbolicBackend[T_expr]) -> Resource[T_expr]:
    assert resource.value is not None, f"Resource {resource.name} has value of None, and this cannot be compiled."
    return Resource(name=resource.name, type=ResourceType(resource.type), value=backend.as_expression(resource.value))


def _connection_from_qref(connection: ConnectionV1) -> tuple[Endpoint, Endpoint]:
    return _endpoint_from_qref(connection.source), _endpoint_from_qref(connection.target)


def _endpoint_from_qref(endpoint: str) -> Endpoint:
    return Endpoint(*endpoint.split(".")) if "." in endpoint else Endpoint(None, endpoint)


@dataclass(frozen=True)
class CompiledRoutine(Generic[T_expr]):
    name: str
    type: str | None
    input_params: Iterable[str]
    children: dict[str, Self]
    ports: dict[str, Port[T_expr]]
    resources: dict[str, Resource[T_expr]]
    connections: dict[Endpoint, Endpoint]
    constraints: Iterable[Constraint[T_expr]] = ()


def compiled_routine_from_qref(
    routine: SchemaV1 | RoutineV1, backend: SymbolicBackend[T_expr]
) -> CompiledRoutine[T_expr]:
    routine = routine.program if isinstance(routine, SchemaV1) else routine
    return CompiledRoutine(
        name=routine.name,
        type=routine.type,
        input_params=tuple(sorted(routine.input_params)),
        children={child.name: compiled_routine_from_qref(child, backend) for child in routine.children},
        ports={port.name: _port_from_qref(port, backend) for port in routine.ports},
        resources={resource.name: _resource_from_qref(resource, backend) for resource in routine.resources},
        connections={source: target for source, target in map(_connection_from_qref, routine.connections)},
    )


def _port_to_qref(port: Port[T_expr], backend: SymbolicBackend[T_expr]) -> PortV1:
    return PortV1(
        name=port.name,
        size=backend.serialize(port.size),
        direction=cast(Literal["input", "output", "through"], port.direction),
    )


def _resource_to_qref(resource: Resource[T_expr], backend: SymbolicBackend[T_expr]) -> ResourceV1:
    return ResourceV1(name=resource.name, type=resource.type.value, value=backend.serialize(resource.value))


def _endpoint_to_qref(endpoint: Endpoint) -> str:
    return endpoint.port_name if endpoint.routine_name is None else f"{endpoint.routine_name}.{endpoint.port_name}"


def routine_to_qref(routine: Routine[T_expr] | CompiledRoutine[T_expr], backend: SymbolicBackend[T_expr]) -> SchemaV1:
    return SchemaV1(version="v1", program=_routine_to_qref_program(routine, backend))


def _routine_to_qref_program(
    routine: Routine[T_expr] | CompiledRoutine[T_expr], backend: SymbolicBackend[T_expr]
) -> RoutineV1:
    kwargs = (
        {
            "linked_params": {source: targets for source, targets in routine.linked_params.items()},
            "local_variables": {var: backend.as_expression(expr) for var, expr in routine.local_variables},
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
        **kwargs,
    )
