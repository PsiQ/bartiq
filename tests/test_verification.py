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

from pathlib import Path

import pytest
import yaml
from qref import SchemaV1

from bartiq.verification import verify_uncompiled_repetitions


def load_invalid_examples():
    with open(Path(__file__).parent / "data/invalid_repetitions.yaml") as f:
        data = yaml.safe_load(f)

    return [
        pytest.param(
            example["input"],
            example["problems"],
            id=example["description"],
        )
        for example in data
    ]


def load_valid_examples():
    with open(Path(__file__).parent / "compilation/data/compile/repetitions.yaml") as f:
        return [example[0] for example in yaml.safe_load(f)]


@pytest.mark.parametrize("valid_program", load_valid_examples())
def test_correct_routines_pass_repetition_verification(valid_program):
    verification_output = verify_uncompiled_repetitions(SchemaV1(**valid_program))
    assert verification_output
    assert len(verification_output.problems) == 0


@pytest.mark.parametrize("input, problems", load_invalid_examples())
def test_invalid_program_fails_to_validate_with_schema_v1(input, problems):
    verification_output = verify_uncompiled_repetitions(SchemaV1(**input))

    # We use sorted here, to make sure that we don't test the order in which the
    # problems appear, as the order is only an implementation detail.
    assert sorted(verification_output.problems) == sorted(problems)
