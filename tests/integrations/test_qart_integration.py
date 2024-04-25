"""
..  Copyright © 2024 PsiQuantum Corp.  All rights reserved.
    PSIQUANTUM CORP. CONFIDENTIAL
    This file includes unpublished proprietary source code of PsiQuantum Corp.
    The copyright notice above does not evidence any actual or intended publication
    of such source code. Disclosure of this source code or any related proprietary
    information is strictly prohibited without the express written permission of
    PsiQuantum Corp.
"""

from bartiq import Routine

try:
    from bartiq.integrations import bartiq_to_qart, qart_to_bartiq

    QART_UNAVAILABLE = False
except ImportError:
    QART_UNAVAILABLE = True

import pytest
from pytest import fixture

# Note: fixture example_routine has to be synced with
# the example_schema_v1 fixture further in this module.


@fixture
def example_routine():
    return Routine(
        name="root",
        type=None,
        input_params=["N"],
        ports={
            "in_0": {"name": "in_0", "size": "N", "direction": "input"},
            "out_0": {"name": "out_0", "size": "N", "direction": "output"},
            "out_1": {"name": "out_1", "size": 3, "direction": "output"},
        },
        resources={
            "n_qubits": {
                "name": "n_qubits",
                "type": "additive",
                "value": {"value": 30, "type": "int"},
            }
        },
        children={
            "foo": {
                "name": "foo",
                "type": None,
                "input_params": ["M"],
                "ports": {
                    "in_0": {"name": "in_0", "size": "M", "direction": "input"},
                    "out_0": {"name": "out_0", "size": 3, "direction": "output"},
                },
            },
            "bar": {
                "name": "bar",
                "type": None,
                "input_params": ["N"],
                "ports": {
                    "in_0": {"name": "in_0", "size": "N", "direction": "input"},
                    "out_0": {"name": "out_0", "size": "N", "direction": "output"},
                },
            },
        },
        linked_params={"N": [("foo", "M"), ("bar", "N")]},
        connections=[
            {"source": "in_0", "target": "foo.in_0"},
            {"source": "foo.out_0", "target": "out_0"},
            {"source": "bar.out_0", "target": "out_1"},
        ],
    )


@fixture
def example_serialized_qart_v1_object():
    return {
        "version": "v1",
        "program": {
            "name": "root",
            "type": None,
            "ports": [
                {"name": "in_0", "size": "N", "direction": "input"},
                {"name": "out_0", "size": "N", "direction": "output"},
                {"name": "out_1", "size": 3, "direction": "output"},
            ],
            "resources": [{"name": "n_qubits", "type": "additive", "value": 30}],
            "input_params": ["N"],
            "children": [
                {
                    "name": "foo",
                    "type": None,
                    "input_params": ["M"],
                    "ports": [
                        {"name": "in_0", "size": "M", "direction": "input"},
                        {"name": "out_0", "size": 3, "direction": "output"},
                    ],
                },
                {
                    "name": "bar",
                    "type": None,
                    "input_params": ["N"],
                    "ports": [
                        {"name": "in_0", "size": "N", "direction": "input"},
                        {"name": "out_0", "size": "N", "direction": "output"},
                    ],
                },
            ],
            "linked_params": [{"source": "N", "targets": ["foo.M", "bar.N"]}],
            "connections": [
                {"source": "in_0", "target": "foo.in_0"},
                {"source": "foo.out_0", "target": "out_0"},
                {"source": "bar.out_0", "target": "out_1"},
            ],
        },
    }


@pytest.mark.skipif(QART_UNAVAILABLE, reason="QART is not installed")
def test_converting_routine_to_qart_v1_gives_correct_output(example_routine, example_serialized_qart_v1_object):
    assert bartiq_to_qart(example_routine).model_dump(exclude_unset=True) == example_serialized_qart_v1_object


@pytest.mark.skipif(QART_UNAVAILABLE, reason="QART is not installed")
def test_converting_qart_v1_object_to_routine_give_correct_output(example_routine, example_serialized_qart_v1_object):
    assert qart_to_bartiq(example_serialized_qart_v1_object) == example_routine


@pytest.mark.skipif(QART_UNAVAILABLE, reason="QART is not installed")
def test_conversion_from_bartiq_to_qart_raises_an_error_if_version_is_unsupported(example_routine):
    with pytest.raises(ValueError):
        bartiq_to_qart(example_routine, version="v3")
