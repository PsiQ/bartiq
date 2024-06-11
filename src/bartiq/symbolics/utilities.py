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

from .. import Routine


def _split_equation(equation: str) -> tuple[str, str]:
    """Splits an equation string and returns the left and right side."""
    if equation.count("=") != 1:
        raise ValueError(f"Equations must contain a single equals sign; found {equation}")

    lhs, rhs = equation.split("=")
    lhs = lhs.strip()
    rhs = rhs.strip()

    if not lhs or not rhs:
        raise ValueError(f"Equations must have both a left- and right-hand side; found {equation}")

    return (lhs, rhs)


def infer_subresources(routine: Routine, backend):
    """Infer what are the resources of a routine's children."""
    expressions = [resource.value for resource in routine.resources.values()]
    for variable in routine.local_variables:
        _, rhs = _split_equation(variable)
        expressions.append(rhs)

    # Any path-prefixed variable (i.e. prefixed by a .-separated path) not
    # in subresources, but found in the RHS of an expression in either costs,
    # local_variables, or output ports.
    subresources = []
    for expr in expressions:
        vars = _extract_input_variables_from_expression(expr, backend)
        # Only consider variables that are subresources (ones that have a "." in the name).
        for var in vars:
            if "." in var:
                subresources.append(var)
    return sorted(set(subresources))


def _extract_input_variables_from_expression(expression, backend):
    assert isinstance(expression, (str, int))
    expression = str(expression)
    return backend.free_symbols_in(backend.as_expression(expression))
