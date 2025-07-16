# latex_expr_dict.py

import re
from dataclasses import dataclass, field, replace

import sympy as sp
from IPython.display import display

from bartiq import CompiledRoutine
from bartiq.symbolics.backend import T, TExpr

MAX_LINE_LENGTH = 160


def escape_latex(text: str) -> str:
    """
    Escapes LaTeX special characters inside strings for use in \text{}.
    """
    replacements = {
        "\\": r"\textbackslash{}",
        "_": r"\_",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    pattern = re.compile("|".join(re.escape(k) for k in replacements))
    return pattern.sub(lambda m: replacements[m.group()], text)


def wrap_latex_expr(expr: sp.Basic, max_length=MAX_LINE_LENGTH) -> str:
    """
    Wraps a sympy expression across multiple lines with indentation
    on continuation lines, KaTeX-safe.
    """
    terms = expr.as_ordered_terms()
    pieces = [sp.latex(t) for t in terms]

    current_line = ""
    lines = []

    for piece in pieces:
        if len(current_line) + len(piece) > max_length:
            lines.append(current_line)
            current_line = ""
        current_line += piece + " + "

    if current_line:
        lines.append(current_line.rstrip(" +"))

    if len(lines) == 1:
        return lines[0]

    return (
        r"\begin{aligned}"
        + r" \\".join(f"& {line}" if i == 0 else f"& \\quad {line}" for i, line in enumerate(lines))
        + r"\end{aligned}"
    )


class LatexExprDict:
    def __init__(self, expr_dict: dict[str, sp.Basic]):
        self.expr_dict = expr_dict

    def _repr_latex_(self):
        lines = [r"\begin{array}{r||l}"]
        items = list(self.expr_dict.items())

        for i, (key, val) in enumerate(items):
            key_latex = escape_latex(key)
            val_latex = wrap_latex_expr(val)

            lines.append(rf"\text{{{key_latex}}} & {val_latex} \\")

            if i == 0:
                # Insert a horizontal line after 'total'
                lines.append(r" \rule{6em}{0.4pt} & \rule{" f"{MAX_LINE_LENGTH // 4}" r"em}{0.4pt} \\")
            elif i < len(items) - 1:
                # Insert a blank line between other rows
                lines.append(r"& \phantom{.} \\")
        lines.append(r"\end{array}")
        return "$$\n" + "\n".join(lines) + "\n$$"

    def show(self):
        """Explicitly render in notebook (optional)"""
        display(self)

    def update(self, key: str, expr: TExpr[T]):
        self.expr_dict[key] = expr

    def __getitem__(self, key):
        return self.expr_dict[key]

    def __setitem__(self, key, value):
        self.expr_dict[key] = value

    def __delitem__(self, key):
        del self.expr_dict[key]

    def __iter__(self):
        return iter(self.expr_dict)

    def __len__(self):
        return len(self.expr_dict)

    def __contains__(self, key):
        return key in self.expr_dict


@dataclass
class Contributions:
    compiled_routine: CompiledRoutine
    resource: str
    contributions: dict[str, TExpr[T]] = field(init=False)

    def __post_init__(self):
        self.contributions = child_contributions(self.compiled_routine, self.resource)

    def _repr_latex_(self) -> str | None:
        return LatexExprDict(self.contributions)._repr_latex_()

    def step_into(self, child: str):
        try:
            return replace(self, compiled_routine=self.compiled_routine.children[child])
        except KeyError as exc:
            valid_names = "\n\t".join(list(self.compiled_routine.children.keys()))
            raise ValueError(f"Valid child routine names are: \n\t{valid_names}") from exc


def child_contributions(compiled_routine: CompiledRoutine, resource: str) -> dict[str, TExpr[T]]:
    return {"total": compiled_routine.resource_values[resource]} | {
        child_name: val
        for child_name, child_rout in compiled_routine.children.items()
        if resource in child_rout.resource_values and (val := child_rout.resource_values[resource]) != 0
    }
