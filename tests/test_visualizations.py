# Copyright 2025 PsiQuantum, Corp.
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
import pytest
from qref import SchemaV1

from bartiq import Routine, compile_routine
from bartiq.symbolics.sympy_backend import SympyBackend
from bartiq.visualizations import TreeMap, _dataframe_with_unique_routine_names


def test_tree_map_input_non_routine_raises():
    with pytest.raises(ValueError, match="Routine should be of type Routine or CompiledRoutine"):
        TreeMap(0.4)


def test_tree_map_invalid_routine_raises():
    input_schema = SchemaV1(
        program={
            "name": "root",
            "resources": [
                {"name": "success_rate", "type": "multiplicative", "value": "success"},
            ],
        },
        version="v1",
    )

    backend = SympyBackend()
    routine_from_qref = Routine.from_qref(input_schema, backend=backend)
    c_routine = compile_routine(routine_from_qref).routine
    with pytest.raises(ValueError, match="only accepts numeric routines"):
        TreeMap(c_routine)


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


def test_dataframe_with_unique_routine_names():
    columns = ["Routine", "Parent", "Contribution"]
    df = pd.DataFrame(test_data_df, columns=columns)
    result = _dataframe_with_unique_routine_names(df)
    assert result.columns.tolist() == columns

    result = result.to_numpy()

    assert result.shape == expected_data.shape
    for row1, row2 in zip(result, expected_data):
        assert len(row1) == len(row2)
        for entry1, entry2 in zip(row1, row2):
            assert entry1 == entry2


def test_get_dataframe():
    input_schema = SchemaV1(
        program={
            "name": "root",
            "children": [
                {
                    "name": "child1",
                    "children": [
                        {
                            "name": "child3",
                            "resources": [
                                {"name": "success_rate", "type": "multiplicative", "value": 7260.0},
                            ],
                        },
                    ],
                    "resources": [
                        {"name": "success_rate", "type": "multiplicative", "value": 3630.0},
                    ],
                },
                {
                    "name": "child2",
                    "resources": [
                        {"name": "success_rate", "type": "multiplicative", "value": 2320.0},
                    ],
                },
            ],
        },
        version="v1",
    )

    expected_data = np.array(
        [
            ["child1", "root", 3630.0],
            ["child3", "child1", 7260.0],
            ["child2", "root", 2320.0],
        ],
        dtype=object,
    )

    backend = SympyBackend()
    routine_from_qref = Routine.from_qref(input_schema, backend=backend)
    c_routine = compile_routine(routine_from_qref).routine

    columns = ["Routine", "Parent", "Contribution"]
    tree_map = TreeMap(c_routine)
    result = tree_map.get_dataframe("success_rate")
    assert result.columns.tolist() == columns

    result = result.to_numpy()

    assert result.shape == expected_data.shape
    for row1, row2 in zip(result, expected_data):
        assert len(row1) == len(row2)
        for entry1, entry2 in zip(row1, row2):
            assert entry1 == entry2


def test_plot_output_type():
    from plotly.graph_objs._figure import Figure

    input_schema = SchemaV1(
        program={
            "name": "root",
            "resources": [
                {"name": "success_rate", "type": "multiplicative", "value": 2320.0},
            ],
        },
        version="v1",
    )

    backend = SympyBackend()
    routine_from_qref = Routine.from_qref(input_schema, backend=backend)
    c_routine = compile_routine(routine_from_qref).routine

    tree_map = TreeMap(c_routine)
    result = tree_map.plot("success_rate")

    assert isinstance(result, Figure)


def test_plot_invalid_resource_raises():
    input_schema = SchemaV1(
        program={
            "name": "root",
            "resources": [
                {"name": "success_rate", "type": "multiplicative", "value": 30.0},
            ],
        },
        version="v1",
    )

    backend = SympyBackend()
    routine_from_qref = Routine.from_qref(input_schema, backend=backend)
    c_routine = compile_routine(routine_from_qref).routine
    tree_map = TreeMap(c_routine)
    with pytest.raises(ValueError, match="Resource to be plotted should be in the valid resources"):
        tree_map.plot("non_existent_resource")
