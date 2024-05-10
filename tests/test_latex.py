"""
..  Copyright © 2022-2023 PsiQuantum Corp.  All rights reserved.
    PSIQUANTUM CORP. CONFIDENTIAL
    This file includes unpublished proprietary source code of PsiQuantum Corp.
    The copyright notice above does not evidence any actual or intended publication
    of such source code. Disclosure of this source code or any related proprietary
    information is strictly prohibited without the express written permission of
    PsiQuantum Corp.

Tests for Estimators' LaTeX rendering.
"""
import pytest

from bartiq import Routine
from bartiq.latex import represent_routine_in_latex

# TODO: convert test cases from make_estimator to Routine
# TODO: convert expected outputs having in mind that now we have:
# - resources instead of costs
# - ports/port sizes instead of registers/register sizes
# - linked_params instead of inherited params
# - local variables instead of local parameters
@pytest.mark.parametrize("routine, kwargs, expected_latex", [
    # Null case
    (
        Routine(), 
        {},
        "\n\n",
    ),
    # Only input parameters
    (
        Routine(input_params=["x", "y"]),
        {},
        r"""
&\bf\text{Input parameters:}\\
&x, y
"""
    ),
    # Path-prefixed input parameters
    (
        # Possibly upgrade to include children
        Routine(
            name="root",
            input_params=["subroutine.x_a", "y_b"],
            children={"subroutine": {"name": "subroutine", "input_params": "x_a"}}
        ),
        {},
        r"""
&\bf\text{Input parameters:}\\
&\text{subroutine}.\!x_{\text{a}}, y_{\text{b}}
"""
    ),
    # Only inherited_params
    (
        # Likewise, consider adding children
        Routine(
            name="root",
            linked_params={
                "x": ["a.i_0", "c.j_1"],
                "y": ["d.k_2", "e.l_3"],
            },
            children={
                "a": {"name": "a", "input_params": ["i_0"]},
                "c": {"name": "c", "input_params": ["j_1"]},
                "d": {"name": "d", "input_params": ["k_2"]},
                "e": {"name": "e", "input_params": ["l_3"]}
            }
        ),
        {},
        r"""
&\bf\text{Inherited parameters:}\\
&x: \text{a_bish.b_bash}.\!i_{\text{0}}, \text{c_bosh}.\!j_{\text{1}}\\
&y: \text{d_hip}.\!k_{\text{2}}, \text{e_hip.f_hooray}.\!l_{\text{3}}
"""
    ),
    # Only input register sizes
    (
        Routine(
            name="root",
            ports={
                "0": {"name": "0", "size": "a", "direction": "input"},
                "b": {"name": "b", "size": "b", "direction": "input"}
            }
        ),
        {},
        r"""
&\bf\text{Input registers:}\\
&\text{#in_0}.\!a, \text{#in_b}.\!b
"""
    ),
    # Only local parameters
    (
        Routine(
            name="root",
            input_params=["a", "b", "c", "y"],
            local_variables=[
                "x_foo = y + a",
                "y_bar = b * c",
            ],
        ),
        {},
        r"""
&\bf\text{Input parameters:}\\
&a, b\\
&\bf\text{Subcosts:}\\
&\text{bish_bash_bosh}.\!N_{\text{noshes}}, \text{clip_clap_clop}.\!N_{\text{horses}}\\
&\bf\text{Local parameters:}\\
&x_{\text{foo}} = a + \text{bish_bash_bosh}.\!N_{\text{noshes}}\\
&y_{\text{bar}} = b \cdot \text{clip_clap_clop}.\!N_{\text{horses}}
"""
    ),
    # Only output registers
    (
        Routine(
            name="root",
            ports={
                "0": {"name": "0", "size": "2", "direction": "output"},
                "b": {"name": "b", "size": "3", "direction": "output"}
            },
            output_register_sizes={"0": "2", "b": "3"},
        ),
        {},
        r"""
&\bf\text{Output registers:}\\
&\text{#out_0} = 2\\
&\text{#out_b} = 3
"""
    ),
    # Only costs
    (
        make_estimator(
            costs=["x = 0", "y = 1"],
        ),
        {},
        r"""
&\bf\text{Costs:}\\
&x = 0\\
&y = 1
"""
    ),
    # The whole shebang
    (
        make_estimator(
            input_params=["x", "y"],
            inherited_params={
                "x": ["a_bish.b_bash.i_0", "c_bosh.j_1"],
                "y": ["d_hip.k_2", "e_hip.f_hooray.l_3"],
            },
            subcosts=["wig_wam.N_tents", "ping_pong.N_serves"],
            input_register_sizes={"0": "a", "b": "b"},
            local_params=[
                "x_foo = bish_bash_bosh.N_noshes + a",
                "y_bar = b * clip_clap_clop.N_horses",
            ],
            costs=["x = 0", "y = 1"],
            output_register_sizes={"0": "2", "b": "3"},
        ),
        {},
        r"""
&\bf\text{Input parameters:}\\
&x, y\\
&\bf\text{Inherited parameters:}\\
&x: \text{a_bish.b_bash}.\!i_{\text{0}}, \text{c_bosh}.\!j_{\text{1}}\\
&y: \text{d_hip}.\!k_{\text{2}}, \text{e_hip.f_hooray}.\!l_{\text{3}}\\
&\bf\text{Subcosts:}\\
&\text{wig_wam}.\!N_{\text{tents}}, \text{ping_pong}.\!N_{\text{serves}}\\
&\bf\text{Input registers:}\\
&\text{#in_0}.\!a, \text{#in_b}.\!b\\
&\bf\text{Local parameters:}\\
&x_{\text{foo}} = a + \text{bish_bash_bosh}.\!N_{\text{noshes}}\\
&y_{\text{bar}} = b \cdot \text{clip_clap_clop}.\!N_{\text{horses}}\\
&\bf\text{Output registers:}\\
&\text{#out_0} = 2\\
&\text{#out_b} = 3\\
&\bf\text{Costs:}\\
&x = 0\\
&y = 1
"""
    ),
    # Different whitespace around operands in assignment string
    (
        make_estimator(
            local_params=['a=1+2', 'b = 3+4'],
            costs=['c=a + b', 'd = a - b'],
        ),
        {},
        r"""
&\bf\text{Local parameters:}\\
&a = 3\\
&b = 7\\
&\bf\text{Costs:}\\
&c = a + b\\
&d = a - b
"""
    ),
    # Don't hide non-root costs (default)
    # Add children, make sure you include them in implementation
    (
        make_estimator(
            costs=[
                'a = 1',
                'a.b = 2',
            ],
        ),
        {},
        r"""
&\bf\text{Costs:}\\
&a = 1\\
&\text{a}.\!b = 2
"""
    ),
    # Hide non-root costs
    (
        make_estimator(
            costs=[
                'a = 1',
                'a.b = 2',
            ],
        ),
        {'show_non_root_costs': False},
        r"""
&\bf\text{Costs:}\\
&a = 1
"""
    ),
    # Sum over all subcosts
    (
        make_estimator(
            costs=[
                'N_x = sum(~.N_x)'
            ],
        ),
        {},
        r"""
&\bf\text{Subcosts:}\\
&\text{~}.\!N_{\text{x}}\\
&\bf\text{Costs:}\\
&N_{\text{x}} = \operatorname{sum}{\left(\text{~}.\!N_{\text{x}} \right)}
"""
    ),
])
def test_represent_routine_in_latex(routine, kwargs, expected_latex):
    expected_string = rf"\begin{{align}}{expected_latex}\end{{align}}"
    assert represent_routine_in_latex(routine, **kwargs) == expected_string
