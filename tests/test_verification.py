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

import re
from pathlib import Path

import pytest
import yaml

from bartiq import Routine
from bartiq.symbolics import sympy_backend
from bartiq.verification import verify_compiled_routine, verify_uncompiled_routine

BACKEND = sympy_backend


def load_compile_test_data(return_uncompiled=True):
    with open(Path(__file__).parent / "compilation/data/compile_test_data.yaml") as f:
        if return_uncompiled:
            return [Routine(**uncompiled) for uncompiled, _ in yaml.safe_load(f)]
        else:
            return [Routine(**compiled) for _, compiled in yaml.safe_load(f)]


@pytest.mark.parametrize("routine", load_compile_test_data(return_uncompiled=True))
def test_verify_uncompiled_routine(routine):
    assert verify_uncompiled_routine(routine, backend=BACKEND)


@pytest.mark.parametrize(
    "routine,expected_problems",
    [
        (
            Routine(
                name="root",
                input_params=["N"],
                children={"a": Routine(name="a", type=None, input_params=["input_0"])},
                type=None,
                linked_params={"M": [("a", "input_0")], "N": [("a", "input_1")]},
            ),
            [
                "M is present in linked_params, but not in input_params\\.",
                "There is a link defined between N and \\('a', 'input_1'\\), "
                "but subroutine a does not have input_param: input_1\\.",
            ],
        ),
        (
            Routine(
                name="root",
                input_params=["N"],
                resources={"X": {"name": "X", "value": "a +", "type": "other"}},
                local_variables=["X=a*"],
                ports={"in_0": {"name": "in_0", "direction": "input", "size": "#"}},
                type=None,
            ),
            [
                "Couldn't parse resource: .* of subroutine: root\\.",
                "Couldn't parse local_variable: .* of subroutine: root\\.",
                "Couldn't parse port size: .* of subroutine: root\\.",
            ],
        ),
    ],
)
def test_verify_uncompiled_routine_fails(routine, expected_problems):
    verification_output = verify_uncompiled_routine(routine, backend=BACKEND)
    assert not verification_output
    assert len(expected_problems) == len(verification_output.problems)
    for expected_problem, problem in zip(expected_problems, verification_output.problems):
        assert re.match(expected_problem, problem)


@pytest.mark.parametrize("routine", load_compile_test_data(return_uncompiled=False))
def test_verify_compiled_routine(routine):
    if "a.a.x" in routine.input_params:
        pytest.xfail(
            "Due to the limitations of handling linked_params, this routine returns verification issue, even though "
            "it compiles properly.",
        )
    assert verify_compiled_routine(routine, backend=BACKEND)


@pytest.mark.parametrize(
    "routine,expected_problems",
    [
        (
            Routine(
                name="root",
                input_params=["N"],
                children={"a": Routine(name="a", type=None, input_params=["X"])},
                type=None,
                linked_params={"M": [("a", "input_0")], "N": [("a", "input_1")]},
            ),
            [
                "Expected linked_params to be removed, found: {'M': \\[\\('a', 'input_0'\\)\\], "
                "'N': \\[\\('a', 'input_1'\\)\\]} in root\\.",
                "Input param X found in subroutine: root.a, which is not among top level params: {'N'}\\.",
            ],
        ),
    ],
)
def test_verify_compiled_routine_fails(routine, expected_problems):
    verification_output = verify_compiled_routine(routine, backend=BACKEND)
    assert not verification_output
    assert len(expected_problems) == len(verification_output.problems)
    for expected_problem, problem in zip(expected_problems, verification_output.problems):
        assert re.match(expected_problem, problem)
