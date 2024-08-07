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

import pytest

from bartiq import Routine
from bartiq.integrations.latex import routine_to_latex

LATEX_TEST_CASES = [
    # Null case
    (
        Routine(name="root"),
        {},
        "\n&\\text{Routine \\textrm{(root)}}\n",
    ),
    # Only input parameters
    (
        Routine(name="root", input_params=["x", "y"]),
        {},
        r"""
&\text{Routine \textrm{(root)}}\newline
&\underline{\text{Input parameters:}}\\
&x, y
""",
    ),
    # Path-prefixed input parameters
    (
        Routine(
            name="root",
            input_params=["subroutine.x_a", "y_b"],
            children={"subroutine": {"name": "subroutine", "input_params": ["x_a"]}},
        ),
        {},
        r"""
&\text{Routine \textrm{(root)}}\newline
&\underline{\text{Input parameters:}}\\
&\text{subroutine}.\!x_{\text{a}}, y_{\text{b}}
""",
    ),
    # Only inherited_params
    (
        Routine(
            name="root",
            linked_params={
                "x": [("a", "i_0"), ("c", "j_1")],
                "y": [("d", "k_2"), ("e", "l_3")],
            },
            children={
                "a": {"name": "a", "input_params": ["i_0"]},
                "c": {"name": "c", "input_params": ["j_1"]},
                "d": {"name": "d", "input_params": ["k_2"]},
                "e": {"name": "e", "input_params": ["l_3"]},
            },
        ),
        {},
        r"""
&\text{Routine \textrm{(root)}}\newline
&\underline{\text{Linked parameters:}}\\
&x: \text{a}.\!i_{\text{0}}, \text{c}.\!j_{\text{1}}\\
&y: \text{d}.\!k_{\text{2}}, \text{e}.\!l_{\text{3}}
""",
    ),
    # Only input register sizes
    (
        Routine(
            name="root",
            ports={
                "in_0": {"name": "in_0", "size": "a", "direction": "input"},
                "b": {"name": "b", "size": "b", "direction": "input"},
            },
        ),
        {},
        r"""
&\text{Routine \textrm{(root)}}\newline
&\underline{\text{Input ports:}}\\
&\text{in\_0} = a\\
&\text{b} = b
""",
    ),
    # Only local parameters
    (
        Routine(
            name="root",
            input_params=["a", "b"],
            local_variables={
                "x_foo": "y + a",
                "y_bar": "b * c",
            },
        ),
        {},
        r"""
&\text{Routine \textrm{(root)}}\newline
&\underline{\text{Input parameters:}}\\
&a, b\newline
&\underline{\text{Local variables:}}\\
&x_{\text{foo}} = a + y\\
&y_{\text{bar}} = b \cdot c
""",
    ),
    # Only output ports
    (
        Routine(
            name="root",
            ports={
                "in_0": {"name": "in_0", "size": "2", "direction": "output"},
                "b": {"name": "b", "size": "3", "direction": "output"},
            },
        ),
        {},
        r"""
&\text{Routine \textrm{(root)}}\newline
&\underline{\text{Output ports:}}\\
&\text{in\_0} = 2\\
&\text{b} = 3
""",
    ),
    # Only costs
    (
        Routine(
            name="root",
            resources={
                "x": {"name": "x", "value": 0, "type": "additive"},
                "y": {"name": "y", "value": 1, "type": "additive"},
            },
        ),
        {},
        r"""
&\text{Routine \textrm{(root)}}\newline
&\underline{\text{Resources:}}\\
&x = 0\\
&y = 1
""",
    ),
    # The whole shebang
    (
        Routine(
            name="root",
            input_params=["x", "y"],
            ports={
                "in_0": {"name": "in_0", "size": "a", "direction": "input"},
                "in_b": {"name": "in_b", "size": "b", "direction": "input"},
                "out_0": {"name": "out_0", "size": "2", "direction": "output"},
                "out_b": {"name": "out_b", "size": "3", "direction": "output"},
            },
            linked_params={
                "x": [("a", "i_0"), ("c", "j_1")],
                "y": [("d", "k_2"), ("e", "l_3")],
            },
            children={
                "a": {"name": "a", "input_params": ["i_0"]},
                "c": {"name": "c", "input_params": ["j_1"]},
                "d": {"name": "d", "input_params": ["k_2"]},
                "e": {"name": "e", "input_params": ["l_3"]},
            },
            local_variables={
                "x_foo": "a.i_0 + a",
                "y_bar": "b * c.j_1",
            },
            resources={
                "t": {"name": "t", "value": 0, "type": "additive"},
            },
        ),
        {},
        r"""
&\text{Routine \textrm{(root)}}\newline
&\underline{\text{Input parameters:}}\\
&x, y\newline
&\underline{\text{Linked parameters:}}\\
&x: \text{a}.\!i_{\text{0}}, \text{c}.\!j_{\text{1}}\\
&y: \text{d}.\!k_{\text{2}}, \text{e}.\!l_{\text{3}}\newline
&\underline{\text{Input ports:}}\\
&\text{in\_0} = a\\
&\text{in\_b} = b\newline
&\underline{\text{Output ports:}}\\
&\text{out\_0} = 2\\
&\text{out\_b} = 3\newline
&\underline{\text{Local variables:}}\\
&x_{\text{foo}} = a + \text{a}.\!i_{\text{0}}\\
&y_{\text{bar}} = b \cdot \text{c}.\!j_{\text{1}}\newline
&\underline{\text{Resources:}}\\
&t = 0
""",
    ),
    # Different whitespace around operands in assignment string
    (
        Routine(
            name="root",
            local_variables={
                "a": "1+2",
                "b": "3+4",
            },
            resources={
                "c": {"name": "c", "value": "a + b", "type": "additive"},
                "d": {"name": "d", "value": "a-b", "type": "additive"},
            },
        ),
        {},
        r"""
&\text{Routine \textrm{(root)}}\newline
&\underline{\text{Local variables:}}\\
&a = 3\\
&b = 7\newline
&\underline{\text{Resources:}}\\
&c = a + b\\
&d = a - b
""",
    ),
    # Don't hide non-root costs (default)
    # Add children, make sure you include them in implementation
    (
        Routine(
            name="root",
            children={
                "a": {
                    "name": "a",
                    "resources": {
                        "y": {"name": "y", "value": "2", "type": "additive"},
                    },
                },
            },
            resources={
                "x": {"name": "x", "value": "1", "type": "additive"},
            },
        ),
        {},
        r"""
&\text{Routine \textrm{(root)}}\newline
&\underline{\text{Resources:}}\\
&x = 1\\
&\text{a}.\!y = 2
""",
    ),
    # Hide non-root costs
    (
        Routine(
            name="root",
            children={
                "a": {
                    "name": "a",
                    "resources": {
                        "y": {"name": "y", "value": "2", "type": "additive"},
                    },
                },
            },
            resources={
                "x": {"name": "x", "value": "1", "type": "additive"},
            },
        ),
        {"show_non_root_resources": False},
        r"""
&\text{Routine \textrm{(root)}}\newline
&\underline{\text{Resources:}}\\
&x = 1
""",
    ),
    # Sum over all subresources
    (
        Routine(
            name="root",
            resources={
                "N_x": {"name": "N_x", "value": "sum(~.N_x)", "type": "additive"},
            },
        ),
        {},
        r"""
&\text{Routine \textrm{(root)}}\newline
&\underline{\text{Resources:}}\\
&N_{\text{x}} = \operatorname{sum}{\left(\text{~}.\!N_{\text{x}} \right)}
""",
    ),
]


@pytest.mark.parametrize("routine, kwargs, expected_latex", LATEX_TEST_CASES)
def test_represent_routine_in_latex(routine, kwargs, expected_latex):
    expected_string = rf"$\begin{{align}}{expected_latex}\end{{align}}$"
    assert routine_to_latex(routine, **kwargs) == expected_string
