from __future__ import annotations

from typing import Generic

import sympy as sp

from bartiq import CompiledRoutine
from bartiq.integrations.latex import (
    _latex_expression,
    create_latex_expression_line_limited,
    escape_latex,
)
from bartiq.symbolics.backend import T, TExpr

MAX_LINE_LENGTH = 160


class DecomposeResources(Generic[T]):
    """A helper class for interacting with a routine hierarchy.

    Designed primarily for use in interactive environments, this class provides a `_repr_latex_` method
    that displays the total cost of a given resource and lists individual contributions from its immediate
    children.

    Args:
        compiled_routine: The compiled routine to interact with.
        resource: The resource cost to decompose.

    Attributes:
        total: The total resource cost for the `compiled_routine`, i.e. `compiled_routine.resource_values[resource]`.
        decomposition: A dictionary of child: contribution entries.
    """

    def __init__(self, compiled_routine: CompiledRoutine, resource: str):
        self.routine = compiled_routine
        self.resource = resource

        self.total: TExpr[T]
        self.decomposition: dict[str, TExpr[T]]
        self.total, self.decomposition = _decompose_resource(self.routine, self.resource)

    def _repr_latex_(self) -> str | None:
        """A LaTeX repr."""
        lines = [r"\begin{array}{r||l}"]
        lines.append(rf"\text{{{'total'}}} & {_route_expression_to_latex(self.total)} \\")
        lines.append(r" \rule{6em}{0.4pt} & \rule{" f"{MAX_LINE_LENGTH // 4}" r"em}{0.4pt} \\")

        for child, resource_contribution in self.decomposition.items():
            key_latex = escape_latex(str(child))
            val_latex = _route_expression_to_latex(resource_contribution)
            lines.append(rf"\text{{{key_latex}}} & {val_latex} \\")
            lines.append(r"& \phantom{.} \\")
            lines.append(r"\hdashline")
            lines.append(r"& \phantom{.} \\")
        lines.append(r"\end{array}")
        return "$$\n" + "\n".join(lines) + "\n$$"

    def descend(self, child: str) -> DecomposeResources:
        """Descend one level in the routine hierarchy and return a new instance.

        Args:
            child: The name of the child to descend into.

        Returns:
            A new DecomposeResources object, instantiated on the child routine.

        Raises:
            ValueError: if an invalid child name is passed.
        """
        try:
            return DecomposeResources(compiled_routine=self.routine.children[child], resource=self.resource)
        except KeyError as exc:
            valid_names = "\n\t".join(list(self.routine.children.keys()))
            raise ValueError(f"Valid child routine names are: \n\t{valid_names}") from exc


def _decompose_resource(compiled_routine: CompiledRoutine, resource: str) -> tuple[TExpr[T], dict[str, TExpr[T]]]:
    """Decompose a resource of a routine into the contributions from immediate children.

    Args:
        compiled_routine: The bartiq CompiledRoutine to decompose resources of.
        resource: the resource to decompose.

    Returns:
        A tuple of the total resource cost in the compiled_routine object, and a dictionary of contributions
        from its immediate children.
    """
    return compiled_routine.resource_values[resource], {
        child_name: val
        for child_name, child_rout in compiled_routine.children.items()
        if resource in child_rout.resource_values and (val := child_rout.resource_values[resource]) != 0
    }


def _route_expression_to_latex(expression: TExpr[T]) -> str:
    """Route a given symbolic expression to a latex expression.

    For SymPy this function first breaks the expression into components to obey line length, and then
    combines it into a cohesive multi-line latex expression.

    Args:
        expression: The symbolic expression.

    Returns:
        A latex expression.
    """
    match expression:
        case int() | float() | str():
            return _latex_expression(str(expression))
        case sp.Basic():
            pieces = [_latex_expression(str(term)) for term in expression.as_ordered_terms()]
            return create_latex_expression_line_limited(chunked_latex_expression=pieces, max_length=MAX_LINE_LENGTH)
        case _:
            raise NotImplementedError(
                f"LaTeX conversion not implemented for type '{type(expression)}'. Expression: '{expression}'."
            )
