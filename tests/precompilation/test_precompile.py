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

from bartiq._routine import Routine
from bartiq.precompilation import precompile
from bartiq.precompilation.stages import (
    AddPassthroughPlaceholder,
    BartiqPrecompilationError,
    add_default_additive_resources,
    add_default_properties,
    unroll_wildcarded_resources,
)

from ..utilities import routine_with_passthrough, routine_with_two_passthroughs

PRECOMP_TEST_CASES = [
    # Default case
    # Should test the following:
    # - Adding missing register sizes for merge
    # - Removing input register size for non-root containers
    (
        {
            "name": "root",
            "type": None,
            "ports": {
                "in_0": {
                    "name": "in_0",
                    "direction": "input",
                    "size": {"type": "str", "value": "x0"},
                },
                "in_1": {
                    "name": "in_1",
                    "direction": "input",
                    "size": {"type": "str", "value": "x1"},
                },
                "out_0": {"name": "out_0", "direction": "output", "size": None},
            },
            "children": {
                "a": {
                    "name": "a",
                    "type": None,
                    "ports": {
                        "in_0": {
                            "name": "in_0",
                            "direction": "input",
                            "size": {"type": "str", "value": "N_0"},
                        },
                        "in_1": {
                            "name": "in_1",
                            "direction": "input",
                            "size": {"type": "str", "value": "N_1"},
                        },
                        "out_0": {"name": "out_0", "direction": "output", "size": None},
                    },
                    "children": {
                        "b": {
                            "name": "b",
                            "type": "merge",
                            "ports": {
                                "in_0": {
                                    "name": "in_0",
                                    "direction": "input",
                                    "size": None,
                                },
                                "in_1": {
                                    "name": "in_1",
                                    "direction": "input",
                                    "size": None,
                                },
                                "out_0": {
                                    "name": "out_0",
                                    "direction": "output",
                                    "size": None,
                                },
                            },
                        }
                    },
                    "connections": [
                        {"source": "b.out_0", "target": "out_0"},
                        {"source": "in_0", "target": "b.in_0"},
                        {"source": "in_1", "target": "b.in_1"},
                    ],
                }
            },
            "connections": [
                {"source": "a.out_0", "target": "out_0"},
                {"source": "in_0", "target": "a.in_0"},
                {"source": "in_1", "target": "a.in_1"},
            ],
        },
        None,
        {
            "name": "root",
            "type": None,
            "ports": {
                "in_0": {
                    "name": "in_0",
                    "direction": "input",
                    "size": {"type": "str", "value": "x0"},
                },
                "in_1": {
                    "name": "in_1",
                    "direction": "input",
                    "size": {"type": "str", "value": "x1"},
                },
                "out_0": {"name": "out_0", "direction": "output", "size": None},
            },
            "children": {
                "a": {
                    "name": "a",
                    "type": None,
                    "ports": {
                        "in_0": {"name": "in_0", "direction": "input", "size": None},
                        "in_1": {"name": "in_1", "direction": "input", "size": None},
                        "out_0": {"name": "out_0", "direction": "output", "size": None},
                    },
                    "children": {
                        "b": {
                            "name": "b",
                            "type": "merge",
                            "ports": {
                                "in_0": {
                                    "name": "in_0",
                                    "direction": "input",
                                    "size": {"type": "str", "value": "N_in_0"},
                                },
                                "in_1": {
                                    "name": "in_1",
                                    "direction": "input",
                                    "size": {"type": "str", "value": "N_in_1"},
                                },
                                "out_0": {
                                    "name": "out_0",
                                    "direction": "output",
                                    "size": {"type": "str", "value": "N_in_0+N_in_1"},
                                },
                            },
                        }
                    },
                    "connections": [
                        {"source": "b.out_0", "target": "out_0"},
                        {"source": "in_0", "target": "b.in_0"},
                        {"source": "in_1", "target": "b.in_1"},
                    ],
                }
            },
            "connections": [
                {"source": "a.out_0", "target": "out_0"},
                {"source": "in_0", "target": "a.in_0"},
                {"source": "in_1", "target": "a.in_1"},
            ],
        },
    ),
    # Insert default register sizes for merge
    (
        {
            "name": "root",
            "type": None,
            "ports": {
                "in_0": {
                    "name": "in_0",
                    "direction": "input",
                    "size": {"type": "str", "value": "x0"},
                },
                "in_1": {
                    "name": "in_1",
                    "direction": "input",
                    "size": {"type": "str", "value": "x1"},
                },
                "out_0": {"name": "out_0", "direction": "output", "size": None},
            },
            "children": {
                "a": {
                    "name": "a",
                    "type": None,
                    "ports": {
                        "in_0": {
                            "name": "in_0",
                            "direction": "input",
                            "size": {"type": "str", "value": "y0"},
                        },
                        "in_1": {
                            "name": "in_1",
                            "direction": "input",
                            "size": {"type": "str", "value": "y1"},
                        },
                        "out_0": {"name": "out_0", "direction": "output", "size": None},
                    },
                    "children": {
                        "b": {
                            "name": "b",
                            "type": "merge",
                            "ports": {
                                "in_0": {
                                    "name": "in_0",
                                    "direction": "input",
                                    "size": None,
                                },
                                "in_1": {
                                    "name": "in_1",
                                    "direction": "input",
                                    "size": None,
                                },
                                "out_0": {
                                    "name": "out_0",
                                    "direction": "output",
                                    "size": None,
                                },
                            },
                        }
                    },
                    "connections": [
                        {"source": "b.out_0", "target": "out_0"},
                        {"source": "in_0", "target": "b.in_0"},
                        {"source": "in_1", "target": "b.in_1"},
                    ],
                }
            },
            "connections": [
                {"source": "a.out_0", "target": "out_0"},
                {"source": "in_0", "target": "a.in_0"},
                {"source": "in_1", "target": "a.in_1"},
            ],
        },
        [add_default_properties],
        {
            "name": "root",
            "type": None,
            "ports": {
                "in_0": {
                    "name": "in_0",
                    "direction": "input",
                    "size": {"type": "str", "value": "x0"},
                },
                "in_1": {
                    "name": "in_1",
                    "direction": "input",
                    "size": {"type": "str", "value": "x1"},
                },
                "out_0": {"name": "out_0", "direction": "output", "size": None},
            },
            "children": {
                "a": {
                    "name": "a",
                    "type": None,
                    "ports": {
                        "in_0": {
                            "name": "in_0",
                            "direction": "input",
                            "size": {"type": "str", "value": "y0"},
                        },
                        "in_1": {
                            "name": "in_1",
                            "direction": "input",
                            "size": {"type": "str", "value": "y1"},
                        },
                        "out_0": {"name": "out_0", "direction": "output", "size": None},
                    },
                    "children": {
                        "b": {
                            "name": "b",
                            "type": "merge",
                            "ports": {
                                "in_0": {
                                    "name": "in_0",
                                    "direction": "input",
                                    "size": {"type": "str", "value": "N_in_0"},
                                },
                                "in_1": {
                                    "name": "in_1",
                                    "direction": "input",
                                    "size": {"type": "str", "value": "N_in_1"},
                                },
                                "out_0": {
                                    "name": "out_0",
                                    "direction": "output",
                                    "size": {"type": "str", "value": "N_in_0+N_in_1"},
                                },
                            },
                        }
                    },
                    "connections": [
                        {"source": "b.out_0", "target": "out_0"},
                        {"source": "in_0", "target": "b.in_0"},
                        {"source": "in_1", "target": "b.in_1"},
                    ],
                }
            },
            "connections": [
                {"source": "a.out_0", "target": "out_0"},
                {"source": "in_0", "target": "a.in_0"},
                {"source": "in_1", "target": "a.in_1"},
            ],
        },
    ),
    # Checks if default additive resources are being added correctly
    (
        {
            "name": "root",
            "type": None,
            "children": {
                "a": {
                    "name": "a",
                    "type": None,
                    "resources": {
                        "N_toffs": {
                            "name": "N_toffs",
                            "type": "additive",
                            "value": {"type": "str", "value": "1"},
                        },
                        "N_meas": {
                            "name": "N_meas",
                            "type": "additive",
                            "value": {"type": "str", "value": "5"},
                        },
                    },
                },
                "b": {
                    "name": "b",
                    "type": None,
                    "resources": {
                        "N_toffs": {
                            "name": "N_toffs",
                            "type": "additive",
                            "value": {"type": "str", "value": "2"},
                        },
                        "N_rots": {
                            "name": "N_rots",
                            "type": "additive",
                            "value": {"type": "str", "value": "3"},
                        },
                        "N_x": {
                            "name": "N_x",
                            "type": "other",
                            "value": {"type": "str", "value": "1"},
                        },
                    },
                },
            },
            "resources": {
                "N_meas": {
                    "name": "N_meas",
                    "type": "additive",
                    "value": {"type": "str", "value": "a.N_meas"},
                }
            },
        },
        [add_default_additive_resources],
        {
            "name": "root",
            "type": None,
            "children": {
                "a": {
                    "name": "a",
                    "type": None,
                    "resources": {
                        "N_toffs": {
                            "name": "N_toffs",
                            "type": "additive",
                            "value": {"type": "str", "value": "1"},
                        },
                        "N_meas": {
                            "name": "N_meas",
                            "type": "additive",
                            "value": {"type": "str", "value": "5"},
                        },
                    },
                },
                "b": {
                    "name": "b",
                    "type": None,
                    "resources": {
                        "N_toffs": {
                            "name": "N_toffs",
                            "type": "additive",
                            "value": {"type": "str", "value": "2"},
                        },
                        "N_rots": {
                            "name": "N_rots",
                            "type": "additive",
                            "value": {"type": "str", "value": "3"},
                        },
                        "N_x": {
                            "name": "N_x",
                            "type": "other",
                            "value": {"type": "str", "value": "1"},
                        },
                    },
                },
            },
            "resources": {
                "N_meas": {
                    "name": "N_meas",
                    "type": "additive",
                    "value": {"type": "str", "value": "a.N_meas"},
                },
                "N_rots": {
                    "name": "N_rots",
                    "type": "additive",
                    "value": {"type": "str", "value": "sum(~.N_rots)"},
                },
                "N_toffs": {
                    "name": "N_toffs",
                    "type": "additive",
                    "value": {"type": "str", "value": "sum(~.N_toffs)"},
                },
            },
        },
    ),
]


@pytest.mark.parametrize("input_dict, precompilation_stages, expected_dict", PRECOMP_TEST_CASES)
def test_precompile_adds_additive_resources(input_dict, precompilation_stages, expected_dict, backend):
    input_routine = Routine(**input_dict)
    precompiled_routine = precompile(input_routine, precompilation_stages=precompilation_stages, backend=backend)
    assert precompiled_routine.model_dump(exclude_unset=True) == expected_dict


WILDCARD_TEST_CASES = [
    (
        {
            "name": "root",
            "type": None,
            "children": {
                "rot_1": {
                    "name": "rot_1",
                    "type": "rot",
                    "resources": {
                        "T": {
                            "name": "T",
                            "type": "other",
                            "value": {"type": "str", "value": "1"},
                        }
                    },
                },
                "rot_2": {
                    "name": "rot_2",
                    "type": "rot",
                    "resources": {
                        "T": {
                            "name": "T",
                            "type": "other",
                            "value": {"type": "str", "value": "1"},
                        }
                    },
                },
                "rot_C": {
                    "name": "rot_C",
                    "type": "rot",
                    "resources": {
                        "T": {
                            "name": "T",
                            "type": "other",
                            "value": {"type": "str", "value": "1"},
                        }
                    },
                },
            },
            "resources": {
                "N_T": {
                    "name": "N_T",
                    "type": "other",
                    "value": {"type": "str", "value": "sum(rot_~.T)"},
                }
            },
        },
        ["N_T", "sum(rot_1.T,rot_2.T,rot_C.T)"],
    ),
    (
        {
            "name": "root",
            "type": None,
            "children": {
                "rot_1": {
                    "name": "rot_1",
                    "type": "rot",
                    "resources": {
                        "T": {
                            "name": "T",
                            "type": "other",
                            "value": {"type": "str", "value": "1"},
                        }
                    },
                },
                "rot_2": {
                    "name": "rot_2",
                    "type": "rot",
                    "resources": {
                        "T": {
                            "name": "T",
                            "type": "other",
                            "value": {"type": "str", "value": "1"},
                        }
                    },
                },
                "rot_C": {
                    "name": "rot_C",
                    "type": "rot",
                    "resources": {
                        "T": {
                            "name": "T",
                            "type": "other",
                            "value": {"type": "str", "value": "1"},
                        }
                    },
                },
            },
            "resources": {
                "N_T": {
                    "name": "N_T",
                    "type": "other",
                    "value": {"type": "str", "value": "sum(~.T)"},
                }
            },
        },
        ["N_T", "sum(rot_1.T,rot_2.T,rot_C.T)"],
    ),
    (
        {
            "name": "root",
            "type": None,
            "children": {
                "rot_T1": {
                    "name": "rot_T1",
                    "type": "rotT",
                    "resources": {
                        "T": {
                            "name": "T",
                            "type": "other",
                            "value": {"type": "str", "value": "1"},
                        }
                    },
                },
                "rot_T2": {
                    "name": "rot_T2",
                    "type": "rotT",
                    "resources": {
                        "T": {
                            "name": "T",
                            "type": "other",
                            "value": {"type": "str", "value": "1"},
                        }
                    },
                },
                "rot_Q1": {
                    "name": "rot_Q1",
                    "type": "rotQ",
                    "resources": {
                        "Q": {
                            "name": "Q",
                            "type": "other",
                            "value": {"type": "str", "value": "1"},
                        }
                    },
                },
                "rot_Q2": {
                    "name": "rot_Q2",
                    "type": "rotQ",
                    "resources": {
                        "Q": {
                            "name": "Q",
                            "type": "other",
                            "value": {"type": "str", "value": "1"},
                        }
                    },
                },
            },
            "resources": {
                "total_cost": {
                    "name": "total_cost",
                    "type": "other",
                    "value": {"type": "str", "value": "sum(~.T) + max(~.Q)"},
                }
            },
        },
        ["total_cost", "sum(rot_T1.T,rot_T2.T) + max(rot_Q1.Q,rot_Q2.Q)"],
    ),
    (
        {
            "name": "root",
            "type": None,
            "children": {
                "rot_T1": {
                    "name": "rot_T1",
                    "type": "rot",
                    "resources": {
                        "T": {
                            "name": "T",
                            "type": "other",
                            "value": {"type": "str", "value": "1"},
                        }
                    },
                },
                "rot_T2": {
                    "name": "rot_T2",
                    "type": "rot",
                    "resources": {
                        "T": {
                            "name": "T",
                            "type": "other",
                            "value": {"type": "str", "value": "1"},
                        }
                    },
                },
            },
            "resources": {
                "total_cost": {
                    "name": "total_cost",
                    "type": "other",
                    "value": {"type": "str", "value": "2*rot_T1.T + 3*max(~.T)"},
                }
            },
        },
        ["total_cost", "2*rot_T1.T + 3*max(rot_T1.T,rot_T2.T)"],
    ),
    (
        {
            "name": "root",
            "type": None,
            "children": {
                "rot_T1": {
                    "name": "rot_T1",
                    "type": "rot",
                    "resources": {
                        "T": {
                            "name": "T",
                            "type": "other",
                            "value": {"type": "str", "value": "1"},
                        }
                    },
                },
                "rot_T2": {
                    "name": "rot_T2",
                    "type": "rot",
                    "resources": {
                        "T": {
                            "name": "T",
                            "type": "other",
                            "value": {"type": "str", "value": "1"},
                        }
                    },
                },
                "sum_rots": {
                    "name": "sum_rots",
                    "type": "sum_rot",
                    "resources": {
                        "R": {
                            "name": "R",
                            "type": "other",
                            "value": {"type": "str", "value": "rot_T1.T + rot_T2.T"},
                        }
                    },
                },
            },
            "resources": {
                "total_cost": {
                    "name": "total_cost",
                    "type": "other",
                    "value": {"type": "str", "value": "sum(~.T)"},
                }
            },
        },
        ["total_cost", "sum(rot_T1.T,rot_T2.T)"],
    ),
    (
        {
            "name": "root",
            "type": None,
            "children": {
                "rot_T1": {
                    "name": "rot_T1",
                    "type": "rot_T",
                    "resources": {
                        "T": {
                            "name": "T",
                            "type": "other",
                            "value": {"type": "str", "value": "1"},
                        }
                    },
                },
                "rot_T2": {
                    "name": "rot_T2",
                    "type": "rot_T",
                    "resources": {
                        "T": {
                            "name": "T",
                            "type": "other",
                            "value": {"type": "str", "value": "1"},
                        }
                    },
                },
                "rot_S1": {
                    "name": "rot_S1",
                    "type": "rot_S",
                    "resources": {
                        "S": {
                            "name": "S",
                            "type": "other",
                            "value": {"type": "str", "value": "1"},
                        }
                    },
                },
            },
            "resources": {
                "total_cost": {
                    "name": "total_cost",
                    "type": "other",
                    "value": {"type": "str", "value": "sum(rot_~.T)"},
                }
            },
        },
        ["total_cost", "sum(rot_T1.T,rot_T2.T)"],
    ),
]


@pytest.mark.parametrize("input_dict, expected_resource", WILDCARD_TEST_CASES)
def test_precompile_handles_wildcards(input_dict, expected_resource, backend):
    input_routine = Routine(**input_dict)
    precompiled_routine = precompile(
        input_routine,
        precompilation_stages=[unroll_wildcarded_resources],
        backend=backend,
    )
    assert precompiled_routine.resources[expected_resource[0]].value == expected_resource[1]


def test_precompile_handles_passthroughs(backend):
    precompiled_routine = precompile(
        routine_with_passthrough(),
        precompilation_stages=[AddPassthroughPlaceholder().add_passthrough_placeholders],
        backend=backend,
    )

    assert "passthrough_0" in precompiled_routine.children["b"].children
    assert "passthrough_1" in precompiled_routine.children["c"].children
    assert len(precompiled_routine.children["b"].connections) == 2
    assert len(precompiled_routine.children["c"].connections) == 2

    precompiled_routine = precompile(
        routine_with_two_passthroughs(),
        precompilation_stages=[AddPassthroughPlaceholder().add_passthrough_placeholders],
        backend=backend,
    )

    assert "passthrough_0" in precompiled_routine.children["c"].children
    assert "passthrough_1" in precompiled_routine.children["c"].children
    assert len(precompiled_routine.children["c"].connections) == 4


FAILING_CASES = [
    (
        {
            "name": "a",
            "type": None,
            "ports": {
                "in_0": {"name": "in_0", "direction": "input", "size": None},
                "in_1": {"name": "in_1", "direction": "input", "size": None},
                "out_0": {"name": "out_0", "direction": "output", "size": None},
                "out_1": {"name": "out_1", "direction": "output", "size": None},
            },
            "children": {
                "passthrough_1": {
                    "name": "passthrough_1",
                    "type": None,
                    "ports": {
                        "in_0": {"name": "in_0", "direction": "input", "size": None},
                        "out_0": {"name": "out_0", "direction": "output", "size": None},
                    },
                    "connections": [{"source": "in_0", "target": "out_0"}],
                },
            },
            "connections": [
                {"source": "in_1", "target": "out_1"},
                {"source": "in_0", "target": "passthrough_1.in_0"},
                {"source": "passthrough_1.out_0", "target": "out_0"},
            ],
        },
        "Cannot add passthrough named passthrough_1, as child with such name already exists.",
    )
]


@pytest.mark.parametrize("input_dict,failure_message", FAILING_CASES)
def test_precompile_raises_correct_exceptions(input_dict, failure_message, backend):
    input_routine = Routine(**input_dict)
    with pytest.raises(BartiqPrecompilationError, match=failure_message):
        precompile(input_routine, backend=backend)


KNOWN_BUGGY_WILDCARD_CASES = [
    (
        {
            "name": "root",
            "type": None,
            "children": {
                "rot_T1": {
                    "name": "rot_T1",
                    "type": "rotT",
                    "resources": {
                        "T": {
                            "name": "T",
                            "type": "other",
                            "value": {"type": "str", "value": "1"},
                        }
                    },
                },
                "rot_T2": {
                    "name": "rot_T2",
                    "type": "rotT",
                    "resources": {
                        "T": {
                            "name": "T",
                            "type": "other",
                            "value": {"type": "str", "value": "1"},
                        }
                    },
                },
                "rot_Q1": {
                    "name": "rot_Q1",
                    "type": "rotQ",
                    "resources": {
                        "Q": {
                            "name": "Q",
                            "type": "other",
                            "value": {"type": "str", "value": "1"},
                        }
                    },
                },
                "rot_Q2": {
                    "name": "rot_Q2",
                    "type": "rotQ",
                    "resources": {
                        "Q": {
                            "name": "Q",
                            "type": "other",
                            "value": {"type": "str", "value": "1"},
                        }
                    },
                },
            },
            "resources": {
                "total_cost": {
                    "name": "total_cost",
                    "type": "other",
                    "value": {"type": "str", "value": "sum(~.T) - max(~.T)"},
                }
            },
        },
        ["sum(rot_T1.T,rot_T2.T) - max(rot_Q1.Q,rot_Q2.Q)"],
        "Fails due to sympy interpreter not handling wildcard expressions.",
    ),
]


@pytest.mark.parametrize("input_dict, expected_resource, failure_message", KNOWN_BUGGY_WILDCARD_CASES)
def test_precompile_with_wildcard_fails(input_dict, expected_resource, failure_message):
    pytest.xfail(failure_message)
    input_routine = Routine(**input_dict)

    precompiled_routine = precompile(input_routine, precompilation_stages=[unroll_wildcarded_resources])
    assert precompiled_routine.resources["total_cost"].value == expected_resource
