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
from typing import Callable, Dict, Union

# Note: when we drop support for 3.9, we will be able to start
# using the Number union with isinstance checks, thus eliminating
# the need of separate NUMBER_TYPES
NUMBER_TYPES = (int, float)
Number = Union[int, float]

# Define mathematical constants
Math_constants: Dict[str, float] = {
    "pi": math.pi,
    "e": math.e,
}

# Define mathematical functions
Math_functions: Dict[str, Callable[[float], float]] = {
    "sin": lambda x: math.sin(math.radians(x)),
    "cos": lambda x: math.cos(math.radians(x)),
    "tan": lambda x: math.tan(math.radians(x)),
    "asin": lambda x: math.degrees(math.asin(x)),
    "acos": lambda x: math.degrees(math.acos(x)),
    "atan": lambda x: math.degrees(math.atan(x)),
    "log": math.log,
    "log10": math.log10,
    "ln": math.log,
    "sqrt": math.sqrt,
    "exp": math.exp,
}

FunctionsMap = dict[str, Callable]
