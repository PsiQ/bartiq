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

import numpy as np
import pandas as pd

from bartiq.visualisations import TreeMap

test_data_df = np.array(
    [
        ["child", "root", 3630.0],
        ["child", "child", 7260.0],
        ["child", "child", 10890.0],
        ["child", "child", 14520.0],
        ["child", "child", 18150.0],
    ],
    dtype=object,
)

expected_data = np.array(
    [
        ["child", "root", 3630.0],
        ["child_2", "child", 7260.0],
        ["child_3", "child_2", 10890.0],
        ["child_4", "child_3", 14520.0],
        ["child_5", "child_4", 18150.0],
    ],
    dtype=object,
)


def test_dataframe_with_unique_routine_names(monkeypatch):
    columns = ["Routine", "Parent", "Contribution"]
    df = pd.DataFrame(test_data_df, columns=columns)
    result = TreeMap.dataframe_with_unique_routine_names(df)
    assert result.columns.tolist() == columns

    result = result.to_numpy()

    assert result.shape == expected_data.shape
    for row1, row2 in zip(result, expected_data):
        assert len(row1) == len(row2)
        for entry1, entry2 in zip(row1, row2):
            assert entry1 == entry2
