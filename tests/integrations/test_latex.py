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
from qref.schema_v1 import RoutineV1

from bartiq.integrations.latex import routine_to_latex

LATEX_TEST_CASES = [
    # Null case
    (
        RoutineV1(name="root"),
        {},
        "\n&\\text{RoutineV1 \\textrm{(root)}}\n",
    ),
    # Only input parameters
    (
        RoutineV1(name="root", input_params=["x", "y"]),
        {},
        r"""
&\text{RoutineV1 \textrm{(root)}}\newline
&\underline{\text{Input parameters:}}\\
&x, y
""",
    ),
    # Path-prefixed input parameters
    (
        RoutineV1(
            name="root",
            input_params=["subroutine.x_a", "y_b"],
            children=[{"name": "subroutine", "input_params": ["x_a"]}],
        ),
        {},
        r"""
&\text{RoutineV1 \textrm{(root)}}\newline
&\underline{\text{Input parameters:}}\\
&\text{subroutine}.\!x_{\text{a}}, y_{\text{b}}
""",
    ),
    # Only inherited_params
    (
        RoutineV1(
            name="root",
            linked_params=[
                {"source": "x", "targets": ["a.i_0", "c.j_1"]},
                {"source": "y", "targets": ["d.k_2", "e.l_3"]},
            ],
            children=[
                {"name": "a", "input_params": ["i_0"]},
                {"name": "c", "input_params": ["j_1"]},
                {"name": "d", "input_params": ["k_2"]},
                {"name": "e", "input_params": ["l_3"]},
            ],
        ),
        {},
        r"""
&\text{RoutineV1 \textrm{(root)}}\newline
&\underline{\text{Linked parameters:}}\\
&x: \text{a}.\!i_{\text{0}}, \text{c}.\!j_{\text{1}}\\
&y: \text{d}.\!k_{\text{2}}, \text{e}.\!l_{\text{3}}
""",
    ),
    # Only input register sizes
    (
        RoutineV1(
            name="root",
            ports=[
                {"name": "in_0", "size": "a", "direction": "input"},
                {"name": "b", "size": "b", "direction": "input"},
            ],
        ),
        {},
        r"""
&\text{RoutineV1 \textrm{(root)}}\newline
&\underline{\text{Input ports:}}\\
&\text{b} = b\\
&\text{in\_0} = a
""",
    ),
    # Only local parameters
    (
        RoutineV1(
            name="root",
            input_params=["a", "b"],
            local_variables={
                "x_foo": "y + a",
                "y_bar": "b * c",
                "z_foo_bar": "a + b",
            },
        ),
        {},
        r"""
&\text{RoutineV1 \textrm{(root)}}\newline
&\underline{\text{Input parameters:}}\\
&a, b\newline
&\underline{\text{Local variables:}}\\
&x_{\text{foo}} = a + y\\
&y_{\text{bar}} = b \cdot c\\
&z_{\text{foo\_bar}} = a + b
""",
    ),
    # Only output ports
    (
        RoutineV1(
            name="root",
            ports=[
                {"name": "in_0", "size": "2", "direction": "output"},
                {"name": "b", "size": "3", "direction": "output"},
            ],
        ),
        {},
        r"""
&\text{RoutineV1 \textrm{(root)}}\newline
&\underline{\text{Output ports:}}\\
&\text{b} = 3\\
&\text{in\_0} = 2
""",
    ),
    # Only costs
    (
        RoutineV1(
            name="root",
            resources=[
                {"name": "x", "value": 0, "type": "additive"},
                {"name": "y", "value": 1, "type": "additive"},
            ],
        ),
        {},
        r"""
&\text{RoutineV1 \textrm{(root)}}\newline
&\underline{\text{Resources:}}\\
&x = 0\\
&y = 1
""",
    ),
    # The whole shebang
    (
        RoutineV1(
            name="root",
            input_params=["x", "y"],
            ports=[
                {"name": "in_0", "size": "a", "direction": "input"},
                {"name": "in_b", "size": "b", "direction": "input"},
                {"name": "out_0", "size": "2", "direction": "output"},
                {"name": "out_b", "size": "3", "direction": "output"},
            ],
            linked_params=[
                {"source": "x", "targets": ["a.i_0", "c.j_1"]},
                {"source": "y", "targets": ["d.k_2", "e.l_3"]},
            ],
            children=[
                {"name": "a", "input_params": ["i_0"]},
                {"name": "c", "input_params": ["j_1"]},
                {"name": "d", "input_params": ["k_2"]},
                {"name": "e", "input_params": ["l_3"]},
            ],
            local_variables={
                "x_foo": "a.i_0 + a",
                "y_bar": "b * c.j_1",
            },
            resources=[
                {"name": "t", "value": 0, "type": "additive"},
            ],
        ),
        {},
        r"""
&\text{RoutineV1 \textrm{(root)}}\newline
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
        RoutineV1(
            name="root",
            local_variables={
                "a": "1+2",
                "b": "3+4",
            },
            resources=[
                {"name": "c", "value": "a + b", "type": "additive"},
                {"name": "d", "value": "a-b", "type": "additive"},
            ],
        ),
        {},
        r"""
&\text{RoutineV1 \textrm{(root)}}\newline
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
        RoutineV1(
            name="root",
            children=[
                {
                    "name": "a",
                    "resources": [
                        {"name": "y", "value": "2", "type": "additive"},
                    ],
                },
            ],
            resources=[
                {"name": "x", "value": "1", "type": "additive"},
            ],
        ),
        {},
        r"""
&\text{RoutineV1 \textrm{(root)}}\newline
&\underline{\text{Resources:}}\\
&x = 1\\
&\text{a}.\!y = 2
""",
    ),
    # Hide non-root costs
    (
        RoutineV1(
            name="root",
            children=[
                {
                    "name": "a",
                    "resources": [
                        {"name": "y", "value": "2", "type": "additive"},
                    ],
                },
            ],
            resources=[
                {"name": "x", "value": "1", "type": "additive"},
            ],
        ),
        {"show_non_root_resources": False},
        r"""
&\text{RoutineV1 \textrm{(root)}}\newline
&\underline{\text{Resources:}}\\
&x = 1
""",
    ),
    # Sum over all subresources
    (
        RoutineV1(
            name="root",
            resources=[
                {"name": "N_x", "value": "sum(~.N_x)", "type": "additive"},
            ],
        ),
        {},
        r"""
&\text{RoutineV1 \textrm{(root)}}\newline
&\underline{\text{Resources:}}\\
&N_{\text{x}} = \operatorname{sum}{\left(\text{~}.\!N_{\text{x}} \right)}
""",
    ),
    # Handle repetition
    (
        RoutineV1(
            name="root",
            children=[
                {
                    "name": "a",
                    "resources": [
                        {"name": "y", "value": "2", "type": "additive"},
                    ],
                },
            ],
            repetition={"count": "log(y+2)", "sequence": {"type": "constant"}},
        ),
        {},
        r"""
&\text{RoutineV1 \textrm{(root)}}\newline
&\underline{\text{Repetition:}}\\
&\text{Count} = \log{\left(y + 2 \right)}\\
&\text{Sequence type}:  constant\newline
&\underline{\text{Resources:}}\\
&\text{a}.\!y = 2
""",
    ),
    # Handle null-sized ports
    (
        RoutineV1(
            name="root",
            ports=[
                {"name": "in_0", "size": None, "direction": "input"},
                {"name": "out_0", "size": None, "direction": "output"},
            ],
        ),
        {},
        r"""
&\text{RoutineV1 \textrm{(root)}}\newline
&\underline{\text{Input ports:}}\\
&\text{in\_0} = None\newline
&\underline{\text{Output ports:}}\\
&\text{out\_0} = None
""",
    ),
    # Latex printer modification case
    (
        RoutineV1(
            name="my_routine",
            type=None,
            resources=[
                {"name": "local_highwater", "type": "other", "value": "10"},
            ],
        ),
        {},
        r"""
&\text{RoutineV1 \textrm{(my\_routine)}}\newline
&\underline{\text{Resources:}}\\
&{local}_{\text{highwater}} = 10
""",
    ),
]


@pytest.mark.parametrize("routine, kwargs, expected_latex", LATEX_TEST_CASES)
def test_represent_routine_in_latex(routine, kwargs, expected_latex):
    expected_string = rf"$\begin{{align}}{expected_latex}\end{{align}}$"
    assert routine_to_latex(routine, **kwargs) == expected_string
