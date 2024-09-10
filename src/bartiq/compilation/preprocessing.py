from collections import defaultdict
from dataclasses import replace
from typing import Callable

from .._routine import Constraint, PortDirection, Resource, ResourceType, Routine
from ..compilation._utilities import is_single_parameter
from ..symbolics.backend import SymbolicBackend, T_expr

PreprocessingStage = Callable[[Routine[T_expr], SymbolicBackend[T_expr]], Routine[T_expr]]


def postorder_transform(transform: PreprocessingStage[T_expr]) -> PreprocessingStage[T_expr]:
    def _inner(unit: Routine[T_expr], backend: SymbolicBackend[T_expr]) -> Routine[T_expr]:
        return transform(
            replace(unit, children={child.name: _inner(child, backend) for child in unit.children.values()}), backend
        )

    return _inner


@postorder_transform
def add_default_additive_resources(unit: Routine[T_expr], backend: SymbolicBackend[T_expr]) -> Routine[T_expr]:
    child_resources_map: defaultdict[str, set[str]] = defaultdict(set)

    for child in unit.children.values():
        for resource in child.resources.values():
            if resource.type == ResourceType.additive:
                child_resources_map[resource.name].add(child.name)

    additional_resources: dict[str, Resource[T_expr]] = {
        # The eefault here is to satisfy the typechecker
        res_name: Resource(
            name=res_name,
            type=ResourceType.additive,
            value=sum((backend.as_expression(f"{child_name}.{res_name}") for child_name in children), start=0),
        )
        for res_name, children in child_resources_map.items()
        if res_name not in unit.resources
    }

    return replace(unit, resources={**unit.resources, **additional_resources})


@postorder_transform
def promote_unlinked_inputs(unit: Routine[T_expr], backend: SymbolicBackend[T_expr]) -> Routine[T_expr]:
    all_targets = [tuple(target) for _, targets in unit.linked_params.items() for target in targets]

    additional_param_links = {
        f"{child.name}.{input}": [(child.name, input)]
        for child in unit.children.values()
        for input in child.input_params
        if (child.name, input) not in all_targets
    }
    return replace(
        unit,
        input_params=tuple([*unit.input_params, *additional_param_links]),
        linked_params={**unit.linked_params, **additional_param_links},
    )


@postorder_transform
def _introduce_port_variables(unit: Routine[T_expr], backend: SymbolicBackend[T_expr]) -> Routine[T_expr]:
    new_ports = {}
    additional_local_variables: dict[str, T_expr] = {}
    new_input_params: list[str] = []
    additional_constraints: list[Constraint[T_expr]] = []
    for port in unit.ports.values():
        if port.direction == PortDirection.output:
            new_ports[port.name] = port
        else:
            new_variable_name = f"#{port.name}"
            new_variable = backend.as_expression(new_variable_name)
            if is_single_parameter((size := backend.serialize(port.size))) and size != new_variable_name:
                if size not in additional_local_variables:
                    additional_local_variables[size] = new_variable
                else:
                    additional_constraints.append(Constraint(new_variable, additional_local_variables[size]))
            elif backend.is_constant_int(port.size):
                additional_constraints.append(Constraint(new_variable, port.size))
            new_ports[port.name] = replace(port, size=new_variable)
            new_input_params.append(new_variable_name)
    return replace(
        unit,
        ports=new_ports,
        input_params=tuple([*unit.input_params, *new_input_params]),
        local_variables={**unit.local_variables, **additional_local_variables},
        constraints=tuple([*unit.constraints, *additional_constraints]),
    )


def introduce_port_variables(unit: Routine[T_expr], backend: SymbolicBackend[T_expr]) -> Routine[T_expr]:
    return replace(
        unit, children={name: _introduce_port_variables(child, backend) for name, child in unit.children.items()}
    )


def propagate_linked_params(unit: Routine[T_expr], backend: SymbolicBackend[T_expr]) -> Routine[T_expr]:
    new_linked_params: dict[str, list[tuple[str, str]]] = {}
    children = unit.children.copy()
    for source_param, targets in unit.linked_params.items():
        current_links: list[tuple[str, str]] = []
        for path, target_param in targets:
            parts = path.split(".", 1)
            if len(parts) == 2:
                child_path, further_path = parts
                new_input_param = f"{further_path}.{target_param}"
                children[child_path] = replace(
                    children[child_path], input_params=[*children[child_path].input_params, new_input_param]
                )
                children[child_path] = replace(
                    children[child_path],
                    linked_params={
                        new_input_param: [(further_path, target_param)],
                        **children[child_path].linked_params,
                    },
                )
                current_links.append((child_path, new_input_param))
            else:
                current_links.append((path, target_param))
        new_linked_params[source_param] = current_links
    return replace(
        unit,
        linked_params=new_linked_params,
        children={name: propagate_linked_params(child, backend) for name, child in children.items()},
    )


DEFAULT_PRECOMPILATION_STAGES = (
    add_default_additive_resources,
    propagate_linked_params,
    promote_unlinked_inputs,
    introduce_port_variables,
)
