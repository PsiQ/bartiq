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

from typing import Optional

from bartiq._routine import Connection, Port


def join_paths(*paths: str) -> str:
    """Helper function for joining paths in a routine."""
    if paths[0] == "":
        paths = paths[1:]
    return ".".join(paths)


def get_port_source(port: Port) -> Port:
    """Finds the port's source port, i.e. the terminal port reached by following upstream connections.
    It ignores the intermediate ports, like parent's ports, which only facilitate
    connections through layers of hierarchy, but do not provide meaningful inputs.
    """
    route = get_route(port, forward=False)
    return route[-1]


def get_port_target(port: Port) -> Port:
    """Finds port's target port, i.e. the terminal port reached by following downstream connections.
    It ignores the intermediate ports, like parent's ports, which only facilitate
    connections through layers of hierarchy, but do not provide meaningful inputs.
    """
    route = get_route(port, forward=True)
    return route[-1]


def get_route(port: Port, forward: bool = True) -> list[Port]:
    """Returns a list of all the ports that will be encountered when following particular port in either direction."""
    route = [port]
    pred = _is_source if forward else _is_target

    while (successor := _get_next_port(port, pred)) is not None:
        port = successor
        route.append(port)
    return route


def _is_source(port: Port, connection: Connection) -> bool:
    return connection.source is port


def _is_target(port: Port, connection: Connection) -> bool:
    return connection.target is port


def _other_end(port: Port, connection: Connection) -> Port:
    return connection.source if connection.target is port else connection.target


def _get_next_port(port: Port, predicate) -> Optional[Port]:
    routine = port.parent
    ancestry_depth = 0

    # Terminate whenever we reach either root or grand-grand parent of port.
    while routine is not None and ancestry_depth < 2:
        for connection in routine.connections:
            if predicate(port, connection):
                return _other_end(port, connection)
        routine = routine.parent
        ancestry_depth += 1

    return None
