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

from typing import Callable, Union

# Note: when we drop support for 3.9, we will be able to start
# using the Number union with isinstance checks, thus eliminating
# the need of separate NUMBER_TYPES
NUMBER_TYPES = (int, float)
Number = Union[int, float]

FunctionsMap = dict[str, Callable]
