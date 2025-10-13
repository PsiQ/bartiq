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
from bartiq.compilation import CompilationFlags, compile_routine
from bartiq.symbolics import sympy_backend


# To add more backends to tests, simply parametrize this fixture.
@pytest.fixture
def backend():
    """Backend used for manipulating symbolic expressions."""
    return sympy_backend


@pytest.fixture
def dummy_qref():
    return {
        "name": "root",
        "children": [
            {
                "name": "a",
                "children": [
                    {
                        "name": "b",
                        "resources": [
                            {"name": "dummy_a", "type": "additive", "value": "max(0, b)"},
                            {"name": "dummy_b", "type": "additive", "value": "log(1 + b)"},
                        ],
                    },
                    {
                        "name": "c",
                        "resources": [
                            {"name": "dummy_a", "type": "additive", "value": "max(0, c)"},
                            {"name": "dummy_b", "type": "additive", "value": "min(2, c)"},
                        ],
                    },
                ],
            },
            {
                "name": "x",
                "children": [
                    {
                        "name": "y",
                        "resources": [
                            {"name": "dummy_a", "type": "additive", "value": "max(0, y)"},
                            {"name": "dummy_b", "type": "additive", "value": "ceiling(y)"},
                        ],
                    },
                    {
                        "name": "z",
                        "resources": [
                            {"name": "dummy_a", "type": "additive", "value": "max(0, z)"},
                            {"name": "dummy_b", "type": "additive", "value": "Heaviside(z, 0.5)"},
                        ],
                    },
                ],
            },
        ],
    }


@pytest.fixture(scope="function")
def dummy_compiled_routine(dummy_qref, backend):
    return compile_routine(
        Routine.from_qref(dummy_qref, backend), compilation_flags=CompilationFlags.EXPAND_RESOURCES
    ).routine
