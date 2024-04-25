"""
..  Copyright © 2024 PsiQuantum Corp.  All rights reserved.
    PSIQUANTUM CORP. CONFIDENTIAL
    This file includes unpublished proprietary source code of PsiQuantum Corp.
    The copyright notice above does not evidence any actual or intended publication
    of such source code. Disclosure of this source code or any related proprietary
    information is strictly prohibited without the express written permission of
    PsiQuantum Corp.
"""

from typing import Any, Union

from qart import SchemaV1

from .. import Port, Routine


def bartiq_to_qart(routine: Routine, version: str = "v1") -> SchemaV1:
    """Convert Bartiq routine to QART object."""
    if version != "v1":
        raise ValueError(f"Unsupported QART schema version {version}")
    return SchemaV1.model_validate({"version": "v1", "program": _bartiq_routine_to_qart_v1_dict(routine)})


def qart_to_bartiq(qart_obj: Union[SchemaV1, dict]) -> Routine:
    """Convert QART object to a Bartiq routine."""
    qart_obj = SchemaV1.model_validate(qart_obj)
    return _routine_v1_to_bartiq_routine(qart_obj.program)


def _scoped_port_name_from_op_port(port: Port, parent: Routine) -> str:
    assert port.parent is not None
    return port.name if port.parent is parent else f"{port.parent.name}.{port.name}"


def _ensure_primitive_type(value: Any) -> Union[int, float, str, None]:
    """Ensure given value is of primitive type (e.g. is not a sympy expression)."""
    return value if value is None or isinstance(value, (int, float, str)) else str(value)


def _bartiq_routine_to_qart_v1_dict(routine: Routine) -> dict:
    return {
        "name": routine.name,
        "type": routine.type,
        "children": [_bartiq_routine_to_qart_v1_dict(child) for child in routine.children.values()],
        "resources": [
            {
                "name": resource.name,
                "type": str(resource.type),
                "value": _ensure_primitive_type(resource.value),
            }
            for resource in routine.resources.values()
        ],
        "ports": [
            {
                "name": port.name,
                "direction": str(port.direction),
                "size": _ensure_primitive_type(port.size),
            }
            for port in routine.ports.values()
        ],
        "connections": [
            {
                "source": _scoped_port_name_from_op_port(connection.source, routine),
                "target": _scoped_port_name_from_op_port(connection.target, routine),
            }
            for connection in routine.connections
        ],
        "input_params": [str(symbol) for symbol in routine.input_params],
        "local_variables": [str(symbol) for symbol in routine.local_variables],
        "linked_params": [
            {
                "source": str(source),
                "targets": [f"{child.name}.{param}" for child, param in targets],
            }
            for source, targets in routine.linked_params.items()
        ],
        "meta": routine.meta,
    }


# Untypes because RoutineV1 is not public in QART
def _routine_v1_to_bartiq_routine(routine_v1) -> Routine:
    return Routine(
        name=routine_v1.name,
        children={child.name: _routine_v1_to_bartiq_routine(child) for child in routine_v1.children},
        type=routine_v1.type,
        ports={port.name: port.model_dump() for port in routine_v1.ports},
        resources={resource.name: resource.model_dump() for resource in routine_v1.resources},
        connections=[connection.model_dump() for connection in routine_v1.connections],
        input_params=routine_v1.input_params,
        linked_params={
            link.source: [target.split(".") for target in link.targets] for link in routine_v1.linked_params
        },
    )
