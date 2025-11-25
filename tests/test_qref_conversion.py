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


import pytest

from bartiq import CompiledRoutine, Routine, compile_routine, routine_to_qref
from bartiq.symbolics.sympy_backend import SympyBackend
from tests.utilities import load_compile_test_data

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


def test_compiled_routine_with_first_pass_resources_can_be_loselessly_converted_to_qref():
    data = {
        "version": "v1",
        "program": {
            "name": "root",
            "repetition": {"count": "R", "sequence": {"type": "constant", "multiplier": 1}},
            "children": [
                {
                    "name": "a",
                    "ports": [
                        {"name": "in_0", "direction": "input", "size": "K"},
                        {"name": "in_1", "direction": "input", "size": "L"},
                        {"name": "out_0", "direction": "output", "size": None},
                        {"name": "out_1", "direction": "output", "size": None},
                    ],
                    "connections": ["in_0 -> a.thru_0", "a.thru_0 -> out_0", "in_1 -> b.thru_0", "b.thru_0 -> out_1"],
                    "children": [
                        {
                            "name": "a",
                            "resources": [
                                {"name": "x", "type": "additive", "value": "N"},
                                {"name": "y", "type": "multiplicative", "value": "N+1"},
                            ],
                            "ports": [{"name": "thru_0", "size": "N", "direction": "through"}],
                            "meta": {"first_pass_only": True},
                        },
                        {
                            "name": "b",
                            "resources": [
                                {"name": "x", "type": "additive", "value": "N"},
                                {"name": "y", "type": "multiplicative", "value": "N+1"},
                            ],
                            "ports": [{"name": "thru_0", "size": "N", "direction": "through"}],
                        },
                    ],
                }
            ],
            "ports": [
                {"name": "in_0", "size": "N", "direction": "input"},
                {"name": "out_0", "size": None, "direction": "output"},
                {"name": "in_1", "size": "M", "direction": "input"},
                {"name": "out_1", "size": None, "direction": "output"},
            ],
            "connections": ["in_0 -> a.in_0", "a.out_0 -> out_0", "in_1 -> a.in_1", "a.out_1 -> out_1"],
        },
    }

    compiled_routine = compile_routine(data).routine

    assert compiled_routine == CompiledRoutine.from_qref(compiled_routine.to_qref(SympyBackend()), SympyBackend())
