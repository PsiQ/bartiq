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

import math
import os

import pytest
from qref import SchemaV1
from qref.schema_v1 import ResourceV1, RoutineV1

from bartiq import compile_routine, evaluate
from bartiq.compilation import CompilationFlags
from bartiq.errors import BartiqCompilationError


def _routine_with_repetition(repetition_dict: dict) -> RoutineV1:
    return SchemaV1(
        program={
            "name": "root",
            "input_params": ["unit_prob", "unit_T"],
            "children": [
                {
                    "name": "child",
                    "resources": [
                        {"name": "T", "type": "additive", "value": "unit_T"},
                        {"name": "success_rate", "type": "multiplicative", "value": "unit_prob"},
                    ],
                }
            ],
            "repetition": repetition_dict,
        },
        version="v1",
    )


def _constant_sequence_sum(unit_cost, count, multiplier):
    sum = 0
    for _ in range(count):
        sum += unit_cost * multiplier
    return sum


def _constant_sequence_prod(unit_cost, count, multiplier):
    prod = 1
    for _ in range(count):
        prod *= unit_cost**multiplier
    return prod


@pytest.mark.parametrize("unit_cost", [(1, 1), (7, 0.9)])
@pytest.mark.parametrize("count", [1, 5, 10, 17])
@pytest.mark.parametrize("multiplier", [1, 2, 5])
def test_constant_sequence_is_correct(unit_cost, count, multiplier):
    unit_T, unit_prob = unit_cost
    routine = _routine_with_repetition({"count": count, "sequence": {"type": "constant", "multiplier": multiplier}})

    compiled_routine = compile_routine(routine).routine
    assignments = {"unit_T": unit_T, "unit_prob": unit_prob}
    evaluated_routine = evaluate(compiled_routine, assignments).routine

    numeric_sum = _constant_sequence_sum(unit_T, count, multiplier)
    numeric_prod = _constant_sequence_prod(unit_prob, count, multiplier)
    assert evaluated_routine.resources["T"].value == numeric_sum
    pytest.approx(numeric_prod, evaluated_routine.resources["success_rate"].value)


def _arithmetic_sequence_sum(unit_cost, count, initial_term, difference):
    current_cost = initial_term * unit_cost
    sum = current_cost
    for _ in range(count - 1):
        current_cost += difference * unit_cost
        sum += current_cost
    return sum


def _arithmetic_sequence_prod(unit_cost, count, initial_term, difference):
    current_cost = initial_term * unit_cost
    prod = current_cost
    for _ in range(count - 1):
        current_cost += difference * unit_cost
        prod *= current_cost
    return prod


@pytest.mark.parametrize("unit_cost", [(1, 1), (7, 0.9)])
@pytest.mark.parametrize("count", [1, 5, 10, 17])
@pytest.mark.parametrize("initial_term", [0, 1, 2, 5])
@pytest.mark.parametrize("difference", [1, 2, 5])
def test_arithmetic_sequence_is_correct(unit_cost, count, initial_term, difference):
    unit_T, unit_prob = unit_cost
    routine = _routine_with_repetition(
        {"count": count, "sequence": {"type": "arithmetic", "initial_term": initial_term, "difference": difference}}
    )

    compiled_routine = compile_routine(routine).routine
    assignments = {"unit_T": unit_T, "unit_prob": unit_prob}
    evaluated_routine = evaluate(compiled_routine, assignments).routine

    numeric_sum = _arithmetic_sequence_sum(unit_T, count, initial_term, difference)
    numeric_prod = _arithmetic_sequence_prod(unit_prob, count, initial_term, difference)
    assert evaluated_routine.resources["T"].value == numeric_sum
    pytest.approx(numeric_prod, evaluated_routine.resources["success_rate"].value)


def _geometric_sequence_sum(unit_cost, count, ratio):
    current_cost = unit_cost
    sum = current_cost
    for _ in range(count - 1):
        current_cost *= ratio
        sum += current_cost
    return sum


def _geometric_sequence_prod(unit_cost, count, ratio):
    current_cost = unit_cost
    prod = current_cost
    for _ in range(count - 1):
        current_cost += ratio * unit_cost
        prod *= current_cost
    return prod


@pytest.mark.parametrize("unit_cost", [(1, 1), (7, 0.9)])
@pytest.mark.parametrize("count", [1, 4, 9])
@pytest.mark.parametrize("ratio", [2, 3])
def test_geometric_sequence_is_correct(unit_cost, count, ratio):
    unit_T, unit_prob = unit_cost
    routine = _routine_with_repetition({"count": count, "sequence": {"type": "geometric", "ratio": ratio}})

    compiled_routine = compile_routine(routine).routine
    assignments = {"unit_T": unit_T, "unit_prob": unit_prob}
    evaluated_routine = evaluate(compiled_routine, assignments).routine

    numeric_sum = _geometric_sequence_sum(unit_T, count, ratio)
    numeric_prod = _geometric_sequence_prod(unit_prob, count, ratio)
    assert evaluated_routine.resources["T"].value == numeric_sum
    pytest.approx(numeric_prod, evaluated_routine.resources["success_rate"].value)


def _closed_form_sum(unit_cost, count):
    return unit_cost * (math.ceil(math.log2(count)) + count**2 - (count) * (count - 1))


def _closed_form_prod(unit_cost, count):
    return unit_cost**count * (math.ceil(math.log2(count)) + count**2 - (count) * (count - 1))


@pytest.mark.parametrize("unit_cost", [(1, 1), (7, 0.9)])
@pytest.mark.parametrize("count", [1, 4, 9])
def test_closed_form_sequence_is_correct(unit_cost, count):
    unit_T, unit_prob = unit_cost
    sum = "ceiling(log2(N)) + N**2 - N*(N-1)"
    prod = "ceiling(log2(N)) + N**2 - N*(N-1)"
    num_terms = "N"
    routine = _routine_with_repetition(
        {"count": count, "sequence": {"type": "closed_form", "sum": sum, "prod": prod, "num_terms_symbol": num_terms}}
    )

    compiled_routine = compile_routine(routine).routine
    assignments = {"unit_T": unit_T, "unit_prob": unit_prob}
    evaluated_routine = evaluate(compiled_routine, assignments).routine

    numeric_sum = _closed_form_sum(unit_T, count)
    numeric_prod = _closed_form_prod(unit_prob, count)
    assert evaluated_routine.resources["T"].value == numeric_sum
    pytest.approx(numeric_prod, evaluated_routine.resources["success_rate"].value)


def _term_expression(i):
    return i**2 - 2 * i + 7 + math.ceil(math.log2((i + 1) * 5))


def _custom_sum(unit_cost, count):
    return sum([_term_expression(i) * unit_cost for i in range(count)])


def _custom_prod(unit_cost, count):
    prod = 1
    for i in range(count):
        prod *= _term_expression(i) * unit_cost
    return prod


@pytest.mark.parametrize("unit_cost", [(1, 1), (7, 0.9)])
@pytest.mark.parametrize("count", [1, 4, 9])
def test_custom_sequence_is_correct(unit_cost, count):
    unit_T, unit_prob = unit_cost
    term_expression = "i**2 - 2*i + 7 + ceiling(log2((i+1)*5))"
    routine = _routine_with_repetition(
        {
            "count": count,
            "sequence": {"type": "custom", "term_expression": term_expression, "iterator_symbol": "i"},
        }
    )

    compiled_routine = compile_routine(routine).routine
    assignments = {"unit_T": unit_T, "unit_prob": unit_prob}
    evaluated_routine = evaluate(compiled_routine, assignments).routine

    numeric_sum = _custom_sum(unit_T, count)
    numeric_prod = _custom_prod(unit_prob, count)
    assert evaluated_routine.resources["T"].value == numeric_sum
    pytest.approx(numeric_prod, evaluated_routine.resources["success_rate"].value)


@pytest.mark.parametrize("sum_none,prod_none", ((True, True), (False, True), (True, False), (False, False)))
def test_closed_form_sequence_works_when_sum_and_prod_unspecified(sum_none, prod_none):
    repetition_dict = {
        "count": 10,
        "sequence": {
            "type": "closed_form",
            "sum": None if sum_none else "ceiling(log2(N)) + N**2 - N*(N-1)",
            "prod": None if prod_none else "ceiling(log2(N)) + N**2 - N*(N-1)",
            "num_terms_symbol": "N",
        },
    }

    routine = _routine_with_repetition(repetition_dict)

    valid_resources = []
    invalid_resources = []
    if not sum_none:
        valid_resources.append({"name": "T", "type": "additive", "value": "unit_T"})
    else:
        invalid_resources.append({"name": "T", "type": "additive", "value": "unit_T"})
    if not prod_none:
        valid_resources.append({"name": "success_rate", "type": "multiplicative", "value": "unit_prob"})
    else:
        invalid_resources.append({"name": "success_rate", "type": "multiplicative", "value": "unit_prob"})

    # Valid case (i.e. additive/multiplicative resources undefined when sum/prod undefined):
    routine.program.children[0].resources = valid_resources

    compiled_routine = compile_routine(routine).routine
    assignments = {"unit_T": 5, "unit_prob": 0.99}
    _ = evaluate(compiled_routine, assignments).routine

    # Invalid case (i.e. additive/multiplicative resources defined when sum/prod undefined):
    routine.program.children[0].resources = invalid_resources
    # Exception won't trigger if there are no resources.
    if len(invalid_resources) != 0:
        with pytest.raises(BartiqCompilationError):
            compiled_routine = compile_routine(routine).routine


@pytest.mark.parametrize("compilation_flags", [None, CompilationFlags.EXPAND_RESOURCES])
def test_custom_sequence_throws_error_when_replacing_iterator_symbol_on_evaluate_side(backend, compilation_flags):
    term_expression = "i**2 - 2*i + 7 + ceiling(log2((i+1)*5))"
    routine = _routine_with_repetition(
        {
            "count": 10,
            "sequence": {"type": "custom", "term_expression": term_expression, "iterator_symbol": "i"},
        }
    )

    assignments = {"i": "j"}
    compiled_routine = compile_routine(routine, compilation_flags=compilation_flags).routine
    with pytest.raises(BartiqCompilationError, match=r"Tried to replace symbol that's used as iterator symbol*"):
        evaluate(compiled_routine, assignments).routine


# At present, the default method of compilation (with transitive resources) does not raise an error
# when attempting to compile a routine where a resource value has the same symbol as an iterator symbol.
# This is because the resource hierarchy is not compiled fully,
# and so the parameter map during the compile sequence does not contain child information.


def test_custom_sequence_throws_error_when_replacing_iterator_symbol_on_compile_side(backend):
    term_expression = "i**2 - 2*i + 7 + ceiling(log2((i+1)*5))"
    routine = _routine_with_repetition(
        {
            "count": 10,
            "sequence": {"type": "custom", "term_expression": term_expression, "iterator_symbol": "i"},
        }
    )

    routine.program.children[0].resources[0].value = "i"
    with pytest.raises(BartiqCompilationError, match=r"Tried to replace symbol that's used as iterator symbol*"):
        compile_routine(routine, compilation_flags=CompilationFlags.EXPAND_RESOURCES)


@pytest.mark.parametrize(
    "repetition_dict",
    (
        {"count": "N", "sequence": {"type": "constant", "multiplier": 3}},
        {"count": "N", "sequence": {"type": "arithmetic", "initial_term": 1, "difference": 3}},
        {"count": "N", "sequence": {"type": "geometric", "ratio": "x"}},
        {
            "count": 10,
            "sequence": {
                "type": "closed_form",
                "sum": "ceiling(log2(N)) + N**2 - N*(N-1)",
                "prod": "ceiling(log2(N)) + N**2 - N*(N-1)",
                "num_terms_symbol": "N",
            },
        },
        {
            "count": "N",
            "sequence": {
                "type": "custom",
                "term_expression": "i**2 - 2*i + 7 + ceiling(log2((i+1)*5))",
                "iterator_symbol": "i",
            },
        },
    ),
)
def test_repetition_serializes_to_qref(repetition_dict):
    routine = _routine_with_repetition(repetition_dict)
    compilation_result = compile_routine(routine)
    compilation_result.to_qref()


def test_raises_exception_when_invalid_resource_types():
    routine = _routine_with_repetition({"count": 5, "sequence": {"type": "constant"}})
    other_resource = ResourceV1(name="other_resource", type="other", value=5)
    routine.program.children[0].resources.append(other_resource)

    with pytest.raises(BartiqCompilationError):
        _ = compile_routine(routine)


@pytest.fixture
def set_repetition_env():
    old_env = os.getenv("BARTIQ_REPETITION_ALLOW_ARBITRARY_RESOURCES")
    os.environ["BARTIQ_REPETITION_ALLOW_ARBITRARY_RESOURCES"] = "True"
    yield
    if old_env is not None:
        os.environ["BARTIQ_REPETITION_ALLOW_ARBITRARY_RESOURCES"] = old_env


@pytest.mark.usefixtures("set_repetition_env")
def test_raises_warning_when_invalid_resource_types_and_env_set():
    routine = _routine_with_repetition({"count": 5, "sequence": {"type": "constant"}})
    other_resource = ResourceV1(name="other_resource", type="other", value=5)
    routine.program.children[0].resources.append(other_resource)

    with pytest.warns(match=r"Can't process resource*"):
        compiled_routine = compile_routine(routine, compilation_flags=CompilationFlags.EXPAND_RESOURCES).routine
        assert compiled_routine.resources["other_resource"].value == 5
        assert compiled_routine.resources["other_resource"].type == "other"


def test_error_raised_when_mismatch_between_parent_and_child_resources_and_skipping_verification():
    routine = _routine_with_repetition({"count": 5, "sequence": {"type": "constant"}})
    routine.program.resources.append(ResourceV1(name="other_resource", type="additive", value=5))
    with pytest.raises(
        BartiqCompilationError, match="Routine with repetition does not share the same resources as its child*"
    ):
        compile_routine(routine, compilation_flags=CompilationFlags.SKIP_VERIFICATION)


def test_error_raised_when_mismatch_between_parent_and_child_resource_names_and_skipping_verification():
    routine = _routine_with_repetition({"count": 5, "sequence": {"type": "constant"}})
    ResourceV1(name="other_resource", type="additive", value=5)
    routine.program.resources.append(ResourceV1(name="T", type="additive", value=5))
    with pytest.raises(
        BartiqCompilationError,
        match="Routine with repetition should have resource names like `child_name.resource_name.*",
    ):
        compile_routine(routine, compilation_flags=CompilationFlags.SKIP_VERIFICATION)
