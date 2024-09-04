from dataclasses import replace

from .._routine_new import Port, Resource
from ..symbolics.backend import SymbolicBackend, T_expr

def evaluate_ports(ports: dict[str, Port[T_expr]], inputs: dict[str, T_expr], backend: SymbolicBackend[T_expr]) -> dict[str, Port[T_expr]]:
    return {name: replace(port, size=backend.substitute_all(port.size, inputs)) for name, port in ports.items()}


def evaluate_resources(resources: dict[str, Resource[T_expr]], inputs: dict[str, T_expr], backend: SymbolicBackend[T_expr]) -> dict[str, Resource[T_expr]]:
    return {
        name: replace(resource, value=backend.substitute_all(resource.value, inputs))
        for name, resource in resources.items()
    }
