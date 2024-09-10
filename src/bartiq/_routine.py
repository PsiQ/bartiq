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

# Note:
#     This module makes heavy use of Pydantic and its validation components.
#     In case the use of name "validation" is confusing, please see pydantic documentation:
#     https://docs.pydantic.dev/latest/concepts/models/ .

from __future__ import annotations

from enum import Enum


class ResourceType(str, Enum):
    """Class for representing types of resources."""

    additive = "additive"
    multiplicative = "multiplicative"
    qubits = "qubits"
    other = "other"


class PortDirection(str, Enum):
    """Class for representing port direction."""

    input = "input"
    output = "output"
    through = "through"
