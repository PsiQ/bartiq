"""
..  Copyright © 2022-2024 PsiQuantum Corp.  All rights reserved.
    PSIQUANTUM CORP. CONFIDENTIAL
    This file includes unpublished proprietary source code of PsiQuantum Corp.
    The copyright notice above does not evidence any actual or intended publication
    of such source code. Disclosure of this source code or any related proprietary
    information is strictly prohibited without the express written permission of
    PsiQuantum Corp.

Tests for numeric estimate evaluation.
"""

import json
from pathlib import Path

import pytest

from bartiq import compile_routine, evaluate
from bartiq._routine import Routine

from ..utilities import routine_with_passthrough, routine_with_two_passthroughs


def load_evaluate_test_data():
    with open(Path(__file__).parent / "data/evaluate_test_data.json") as f:
        return json.load(f)


EVALUTE_TEST_CASES = load_evaluate_test_data()


@pytest.mark.parametrize("input_dict, assignments, expected_dict", EVALUTE_TEST_CASES)
def test_evaluate(input_dict, assignments, expected_dict, backend):
    evaluated_routine = evaluate(Routine(**input_dict), assignments, backend=backend)
    assert evaluated_routine == Routine(**expected_dict)


@pytest.mark.parametrize(
    "op, assignments, expected_sizes",
    [
        (routine_with_passthrough(), ["N=10"], {"out_0": "10"}),
        (routine_with_passthrough(a_out_size="N+2"), ["N=10"], {"out_0": "12"}),
        (routine_with_two_passthroughs(), ["N=10", "M=7"], {"out_0": "10", "out_1": "7"}),
    ],
)
def test_passthroughs(op, assignments, expected_sizes, backend):
    compiled_routine = compile_routine(op)
    evaluated_routine = evaluate(compiled_routine, assignments=assignments, backend=backend)
    for port_name, size in expected_sizes.items():
        assert evaluated_routine.ports[port_name].size == size


def custom_function(a, b):
    if a > 0:
        return a + b
    else:
        return a - b


@pytest.mark.parametrize(
    "input_dict, assignments, functions_map, expected_dict",
    [
        (
            {
                "name": "",
                "type": "foo",
                "children": {
                    "a": {
                        "name": "a",
                        "type": "a",
                        "resources": {
                            "X": {
                                "name": "X",
                                "type": "other",
                                "value": {"type": "str", "value": "2*N + a.unknown_fun(1)"},
                            }
                        },
                        "input_params": ["N"],
                    },
                    "b": {
                        "name": "b",
                        "type": "b",
                        "resources": {
                            "X": {
                                "name": "X",
                                "type": "other",
                                "value": {"type": "str", "value": "b.my_f(N, 2) + 3"},
                            }
                        },
                        "input_params": ["N"],
                    },
                },
                "resources": {
                    "X": {
                        "name": "X",
                        "type": "other",
                        "value": {
                            "type": "str",
                            "value": "2*N + b.my_f(N, 2) + 3 + a.unknown_fun(1)",
                        },
                    }
                },
                "input_params": ["N"],
            },
            ["N = 5"],
            {"b.my_f": custom_function},
            {
                "name": "",
                "type": "foo",
                "children": {
                    "a": {
                        "name": "a",
                        "type": "a",
                        "resources": {
                            "X": {
                                "name": "X",
                                "type": "other",
                                "value": {"type": "str", "value": "a.unknown_fun(1) + 10"},
                            }
                        },
                    },
                    "b": {
                        "name": "b",
                        "type": "b",
                        "resources": {
                            "X": {
                                "name": "X",
                                "type": "other",
                                "value": {"type": "str", "value": "10"},
                            }
                        },
                    },
                },
                "resources": {
                    "X": {
                        "name": "X",
                        "type": "other",
                        "value": {"type": "str", "value": "a.unknown_fun(1) + 20"},
                    }
                },
            },
        ),
    ],
)
def test_evaluate_with_functions_map(input_dict, assignments, functions_map, expected_dict, backend):
    evaluated_routine = evaluate(Routine(**input_dict), assignments, backend=backend, functions_map=functions_map)
    assert evaluated_routine == Routine(**expected_dict)
