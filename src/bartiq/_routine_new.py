from dataclasses import dataclass
from graphlib import TopologicalSorter
from typing import Generic, Iterable, Optional

from typing_extensions import Self

from ._routine import Port, PortDirection, Resource, ResourceType, Routine
from .symbolics.backend import SymbolicBackend, T_expr


@dataclass(frozen=True)
class _Port(Generic[T_expr]):
    name: str
    direction: str
    size: T_expr


@dataclass(frozen=True)
class _Resource(Generic[T_expr]):
    name: str
    type: ResourceType
    value: T_expr


@dataclass(frozen=True)
class CompilationUnit(Generic[T_expr]):
    name: str
    type: Optional[str]
    input_params: Iterable[str]
    linked_params: dict[str, tuple[str, str]]
    local_variables: dict[str, T_expr]
    children: dict[str, Self]
    ports: dict[str, _Port[T_expr]]
    resources: dict[str, _Resource[T_expr]]
    connections: dict[str, str]

    @property
    def inner_connections(self) -> dict[str, str]:
        return {source: target for source, target in self.connections.items() if "." in source and "." in target}

    def sorted_children(self) -> Iterable[Self]:
        predecessor_map: dict[str, set[str]] = {name: set() for name in self.children}
        for source, target in self.inner_connections.items():
            predecessor_map[target.split(".")[0]].add(source.split(".")[0])

        return [self.children[name] for name in TopologicalSorter(predecessor_map).static_order()]


def _port_from_bartiq(port: Port, backend: SymbolicBackend[T_expr]) -> _Port[T_expr]:
    if port.size is None:
        size = f"{port.parent.name}.{port.name}" if port.direction != "output" else port.name
    else:
        size = port.size
    return _Port(name=port.name, direction=PortDirection(port.direction).value, size=backend.as_expression(size))


def _resource_from_bartiq(resource: Resource, backend: SymbolicBackend[T_expr]) -> _Resource[T_expr]:
    return _Resource(name=resource.name, type=resource.type, value=backend.as_expression(resource.value))


def compilation_unit_from_bartiq(routine: Routine, backend: SymbolicBackend[T_expr]) -> CompilationUnit[T_expr]:
    return CompilationUnit(
        name=routine.name,
        type=routine.type,
        input_params=tuple(sorted(routine.input_params)),
        linked_params={source: targets for source, targets in routine.linked_params.items()},
        children={name: compilation_unit_from_bartiq(child, backend) for name, child in routine.children.items()},
        ports={name: _port_from_bartiq(port, backend) for name, port in routine.ports.items()},
        resources={name: _resource_from_bartiq(resource, backend) for name, resource in routine.resources.items()},
        connections={(conn := connection.model_dump())["source"]: conn["target"] for connection in routine.connections},
        local_variables={var: backend.as_expression(value) for var, value in routine.local_variables.items()},
    )


def _port_to_bartiq(port: _Port[T_expr], backend: SymbolicBackend[T_expr]) -> Port:
    return Port(name=port.name, size=backend.serialize(port.size), direction=PortDirection(port.direction))


def _resource_to_bartiq(resource: _Resource[T_expr], backend: SymbolicBackend[T_expr]) -> Resource:
    return Resource(name=resource.name, type=resource.type, value=backend.serialize(resource.value))


def compilation_unit_to_bartiq(compilation_unit: CompilationUnit[T_expr], backend: SymbolicBackend[T_expr]) -> Routine:
    return Routine(
        name=compilation_unit.name,
        type=compilation_unit.type,
        input_params=compilation_unit.input_params,
        linked_params={source: targets for source, targets in compilation_unit.linked_params.items()},
        children={
            name: compilation_unit_to_bartiq(child, backend) for name, child in compilation_unit.children.items()
        },
        ports={name: _port_to_bartiq(port, backend) for name, port in compilation_unit.ports.items()},
        resources={
            name: _resource_to_bartiq(resource, backend) for name, resource in compilation_unit.resources.items()
        },
        connections=[{"source": source, "target": target} for source, target in compilation_unit.connections.items()],
    )
