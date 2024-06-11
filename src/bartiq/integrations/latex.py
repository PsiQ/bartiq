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

from sympy import latex, symbols

from .._routine import Routine
from ..compilation._utilities import split_equation
from ..symbolics.sympy_interpreter import parse_to_sympy


def routine_to_latex(routine: Routine, show_non_root_resources: bool = True) -> str:
    """Returns a snippet of LaTeX used to render the routine using clear LaTeX.

    Args:
        routine: The routine to render.
        show_non_root_costs: If ``True`` (default), displays all costs, otherwise only includes costs
            from the root node.

    Returns:
        A LaTeX snippet of the routine.
    """
    lines = [_format_object_header(routine)]
    lines.extend([format_line(data) for attr_name, format_line in SECTIONS if (data := getattr(routine, attr_name))])

    # We deal with resources separately due to show_non_root_resources option
    if resource_section := _format_resources(routine, show_non_root_resources):
        lines.append(resource_section)

    return "$\\begin{align}\n" + "\\newline\n".join(lines) + "\n\\end{align}$"


def _format_object_header(routine: Routine) -> str:
    """Formats the standard object repr as a header."""
    cls = type(routine)
    escaped_routine_name = routine.name.replace("_", r"\_")
    return rf"&\text{{{cls.__name__} \textrm{{({escaped_routine_name})}}}}"


def _format_input_params(input_params: list[str]):
    """Formats input parameters to LaTeX."""
    input_params = [_format_param(input_param) for input_param in input_params]
    return _format_section_one_line("Input parameters", input_params)


def _format_linked_params(linked_params):
    """Formats linked parameters to LaTeX."""
    lines = []
    for param, children_links in linked_params.items():
        key = _format_param_math(param)
        param_names = [".".join([path, target_param]) for path, target_param in children_links]
        values = [_format_param(param) for param in param_names]
        lines.append(f"&{key}: " + ", ".join(values))
    return _format_section_multi_line("Linked parameters", lines)


def _format_input_port_sizes(ports):
    return _format_port_sizes(ports, "Input")


def _format_output_port_sizes(ports):
    return _format_port_sizes(ports, "Output")


def _format_port_sizes(ports, label):
    lines = []
    for port in ports.values():
        port_name = port.name
        lines.append(f"&{_format_name_text(port_name)} = {_latex_expression(port.size)}")
    return _format_section_multi_line(f"{label} ports", lines)


def _format_local_variables(local_variables):
    """Formats routine's local variables to LaTeX."""
    lines = []
    for variable in local_variables:
        assignment, expression = split_equation(variable)
        lines.append(f"&{_format_param_math(assignment)} = {_latex_expression(expression)}")
    return _format_section_multi_line("Local variables", lines)


SECTIONS = [
    ("input_params", _format_input_params),
    ("linked_params", _format_linked_params),
    ("input_ports", _format_input_port_sizes),
    ("output_ports", _format_output_port_sizes),
    ("local_variables", _format_local_variables),
]


def _format_section_one_line(header, entries):
    """Formats a parameter section into a bolded header followed by a comma-separated list of entries."""
    return f"&\\underline{{\\text{{{header}:}}}}\\\\\n&" + ", ".join(entries)


def _format_section_multi_line(header, lines):
    """Formats a parameter section into a bolded header followed by a series of lines."""
    return f"&\\underline{{\\text{{{header}:}}}}\\\\\n" + "\\\\\n".join(lines)


def _format_param(param):
    if "." in param:
        path, local_param = param.rsplit(".", 1)
        return rf"{_format_param_text(path)}.\!{_format_local_param(local_param)}"
    return _format_local_param(param)


def _format_local_param(param):
    """Formats a non-dot-separated parameter based upon what would render best."""
    return _format_param_math(param) if param.count("_") <= 1 else _format_param_text(param)


def _format_param_text(param):
    """Formats a param as text."""
    if param.count("_") == 0:
        return rf"\text{{{param}}}"
    elif param.count("_") == 1:
        symbol, subscript = param.split("_")
        return rf"\text{{{symbol}}}_\text{{{subscript}}}"
    else:
        symbol, *subscripts = param.split("_")
        escaped_subscript = r"\_".join(subscripts)
        return rf"\text{{{symbol}}}_\text{{{escaped_subscript}}}"


def _format_name_text(name):
    escaped_name = name.replace("_", r"\_")
    return rf"\text{{{escaped_name}}}"


def _format_param_math(param):
    """Formats a param as math."""
    if "_" in param:
        return _format_param_math_with_subscript(param)
    return latex(symbols(param))


def _format_param_math_with_subscript(param):
    """Formats a subscripted param as math."""
    symbol, subscript = param.split("_", 1)
    subscript_latex = latex(symbols(subscript))
    symbol_latex = latex(symbols(symbol))

    # If subscript contains something that needs LaTeX to render, use that, but render text as text.
    # For example, if subscript is "lambda", this will become "\\lambda", which we want to render symbolically.
    if r"\\" in subscript_latex:
        subscript = subscript_latex
    else:
        subscript = rf"\text{{{subscript}}}"

    return rf"{symbol_latex}_{{{subscript}}}"


def _latex_expression(expression: str) -> str:
    """Maps an expression string to valid LaTeX."""
    sympy_expression = parse_to_sympy(str(expression))
    symbol_names = {symbol: _format_param(str(symbol)) for symbol in sympy_expression.free_symbols}
    return latex(sympy_expression, symbol_names=symbol_names, mul_symbol="dot")


def _format_resources(routine: Routine, show_non_root_resources: bool):
    lines = []
    lines += _get_resources_lines(routine.resources)
    if show_non_root_resources:
        subroutines_to_process = [r for r in routine.walk() if r is not routine]
        for subroutine in subroutines_to_process:
            lines += _get_resources_lines(subroutine.resources, subroutine.name)
    if len(lines) > 0:
        return _format_section_multi_line("Resources", lines)


def _get_resources_lines(resources, path=None):
    """Formats resources to LaTeX."""
    lines = []
    for resource in resources.values():
        if path is None:
            resource_path = resource.name
        else:
            resource_path = f"{path}.{resource.name}"
        lines.append(f"&{_format_param(resource_path)} = {_latex_expression(resource.value)}")
    return lines
