"""
..  Copyright © 2022-2024 PsiQuantum Corp.  All rights reserved.
    PSIQUANTUM CORP. CONFIDENTIAL
    This file includes unpublished proprietary source code of PsiQuantum Corp.
    The copyright notice above does not evidence any actual or intended publication
    of such source code. Disclosure of this source code or any related proprietary
    information is strictly prohibited without the express written permission of
    PsiQuantum Corp.

Precompilation logic.
"""

from ._core import default_precompilation_stages, precompile
from .stages import (
    AddPassthroughPlaceholder,
    add_default_additive_costs,
    add_default_properties,
    remove_non_root_container_input_register_sizes,
    unroll_wildcarded_costs,
)

__all__ = [
    "precompile",
    "default_precompilation_stages",
    "remove_non_root_container_input_register_sizes",
    "add_default_properties",
    "add_default_additive_costs",
    "unroll_wildcarded_costs",
    "AddPassthroughPlaceholder",
]
