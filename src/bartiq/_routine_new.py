from dataclasses import dataclass
from enum import Enum, auto
from graphlib import TopologicalSorter
from typing import Generic, Iterable, Optional

from typing_extensions import Self

from ._routine import Connection
from ._routine import Port as OldPort
from ._routine import PortDirection
from ._routine import Resource as OldResource
from ._routine import ResourceType, Routine
from .symbolics.backend import SymbolicBackend, T_expr


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
    routine_name: Optional[str]
    port_name: str


@dataclass(frozen=True)
class CompilationUnit(Generic[T_expr]):
    name: str
    type: Optional[str]
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
            if source.routine_name == target.routine_name:
                raise ValueError("cycle?")
            predecessor_map[target.routine_name].add(source.routine_name)

        return [self.children[name] for name in TopologicalSorter(predecessor_map).static_order()]


@dataclass(frozen=True)
class CompiledRoutine(Generic[T_expr]):
    name: str
    type: Optional[str]
    input_params: Iterable[str]
    children: dict[str, Self]
    ports: dict[str, Port[T_expr]]
    resources: dict[str, Resource[T_expr]]
    connections: dict[Endpoint, Endpoint]
    constraints: Iterable[Constraint[T_expr]] = ()


def _port_from_bartiq(port: OldPort, backend: SymbolicBackend[T_expr]) -> Port[T_expr]:
    if port.size is None:
        size = f"#{port.name}"
    else:
        size = port.size
    return Port(name=port.name, direction=PortDirection(port.direction).value, size=backend.as_expression(size))


def _resource_from_bartiq(resource: OldResource, backend: SymbolicBackend[T_expr]) -> Resource[T_expr]:
    return Resource(name=resource.name, type=resource.type, value=backend.as_expression(resource.value))


def _endpoint_from_bartiq(endpoint: str) -> Endpoint:
    return Endpoint(*endpoint.split(".")) if "." in endpoint else Endpoint(None, endpoint)


def _connection_from_bartiq(connection: Connection) -> tuple[Endpoint, Endpoint]:
    dump = connection.model_dump()
    return _endpoint_from_bartiq(dump["source"]), _endpoint_from_bartiq(dump["target"])


def compilation_unit_from_bartiq(routine: Routine, backend: SymbolicBackend[T_expr]) -> CompilationUnit[T_expr]:
    return CompilationUnit(
        name=routine.name,
        type=routine.type,
        input_params=tuple(sorted(routine.input_params)),
        linked_params={source: targets for source, targets in routine.linked_params.items()},
        children={name: compilation_unit_from_bartiq(child, backend) for name, child in routine.children.items()},
        ports={name: _port_from_bartiq(port, backend) for name, port in routine.ports.items()},
        resources={name: _resource_from_bartiq(resource, backend) for name, resource in routine.resources.items()},
        connections={source: target for source, target in map(_connection_from_bartiq, routine.connections)},
        local_variables={var: backend.as_expression(value) for var, value in routine.local_variables.items()},
    )


def _port_to_bartiq(port: Port[T_expr], backend: SymbolicBackend[T_expr]) -> OldPort:
    return OldPort(name=port.name, size=backend.serialize(port.size), direction=PortDirection(port.direction))


def _resource_to_bartiq(resource: Resource[T_expr], backend: SymbolicBackend[T_expr]) -> OldResource:
    return OldResource(name=resource.name, type=resource.type, value=backend.serialize(resource.value))


def _endpoint_to_bartiq(endpoint: Endpoint) -> str:
    return endpoint.port_name if endpoint.routine_name is None else f"{endpoint.routine_name}.{endpoint.port_name}"


def compiled_routine_to_bartiq(compilation_unit: CompiledRoutine[T_expr], backend: SymbolicBackend[T_expr]) -> Routine:
    return Routine(
        name=compilation_unit.name,
        type=compilation_unit.type,
        input_params=compilation_unit.input_params,
        children={
            name: compiled_routine_to_bartiq(child, backend) for name, child in compilation_unit.children.items()
        },
        ports={name: _port_to_bartiq(port, backend) for name, port in compilation_unit.ports.items()},
        resources={
            name: _resource_to_bartiq(resource, backend) for name, resource in compilation_unit.resources.items()
        },
        connections=[
            {"source": _endpoint_to_bartiq(source), "target": _endpoint_to_bartiq(target)}
            for source, target in compilation_unit.connections.items()
        ],
    )
