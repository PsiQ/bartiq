"""
..  Copyright © 2023-2024 PsiQuantum Corp.  All rights reserved.
    PSIQUANTUM CORP. CONFIDENTIAL
    This file includes unpublished proprietary source code of PsiQuantum Corp.
    The copyright notice above does not evidence any actual or intended publication
    of such source code. Disclosure of this source code or any related proprietary
    information is strictly prohibited without the express written permission of
    PsiQuantum Corp.

Utilities used for symbolic compilation.
"""

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


def infer_subcosts(routine: Routine, backend):
    """Infer subcosts for a routine."""
    expressions = [resource.value for resource in routine.resources.values()]
    for variable in routine.local_variables:
        _, rhs = _split_equation(variable)
        expressions.append(rhs)

    # Any path-prefixed variable (i.e. prefixed by a .-separated path) not
    # in subcosts, but found in the RHS of an expression in either costs,
    # local_variables, or output ports.
    subcosts = []
    for expr in expressions:
        vars = _extract_input_variables_from_expression(expr, backend)
        # Only consider variables that are subcosts (ones that have a "." in the name).
        for var in vars:
            if "." in var:
                subcosts.append(var)
    return sorted(set(subcosts))


def _extract_input_variables_from_expression(expression, backend):
    assert isinstance(expression, (str, int))
    expression = str(expression)
    return backend.free_symbols_in(backend.as_expression(expression))
