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
"""Functions and classes for visualizing the data contained in routines."""

from __future__ import annotations

from numbers import Number
from typing import Union

import pandas as pd
import plotly.express as px
from plotly.graph_objs._figure import Figure as PlotlyFig

from bartiq import CompiledRoutine, Resource, Routine
from bartiq.compilation import compile_routine


class TreeMap:
    """Plot treemaps for different resources given a numeric compiled routine.

    The input should be a ``Routine`` or a ``CompiledRoutine`` object. If the
    routine was not compiled before, then instantiating this class will compile
    it.

    Args:
        routine: The routine to generate treemaps for.

    Raises:
        ValueError: If any resource in the top level routine has a non-numeric value.
    """

    COLUMNS = ["Routine", "Parent", "Contribution"]

    def __init__(self, routine: Union[CompiledRoutine, Routine]):
        if not isinstance(routine, (CompiledRoutine, Routine)):
            raise ValueError(
                f"Routine should be of type Routine or CompiledRoutine, received object with type {type(routine)}."
            )

        if isinstance(routine, Routine):
            routine = compile_routine(routine).routine

        if not routine.is_numeric():
            raise ValueError(f"{self.__class__.__name__} only accepts numeric routines.")

        self.routine = routine
        self.valid_resources = set([resource_name for resource_name in self.routine.resources.keys()])

    def get_dataframe(self, resource: str) -> pd.DataFrame:
        """Get the dataframe defining the treemap for a given resource in the routine.

        Args:
            resource: Resource type to isolate.

        Returns:
            pd.DataFrame
        """
        df = pd.DataFrame([], columns=self.COLUMNS)
        output_from_parent = _get_descendant_contributions(self.routine, resource)

        def _update_dataframe_recursive(
            output_from_parent: NestedContributions, parent: str, df: pd.DataFrame
        ) -> pd.DataFrame:
            direct_children_contributions, grandchildren_contributions = output_from_parent
            for child, contrib in direct_children_contributions.items():
                if df.empty:
                    df = pd.DataFrame([[child, parent, contrib]], columns=self.COLUMNS)
                else:
                    df = pd.concat(
                        [
                            df,
                            pd.DataFrame([[child, parent, contrib]], columns=self.COLUMNS),
                        ],
                        ignore_index=True,
                    )
                if child in grandchildren_contributions:
                    df = _update_dataframe_recursive(grandchildren_contributions[child], parent=child, df=df)
            return df

        return _update_dataframe_recursive(output_from_parent, self.routine.name, df)

    def plot(self, resource: str) -> PlotlyFig:
        """Plot the treemap. This function returns a plotly `Figure` object, and calling
        .show() on the output will display the plot.

        Args:
            resource: Resource type to isolate.

        Returns:
            PlotlyFig
        """
        data_frame = self.get_dataframe(resource=resource)
        routine_col = self.COLUMNS[0]

        # plotly may not render treemap without unique ID (routine) labels -
        # create new dataframe with unique routine names if needed
        if data_frame[routine_col].duplicated().any():
            data_frame = _dataframe_with_unique_routine_names(data_frame)

        fig = px.treemap(
            data_frame,
            names="Routine",
            values="Contribution",
            parents="Parent",
            color="Contribution",
            color_continuous_scale="reds",
            title=f"{resource}",
        )

        fig.update_traces(root_color="lightgrey")
        fig.update_layout(margin=dict(t=50, l=25, r=25, b=25), autosize=True, font=dict(size=15))

        return fig


######################################################


Contributions = dict[str, Number]


def _get_child_contributions(routine: CompiledRoutine, resource: str) -> Contributions:
    return {
        child_routine.name: x
        for child_routine in routine.children.values()
        if (
            x := child_routine.resources.get(resource, Resource(name=resource, type=None, value=0)).value
            / (routine.resources[resource].value)
        )
    }


NestedContributions = tuple[Contributions, dict[str, Contributions]]


def _get_descendant_contributions(routine: CompiledRoutine, resource: str) -> NestedContributions:
    direct_children_contributions = _get_child_contributions(routine=routine, resource=resource)
    grandchildren = {
        child: _get_descendant_contributions(routine=routine.children[child], resource=resource)
        for child in direct_children_contributions
    }
    return (direct_children_contributions, grandchildren)


def _dataframe_with_unique_routine_names(df):
    """Get the dataframe with unique routine names ready to be plotted.

    Certain routine names may appear more than once in a
    ``CompiledRoutine``. These are not easily handled by ``plotly`` because
    it cannot work out redundant routine names as well as parent-child
    relations for redundant names.

    This method applies a renaming based on the input dataframe such that
    each new definition of a routine whose name already exists is renamed.
    The new name is the original routine name folowed by an underscore
    separator and a numerical counter.

    Note: this method assumes that the data in the dataframe are ordered.
    This is used to determine new parent data. Specficially, each time a
    routine is defined with a certain name, any following row in the
    dataframe that contains this routine as its parent will (of course) be
    mapped to that particular routine as a child. Due to the renaming
    described above, the parent entry of new row is also renamed to the
    latest unique name that was created based on an input routine name.

    For example: assume that "routine1" has been defined and "routine1" is
    redefined once again. This method will rename the new routine to
    "routine1_2" and any subsequent rows marking "routine1" as a parent
    will also be changed such that they mark "routine1_2" as a parent.

    Args:
        df: Input dataframe that (likely) contains redundancies in the
            routine names.

    Returns:
        pd.DataFrame
    """
    routine_name_counter: dict[str, int] = {}
    old_name_to_latest_unique_name: dict[str, str] = {}
    result = []

    routine_col = TreeMap.COLUMNS[0]
    parent_col = TreeMap.COLUMNS[1]

    for _, row in df.iterrows():
        routine = row[routine_col]
        parent = row[parent_col]

        # Handle routine name uniqueness
        count = routine_name_counter.get(routine, 0) + 1
        routine_name_counter[routine] = count
        unique_routine_name = f"{routine}_{count}" if count > 1 else routine

        # Update parent to latest known mapping
        unique_parent = old_name_to_latest_unique_name.get(parent, parent)
        old_name_to_latest_unique_name[routine] = unique_routine_name

        result.append({**row, routine_col: unique_routine_name, parent_col: unique_parent})

    return pd.DataFrame(result)
