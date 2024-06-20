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
from bartiq.compilation._symbolic_function import (
    SymbolicFunction, to_symbolic_function,
    update_routine_with_symbolic_function)
from bartiq.errors import BartiqCompilationError


def _make_routine(**kwargs) -> Routine:
    routine = Routine(name="root", type="dummy", **kwargs)
    # This logic is needed as we cast everything to strings when we translate to symbolic function.
    for subroutine in routine.walk():
        for resource in subroutine.resources.values():
            resource.value = str(resource.value)
        for port in subroutine.ports.values():
            port.size = str(port.size)

    return routine


def _cost_str_to_resource(cost_str):
    lhs, rhs = cost_str.split("=")
    return {"name": lhs.strip(), "type": "other", "value": rhs.strip()}


def _ports_from_reg_sizes(reg_sizes, short_dir):
    (prefix, direction) = ("in_", "input") if short_dir == "in" else ("out_", "output")
    return {(name := f"{prefix}{k}"): {"name": name, "direction": direction, "size": v} for k, v in reg_sizes.items()}


def _dummy_resources(cost_strs):
    return {(res := _cost_str_to_resource(cost_str))["name"]: res for cost_str in cost_strs}


TO_SYMBOLIC_FUNCTION_TEST_CASES = [
    # Null case
    (_make_routine(), ([], [])),
    # Simple case with no register sizes
    (
        _make_routine(input_params=["a", "b"], resources=_dummy_resources(["x = a + b", "y = a - b"])),
        (["a", "b"], ["x = a + b", "y = a - b"]),
    ),
    # No register sizes, but including local parameters
    (
        _make_routine(
            input_params=["a", "b"],
            local_variables=["m = a + b", "n = a - b"],
            resources=_dummy_resources(["x = m + n", "y = m - n"]),
        ),
        (["a", "b"], ["x = 2 * a", "y = 2 * b"]),
    ),
    # No register sizes, but including self-referential local parameters
    (
        _make_routine(
            input_params=["a", "b"],
            local_variables=["m = a ** 2", "n = b ** 2", "w = m + n"],
            resources=_dummy_resources(["x = w - m", "y = w - n"]),
        ),
        (["a", "b"], ["x = b ** 2", "y = a ** 2"]),
    ),
    # Input and output register sizes
    (
        _make_routine(
            ports={
                **_ports_from_reg_sizes({"psi": "N"}, "in"),
                **_ports_from_reg_sizes({"psi": "3 * N"}, "out"),
            }
        ),
        (["#in_psi.N"], ["#out_psi = 3 * #in_psi.N"]),
    ),
    # Input and output register sizes with local parameters
    (
        _make_routine(
            local_variables=["M = 3 * N"],
            ports={
                **_ports_from_reg_sizes({"psi": "N"}, "in"),
                **_ports_from_reg_sizes({"psi": "M"}, "out"),
            },
        ),
        (["#in_psi.N"], ["#out_psi = 3 * #in_psi.N"]),
    ),
    # Both inputs have the same size
    (
        _make_routine(
            ports={
                **_ports_from_reg_sizes({"0": "N", "1": "N"}, "in"),
                **_ports_from_reg_sizes({"0": "2*N"}, "out"),
            }
        ),
        (["#in_0.N", "#in_1.N"], ["#out_0 = 2*#in_0.N"]),
    ),
    # Multiple inputs have the same size
    (
        _make_routine(
            ports={
                **_ports_from_reg_sizes({"0": "A", "1": "A", "2": "B", "3": "C", "4": "B", "5": "A", "6": "C"}, "in"),
                **_ports_from_reg_sizes({"0": "A + B + 2*C"}, "out"),
            }
        ),
        (
            ["#in_0.A", "#in_1.A", "#in_2.B", "#in_3.C", "#in_4.B", "#in_5.A", "#in_6.C"],
            ["#out_0 = #in_0.A + #in_2.B + 2*#in_3.C"],
        ),
    ),
    # Multiple inputs have the same size and we use input params
    (
        _make_routine(
            input_params=["a", "b"],
            ports={
                **_ports_from_reg_sizes({"0": "N", "1": "N"}, "in"),
                **_ports_from_reg_sizes({"0": "2*N"}, "out"),
            },
        ),
        (["#in_0.N", "#in_1.N", "a", "b"], ["#out_0 = 2*#in_0.N"]),
    ),
    # Only inputs are subresources
    (
        _make_routine(resources=_dummy_resources(["x = a.N + a.b.N"])),
        (["a.N", "a.b.N"], ["x = a.N + a.b.N"]),
    ),
    # Input params and subresources
    (
        _make_routine(input_params=["N"], resources=_dummy_resources(["x = N + a.N + a.b.N"])),
        (["N", "a.N", "a.b.N"], ["x = N + a.N + a.b.N"]),
    ),
    # Input params, subresources, and local parameters
    (
        _make_routine(
            input_params=["N"],
            local_variables=["M = N + a.N + a.b.N"],
            resources=_dummy_resources(["x = M"]),
        ),
        (["N", "a.N", "a.b.N"], ["x = N + a.N + a.b.N"]),
    ),
    # The whole shebang
    (
        _make_routine(
            input_params=["N"],
            # NOTE: the following should be ignored, since it doesn't directly affect the parent's function
            linked_params={"N": [("a", "N"), ("a", "b.N")]},
            ports={
                **_ports_from_reg_sizes(
                    {
                        "psi": "a",
                        "phi": "b",
                    },
                    "in",
                ),
                **_ports_from_reg_sizes(
                    {
                        "psi": "M",
                        "phi": "C",
                    },
                    "out",
                ),
            },
            local_variables=[
                "M = N + a.N + a.b.N",
                "C = a + b",
            ],
            resources=_dummy_resources(["x = M + C"]),
            children={
                "a": {
                    "name": "a",
                    "type": "dummy",
                    "children": {"b": {"name": "b", "type": "dummy"}},
                }
            },
        ),
        (
            ["N", "a.N", "a.b.N", "#in_psi.a", "#in_phi.b"],
            [
                "x = N + a.N + a.b.N + #in_psi.a + #in_phi.b",
                "#out_psi = N + a.N + a.b.N",
                "#out_phi = #in_psi.a + #in_phi.b",
            ],
        ),
    ),
    # Allow reuse of cost in subsequent costs expressions
    (
        _make_routine(
            ports={
                **_ports_from_reg_sizes({"comp_0": "b_0"}, "in"),
                **_ports_from_reg_sizes(
                    {
                        "comp_0": "b_0",
                        "anc": "b_anc",
                    },
                    "out",
                ),
            },
            local_variables=["b_anc = 1"],
            resources=_dummy_resources(
                [
                    "Q_anc = b_0",
                    "B_anc = 1",
                    "Q = Q_anc + b_0 + B_anc",
                ]
            ),
        ),
        (
            ["#in_comp_0.b_0"],
            [
                "Q_anc = #in_comp_0.b_0",
                "B_anc = 1",
                "Q = 2*#in_comp_0.b_0 + 1",
                "#out_comp_0 = #in_comp_0.b_0",
                "#out_anc = 1",
            ],
        ),
    ),
    # Special case for when an input port has a constant size
    (
        _make_routine(
            ports=_ports_from_reg_sizes(
                {
                    "0": 1,
                    "foo": "bar",
                },
                "in",
            ),
        ),
        (["#in_foo.bar"], ["#in_0 = 1"]),
    ),
]


@pytest.mark.parametrize("routine, expected_function", TO_SYMBOLIC_FUNCTION_TEST_CASES)
def test_to_symbolic_function(routine, expected_function, backend):
    expected_function = SymbolicFunction.from_str(*expected_function, backend)

    assert to_symbolic_function(routine, backend) == expected_function


@pytest.mark.parametrize(
    "routine, expected_error",
    [
        # Non-trivial expressions for input register sizes
        (
            _make_routine(
                ports={
                    **_ports_from_reg_sizes({"psi": "N", "anc": "2 * N"}, "in"),
                    **_ports_from_reg_sizes({"psi": "3 * N"}, "out"),
                }
            ),
            "Non-trivial input sizes not yet supported",
        ),
        # Redundant variable in both costs and local_params
        (
            _make_routine(
                local_variables=["x = 1"],
                resources=_dummy_resources(["z = x + 1", "x = 1"]),
            ),
            "Variable is redundantly defined in local_params and costs.",
        ),
        # Order of costs is incorrect
        (
            _make_routine(
                resources=_dummy_resources(["z = x + 1", "x = 1"]),
            ),
            "Expressions must not contain unknown variables.",
        ),
    ],
)
def test_to_symbolic_function_errors(routine, expected_error, backend):
    with pytest.raises(BartiqCompilationError, match=expected_error):
        to_symbolic_function(routine, backend)


UPDATE_ROUTINE_WITH_SYMBOLIC_FUNCTION_TEST_CASES = [
    # Null case
    (
        _make_routine(),
        ([], []),
        _make_routine(),
    ),
    # Input-only case
    (
        _make_routine(),
        (["x", "y"], []),
        _make_routine(
            input_params=["x", "y"],
        ),
    ),
    # Input-only case, but with ports
    (
        _make_routine(
            input_params=["x", "y"],
            ports=_ports_from_reg_sizes({"0": None}, "in"),
        ),
        (["x", "y", "#in_0.z"], []),
        _make_routine(
            input_params=["x", "y"],
            ports=_ports_from_reg_sizes({"0": "z"}, "in"),
        ),
    ),
    # Output-only case
    (
        _make_routine(),
        ([], ["a = 42", "b = 24"]),
        _make_routine(
            resources=_dummy_resources(["a = 42", "b = 24"]),
        ),
    ),
    # Output-only case, but with ports
    (
        _make_routine(
            ports=_ports_from_reg_sizes({"0": None}, "out"),
        ),
        ([], ["a = 42", "b = 24", "#out_0 = 101"]),
        _make_routine(
            ports=_ports_from_reg_sizes({"0": "101"}, "out"),
            resources=_dummy_resources(["a = 42", "b = 24"]),
        ),
    ),
    # Input and output case
    (
        _make_routine(),
        (["x", "y"], ["a = x + y", "b = x - y"]),
        _make_routine(
            input_params=["x", "y"],
            resources=_dummy_resources(["a = x + y", "b = x - y"]),
        ),
    ),
    # Input and output case, with ports
    (
        _make_routine(
            input_params=["x", "y"],
            ports={
                **_ports_from_reg_sizes({"0": None}, "in"),
                **_ports_from_reg_sizes({"0": None}, "out"),
            },
        ),
        (["x", "y", "#in_0.z"], ["a = x + y", "b = x - y - #in_0.z", "#out_0 = x * y * #in_0.z"]),
        _make_routine(
            input_params=["x", "y"],
            ports={
                **_ports_from_reg_sizes({"0": "z"}, "in"),
                **_ports_from_reg_sizes({"0": "x*y*z"}, "out"),
            },
            resources=_dummy_resources(["a = x + y", "b = x - y - z"]),
        ),
    ),
    # Constant input register size
    (
        _make_routine(
            ports=_ports_from_reg_sizes(
                {
                    "0": None,
                    "foo": None,
                },
                "in",
            ),
        ),
        (["#in_foo.bar"], ["#in_0 = 1"]),
        _make_routine(
            ports=_ports_from_reg_sizes(
                {
                    "0": 1,
                    "foo": "bar",
                },
                "in",
            ),
        ),
    ),
]


@pytest.mark.parametrize("routine, function, expected_routine", UPDATE_ROUTINE_WITH_SYMBOLIC_FUNCTION_TEST_CASES)
def test_update_routine_with_symbolic_function(routine, function, expected_routine, backend):
    function = SymbolicFunction.from_str(*function, backend)

    update_routine_with_symbolic_function(routine, function)
    assert routine == expected_routine

    # Check roundtrip
    assert to_symbolic_function(routine, backend) == function


@pytest.mark.parametrize(
    "routine, function, expected_error",
    [
        # Non-integer input register size
        (
            _make_routine(
                ports=_ports_from_reg_sizes({"0": None}, "in"),
            ),
            (["x"], ["#in_0 = x"]),
            "Only constant-sized input register sizes supported in function outputs",
        ),
    ],
)
def test_update_routine_with_symbolic_function_fails(routine, function, expected_error, backend):
    function = SymbolicFunction.from_str(*function, backend)
    with pytest.raises(BartiqCompilationError, match=expected_error):
        update_routine_with_symbolic_function(routine, function)
