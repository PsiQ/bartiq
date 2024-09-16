from collections import defaultdict
from dataclasses import replace
from typing import Callable, TypeVar

from .._routine import Constraint, PortDirection, Resource, ResourceType, Routine
from ..symbolics.backend import SymbolicBackend, TExpr

T = TypeVar("T")

PreprocessingStage = Callable[[Routine[T], SymbolicBackend[T]], Routine[T]]


def postorder_transform(transform: PreprocessingStage[T]) -> PreprocessingStage[T]:
    """Given a callable mapping a routine to a routine, expand it to transform hierarchical graph in postorder fashion.

    Args:
        transform: a function accepting a routine and a symbolic backend and returning a new routine.

    Returns:
        A function with the same signature as `transform`. The function works by traversing the hierarchical graph
        in postorder, applying `transform` to each child before applying it to the parent.
    """

    def _inner(routine: Routine[T], backend: SymbolicBackend[T]) -> Routine[T]:
        return transform(
            replace(routine, children={child.name: _inner(child, backend) for child in routine.children.values()}),
            backend,
        )

    return _inner


@postorder_transform
def add_default_additive_resources(routine: Routine[T], backend: SymbolicBackend[T]) -> Routine[T]:
    """Adds additive resources to all the ancestors of a particular having this resource.

    Since additive resources follow simple rules (value of a resource is equal to sum of the resources
    of it's children), rather than defining it for all the subroutines, we can just have it defined for
    appropriate leaves and then "bubble it up" using this preprocessing transformation.

    Args:
        routine: routine to be preprocessed
        backend: a backend used for manipulating symbolic expressions.

    Returns:
        A routine with all the additive resources defined appropriately at all levels of the hierarchy.
    """
    child_resources_map: defaultdict[str, set[str]] = defaultdict(set)

    for child in routine.children.values():
        for resource in child.resources.values():
            if resource.type == ResourceType.additive:
                child_resources_map[resource.name].add(child.name)

    additional_resources: dict[str, Resource[T]] = {
        res_name: Resource(
            name=res_name,
            type=ResourceType.additive,
            value=sum(
                (backend.as_expression(f"{child_name}.{res_name}") for child_name in children),  # type: ignore
                0,
            ),
        )
        for res_name, children in child_resources_map.items()
        if res_name not in routine.resources
    }

    return replace(routine, resources={**routine.resources, **additional_resources})


@postorder_transform
def promote_unlinked_inputs(routine: Routine[T], backend: SymbolicBackend[T]) -> Routine[T]:
    """Adds unlinked child params to the parent.

    If a leaf subroutine had some parameters which are not accessible from the top level routine,
    we would not be able compile it. Therefore, this function takes any `input_param` which is not
    linked to the parent and adds it to the parent alongside a corresponding link.

    Args:
        routine: routine to be preprocessed
        backend: a backend used for manipulating symbolic expressions.

    Returns:
        A routine with the missing links added.
    """
    all_targets = [tuple(target) for _, targets in routine.linked_params.items() for target in targets]

    additional_param_links = {
        f"{child.name}.{input}": ((child.name, input),)
        for child in routine.children.values()
        for input in child.input_params
        if (child.name, input) not in all_targets
    }
    return replace(
        routine,
        input_params=tuple([*routine.input_params, *additional_param_links]),
        linked_params={**routine.linked_params, **additional_param_links},
    )


@postorder_transform
def _introduce_port_variables(routine: Routine[T], backend: SymbolicBackend[T]) -> Routine[T]:
    new_ports = {}
    additional_local_variables: dict[str, TExpr[T]] = {}
    new_input_params: list[str] = []
    additional_constraints: list[Constraint[T]] = []
    for port in routine.ports.values():
        if port.direction == PortDirection.output:
            new_ports[port.name] = port
        else:
            new_variable_name = f"#{port.name}"
            new_variable = backend.as_expression(new_variable_name)
            if (size := backend.serialize(port.size)) != new_variable_name and backend.is_single_parameter(port.size):
                if size not in additional_local_variables:
                    additional_local_variables[size] = new_variable
                else:
                    additional_constraints.append(Constraint(new_variable, additional_local_variables[size]))
            elif backend.is_constant_int(port.size):
                additional_constraints.append(Constraint(new_variable, port.size))
            new_ports[port.name] = replace(port, size=new_variable)
            new_input_params.append(new_variable_name)
    return replace(
        routine,
        ports=new_ports,
        input_params=tuple([*routine.input_params, *new_input_params]),
        local_variables={**routine.local_variables, **additional_local_variables},
        constraints=tuple([*routine.constraints, *additional_constraints]),
    )


def introduce_port_variables(routine: Routine[T], backend: SymbolicBackend[T]) -> Routine[T]:
    """Adds variables representing port sizes to a routine.

    Args:
        routine: routine to be preprocessed
        backend: a backend used for manipulating symbolic expressions.

    Returns:
        A routine with the extra variables representing port sizes.
    """

    return replace(
        routine, children={name: _introduce_port_variables(child, backend) for name, child in routine.children.items()}
    )


def propagate_linked_params(routine: Routine[T], backend: SymbolicBackend[T]) -> Routine[T]:
    """Turns parameter links of level deeper than one into series of direct links.

    Args:
        routine: routine to be preprocessed
        backend: a backend used for manipulating symbolic expressions.

    Returns:
        A routine with the deep linked params decomposed and approprietly defined at each level.
    """
    new_linked_params: dict[str, tuple[tuple[str, str], ...]] = {}
    children = routine.children.copy()
    for source_param, targets in routine.linked_params.items():
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
                        new_input_param: ((further_path, target_param),),
                        **children[child_path].linked_params,
                    },
                )
                current_links.append((child_path, new_input_param))
            else:
                current_links.append((path, target_param))
        new_linked_params[source_param] = tuple(current_links)
    return replace(
        routine,
        linked_params=new_linked_params,
        children={name: propagate_linked_params(child, backend) for name, child in children.items()},
    )


DEFAULT_PREPROCESSING_STAGES = (
    add_default_additive_resources,
    propagate_linked_params,
    promote_unlinked_inputs,
    introduce_port_variables,
)
