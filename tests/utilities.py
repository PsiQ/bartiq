"""
..  Copyright © 2022-2024 PsiQuantum Corp.  All rights reserved.
    PSIQUANTUM CORP. CONFIDENTIAL
    This file includes unpublished proprietary source code of PsiQuantum Corp.
    The copyright notice above does not evidence any actual or intended publication
    of such source code. Disclosure of this source code or any related proprietary
    information is strictly prohibited without the express written permission of
    PsiQuantum Corp.

Utilities for compilation tests.
"""

from bartiq._routine import Routine


def routine_with_passthrough(a_out_size="N"):
    """Routine with a passthrough, used for testing."""
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
                    "out_0": {"name": "out_0", "direction": "output", "size": f"{a_out_size}"},
                },
            ),
            "b": Routine(
                name="b",
                type=None,
                ports={
                    "in_0": {"name": "in_0", "direction": "input", "size": None},
                    "out_0": {"name": "out_0", "direction": "output", "size": None},
                },
                connections=[{"source": "in_0", "target": "out_0"}],
            ),
            "c": Routine(
                name="c",
                type=None,
                ports={
                    "in_0": {"name": "in_0", "direction": "input", "size": None},
                    "out_0": {"name": "out_0", "direction": "output", "size": None},
                },
                connections=[{"source": "in_0", "target": "out_0"}],
            ),
        },
        connections=[
            {"source": "in_0", "target": "a.in_0"},
            {"source": "a.out_0", "target": "b.in_0"},
            {"source": "b.out_0", "target": "c.in_0"},
            {"source": "c.out_0", "target": "out_0"},
        ],
        type=None,
    )


def routine_with_two_passthroughs():
    """Routine with a two passthroughs, used for testing."""
    return Routine(
        name="",
        type=None,
        input_params=["N"],
        ports={
            "in_0": {"name": "in_0", "direction": "input", "size": "N"},
            "in_1": {"name": "in_1", "direction": "input", "size": "M"},
            "out_0": {"name": "out_0", "direction": "output", "size": None},
            "out_1": {"name": "out_1", "direction": "output", "size": None},
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
            "c": Routine(
                name="c",
                type=None,
                ports={
                    "in_0": {"name": "in_0", "direction": "input", "size": None},
                    "in_1": {"name": "in_1", "direction": "input", "size": None},
                    "out_0": {"name": "out_0", "direction": "output", "size": None},
                    "out_1": {"name": "out_1", "direction": "output", "size": None},
                },
                connections=[
                    {"source": "in_0", "target": "out_0"},
                    {"source": "in_1", "target": "out_1"},
                ],
            ),
        },
        connections=[
            {"source": "in_0", "target": "a.in_0"},
            {"source": "in_1", "target": "b.in_0"},
            {"source": "a.out_0", "target": "c.in_0"},
            {"source": "b.out_0", "target": "c.in_1"},
            {"source": "c.out_0", "target": "out_0"},
            {"source": "c.out_1", "target": "out_1"},
        ],
    )
