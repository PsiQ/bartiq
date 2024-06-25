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

# Note:
#     This module makes heavy use of Pydantic and its validation components.
#     In case the use of name "validation" is confusing, please see pydantic documentation:
#     https://docs.pydantic.dev/latest/concepts/models/ .

from __future__ import annotations

from collections import Counter, defaultdict
from enum import Enum
from typing import Annotated, Any, Iterable, Optional, Sequence, TypeVar, Union, cast

from pydantic import BaseModel as _BaseModel
from pydantic import (
    BeforeValidator,
    Field,
    PlainSerializer,
    StringConstraints,
    field_serializer,
    field_validator,
)
from qref.schema_v1 import NAME_PATTERN
from typing_extensions import Self

T = TypeVar("T", bound="Routine")

TYPE_LOOKUP = {
    int: "int",
    float: "float",
    str: "str",
    type(None): None,
}

Value = Union[int, float, str]
Symbol = str
_Name = Annotated[str, StringConstraints(pattern=rf"^{NAME_PATTERN}$")]


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


def _serialize_value(value: Optional[Value]) -> dict[str, Union[str, int, float, None]]:
    return {"type": TYPE_LOOKUP[type(value)], "value": value}


def _deserialize_value(v: Union[dict[str, Any], Value]) -> Value:
    if isinstance(v, dict):
        return v["value"]
    else:
        return v


AnnotatedValue = Annotated[Value, BeforeValidator(_deserialize_value), PlainSerializer(_serialize_value)]


def _resolve_port(selector: str, children: dict[str, Routine], ports: dict[str, Port]):
    *child_selector, port_name = selector.split(".")
    return children[child_selector[0]].ports[port_name] if child_selector else ports[port_name]


def _parse_connection_dict(connection: dict[str, str], children: dict[str, Routine], ports: dict) -> Connection:
    try:
        return Connection(
            source=_resolve_port(connection["source"], children, ports),
            target=_resolve_port(connection["target"], children, ports),
        )
    # If we wouldn't re-raise KeyError as ValueError, pydantic validation would have confusing error message.
    except KeyError as e:
        raise ValueError(
            "Inconsistent children data when parsing connections. Most probably some of the "
            "child routine failed to validate or the names used in connections don't match the routines."
        ) from e


def _find_descendant(selector, children):
    direct_child_selector, *sub_selector = selector.split(".", 1)
    try:
        child = children[direct_child_selector]
        return child.find_descendant(sub_selector[0]) if sub_selector else child
    except (KeyError, ValueError) as e:
        raise ValueError("Child {selector} not found.") from e


def _update_parent(children, parent: Routine) -> None:
    for child in children:
        child.parent = parent


def _sort_children_topologically(routine: T) -> Iterable[T]:
    """Sort children of given routine topologically.

    This function uses Kahn's algorithm, see:
    https://en.wikipedia.org/wiki/Topological_sorting

    Topological order is not unique, but guarantees that if two children a and b
    are joined by the edge a->b, then a will appear in the order before b
    (but not necessarily just before).
    """
    # Extract connections that are relevant to children ordering, i.e. only the ones
    # that connect two children (and not children with parent).
    # For each such connection we only preserve the name of the source and target child,
    # the names of children will serves as names of nodes in graph.
    graph_edges = set(
        (cn.source.parent.name, cn.target.parent.name)  # type: ignore
        for cn in routine.connections
        if cn.source.parent is not routine and cn.target.parent is not routine
    )

    # Count number of incoming edges for each node, this will be used for
    # detecting dangling nodes.
    in_degrees = Counter(target for _, target in graph_edges)

    # Also, construct adjacency list, this will help us to virtually "remove"
    # edges and make some nodes dangle!
    adjacencies = defaultdict(set)

    for source, target in graph_edges:
        adjacencies[source].add(target)

    # Find dangling nodes, i.e. ones that don't have any incoming edge.
    dangling_nodes = [name for name in routine.children if in_degrees[name] == 0]

    # Proceed while there are any dangling nodes
    while dangling_nodes:
        # Pick one such node and remove all edges that go out of it
        current_node = dangling_nodes.pop()
        for dst in adjacencies[current_node]:
            # Actually, we don't have to perform any removal, it is sufficient
            # to decrease indegree of the other end of the edge.
            in_degrees[dst] -= 1

            # If it was the last incoming edge, we found a new dangling node,
            # and hence we add it to the list of dangling nodes.
            if in_degrees[dst] == 0:
                dangling_nodes.append(dst)
        # Finally, yield child corresponding to current node and move to the next one.
        yield cast(T, routine.children[current_node])

    # If there was an edge that we didn't "remove", it must mean there was a cycle.
    # We have to raise an error because the ordering we found so far is
    # incomplete and incorrect.
    if any(deg > 0 for deg in in_degrees.values()):
        raise ValueError(f"A cycle occurred while sorting children of routine {routine.name}.")


class BaseModel(_BaseModel):
    """Base class for all our models.

    The model uses enum values for serialization and allows for arbitrary types,
    which is needed for handling sympy symbols.
    """

    model_config = {"arbitrary_types_allowed": True, "use_enum_values": True, "extra": "forbid"}


class Routine(BaseModel):
    """Subroutine in a quantum program.

    Attributes:
        name: Name of the subroutine.
        type: Type of the subroutine, might be None.
        ports: Dictionary mapping port name to corresponding Port object with the same name.
        parent: A Routine whose this routine is subroutine of. Might be None, in which
            case the routine is considered to be root of computation.
        children: Dictionary mapping name of subroutine of this routine into routine
            object with the same name.
        connections: List of connections objects, containing all the directed edges between
            either ports of this routine and ports of its children or ports of two children.
            Importantly, by convention, connection objects cannot descend further then one
            generation (i.e. there might not be a connection between routine and its
            grandchild).
        resources: Dictionary mapping name of the resource to corresponding Resource object.
        input_params: Sequence of symbols determining inputs for this routine.
        local_variables: Convenience aliases to expressions commonly used within this Routine.
            For instance, for a Routine with input parameter d one of the local variables
            can be N=ceil(log_2(d)).
        linked_params: Dictionary defining relations between parameters of this routine and
            parameters of its children. This dictionary is keyed with this routine's
            symbols, with the corresponding values being list of pairs (child, param) to
            which the symbol is connected to. Unlike connections, parameters links might
            descend further than one generation.
        meta: Addictional free-form information associated with this routine.
    """

    name: _Name
    type: Optional[str] = None
    ports: dict[str, Port] = Field(default_factory=dict)
    parent: Optional[Self] = Field(exclude=True, default=None)
    children: dict[str, Routine] = Field(default_factory=dict)
    connections: list[Connection] = Field(default_factory=list)
    resources: dict[str, Resource] = Field(default_factory=dict)
    input_params: Sequence[Symbol] = Field(default_factory=list)
    local_variables: list[str] = Field(default_factory=list)
    linked_params: dict[Symbol, list[tuple[str, Symbol]]] = Field(default_factory=dict)
    meta: Optional[dict[str, Any]] = Field(default_factory=dict)

    def __init__(self, **data: Any):
        sanitized_data = {k: v for k, v in data.items() if v != [] and v != {}}
        super().__init__(**sanitized_data)
        _update_parent(self.ports.values(), self)
        _update_parent(self.connections, self)
        _update_parent(self.children.values(), self)
        _update_parent(self.resources.values(), self)

    def __repr__(self):
        return f'<{self.__class__.__name__} name="{self.name}">'

    def __eq__(self, other: Any):
        return isinstance(other, Routine) and self.model_dump() == other.model_dump()

    def walk(self) -> Iterable[Self]:
        """Iterates through all the ancestry, deep-first."""
        for child in _sort_children_topologically(self):
            yield from child.walk()
        yield self

    @property
    def input_ports(self) -> dict[str, Port]:
        """Dictionary of input ports of this routine."""
        return {
            port_name: port
            for port_name, port in self.ports.items()
            if port.direction in (PortDirection.input, PortDirection.through)
        }

    @property
    def output_ports(self) -> dict[str, Port]:
        """Dictionary of output ports of this routine."""
        return {
            port_name: port
            for port_name, port in self.ports.items()
            if port.direction in (PortDirection.output, PortDirection.through)
        }

    @property
    def is_leaf(self) -> bool:
        """Return True if this routine is a leaf, and false otherwise.

        By the definition, a routine is a leaf iff it has no children.
        """
        return len(self.children) == 0

    @property
    def is_root(self) -> bool:
        """Return True if this routine is a root, and false otherwise.

        By the definition, a routine is a root iff it doesn't have a parent.
        """
        return self.parent is None

    @field_validator("connections", mode="before")
    @classmethod
    def _validate_connections(cls, v, values) -> list[Connection]:
        return [
            (
                connection
                if isinstance(connection, Connection)
                else _parse_connection_dict(connection, values.data.get("children", {}), values.data.get("ports", {}))
            )
            for connection in v
        ]

    @field_serializer("connections")
    def _serialize_connections(self, connections):
        return [connection.model_dump() for connection in sorted(connections, key=Connection.model_dump_json)]

    @field_serializer("input_params")
    def _serialize_input_params(self, input_params):
        return sorted(input_params)

    def find_descendant(self, selector: str) -> Routine:
        """Given a selector of a child, return the corresponding routine.

        Args:
            selector: a string comprising sequence of names determining the child.
                For instance, a string "a.b.c" mean child with name "c" of
                routine with name "b", which itself is a child of routine "a"
                which is a child of self. If empty string is provided, returns itself.

        Returns:
            Routine corresponding to given selector.

        Raises:
            ValueError: if given child is not found.
        """
        if selector == "":
            return self
        else:
            return _find_descendant(selector, self.children)

    def relative_path_from(self, ancestor: Optional[Routine], exclude_root_name: bool = False) -> str:
        """Return relative path to the ancestor.

        Args:
            ancestor: Ancestor from which a relative path to self should be found.
            exclude_root_name: if True, removes the name of the root from the relative path, if it is present.

        Returns:
            selector s such that ancestor.find_descendant(s) is self.

        Raises:
            ValueError: If ancestor is not, in fact, an ancestor of self.
        """

        # For root node return an empty string
        if self.parent is None and ancestor is None and exclude_root_name:
            return ""
        if self.parent is ancestor:
            return self.name
        else:
            try:
                return f"{self.parent.relative_path_from(ancestor, exclude_root_name=exclude_root_name)}.{self.name}"  # type: ignore # noqa: E501
            except (ValueError, AttributeError) as e:
                raise ValueError("Ancestor not found.") from e

    def absolute_path(self, exclude_root_name: bool = False) -> str:
        """Returns a path from root.

        Args:
            exclude_root_name: If true, excludes name of root from the path. Default: False
        """
        if self.parent is None and exclude_root_name:
            return ""
        else:
            return self.relative_path_from(None, exclude_root_name=exclude_root_name).removeprefix(".")

    def _repr_markdown_(self):
        from .integrations.latex import routine_to_latex

        return routine_to_latex(self)


class Resource(BaseModel):
    """Resource associated with a routine.

    Attributes:
        name: Name of the resource.
        type: Type of the resource.
        parent: Routine whose resource this object represents.
        value: Value of the resources, either concrete one or a variable.
    """

    name: _Name
    type: ResourceType
    parent: Optional[Routine] = Field(exclude=True, default=None)
    value: AnnotatedValue

    def __repr__(self):
        return f'<{self.__class__.__name__} name="{self.name}" value="{self.value}">'


class Port(BaseModel):
    """Class representing a port.

    Attributes:
        name: Name of this port.
        parent: Routine to which this port belongs to.
        direction: Direction of this port. Port can be either input, output or
            bidirectional.
        size: Size of this port. It might be a concrete value or a variable.
        meta: Additional free-form data associated with this port.
    """

    name: _Name
    parent: Optional[Routine] = Field(exclude=True, default=None)
    direction: PortDirection
    size: Optional[AnnotatedValue]
    meta: Optional[dict[str, Any]] = Field(default_factory=dict)

    def __repr__(self):
        parent_name = "none" if self.parent is None else self.parent.name
        size_value = "None" if self.size is None else f'"{self.size}"'
        return f"{self.__class__.__name__}({parent_name}.#{self.name}, size={size_value}, {self.direction})"

    def absolute_path(self, exclude_root_name: bool = False) -> str:
        """Returns a path from root.

        Args:
            exclude_root_name: If true, excludes name of root from the path. Default: False
        """
        assert self.parent is not None
        if self.parent.absolute_path(exclude_root_name=exclude_root_name) == "":
            return f"#{self.name}"
        else:
            return f"{self.parent.absolute_path(exclude_root_name=exclude_root_name)}.#{self.name}"


class Connection(BaseModel):
    """Connection between two ports.

    Attributes:
        source: Port which the connection comes from.
        target: Port the connection targets.
        parent: Routine this connection belongs to. Note: it is marked as Optional
            only because of how Routine objects are internally constructed. In
            correctly constructed routines, no actual connection should have
            a None as a parent.
    """

    source: Port
    target: Port
    parent: Optional[Routine] = Field(exclude=True, default=None)

    def __repr__(self):
        parent_name = "none" if self.parent is None else self.parent.name
        return f"{self.__class__.__name__}({parent_name}.#{self.source.name} -> {parent_name}.#{self.target.name})"

    @field_serializer("source", "target")
    def _serialize_port(self, port):
        return port.name if port.parent is self.parent else f"{port.parent.name}.{port.name}"
