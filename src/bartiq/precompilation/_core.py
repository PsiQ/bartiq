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

from typing import Callable, Optional

from .. import Routine
from ..symbolics.backend import SymbolicBackend
from .stages import (
    AddPassthroughPlaceholder,
    add_default_additive_resources,
    add_default_properties,
    propagate_linked_params,
    remove_non_root_container_input_register_sizes,
    unroll_wildcarded_resources,
)

PrecompilationStage = Callable[[Routine, SymbolicBackend], None]


def precompile(
    routine: Routine, backend: SymbolicBackend, precompilation_stages: Optional[list[PrecompilationStage]] = None
) -> Routine:
    """A precompilation stage that transforms a routine prior to estimate compilation.

    If no precompilation stages are specified, the following precompilation stages are performed by default (in order):
    1. Adds default resources and register sizes for the following routine types:
      - `merge`
    2. Adds additive resources to routines if there's an additive resources in any of the children.
    3. Adds "fake routines" when passthrough is detected.
    4. Removes input register sizes from non-root routines as they will be derived from the connected output ports
        in the compilation process.
    5. Replaces wildcard statements ("~") with appropriate expressions.

    Args:
        routine: A uncompiled routine.
        backend: Backend used to perform expression manipulation.
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
        add_default_additive_resources,
        AddPassthroughPlaceholder().add_passthrough_placeholders,
        remove_non_root_container_input_register_sizes,
        unroll_wildcarded_resources,
        propagate_linked_params,
    ]
