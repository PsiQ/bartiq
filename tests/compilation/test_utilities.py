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

from bartiq.compilation._utilities import is_single_parameter


@pytest.mark.parametrize(
    "expression, expected",
    [
        # Good params
        ("x", True),
        ("lambda", True),
        ("one", True),
        ("some.path.to.param", True),
        ("some.path.to.#port.param", True),
        # Bad params
        ("x + y", False),
        ("1", False),
        ("3.141", False),
        ("N+1", False),
        ("ceil(log_2(N))", False),
        (None, False),
    ],
)
def test_is_single_parameter(expression, expected):
    assert is_single_parameter(expression) == expected
