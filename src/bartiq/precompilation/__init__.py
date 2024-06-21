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

from ._core import default_precompilation_stages, precompile
from .stages import (
    AddPassthroughPlaceholder,
    add_default_additive_resources,
    add_default_properties,
    remove_non_root_container_input_register_sizes,
    unroll_wildcarded_resources,
)

__all__ = [
    "precompile",
    "default_precompilation_stages",
    "remove_non_root_container_input_register_sizes",
    "add_default_properties",
    "add_default_additive_resources",
    "unroll_wildcarded_resources",
    "AddPassthroughPlaceholder",
]
