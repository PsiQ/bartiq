"""
..  Copyright © 2024 PsiQuantum Corp.  All rights reserved.
    PSIQUANTUM CORP. CONFIDENTIAL
    This file includes unpublished proprietary source code of PsiQuantum Corp.
    The copyright notice above does not evidence any actual or intended publication
    of such source code. Disclosure of this source code or any related proprietary
    information is strictly prohibited without the express written permission of
    PsiQuantum Corp.

Type definitions for the compilation core.
"""

from typing import Callable, Union

# Note: when we drop support for 3.9, we will be able to start
# using the Number union with isinstance checks, thus eliminating
# the need of separate NUMBER_TYPES
NUMBER_TYPES = (int, float)
Number = Union[int, float]

FunctionsMap = dict[str, Callable]
