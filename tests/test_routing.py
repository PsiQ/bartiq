"""
..  Copyright © 2022-2024 PsiQuantum Corp.  All rights reserved.
    PSIQUANTUM CORP. CONFIDENTIAL
    This file includes unpublished proprietary source code of PsiQuantum Corp.
    The copyright notice above does not evidence any actual or intended publication
    of such source code. Disclosure of this source code or any related proprietary
    information is strictly prohibited without the express written permission of
    PsiQuantum Corp.

Tests for routing module.
"""

import pytest

from bartiq._routine import Routine
from bartiq.routing import get_port_source, get_port_target, join_paths

from .utilities import routine_with_passthrough


@pytest.mark.parametrize(
    "inputs, output",
    [
        (["obj_1", "obj_2", "obj_3"], "obj_1.obj_2.obj_3"),
        (["", "obj_2", "obj_3"], "obj_2.obj_3"),
    ],
)
def test_join_paths(inputs, output):
    assert join_paths(*inputs) == output


def _simple_routine():
    return Routine(
        name="",
        input_params=["N"],
        ports={
            "in_0": {"name": "in_0", "direction": "input", "size": "N"},
            "out_0": {"name": "out_0", "direction": "output", "size": None},
        },
        children={
            "a": Routine(
                name="a",
                type=None,
                ports={
                    "in_0": {"name": "in_0", "direction": "input", "size": "N"},
                    "out_0": {"name": "out_0", "direction": "output", "size": "N"},
                },
            ),
            "b": Routine(
                name="b",
                type=None,
                ports={
                    "in_0": {"name": "in_0", "direction": "input", "size": "N"},
                    "out_0": {"name": "out_0", "direction": "output", "size": "N"},
                },
            ),
        },
        connections=[
            {"source": "in_0", "target": "a.in_0"},
            {"source": "a.out_0", "target": "b.in_0"},
            {"source": "b.out_0", "target": "out_0"},
        ],
        type=None,
    )


def _nested_routine():
    return Routine(
        name="",
        input_params=["N"],
        ports={
            "in_0": {"name": "in_0", "direction": "input", "size": "N"},
            "out_0": {"name": "out_0", "direction": "output", "size": None},
        },
        children={
            "a": Routine(
                name="a",
                type=None,
                ports={
                    "in_0": {"name": "in_0", "direction": "input", "size": "N"},
                    "out_0": {"name": "out_0", "direction": "output", "size": "N"},
                },
                children={
                    "c": Routine(
                        name="c",
                        type=None,
                        ports={
                            "in_0": {"name": "in_0", "direction": "input", "size": "N"},
                            "out_0": {"name": "out_0", "direction": "output", "size": "N"},
                        },
                    ),
                },
                connections=[
                    {"source": "in_0", "target": "c.in_0"},
                    {"source": "c.out_0", "target": "out_0"},
                ],
            ),
            "b": Routine(
                name="b",
                type=None,
                ports={
                    "in_0": {"name": "in_0", "direction": "input", "size": "N"},
                    "out_0": {"name": "out_0", "direction": "output", "size": "N"},
                },
                children={
                    "d": Routine(
                        name="d",
                        type=None,
                        ports={
                            "in_0": {"name": "in_0", "direction": "input", "size": "N"},
                            "out_0": {"name": "out_0", "direction": "output", "size": "N"},
                        },
                    ),
                },
                connections=[
                    {"source": "in_0", "target": "d.in_0"},
                    {"source": "d.out_0", "target": "out_0"},
                ],
            ),
        },
        connections=[
            {"source": "in_0", "target": "a.in_0"},
            {"source": "a.out_0", "target": "b.in_0"},
            {"source": "b.out_0", "target": "out_0"},
        ],
        type=None,
    )


@pytest.mark.parametrize(
    "parent_path, port_name, source_port_path, routine",
    [
        ("a", "in_0", "#in_0", _simple_routine()),  # Input connected to root
        ("", "out_0", "b.#out_0", _simple_routine()),  # Root output connected to a child
        ("b", "in_0", "a.#out_0", _simple_routine()),  # Input connected to another sibling
        ("", "out_0", "b.d.#out_0", _nested_routine()),  # Root output connected to a grand child
        ("a.c", "in_0", "#in_0", _nested_routine()),  # Input connected to root through parent
        (
            "b.d",
            "in_0",
            "a.c.#out_0",
            _nested_routine(),
        ),  # Input connected to other routine in the hierarchy
        (
            "c",
            "in_0",
            "a.#out_0",
            routine_with_passthrough(),
        ),  # Input connected to another sibling through a passthrough
    ],
)
def test_get_port_source(parent_path, port_name, source_port_path, routine):
    port_parent = routine.find_descendant(parent_path)
    port = port_parent.ports[port_name]
    assert get_port_source(port).absolute_path == source_port_path


@pytest.mark.parametrize(
    "parent_path, port_name, target_port_path, routine",
    [
        ("b", "out_0", "#out_0", _simple_routine()),  # Output connected to root
        ("", "in_0", "a.#in_0", _simple_routine()),  # Root output connected to a child
        ("a", "out_0", "b.#in_0", _simple_routine()),  # Output connected to another sibling
        ("", "in_0", "a.c.#in_0", _nested_routine()),  # Root input connected to a grand child
        ("b.d", "out_0", "#out_0", _nested_routine()),  # Output connected to root through parent
        (
            "a.c",
            "out_0",
            "b.d.#in_0",
            _nested_routine(),
        ),  # Output connected to other routine in the hierarchy
        (
            "a",
            "out_0",
            "#out_0",
            routine_with_passthrough(),
        ),  # Output connected to a root through a passthrough
    ],
)
def test_get_port_target(parent_path, port_name, target_port_path, routine):
    port_parent = routine.find_descendant(parent_path)
    port = port_parent.ports[port_name]
    assert get_port_target(port).absolute_path == target_port_path
