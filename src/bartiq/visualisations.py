from __future__ import annotations

from numbers import Number
from typing import Literal

import pandas as pd
import plotly.express as px
from plotly.graph_objs._figure import Figure as PlotlyFig

from bartiq import CompiledRoutine, Resource


class TreeMap:
    """Plot treemaps for different resources given a numeric compiled routine.

    Args:
        routine: The routine to generate treemaps for.

    Raises:
        ValueError: If any resource in the top level routine has a non-numeric value.
    """

    COLUMNS = ["Routine", "Parent", "Contribution"]

    def __init__(self, routine: CompiledRoutine):
        self.routine = routine
        if any(not isinstance(x.value, Number) for x in self.routine.resources.values()):
            raise ValueError(f"{self.__class__.__name__} only accepts numeric routines.")

        self.valid_resources = set([resource_name for resource_name in self.routine.resources.keys()])

    def get_dataframe(self, resource: str, scale_to: Literal["parent", "root"] | Number = 1) -> pd.DataFrame:
        """Get the dataframe defining the treemap for a given resource in the routine.

        Args:
            resource: Resource type to isolate.
            scale_to: Optional input to rescale the values. Accepts a numeric value or string literal `parent`,
            which will scale each resource count as a fraction of its parents. Defaults to 1, which is no scaling.

        Returns:
            pd.DataFrame
        """
        df = pd.DataFrame([], columns=self.COLUMNS)
        output_from_parent = _get_descendant_contributions(
            self.routine, resource, scale_to=self.routine.resources[resource].value if scale_to == "root" else scale_to
        )

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

    @classmethod
    def dataframe_with_unique_routine_names(cls, df):
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

        routine_col = cls.COLUMNS[0]
        parent_col = cls.COLUMNS[1]

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

    def plot(self, resource: str, scale_to: Literal["parent"] | Number = 1) -> PlotlyFig:
        """Plot the treemap. This function returns a plotly `Figure` object, and calling
        .show() on the output will display the plot.

        Args:
            resource: Resource type to isolate.
            scale_to: Optional input to rescale the values. Accepts a numeric value or string literal `parent`,
            which will scale each resource count as a fraction of its parents. Defaults to 1, which is no scaling.

        Returns:
            PlotlyFig
        """
        data_frame = self.get_dataframe(resource=resource, scale_to=scale_to)
        routine_col = self.COLUMNS[0]

        # plotly may not render treemap without unique ID (routine) labels -
        # create new dataframe with unique routine names if needed
        if data_frame[routine_col].duplicated().any():
            data_frame = self.dataframe_with_unique_routine_names(data_frame)

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


def _get_child_contributions(routine: CompiledRoutine, resource: str, scale_to: str | int = 1) -> Contributions:
    return {
        child_routine.name: x
        for child_routine in routine.children.values()
        if (
            x := child_routine.resources.get(resource, Resource(name=resource, type=None, value=0)).value
            / (routine.resources[resource].value if scale_to == "parent" else scale_to)
        )
    }


NestedContributions = tuple[Contributions, dict[str, Contributions]]


def _get_descendant_contributions(
    routine: CompiledRoutine, resource: str, scale_to: str | int = 1
) -> NestedContributions:
    direct_children_contributions = _get_child_contributions(routine=routine, resource=resource, scale_to=scale_to)
    grandchildren = {
        child: _get_descendant_contributions(routine=routine.children[child], resource=resource, scale_to=scale_to)
        for child in direct_children_contributions
    }
    return (direct_children_contributions, grandchildren)
