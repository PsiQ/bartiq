"""
..  Copyright © 2023-2024 PsiQuantum Corp.  All rights reserved.
    PSIQUANTUM CORP. CONFIDENTIAL
    This file includes unpublished proprietary source code of PsiQuantum Corp.
    The copyright notice above does not evidence any actual or intended publication
    of such source code. Disclosure of this source code or any related proprietary
    information is strictly prohibited without the express written permission of
    PsiQuantum Corp.

Functions for the precompilation stage of estimate compilation.
"""

# flake8: noqa
from typing import Any, Callable, Optional

from .. import Routine
from ..symbolics.backend import SymbolicBackend
from .stages import (
    AddPassthroughPlaceholder,
    add_default_additive_costs,
    add_default_properties,
    remove_non_root_container_input_register_sizes,
    unroll_wildcarded_costs,
)

PrecompilationStage = Callable[[Routine, SymbolicBackend], Routine]


def precompile(routine: Routine, backend, precompilation_stages: Optional[list[PrecompilationStage]] = None) -> Routine:
    """A precompilation stage that transforms a routine prior to estimate compilation.

    If no precompilation stages are specified, the following precompilation stages are performed by default (in order):
    1. Adds default costs and register sizes for the following routine types:
      - `merge`
    2. Adds additive costs to routines if there's an additive cost in any of the children.
    3. Adds "fake routines" when passthrough is detected.
    4. Removes input register sizes from non-root routines as they will be derived from the connected output ports
        in the compilation process.
    5. Replaces wildcard statements ("~") with appropriate expressions.

    Args:
        routine: A uncompiled routine.
        precompilation_stages: A list of functions that modify routine and all it's sub-routines in place.
    """
    # Define the transforms to apply to each routine
    if precompilation_stages is None:
        precompilation_stages = default_precompilation_stages()

    # Apply precompilation transforms
    for subroutine in routine.walk():
        for precompilation_function in precompilation_stages:
            precompilation_function(subroutine, backend)
    return routine


def default_precompilation_stages():
    """Default suite of precompilation stages."""
    return [
        add_default_properties,
        add_default_additive_costs,
        AddPassthroughPlaceholder().add_passthrough_placeholders,
        remove_non_root_container_input_register_sizes,
        unroll_wildcarded_costs,
    ]
