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

import warnings
from typing import Any, Optional, cast, overload

from .. import Port, Routine
from ..errors import BartiqCompilationError
from ..precompilation._core import PrecompilationStage, precompile
from ..routing import get_port_source, get_port_target, join_paths
from ..symbolics import sympy_backend
from ..symbolics.backend import SymbolicBackend, T_expr
from ..symbolics.variables import DependentVariable
from ..verification import verify_compiled_routine, verify_uncompiled_routine
from ._symbolic_function import (
    RoutineWithFunction,
    SymbolicFunction,
    compile_functions,
    define_expression_functions,
    rename_functions,
    rename_variables,
    to_symbolic_function,
    update_routine_with_symbolic_function,
)
from ._utilities import get_children_in_walk_order, is_constant_int, is_single_parameter
from .types import FunctionsMap, Number


@overload
def compile_routine(
    routine: Routine,
    *,
    precompilation_stages: Optional[list[PrecompilationStage]] = None,
    global_functions: Optional[list[str]] = None,
    functions_map: Optional[FunctionsMap] = None,
    skip_verification: bool = False,
) -> Routine:
    pass  # pragma: no cover


@overload
def compile_routine(
    routine: Routine,
    *,
    backend: SymbolicBackend[T_expr],
    precompilation_stages: Optional[list[PrecompilationStage]] = None,
    global_functions: Optional[list[str]] = None,
    functions_map: Optional[FunctionsMap] = None,
    skip_verification: bool = False,
) -> Routine:
    pass  # pragma: no cover


def compile_routine(
    routine,
    *,
    backend=sympy_backend,
    precompilation_stages=None,
    global_functions=None,
    functions_map=None,
    skip_verification: bool = False,
):
    """Compile estimates for given uncompiled Routine.

    Args:
        routine: Routine to be compiled
        backend: The backend to use for manipulating symbolic expressions. Defaults to
            sympy_backend.
        precompilation_stages: a list of precompilation stages which should be applied. If `None`,
            default precompilation stages are used.
        global_functions: functions in the cost expressions which we don't want to have namespaced.
        functions_map: a dictionary which specifies non-standard functions which need to applied during compilation.
        skip_verification: if True, skips routine verification before and after compilation.
    """
    return _compile_routine(routine, backend, precompilation_stages, global_functions, functions_map, skip_verification)


def _compile_routine(
    routine: Routine,
    backend: SymbolicBackend[T_expr],
    precompilation_stages: Optional[list[PrecompilationStage]] = None,
    global_functions: Optional[list[str]] = None,
    functions_map: Optional[FunctionsMap] = None,
    skip_verification: bool = False,
):
    precompile(routine, precompilation_stages=precompilation_stages, backend=backend)
    if not skip_verification:
        verification_result = verify_uncompiled_routine(routine, backend=backend)
        if not verification_result:
            problems = [problem + "\n" for problem in verification_result.problems]
            raise BartiqCompilationError(
                f"Found the following issues with the provided routine before the compilation started: {problems}",
            )

    # NOTE: This step must be completed BEFORE we start to compile the functions, as parents must be allowed to
    # update their childrens' functions (to support parameter inheritance).
    routine_with_functions = _add_function_to_routine(routine, global_functions, backend)

    compiled_routine_with_funcs = _compile_routine_with_functions(routine_with_functions, functions_map, backend)

    compiled_routine = compiled_routine_with_funcs.to_routine()
    compiled_routine = _remove_children_costs(compiled_routine)
    if not skip_verification:
        verification_result = verify_compiled_routine(compiled_routine, backend=backend)
        if not verification_result:
            warnings.warn(
                "Found the following issues with the provided routine after the compilation has finished:"
                f" {verification_result.problems}",
            )
        # if len(verification_result.problems) != 0:
        #     breakpoint()
    return compiled_routine


def _add_function_to_routine(
    routine: Routine, global_functions: Optional[list[str]], backend: SymbolicBackend[T_expr]
) -> RoutineWithFunction[T_expr]:
    """Converts each routine to a symbolic function."""
    routine_with_functions = RoutineWithFunction.from_routine(routine)

    for subroutine in routine_with_functions.walk():
        subroutine.symbolic_function = _map_routine_to_function(subroutine, global_functions, backend)

    return routine_with_functions


def _map_routine_to_function(
    routine: RoutineWithFunction[T_expr],
    global_functions: Optional[list[str]],
    backend: SymbolicBackend[T_expr],
) -> SymbolicFunction[T_expr]:
    """Converts a routine to a symbolic function."""
    local_function = to_symbolic_function(routine, backend)

    # Updates the functions' namespace to a path-prefixed global
    global_function = _add_function_namespace(
        local_function, routine.absolute_path(exclude_root_name=True), global_functions
    )
    # Pull in and push out register sizes
    # NOTE: Non-leaf routines shouldn't have input or output register sizes defined
    # (since they are dependent upon the size of some other routines's register), so skip this step for them.
    if routine.is_leaf:
        # Only apply to non-root leaves; root leaves have no connections and so can be ignored
        if not routine.is_root:
            # Pull in the correct size param to use
            global_function = _pull_in_input_register_size_params(global_function, routine, backend)

        # Push out output port register sizes to targets
        global_function = _push_out_output_register_size_params(global_function, routine, backend)

    # If not a leaf, perform parameter inheritance
    else:
        _pass_on_inherited_params(routine)

    return global_function


def _add_function_namespace(
    function: SymbolicFunction[T_expr],
    namespace: Optional[str],
    global_functions: Optional[list[str]],
) -> SymbolicFunction[T_expr]:
    """Adds a namespace prefix to all parameters and user-defined expression functions in the function."""
    # Deal with trivial root case
    if not namespace:
        return function

    new_function = function
    # First, rename functions
    global_functions = global_functions or []
    function_namespace_map = {
        expression_function: join_paths(namespace, expression_function)
        for output in new_function.outputs.values()
        for expression_function in output.expression_functions
        if expression_function not in global_functions
    }
    new_function = rename_functions(new_function, function_namespace_map)
    # Next, rename variables
    variables = list(new_function.inputs.values()) + list(new_function.outputs.values())
    variable_namespace_map = {variable.symbol: join_paths(namespace, variable.symbol) for variable in variables}
    new_function = rename_variables(new_function, variable_namespace_map)

    return new_function


def _pull_in_input_register_size_params(
    function: SymbolicFunction[T_expr],
    routine: RoutineWithFunction[T_expr],
    backend: SymbolicBackend[T_expr],
) -> SymbolicFunction[T_expr]:
    """Rename input register sizes of the child with the parameter associated with the connected parent port."""
    new_function = function
    for input_port in routine.input_ports.values():
        new_function = _pull_in_input_register_size_param(new_function, input_port, backend)
    return new_function


def _pull_in_input_register_size_param(
    function: SymbolicFunction[T_expr], input_port: Port, backend: SymbolicBackend[T_expr]
) -> SymbolicFunction[T_expr]:
    """Renames a leaf's input register size to the associated high-level register size."""
    source_port = get_port_source(input_port)
    source_parent = source_port.parent
    assert source_parent is not None
    # In the case where the source is not the root (and hence must be a leaf), do nothing as this will be dealt with
    # when we push out the output register sizes.
    if source_parent.is_leaf:
        return function

    # If the source is not the root or a leaf, then it's a non-root container and so something's not connected up
    if not source_parent.is_root:
        raise BartiqCompilationError(
            "Can only pull in size parameters from the root routine, but source is a non-root non-leaf routine; "
            f"attempted to pull {source_port.absolute_path(exclude_root_name=True)} in to "
            f"{input_port.absolute_path(exclude_root_name=True)}."
            f"This indicates that {source_port.absolute_path(exclude_root_name=True)} terminates a connection "
            f"on a non-leaf routine, which is an invalid topology. "
            f"Please connect {source_port.absolute_path(exclude_root_name=True)} to a leaf port."
        )

    root_input_register_size = source_parent.input_ports[source_port.name].size

    # If the root input is of constant size, then we add this as an output to the new function
    if is_constant_int(root_input_register_size):
        assert isinstance(root_input_register_size, (int, str))
        new_function = set_input_port_size_to_constant_value(
            function, input_port.absolute_path(exclude_root_name=True), int(root_input_register_size), backend
        )
        return new_function

    # If the root input is of variable size, then we will rename the parameter with the root parameter
    elif is_single_parameter(root_input_register_size):
        root_param = join_paths(source_port.absolute_path(exclude_root_name=True), str(root_input_register_size))
        param = str(input_port.size)
        leaf_param = join_paths(input_port.absolute_path(exclude_root_name=True), param)
        if is_constant_int(param):
            raise BartiqCompilationError(
                "Input registers cannot be constant-sized; "
                f"attempted to merge register size {root_param} with {leaf_param}"
            )
        new_function = rename_variables(function, {leaf_param: root_param})

        return new_function

    raise BartiqCompilationError(
        f"Register sizes must either be integers or single parameters; found {root_input_register_size}"
    )


def set_input_port_size_to_constant_value(
    function: SymbolicFunction[T_expr],
    port_path: str,
    value: Number,
    backend: SymbolicBackend[T_expr],
) -> SymbolicFunction[T_expr]:
    """Assigns an input port size to a constant numeric value.

    NOTE: if multiple input ports share the same size variable parameter, then all these will be set to the same size.

    Args:
        function: The symbolic function that contains the a variable for an input port size.
        port_path: The global path to the port.
        value: The numeric value to assing to the port.
        backend: backend used for manipulating symbolic expressions.

    Returns:
        A new symbolic function with the port size parameter set.
    """
    # Case 1: function takes port size as input, so remove this and add a constant size and return the new function
    for input in function.inputs:
        input_path, input_param = _split_local_path(str(input))
        if input_path == port_path:
            # First, if a given variable is present in more than one port, simplify it.
            variable_map = _get_substitution_map(function, input_param, value)

            new_inputs = [
                input_variable
                for input_symbol, input_variable in function.inputs.items()
                if input_symbol not in variable_map
            ]

            new_outputs = []
            for variable, value in variable_map.items():
                variable_port_path, _ = _split_local_path(variable)
                new_output = DependentVariable(
                    symbol=variable_port_path,
                    expression=backend.as_expression(value),
                    backend=backend,
                )
                new_outputs.append(new_output)
            for old_output in function.outputs.values():
                new_output = old_output
                for variable, value in variable_map.items():
                    new_output = new_output.substitute(variable, value)
                new_outputs.append(new_output)

            return SymbolicFunction(new_inputs, new_outputs)

    # Case 2: function has port size set to constant, so check that the values match and return the original function
    port_path_value = function.outputs.get(port_path).value
    # Shouldn't be possible that function doesn't know anything about that port whatsoever
    assert port_path_value is not None, f"Expected function {function} to reference {port_path}, but it doesn't."
    if int(port_path_value) != int(value):
        raise BartiqCompilationError(
            "Failed to set constant register size value because port already has a different constant size; "
            f"register {port_path} has size {value}, but attempted to assign {port_path_value}."
        )
    return function


def _get_substitution_map(function: SymbolicFunction[T_expr], param: str, value: Any) -> dict[str, Any]:
    subs_map = {}
    for input in function.inputs:
        _, input_variable = _split_local_path(str(input))
        if input_variable == param:
            subs_map[str(input)] = value
    return subs_map


def _push_out_output_register_size_params(
    function: SymbolicFunction[T_expr],
    routine: RoutineWithFunction,
    backend: SymbolicBackend[T_expr],
) -> SymbolicFunction:
    """Renames the register size parameters for output ports to match their targets."""
    # Deal with root edge case
    if routine.is_root:
        return function

    new_function = function
    for port in routine.output_ports.values():
        output = port.absolute_path(exclude_root_name=True)
        source_register_size_variable = function.outputs[output]
        target_port = get_port_target(port)
        target_routine = target_port.parent
        assert target_routine is not None

        # If the current port's register size is a constant, then we need to propagate that to the target ports
        if backend.is_constant_int(source_register_size_variable.expression) and target_routine.is_leaf:
            target_function = to_symbolic_function(target_routine, backend)
            # NOTE: due to the walk order, the target function's variables are still be local
            target_function_input = f"#{target_port.name}"
            source_register_size = source_register_size_variable.value
            new_target_function = set_input_port_size_to_constant_value(
                target_function, target_function_input, source_register_size, backend
            )
            update_routine_with_symbolic_function(target_routine, new_target_function)

        # Otherwise, rename the source register size to match its target
        else:
            target_param = _resolve_target_param(target_port)
            _, param = _split_local_path(target_param)
            if is_constant_int(param):
                raise BartiqCompilationError(
                    "Input registers cannot be constant-sized; "
                    f"attempted to merge register size {source_register_size_variable} with {target_param}"
                )
            new_function = rename_variables(new_function, {port.absolute_path(exclude_root_name=True): target_param})

    # Return function with renamed parameters
    return new_function


def _resolve_target_param(target: Port) -> str:
    """Resolves the register size of some target port."""
    target_routine = target.parent
    assert target_routine is not None
    if not target_routine.is_leaf:
        # In the case the target port isn't on a leaf, it will be a root output, so use port's path (e.g. #out_0)
        assert (
            target_routine.is_root
        ), "Shouldn't ever find non-root non-leaf target. Most likely ports are connected incorrectly"
        return target.absolute_path(exclude_root_name=True)

    if target.size is None or target.size == "":
        raise BartiqCompilationError(
            f"No size found for input register {target.name} in {target.absolute_path(exclude_root_name=True)}"
        )
    target_register_param = str(target.size)
    return join_paths(target.absolute_path(exclude_root_name=True), target_register_param)


def _pass_on_inherited_params(routine: RoutineWithFunction[T_expr]) -> None:
    """Overwrites childrens' parameters."""
    for local_ancestor_param, links in routine.linked_params.items():
        global_ancestor_param = join_paths(routine.absolute_path(exclude_root_name=True), local_ancestor_param)
        for inheritor_path, param_name in links:
            if "." in inheritor_path:
                raise BartiqCompilationError(
                    "Error when passing inherited params. "
                    f"The inheritor {inheritor_path} is not a direct descendant of {routine.name}. "
                    "Make sure the parameter linkage happen only one level deep."
                )
            inheritor = routine.children[inheritor_path]
            # Define ancestor-to-inheritor parameter map
            param_map = {join_paths(inheritor.absolute_path(exclude_root_name=True), param_name): global_ancestor_param}

            # Apply the renaming to the inheritor routine as well as all descendent routines.
            # This is needed because inheritance happens from the bottom up, so if a subroutine of the current
            # inheritor has already inherited a param from it, then we need to propagate this renaming downwards.
            # The cast below will become redundant when pydantic starts supporting typing.Self
            # See: https://github.com/pydantic/pydantic/pull/9023
            for descendant in cast(RoutineWithFunction[T_expr], inheritor).walk():
                assert descendant.symbolic_function is not None
                descendant.symbolic_function = rename_variables(descendant.symbolic_function, param_map)
    routine.linked_params = {}


def _compile_routine_with_functions(
    routine: RoutineWithFunction[T_expr],
    functions_map: Optional[FunctionsMap],
    backend: SymbolicBackend[T_expr],
) -> RoutineWithFunction[T_expr]:
    """Compiles a routine using symbolic function."""
    # Deal with leaf root edge case
    if routine.is_leaf:
        assert routine.symbolic_function is not None
        symbolic_function = define_expression_functions(routine.symbolic_function, functions_map)
        update_routine_with_symbolic_function(routine, symbolic_function)
    else:
        routine = _compile_routine_non_leaf_root(routine, functions_map, backend)

    routine.symbolic_function = None
    for subroutine in routine.walk():
        subroutine.local_variables = []

    return routine


def _compile_routine_non_leaf_root(
    routine: RoutineWithFunction[T_expr],
    functions_map: Optional[FunctionsMap],
    backend: SymbolicBackend[T_expr],
) -> RoutineWithFunction[T_expr]:
    """Walks over the routine and compiles all the symbolic functions."""
    for subroutine in routine.walk():
        if subroutine.is_leaf:
            compiled_function = _compile_function_to_routine_leaf_non_root(subroutine)
        else:
            compiled_function = _compile_function_to_routine_non_leaf_non_root(subroutine, backend)

        if functions_map:
            compiled_function = define_expression_functions(compiled_function, functions_map, strict=False)
        update_routine_with_symbolic_function(subroutine, compiled_function)
    return routine


def _compile_function_to_routine_leaf_non_root(
    routine: RoutineWithFunction[T_expr],
) -> SymbolicFunction[T_expr]:
    """Compiles a symbolic function for a leaf, which is not a root."""
    # Undo the output register pushing out and input register pulling in to produce a valid routine
    assert routine.symbolic_function is not None
    local_function = _undo_push_out_output_register_size_params(routine.symbolic_function, routine)
    local_function = _undo_pull_in_input_register_size_params_leaf(local_function, routine)

    # Remove the global path namespace to make routine ignorant of higher structure
    namespace = routine.absolute_path(exclude_root_name=True)
    local_function = _remove_function_namespace(local_function, namespace)

    return local_function


def _remove_function_namespace(function: SymbolicFunction[T_expr], namespace: str) -> SymbolicFunction[T_expr]:
    """Removes a namespace prefix to all parameters in the function."""
    # Deal with root case
    if not namespace:
        return function

    namespace_map = {}
    old_params = map(str, list(function.inputs) + list(function.outputs.keys()))
    for old_param in old_params:
        if old_param.startswith(namespace):
            namespace_prefix = f"{namespace}."
            new_param = old_param.removeprefix(namespace_prefix)
            namespace_map[old_param] = new_param

    return rename_variables(function, namespace_map)


def _compile_function_to_routine_non_leaf_non_root(
    routine: RoutineWithFunction[T_expr], backend: SymbolicBackend[T_expr]
) -> SymbolicFunction[T_expr]:
    """Compiles a non-leaf's symbolic function."""
    # Grab the functions to be compiled

    function = routine.symbolic_function

    subfunctions = [child.symbolic_function for child in get_children_in_walk_order(routine)]

    # Compile the functions to a single function for the current routine
    all_functions = cast(list[SymbolicFunction[T_expr]], [*subfunctions, function])
    new_function = compile_functions(all_functions)

    # Deal with outputs associated with constant-sized registers.
    # NOTE: Constant-sized ports are stored as output values, so these are added to compiled function during compilation
    new_function = _remove_constant_register_sizes_non_leaf_non_root(routine, new_function)

    # Update routine with the function
    routine.symbolic_function = new_function

    # First, make sure the function is in terms of the routines's register input params and not its childrens'
    new_function = _undo_pull_in_input_register_size_params_non_leaf(new_function, routine)

    # Next, undo the pushing out of output register size parameter needed for function compilation
    new_function = _undo_push_out_output_register_size_params(new_function, routine)

    # Next, remove any global parameter namespaces to ensure the function is locally consistent.
    namespace = routine.absolute_path(exclude_root_name=True)
    new_function = _remove_function_namespace(new_function, namespace)

    # Lastly, go find the sizes of any constant-sized registers which weren't included in the compilation
    new_function = _infer_missing_register_sizes(new_function, routine, backend)
    return new_function


def _remove_constant_register_sizes_non_leaf_non_root(
    routine: Routine, function: SymbolicFunction[T_expr]
) -> SymbolicFunction[T_expr]:
    """Removes any constant register sizes associated with subroutine."""
    # First, go through and drop all function outputs associated with constant subroutine register sizes.
    new_outputs = {}
    for output_symbol, output_variable in function.outputs.items():
        path, name = _split_local_path(str(output_symbol))

        # Case 1: It's a constant register size
        if name.startswith("#") and output_variable.is_constant_int:
            # Case 1.1: It's a constant register size for the current routine => keep
            if path == routine.absolute_path(exclude_root_name=True):
                new_outputs[output_symbol] = output_variable

            # Case 1.2: It's a constant register size for another routine => ignore
            else:
                continue

        # Case 2: It's not a constant register size => keep
        else:
            new_outputs[output_symbol] = output_variable

    return SymbolicFunction(function.inputs, new_outputs)


def _undo_pull_in_input_register_size_params_leaf(
    function: SymbolicFunction[T_expr], routine: Routine
) -> SymbolicFunction[T_expr]:
    """Renames the input register size params of any inputs connected to the parent with the parent's size param."""
    param_map = {}
    for input_port in routine.input_ports.values():
        source_port = get_port_source(input_port)
        source_parent = source_port.parent
        assert source_parent is not None

        # Only undo pulling in input register size params if the port is connected to the root
        if not source_parent.is_root:
            continue

        source_register = source_port.name
        source_param = str(source_parent.input_ports[source_register].size)
        child_param = join_paths(source_port.absolute_path(exclude_root_name=True), source_param)
        parent_param = join_paths(input_port.absolute_path(exclude_root_name=True), source_param)
        param_map[child_param] = parent_param

    return rename_variables(function, param_map)


def _undo_pull_in_input_register_size_params_non_leaf(
    function: SymbolicFunction[T_expr], routine: Routine
) -> SymbolicFunction[T_expr]:
    """Renames the input register size params for any input connected to the parent with the parent's size param."""
    # Deal with root edge case
    if routine.is_root:
        return function

    param_map = {}
    for input_port in routine.input_ports.values():
        source_port = get_port_source(input_port)
        source_parent = source_port.parent
        assert source_parent is not None

        # If the input port is connected to the root, then function will be in terms of the root port's register size
        if source_parent.is_root:
            port = source_port
        # If the input port isn't connected to the root, the input register size will be that of the subroutines'
        else:
            port = get_port_target(input_port)

        param = str(port.size)

        if is_constant_int(param):
            child_param = port.absolute_path(exclude_root_name=True)
            parent_param = input_port.absolute_path(exclude_root_name=True)
        elif is_single_parameter(param):
            child_param = join_paths(port.absolute_path(exclude_root_name=True), param)
            parent_param = join_paths(input_port.absolute_path(exclude_root_name=True), param)
        else:
            raise ValueError("param should be either integer or a single symbol, got {param}.")

        param_map[child_param] = parent_param

    new_function = rename_variables(function, param_map)
    return new_function


def _undo_push_out_output_register_size_params(
    function: SymbolicFunction[T_expr],
    routine: RoutineWithFunction[T_expr],
) -> SymbolicFunction[T_expr]:
    """Renames the register size parameters for output ports to match their targets."""
    # Deal with root edge case
    if routine.is_root:
        return function

    # Define parameter map
    param_map = {}
    for source in routine.output_ports.values():
        target = get_port_target(source)
        assert target.parent is not None
        new_param = (
            _resolve_target_param(target) if target.parent.is_leaf else target.absolute_path(exclude_root_name=True)
        )
        param_map[new_param] = source.absolute_path(exclude_root_name=True)

    # Return function with renamed parameters
    return rename_variables(function, param_map)


def _infer_missing_register_sizes(
    function: SymbolicFunction[T_expr],
    routine: RoutineWithFunction[T_expr],
    backend: SymbolicBackend[T_expr],
) -> SymbolicFunction[T_expr]:
    """Goes and routes out any missing register sizes (which should be associated with constant register sizes)."""
    known_register_sizes = _extract_known_register_sizes(function)
    new_outputs = {**function.outputs}
    for port in routine.ports.values():
        # Skip if we've already got an expression for the size in the function
        if port.name in known_register_sizes:
            continue

        # Otherwise, go find what the size should be, check it's a constant, and add it to the function's outputs
        port_endpoint = _get_internal_port_endpoint(port)
        if is_constant_int(port_endpoint.size):
            assert port_endpoint.size  # To satisfy typechecker
            new_output_symbol = f"#{port.name}"
            new_outputs[new_output_symbol] = DependentVariable(
                new_output_symbol, backend.as_expression(port_endpoint.size), backend=backend
            )
    return SymbolicFunction(function.inputs, new_outputs)


def _extract_known_register_sizes(function: SymbolicFunction[T_expr]) -> list[str]:
    """Returns a list of register sizes referenced by the function (as inputs or outputs).

    NOTE: this function assumes that all paths have been removed
    """
    known_register_sizes = []

    # First, check the inputs
    for input in map(str, function.inputs):
        # NOTE: Input should be formatted as "#direction_name.param"
        if input.startswith("#"):
            # Split into "#direction_name" and "param"
            port, param = _split_local_path(input)
            # NOTE: strip off the '#' prefix
            known_register_sizes.append(port[1:])
        else:
            assert "#" not in input, f"Expected all param paths to have been removed, but found {input}"

    # Next, the function outputs
    for output in map(str, function.outputs.keys()):
        # NOTE: Output should be formatted as "#direction_name"
        if output.startswith("#"):
            # NOTE: strip off the '#' prefix
            known_register_sizes.append(output[1:])
        else:
            assert "#" not in output, f"Expected all param paths to have been removed, but found {output}"

    return known_register_sizes


def _get_internal_port_endpoint(port: Port) -> Port:
    """Returns the endpoint of the port internal to its routine."""
    if port.direction == "input":
        endpoint = get_port_target(port)
    if port.direction == "output":
        endpoint = get_port_source(port)

    assert endpoint is not None, f"Expected {port.absolute_path(exclude_root_name=True)} to have an internal endpoint."
    return endpoint


def _split_local_path(path: str) -> tuple[str, str]:
    """Split path into parent path and local name, much like directory path and a file name."""
    *parent_path, name = path.rsplit(".", 1)
    return ("" if parent_path == [] else parent_path[0]), name


def _remove_children_costs(routine: Routine) -> Routine:
    # NOTE: we probably should not be adding children costs in the first place, rather than removing it.
    for subroutine in routine.walk():
        subroutine.resources = {name: res for name, res in subroutine.resources.items() if "." not in name}
    return routine
