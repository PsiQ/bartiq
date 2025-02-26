# Copyright 2025 PsiQuantum, Corp.
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

from bartiq import CompiledRoutine, Routine, routine_to_qref
from bartiq.symbolics.sympy_backends import SympyBackend


def load_compile_test_data():
    test_files_path = Path(__file__).parent / "compilation/data/compile/"
    for path in sorted(test_files_path.rglob("*.yaml")):
        with open(path) as f:
            for original, expected in yaml.safe_load(f):
                yield (SchemaV1(**original), SchemaV1(**expected))


COMPILE_TEST_DATA = load_compile_test_data()


@pytest.mark.parametrize("input_routine, input_compiled_routine", COMPILE_TEST_DATA)
def test_qref_back_and_forth_conversion(input_routine, input_compiled_routine):
    backend = SympyBackend()
    routine_from_qref = Routine.from_qref(input_routine, backend=backend)

    # Normally we compare QREF objects directly, but this fails for two reasons:
    # 1. When creating Routine object from QREF, we introduce some minor changes to it to simplify later processing.
    # 2. Resource costs in QREF are strings and the order of the symbols in the expression can change.
    # Rather than implementing an elaborate function for comparing QREFs with those extra conditions,
    # we decided that creating Routine objects and comparing them checks essentially the same thing.
    qref_routine = routine_from_qref.to_qref(backend)
    assert Routine.from_qref(qref_routine, backend=backend) == Routine.from_qref(input_routine, backend=backend)

    compiled_routine_from_qref = Routine.from_qref(input_compiled_routine, backend=backend)
    qref_compiled_routine = compiled_routine_from_qref.to_qref(backend)
    assert CompiledRoutine.from_qref(qref_compiled_routine, backend=backend) == CompiledRoutine.from_qref(
        input_compiled_routine, backend=backend
    )

    # This is to check whether `routine_to_qref` yields the same results.
    qref_routine = routine_to_qref(routine_from_qref, backend)
    assert Routine.from_qref(qref_routine, backend=backend) == Routine.from_qref(input_routine, backend=backend)
