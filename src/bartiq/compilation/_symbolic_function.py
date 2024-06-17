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

from __future__ import annotations

from typing import Any, Generic, Optional, TypeVar, Union

from pydantic import Field

from .. import Port, Resource, ResourceType, Routine
from ..errors import BartiqCompilationError
from ..symbolics.backend import SymbolicBackend, T_expr
from ..symbolics.utilities import infer_subresources
from ..symbolics.variables import DependentVariable, IndependentVariable
from ._utilities import is_constant_int, is_single_parameter, split_equation
from .types import FunctionsMap, Number

# NOTE: there's still a terminology indecision between input/output and independent/dependent.
# This will perhaps be more intuitive when we move to the "function graph" picture, but for now it will remain, so FYI.


SymbolicFunctionInputs = Union[list[IndependentVariable], dict[str, IndependentVariable]]
SymbolicFunctionOutputs = Union[list[DependentVariable[T_expr]], dict[str, DependentVariable[T_expr]]]


TVar = TypeVar("TVar", "IndependentVariable", "DependentVariable")
T = TypeVar("T", bound="SymbolicFunction")


class SymbolicFunction(Generic[T_expr]):
    """Class for representing symbolic functions over arbitrary input variables and output expressions."""

    def __init__(self, inputs: SymbolicFunctionInputs, outputs: SymbolicFunctionOutputs[T_expr]) -> None:
        """Initialises the class and then ensures everything checks out."""
        # Data conversion
        assert isinstance(inputs, (list, dict))
        self._inputs = inputs if isinstance(inputs, dict) else _to_variable_lookup(inputs)

        assert isinstance(outputs, (list, dict))
        self._outputs = outputs if isinstance(outputs, dict) else _to_variable_lookup(outputs)

        # Data validation
        self.verify()

    def verify(self) -> None:
        """Ensures no funny business."""
        _verify_symbolic_function(self)

    @property
    def inputs(self):
        """Returns function inputs."""
        return self._inputs

    @property
    def outputs(self):
        """Returns function outputs."""
        return self._outputs

    def __eq__(self, other: object) -> bool:
        """Checks equality independent of input/output order."""
        if not isinstance(other, SymbolicFunction):
            raise RuntimeError(f"Cannot compare SymbolicFunction with an object of type: {type(other)}")

        return all(
            [
                sorted(self.inputs.items()) == sorted(other.inputs.items()),
                sorted(self.outputs.items()) == sorted(other.outputs.items()),
            ]
        )

    # Unfortunately, the typing below is very limited, but it cannot be improved unless
    # the typing issue https://github.com/python/typing/issues/548 is first resolved
    # positively.
    # Optimally, from_str method would have a signature like:
    # def from_str(cls: Type[T], ...) -> T[T_expr]
    # But TypeVars cannot have arguments.
    @classmethod
    def from_str(
        cls, inputs: list[str], outputs: list[str], backend: SymbolicBackend[T_expr]
    ) -> SymbolicFunction[T_expr]:
        """Creates a SymbolicFunction instance from lists of easy-to-write strings.

        Args:
            inputs: A list of valid sympy input variable names, e.g. ``['x', 'y', 'z']``.
            outputs: A list of expressions names, which must be in the format ``X = Y``
                where ``X`` is a single symbol and ``Y`` is a sympify-able expression,
                e.g. ``['a = b + c', 'x = f(y)']``.
            backend: A backend used for manipulating symbolic expressions.
        """
        return cls(_parse_input_expressions(inputs), parse_output_expressions(outputs, backend))

    def to_str(self) -> tuple[list[str], list[str]]:
        """Serialises the SymbolicFunction to a string (in the format required by ``from_str``)."""
        return (_serialize_variables(self.inputs), _serialize_variables(self.outputs))

    def __repr__(self) -> str:
        inputs = list(self._inputs.values())
        outputs = list(self._outputs.values())
        return f"SymbolicFunction(inputs={inputs}, outputs={outputs})"


def _to_variable_lookup(variables: list[TVar]) -> dict[str, TVar]:
    """Maps a list of variables to an easy-to-use dictionary."""
    # Ensure no duplicated symbols before we cast to dicts
    _verify_no_repeated_variable_symbols(variables)
    return {variable.symbol: variable for variable in variables}


def _verify_no_repeated_variable_symbols(variables: list[TVar]) -> None:
    """Checks that none of the variables share the same symbol."""
    symbols = [variable.symbol for variable in variables]
    unique_symbols = set(symbols)
    if len(unique_symbols) < len(symbols):
        raise BartiqCompilationError(f"Variable list contains repeated symbol; found {variables}")


def compile_functions(functions: list[SymbolicFunction[T_expr]]) -> SymbolicFunction[T_expr]:
    """Compiles a series of functions into a single function.

    The compiled function is the function produced when function inputs and outputs sharing the same name are
    associated, such that said output is passed as input to one or more later functions. Such I/O connections therefore
    represent the creation and consumption of "intermediate" variables. Hence, any output that is not
    referenced by a later function becomes an output of the compiled function. Similarly, inputs which do not share
    a name with the output of a previous function becomes an input of the compiled function.

    Compilation is thus performed iteratively, with each function in the list merged into the function produced from
    the compilation of all previous functions. Hence, functions must be ordered such that any function that requires
    an input from the output of a previous function must come after it in the ``functions`` list.

    Args:
        functions: The symbolic functions to be merged into a single function.
            See the :func:`SymbolicFunction` docs for how these are defined.

    Returns:
        :func:`SymbolicFunction`: A single function.
    """
    compiled_function = SymbolicFunction[T_expr]([], {})
    for function in functions:
        compiled_function = _merge_functions(compiled_function, function)
    return compiled_function


def _parse_input_expressions(inputs: list[str]) -> list[IndependentVariable]:
    """Parses a list of input variables strings to a list of :class:`~.IndependentVariable`s."""
    return [IndependentVariable.from_str(inpt) for inpt in inputs]


def parse_output_expressions(
    output_expressions: list[str], backend: SymbolicBackend[T_expr]
) -> list[DependentVariable[T_expr]]:
    """Parses a list of output expressions to a dictionary mapping output symbols to their expressions."""
    return [parse_output_expression(output_expression, backend) for output_expression in output_expressions]


def parse_output_expression(output_expression: str, backend: SymbolicBackend[T_expr]) -> DependentVariable[T_expr]:
    """Parses a single output expression string to an output variable."""
    return DependentVariable.from_str(output_expression, backend)


def _merge_functions(
    function_1: SymbolicFunction[T_expr], function_2: SymbolicFunction[T_expr]
) -> SymbolicFunction[T_expr]:
    """Merges a target function (2) into a base function (1)."""
    # Check that no outputs in function 2 are already inputs of function 1
    for output_2 in function_2.outputs.keys():
        if output_2 in function_1.inputs:
            raise BartiqCompilationError(
                "Target function outputs must not reference base function inputs when merging; "
                f"found reuse of symbol {output_2} in {function_1.inputs}."
            )

    inputs_new = function_1.inputs.copy()
    outputs_new = function_2.outputs.copy()
    outputs_1 = function_1.outputs.copy()
    inputs_2 = function_2.inputs

    # Inputs for function 2 that are outputs from function 1 define substitutions. Otherwise add them as new inputs.
    for input_2_symbol, input_2_variable in inputs_2.items():
        if input_2_symbol in outputs_1:
            output_1_expression = str(outputs_1.pop(input_2_symbol).expression)
            outputs_new = {
                output_symbol: output_variable.substitute(input_2_symbol, output_1_expression)
                for output_symbol, output_variable in outputs_new.items()
            }
        else:
            inputs_new[input_2_symbol] = input_2_variable

    # Check remaining outputs don't clash with those already added, and if not add them as well
    for output_1_symbol, output_1_variable in outputs_1.items():
        if output_1_symbol in outputs_new:
            outputs_new_variable = outputs_new[output_1_symbol]
            if output_1_variable != outputs_new_variable:
                raise BartiqCompilationError(
                    "Merging functions may only have same outputs if the outputs share the same expression; "
                    f"found conflict {output_1_variable} and {outputs_new_variable}."
                    "Perhaps size of a port should be derived (i.e. set to None), but it's already set to some value."
                )

        outputs_new[output_1_symbol] = output_1_variable

    return SymbolicFunction(inputs_new, outputs_new)


def _serialize_variables(variables: Union[dict[str, IndependentVariable], dict[str, DependentVariable]]) -> list[str]:
    """Serializes variables."""
    assert isinstance(variables, dict)
    return [str(variable) for variable in variables.values()]


def _verify_symbolic_function(function: SymbolicFunction) -> None:
    """No monkey business allowed."""
    _verify_inputs_are_independent_variables(function)
    _verify_outputs_dont_redefine_inputs(function)
    _verify_outputs_defined_over_known_variables(function)


def _verify_inputs_are_independent_variables(function: SymbolicFunction) -> None:
    """Checks that a function has valid input variables."""
    for input in function.inputs.values():
        if not isinstance(input, IndependentVariable):
            raise BartiqCompilationError(f"All inputs must be independent variables; found {input}.")


def _verify_outputs_dont_redefine_inputs(function: SymbolicFunction) -> None:
    """Check that outputs don't reuse input symbols."""
    reused_symbols = set(function.outputs.keys()) & set(function.inputs.keys())
    if reused_symbols:
        raise BartiqCompilationError(f"Outputs must not reuse input symbols; reused symbols: {reused_symbols}.")


def _verify_outputs_defined_over_known_variables(function: SymbolicFunction) -> None:
    """Checks no expression is sneaking in unknown variables."""
    outputs = function.outputs.values()
    known_variables = set(function.inputs.keys())
    for output in outputs:
        _verify_output_defined_over_known_variables(output, known_variables)


def _verify_output_defined_over_known_variables(output: DependentVariable, known_variables: set[str]) -> None:
    """Checks an output expression is only defined over a set of known variables.

    N.B.: this doesn't check there aren't any unknown functions in there.
    However, we may want to do this in the future.
    """
    unknown_variables = set(output.expression_variables) - known_variables
    if unknown_variables:
        raise BartiqCompilationError(
            "Expressions must not contain unknown variables.\n"
            f"Expression: {output}\n"
            f"Known variables: {known_variables}\n"
            f"Unknown variables: {unknown_variables}."
        )


def rename_variables(function: SymbolicFunction, variable_map: dict[str, str]) -> SymbolicFunction:
    """Returns a new function with variables renamed.

    Args:
        function: The function being renamed.
        variable_map: The new variable names, keyed by their old ones.

    """
    new_inputs, new_outputs = _get_renamed_inputs_and_outputs(function, variable_map)

    # Return a new function instance
    return SymbolicFunction(new_inputs, new_outputs)


def _get_renamed_inputs_and_outputs(
    function: SymbolicFunction, variable_map: dict[str, str]
) -> tuple[SymbolicFunctionInputs, SymbolicFunctionOutputs]:
    """Returns inputs and outputs of a given function renamed according to variable_map.

    Args:
        function: The function being renamed.
        variable_map: The new variable names, keyed by their old ones.
    """
    return (
        _get_renamed_inputs(function, variable_map),
        _get_renamed_outputs(function, variable_map),
    )


def _get_renamed_inputs(function: SymbolicFunction, variable_map: dict[str, str]) -> SymbolicFunctionInputs:
    # Apply the substitution map to produce new inputs and remove any duplicates
    new_inputs: SymbolicFunctionInputs = {}
    for old_symbol, old_variable in function.inputs.items():
        new_symbol = old_symbol
        new_variable = old_variable

        # NOTE: We interpret the variable map as ordered, so loop over substitutions from first to last.
        # NOTE: This means that chained substitutions can be implemented, but loops won't be problematic.
        # E.g. a -> b, b -> c, c -> a will map a, b, and c to a.
        for initial_symbol, final_symbol in variable_map.items():
            if new_symbol == initial_symbol:
                new_symbol = final_symbol
                new_variable = old_variable.rename_symbol(final_symbol)

        # Case 1: new variable not a known input, so add
        if new_symbol not in new_inputs:
            pass

        # Case 2: new variable is a known input, but the same (e.g. x = 1, y = 1 with variable map x -> y), so pass
        elif new_inputs[new_symbol] == new_variable:
            pass

        # Case 3 new variable is a known input, but different (e.g. x = 1, y = 2 with variable map x -> y), so error
        else:
            raise BartiqCompilationError(
                f"Cannot rename input variable; "
                f"couldn't rename {old_variable} to {new_symbol} due to clash with {new_inputs[new_symbol]}."
            )

        new_inputs[new_symbol] = new_variable

    return new_inputs


def _get_renamed_outputs(function: SymbolicFunction, variable_map: dict[str, str]) -> SymbolicFunctionOutputs:
    # Apply substitution map for outputs, checking for any renaming clashes
    new_outputs = function.outputs

    for old_variable, new_variable in variable_map.items():
        current_outputs = new_outputs
        new_outputs = {}

        for current_symbol, current_output in current_outputs.items():
            # First generate the new output
            # Case 1: Old variable is LHS symbol, so rename
            if current_symbol == old_variable:
                new_output = current_output.rename_symbol(new_variable)

            # Case 2: Old variable is symbol in RHS expression, so substitute
            elif old_variable in current_output.expression_variables:
                new_output = current_output.substitute(old_variable, new_variable)

            # Case 3: Old variable doesn't appear, leave output unchanged
            else:
                new_output = current_output

            # Next, track the new output
            # Case 1: new variable not a known output, so add
            new_symbol = new_output.symbol
            if new_symbol not in new_outputs:
                new_outputs[new_symbol] = new_output

            # Case 2: new variable is a known output, but the same expression as before, so pass
            # (e.g. x = a + b, y = 2 * b with variable map x -> y, a -> b)
            elif new_outputs[new_symbol] == new_output:
                pass

            # Case 3: new variable is a known output, but with a different expression, so error
            # (e.g. x = a + b, y = 2 * b with variable map x -> y, a -> c)
            else:
                raise BartiqCompilationError(
                    "Cannot rename output variable; "
                    f"couldn't map {old_variable} to {new_variable} in {current_output} due to clash with "
                    f"{new_outputs[current_symbol]}."
                )

    return new_outputs


def rename_functions(function: SymbolicFunction, function_map: dict[str, str]) -> SymbolicFunction:
    """Returns a new function with expression functions renamed.

    Args:
        function: The symbolic function being renamed.
        function_map: The new function names, keyed by their old ones.

    """
    old_outputs = function.outputs.values()  # Output dependent variables
    new_outputs = []
    for old_output in old_outputs:
        new_output = old_output
        for old_function, new_function in function_map.items():
            new_output = new_output.rename_function(old_function, new_function)
        new_outputs.append(new_output)

    # Return a new function instance
    return SymbolicFunction(function.inputs, new_outputs)


def evaluate_function_at(
    function: SymbolicFunction[T_expr],
    variable: str,
    value: Number,
    backend: SymbolicBackend[T_expr],
) -> SymbolicFunction[T_expr]:
    """Evalutes a symbolic function over a single numeric variable assignment."""
    # Catch evaluation misses
    old_inputs = function.inputs
    if variable not in old_inputs:
        raise BartiqCompilationError(f"Cannot evaluate function {function} for unknown input variable {variable}.")

    # Generate new inputs
    old_input = old_inputs.pop(variable)
    new_input = old_input.with_new_value(value)
    new_inputs = {
        **old_inputs,
        variable: new_input,
    }

    # Generate new outputs
    old_outputs = function.outputs
    new_outputs = {}
    for symbol, old_output in old_outputs.items():
        old_output_expression_variables = old_output.expression_variables
        if variable in old_output_expression_variables:
            old_output_expression_variable = old_output_expression_variables.pop(variable)
            new_output_expression_variable = old_output_expression_variable.with_new_value(value)
            new_output_expression_variables = {
                new_output_expression_variable.symbol: new_output_expression_variable,
                **old_output_expression_variables,
            }
            new_output: DependentVariable = DependentVariable(
                symbol=old_output.symbol,
                expression=old_output.expression,
                expression_variables=new_output_expression_variables,
                expression_functions=old_output.expression_functions,
                description=old_output.description,
                backend=backend,
            )
            new_outputs[symbol] = new_output
        else:
            new_outputs[symbol] = old_output

    return SymbolicFunction(new_inputs, new_outputs)


def define_expression_functions(
    function: SymbolicFunction[T_expr],
    functions_map: Optional[FunctionsMap],
    strict: bool = True,
) -> SymbolicFunction[T_expr]:
    """Substitute callable functions in the input SymbolicFunction object with functions provided by functions_map.

    For example, if the output of the symbolic function is "2*x + f(y)", and we provide the following map:
    {"f": lambda x: 2*x}, substitution will yield symbolic function with the output: "2*x + 2*y".
    If given function cannot be executed (e.g. because it has a condition and the input is symbol), it won't change.

    Args:
        function: SymbolicFunction which we want to update
        functions_map: A dictionary with string keys and callable functions as values.
        strict: If ``True``, throws an error if the function being defined doesn't occur in the expression.

    """
    # Define defaults
    functions_map = functions_map or {}

    # If we're not being strict, go find the subset of expression functions that occur in the map and function
    if not strict:
        known_expression_functions = set(
            function for output in function.outputs.values() for function in output.expression_functions
        )
        functions_map = {
            name: definition for name, definition in functions_map.items() if name in known_expression_functions
        }

    new_outputs = []
    for old_output in function.outputs.values():
        new_output = old_output
        for function_name, function_defn in functions_map.items():
            new_output = new_output.define_function(function_name, function_defn)
        new_outputs.append(new_output)

    return SymbolicFunction(function.inputs, new_outputs)


class RoutineWithFunction(Routine, Generic[T_expr]):
    """Extension of the Routine class, which includes information about SymbolicFunciton for each subroutine."""

    symbolic_function: Optional[SymbolicFunction[T_expr]] = None
    parent: Optional[RoutineWithFunction[T_expr]] = Field(exclude=True, default=None)
    children: dict[str, RoutineWithFunction] = Field(default_factory=dict)  # type: ignore

    def __init__(self, **data: Any):
        super().__init__(**data)

    @classmethod
    def from_routine(cls, routine: Routine) -> RoutineWithFunction:
        """Transforms Routine object into RoutineWithFunction."""
        return cls(**routine.model_dump())

    def to_routine(self) -> Routine:
        """Generates Routine object, which doesn't include the information about symbolic functions."""
        serialized_dict = self.model_dump()
        sanitized_dict = _delete_key(serialized_dict, "symbolic_function")
        return Routine(**sanitized_dict)


def _delete_key(dictionary, key_to_delete):
    if not isinstance(dictionary, dict):
        return dictionary

    for key, value in list(dictionary.items()):
        if key == key_to_delete:
            del dictionary[key]
        elif isinstance(value, dict):
            dictionary[key] = _delete_key(value, key_to_delete)
        else:
            pass

    return dictionary


def to_symbolic_function(routine: Routine, backend: SymbolicBackend[T_expr]) -> SymbolicFunction[T_expr]:
    """Converts a routine to a symbolic function.

    Args:
        routine: The routine to be mapped to a symbolic function.
        backend: A backend used for manipulating symbolic expressions.
    """
    subresources = infer_subresources(routine, backend)
    inputs = [IndependentVariable.from_str(input_symbol) for input_symbol in list(routine.input_params) + subresources]

    # NOTE: since multiple ports can have the same input size, this map defines a substitution for size parameters to
    # the variable corresponding to the first register with said size. Given that such variables are suffixed by the
    # input parameter, this means we will still be able to map back to our routine later.
    # e.g. if both in_0 and in_1 have size N, this will be {'N': '0.N'}.
    input_param_to_input_register_variables_map: dict[str, str] = {}
    for port in routine.input_ports.values():
        parameter = port.size
        if is_single_parameter(parameter):
            assert isinstance(parameter, str)
            input_variable = IndependentVariable(f"#{port.name}.{parameter}")
            inputs.append(input_variable)

            input_param_to_input_register_variables_map.setdefault(parameter, input_variable.symbol)

    init_outputs = _get_function_outputs(routine, backend)

    final_outputs = [
        init_output.substitute_series(input_param_to_input_register_variables_map)  # type: ignore[arg-type]
        for init_output in init_outputs
    ]
    function = SymbolicFunction(inputs, final_outputs)
    return function


def _get_function_outputs(routine: Routine, backend: SymbolicBackend[T_expr]) -> list[DependentVariable]:
    """Reads a routine to determine what are its output variables."""
    local_params = parse_output_expressions(routine.local_variables, backend)
    return [
        *_make_cost_variables(list(routine.resources.values()), local_params, backend),
        *_make_output_register_size_variables(routine.output_ports, local_params, backend),
        *_make_input_register_constants(routine.input_ports, backend),
        # NOTE: the following is just a placeholder for when we support non-trivial input register sizes
        *_make_input_register_size_variables(routine.input_ports, local_params, backend),
    ]


def _make_cost_variables(
    resources: list[Resource],
    local_params: list[DependentVariable[T_expr]],
    backend: SymbolicBackend[T_expr],
) -> list[DependentVariable[T_expr]]:
    """Compiles a cost variable, taking into account any local parameters."""
    # This allows users to reuse costs in subsequent expressions.
    known_params = {local_param.symbol: local_param for local_param in local_params}
    costs = _resources_to_cost_expressions(resources)
    new_cost_variables = []
    for old_output_variable in parse_output_expressions(costs, backend):
        # Substitute any local parameters
        cost = old_output_variable.symbol
        if cost in known_params:
            raise BartiqCompilationError("Variable is redundantly defined in local_params and costs.")
        new_output_variable = _substitute_local_parameters(old_output_variable, known_params)

        # Add cost to known parameters
        known_params[cost] = new_output_variable

        # Add new cost variable
        new_cost_variables.append(new_output_variable)

    return new_cost_variables


def _resources_to_cost_expressions(resources: list[Resource]) -> list[str]:
    expressions = []
    for resource in resources:
        expressions.append(f"{resource.name} = {resource.value}")
    return expressions


def _make_output_register_size_variables(
    output_ports: dict[str, Port],
    local_params: list[DependentVariable[T_expr]],
    backend: SymbolicBackend[T_expr],
) -> list[DependentVariable[T_expr]]:
    """Compiles an output register size variables, taking into account any local parameters."""
    output_register_sizes = {key: port.size for key, port in output_ports.items() if port.size is not None}

    output_expression_strs = [
        f"{_get_output_name(output)} = {expression_str}" for output, expression_str in output_register_sizes.items()
    ]
    # Next, substitute in any local params
    known_params = {local_param.symbol: local_param for local_param in local_params}
    return [
        _substitute_local_parameters(output, known_params)
        for output in parse_output_expressions(output_expression_strs, backend)
    ]


def _get_output_name(output: str) -> str:
    if output.startswith("#"):
        return output
    else:
        return f"#{output}"


def _make_input_register_size_variables(
    input_ports: dict[str, Port],
    local_params: list[DependentVariable[T_expr]],
    backend: SymbolicBackend[T_expr],
) -> list[DependentVariable[T_expr]]:
    """Identifies non-trivial input register size expressions and formats them as output variables.

    XXX: This is implemented to catch such cases and throw an exception, and is left in to make later inclusion easier.
    """
    input_register_sizes = {key: port.size for key, port in input_ports.items() if port.size is not None}
    # First, remove all the #in_ prefixes to get the corresponding output variables
    output_expression_strs = [
        f"{input} = {expression_str}"
        for input, expression_str in _get_non_trivial_input_register_sizes(input_register_sizes).items()
    ]

    # Next, substitute in any local params
    known_params = {local_param.symbol: local_param for local_param in local_params}
    return [
        _substitute_local_parameters(output, known_params)
        for output in parse_output_expressions(output_expression_strs, backend)
    ]


def _get_non_trivial_input_register_sizes(input_register_sizes):
    """Identifies input register sizes which aren't defined as a single parameter."""
    input_register_expressions = {
        inpt: expression
        for inpt, expression in input_register_sizes.items()
        if not (is_constant_int(expression) or is_single_parameter(expression))
    }

    if input_register_expressions:
        raise BartiqCompilationError(
            f"Non-trivial input sizes not yet supported; found non-trivial expressions {input_register_expressions}."
        )

    return input_register_expressions


def _make_input_register_constants(
    input_ports: dict[str, Port], backend: SymbolicBackend[T_expr]
) -> list[DependentVariable[T_expr]]:
    """Identifies constant input register sizes and formats them as output variables."""
    input_register_sizes = {key: port.size for key, port in input_ports.items() if port.size is not None}

    output_expression_strs = [
        f"#{inpt} = {expression_str}"
        for inpt, expression_str in input_register_sizes.items()
        if is_constant_int(expression_str)
    ]
    return parse_output_expressions(output_expression_strs, backend)


def _substitute_local_parameters(output_variable, local_params):
    """Substitutes all local parameters into output variable."""
    # Exit early if not a parameterised expression
    if not output_variable.expression_variables:
        return output_variable

    substitution_map = {
        symbol: variable.expression
        # NOTE: Params are substituted in reverse order so that later expressions can refer to previous local params
        for symbol, variable in list(local_params.items())[::-1]
    }
    return output_variable.substitute_series(substitution_map)


def update_routine_with_symbolic_function(routine: Routine, function: SymbolicFunction) -> None:
    """This function modifies a Routine in place and updates its fields with information from a given function."""
    input_params, input_register_sizes_from_inputs = _parse_function_inputs(function)
    costs, registers_sizes_from_outputs = _parse_function_outputs(function, input_register_sizes_from_inputs)
    routine.input_params = sorted(input_params)
    linked_params_to_remove = set(routine.linked_params.keys()) - set(input_params)
    for param in linked_params_to_remove:
        del routine.linked_params[param]

    for port_name, port_size in input_register_sizes_from_inputs.items():
        routine.input_ports[port_name].size = str(port_size)
    for port_name, port_size in registers_sizes_from_outputs.items():
        target_port = routine.ports[port_name]
        if target_port.direction == "input":
            if not is_constant_int(port_size):
                raise BartiqCompilationError(
                    "Only constant-sized input register sizes supported in function outputs; " f"found {port_size}."
                )
        target_port.size = str(port_size)
    for cost in costs:
        lhs, rhs = split_equation(cost)
        if lhs in routine.resources:
            routine.resources[lhs].value = rhs
        else:
            raw_name = lhs.split(".")[-1]
            type = ResourceType.other
            routine.resources[lhs] = Resource(name=raw_name, value=rhs, parent=routine, type=type)


def _parse_function_inputs(function):
    """Parses the function's input variables and determines which are input parameters vs input register sizes."""
    input_params = []
    input_register_sizes = {}
    for input_symbol, input_variable in function.inputs.items():
        if input_symbol.startswith("#"):
            port_name, variable_name = input_symbol.split(".")
            register_name = port_name.removeprefix("#")

            # If the input register has a constant size value, then report that over the variable name
            if input_variable.value is None:
                input_register_sizes[register_name] = variable_name
            else:
                input_register_sizes[register_name] = input_variable.value

        else:
            # Only include input param if the variable doesn't have a value
            if not input_variable.value:
                input_params.append(input_symbol)

    return input_params, input_register_sizes


def _parse_function_outputs(function, input_register_sizes_from_inputs):
    """Parses the function's output variables and determines which are output costs vs output register sizes."""
    costs = []
    register_sizes = {}

    input_register_reparams = {
        f"#{register}.{size}": size for register, size in input_register_sizes_from_inputs.items()
    }

    for output_symbol, output_variable in function.outputs.items():
        output_variable = output_variable.substitute_series(input_register_reparams)
        if output_symbol.startswith("#"):
            output_register = output_symbol.removeprefix("#")
            if type(output_variable) is IndependentVariable:
                register_sizes[output_register] = output_variable.value
            elif type(output_variable) is DependentVariable:
                register_sizes[output_register] = output_variable.evaluated_expression
            else:
                raise TypeError(
                    "Invalid type. Expected either IndependentVariable or DependentVariable, "
                    f"got {type(output_variable)}"
                )
        else:
            cost_value = (
                output_variable.evaluated_expression if output_variable.value is None else output_variable.value
            )

            costs.append(f"{output_symbol} = {cost_value}")

    return costs, register_sizes
