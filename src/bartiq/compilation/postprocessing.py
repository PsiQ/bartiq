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

from typing import Any, Callable

from .._routine import CompiledRoutine
from ..symbolics.backend import SymbolicBackend, T
from ..transform import add_aggregated_resources

PostprocessingStage = Callable[[CompiledRoutine[T], SymbolicBackend[T]], CompiledRoutine[T]]

DEFAULT_POSTPROCESSING_STAGES: list[PostprocessingStage] = []


def aggregate_resources(
    aggregation_dict: dict[str, dict[str, Any]], remove_decomposed: bool = True
) -> PostprocessingStage[T]:
    """Returns a postprocessing stage which aggregates resources using `add_aggregated_resources` method.

    This function is just a wrapper around `add_aggregated_resources` method from `bartiq.transform.
    For more details how it works, please see its documentation.

    Args
        aggregation_dict: A dictionary that decomposes resources into more fundamental components along with their
        respective multipliers.
        remove_decomposed : Whether to remove the decomposed resources from the routine.
            Defaults to True.

    """

    def _inner(routine: CompiledRoutine[T], backend: SymbolicBackend[T]) -> CompiledRoutine[T]:
        return add_aggregated_resources(routine, aggregation_dict, remove_decomposed, backend)

    return _inner
