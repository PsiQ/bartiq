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
import pytest_diff

from bartiq.compilation._symbolic_function import SymbolicFunction
from bartiq.symbolics import sympy_backend


# To add more backends to tests, simply parametrize this fixture.
@pytest.fixture
def backend():
    """Backend used for manipulating symbolic expressions."""
    return sympy_backend


@pytest_diff.registry.register(SymbolicFunction)
def diff_symbolic_function(x, y):
    """Differ for custom :class:`~.SymbolicFunction` objects."""
    inputs_x, inputs_y = set(x.inputs), set(y.inputs)
    inputs_in_x_and_y = inputs_x & inputs_y
    inputs_in_x_not_y = inputs_x - inputs_y
    inputs_in_y_not_x = inputs_y - inputs_x

    outputs_x, outputs_y = set(x.outputs.values()), set(y.outputs.values())
    outputs_in_x_and_y = outputs_x & outputs_y
    outputs_in_x_not_y = outputs_x - outputs_y
    outputs_in_y_not_x = outputs_y - outputs_x
    return [
        "",
        "### Inputs ###",
        f"LHS: {inputs_x}",
        f"RHS: {inputs_y}",
        "",
        "Inputs in LHS and RHS:",
        str(inputs_in_x_and_y),
        "Inputs in LHS missing from RHS:",
        str(inputs_in_x_not_y),
        "Inputs in RHS missing from LHS:",
        str(inputs_in_y_not_x),
        "",
        "### Outputs ###",
        "LHS:",
        *_format_output_strings(outputs_x),
        "RHS:",
        *_format_output_strings(outputs_y),
        "",
        "Outputs in LHS and RHS:",
        *_format_output_strings(outputs_in_x_and_y),
        "Outputs in LHS missing from RHS:",
        *_format_output_strings(outputs_in_x_not_y),
        "Outputs in RHS missing from LHS:",
        *_format_output_strings(outputs_in_y_not_x),
    ]


def _format_output_strings(outputs):
    return sorted([f"* {output}" for output in outputs])
