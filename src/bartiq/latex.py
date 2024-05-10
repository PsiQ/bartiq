"""
..  Copyright © 2022-2024 PsiQuantum Corp.  All rights reserved.
    PSIQUANTUM CORP. CONFIDENTIAL
    This file includes unpublished proprietary source code of PsiQuantum Corp.
    The copyright notice above does not evidence any actual or intended publication
    of such source code. Disclosure of this source code or any related proprietary
    information is strictly prohibited without the express written permission of
    PsiQuantum Corp.

Utilities for rendering estimators in LaTeX.
"""
from sympy import latex, symbols
from typing import Optional

from apollo_tools.paths import split_local_path

from .compile.sympy_interpreter import parse_to_sympy
from ._routine import Routine
from bartiq.symbolics.sympy_interpreter import parse_to_sympy
from knifey.circuits.utilities.misc import get_input_name, get_output_name
from .utilities import get_fields, split_equation


SECTIONS = [
    # pairs of the form (get_line_data, format_line_data)
    # TODO: actually implement the functions listed below, base on the estimator-based ones further in this file
    # TODO: ordering of this list matters, make sure it is correct
    (get_input_params, format_input_params),
    (get_linked_params, format_linked_params)
    (get_input_port_sizes, format_input_port_sizes),
    (get_resources, format_resources),
    (get_output_port_sizes, format_output_port_sizes),
]



def represent_routine_in_latex(routine: Routine, show_non_root_resources: Optional[bool] = True) -> str:
    """Returns a snippet of LaTeX used to render the routine using clear LaTeX.

    Args:
        routine: The routine to render.
        show_non_root_costs: If ``True`` (default), displays all costs, otherwise only includes costs
        from the route node.

    Returns:
        A LaTeX snippet of the routine.
    """
    lines = [
        format_line(data, show_non_root_resources=show_non_root_resources)
        for get_line_data, format_line in SECTIONS if (data := get_line_data(routine))
    ]

    return '\\begin{align}\n' + '\\\\\n'.join(lines) + '\n\\end{align}'


# TODO: the functions below should almost work, but they previously accepted an estimator
# They have to be changd so they accept precisely the data they operate on.
# other differences would be in naming of the sections:
# costs -> resources
# inherited params -> linked params
# local parameters -> local variables
# register sizes -> port sizes
def _format_input_params(estimator, **kwargs):
    """Formats estimator input parameters to LaTeX."""
    input_params = [
        _format_param(input_param)
        for input_param in estimator.input_params
    ]
    return _format_section_one_line("Input parameters", input_params)


def _format_section_one_line(header, entries):
    """Formats a parameter section into a bolded header followed by a comma-separated list of entries."""
    return f"&\\bf\\text{{{header}:}}\\\\\n&" + ', '.join(entries)


def _format_inherited_params(estimator, **kwargs):
    """Formats estimator inherited parameters to LaTeX."""
    lines = []
    for param, inheritors in estimator.inherited_params.items():
        key = _format_param_math(param)
        values = [
            _format_param(inheritor)
            for inheritor in inheritors
        ]
        lines.append(f"&{key}: " + ', '.join(values))
    return _format_section_multi_line("Inherited parameters", lines)


def _format_section_multi_line(header, lines):
    """Formats a parameter section into a bolded header followed by a series of lines."""
    return f"&\\bf\\text{{{header}:}}\\\\\n" + '\\\\\n'.join(lines)


def get_input_port_sizes(routine):
    pass


def format_port_sizes(port_sizes):
    pass
def _format_param(param):
    if '.' in param:
        path, local_param = split_local_path(param)
        return rf"{_format_param_text(path)}.\!{_format_local_param(local_param)}"
    return _format_local_param(param)


def _format_local_param(param):
    """Formats a non-dot-separated parameter based upon what would render best."""
    return _format_param_math(param) if param.count('_') <= 1:
    return _format_param_text(param)


def _format_param_text(param):
    """Formats a param as text."""
    return rf"\text{{{param}}}"


def _format_param_math(param):
    """Formats a param as math."""
    if '_' in param:
        return _format_param_math_with_subscript(param)
    return latex(symbols(param))


def _format_param_math_with_subscript(param):
    """Formats a subscripted param as math."""
    symbol, subscript = param.split('_', 1)
    subscript_latex = latex(symbols(subscript))
    symbol_latex = latex(symbols(symbol))

    # If subscript contains something that needs LaTeX to render, use that, but render text as text.
    # For example, if subscript is "lambda", this will become "\\lambda", which we want to render symbolically.
    if r"\\" in subscript_latex:
        subscript = subscript_latex
    else:
        subscript = rf"\text{{{subscript}}}"

    return rf"{symbol_latex}_{{{subscript}}}"


def _format_subcosts(estimator, **kwargs):
    """Formats estimator subcosts to LaTeX."""
    values = [
        _format_param(subcost)
        for subcost in estimator.subcosts
    ]
    return _format_section_one_line("Subcosts", values)


def _format_input_register_sizes(estimator, **kwargs):
    """Formats estimator input register sizes to LaTeX."""
    values = []
    for register, size in estimator.input_register_sizes.items():
        port_name = get_input_name(register)
        values.append(rf"{_format_param_text(port_name)}.\!{_format_param_math(size)}")
    return _format_section_one_line("Input registers", values)


def _format_local_params(estimator, **kwargs):
    """Formats estimator local parameters to LaTeX."""
    lines = []
    for local_param in estimator.local_params:
        assignment, expression = split_equation(local_param)
        lines.append(f"&{_format_param_math(assignment)} = {_latex_expression(expression)}")
    return _format_section_multi_line("Local parameters", lines)


def _format_costs(estimator, **kwargs):
    """Formats estimator costs to LaTeX."""
    show_non_root_costs = kwargs['show_non_root_costs']
    lines = []
    for cost in estimator.costs:
        assignment, expression = split_equation(cost)
        if not show_non_root_costs and '.' in assignment:
            continue
        lines.append(f"&{_format_param(assignment)} = {_latex_expression(expression)}")
    return _format_section_multi_line("Costs", lines)


def _format_output_register_sizes(estimator, **kwargs):
    """Returns the output register sizes formatted in LaTeX."""
    lines = []
    for register, expression in estimator.output_register_sizes.items():
        port_name = get_output_name(register)
        lines.append(f"&{_format_param_text(port_name)} = {_latex_expression(expression)}")
    return _format_section_multi_line("Output registers", lines)


def _latex_expression(expression):
    """Maps an expression string to valid LaTeX."""
    sympy_expression = parse_to_sympy(expression)
    symbol_names = {
        symbol: _format_param(str(symbol))
        for symbol in sympy_expression.free_symbols
    }
    return latex(sympy_expression, symbol_names=symbol_names, mul_symbol='dot')


ROUTINE_FIELD_LATEX_FORMATTERS = {
    'input_params': _format_input_params,
    'inherited_params': _format_inherited_params,
    'subcosts': _format_subcosts,
    'input_register_sizes': _format_input_register_sizes,
    'local_params': _format_local_params,
    'output_register_sizes': _format_output_register_sizes,
    'costs': _format_costs,
}
