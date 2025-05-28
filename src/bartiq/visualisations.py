from __future__ import annotations
from typing import Literal
import pandas as pd
import plotly.express as px
from plotly.graph_objs._figure import Figure as PlotlyFig
from numbers import Number

from bartiq import CompiledRoutine, Resource


class TreeMap:
    """Plot treemaps for different resources given a numeric compiled routine.

    Args:
        routine: The routine to generate treemaps for.

    Raises:
        ValueError: If any resource in the top level routine has a non-numeric value.
    """

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
        COLUMNS = ["Routine", "Parent", "Contribution"]

        df = pd.DataFrame([], columns=COLUMNS)
        output_from_parent = _get_descendant_contributions(
            self.routine, resource, scale_to=self.routine.resources[resource].value if scale_to == "root" else scale_to
        )

        def _update_dataframe_recursive(
            output_from_parent: NestedContributions, parent: str, df: pd.DataFrame
        ) -> pd.DataFrame:
            direct_children_contributions, grandchildren_contributions = output_from_parent
            for child, contrib in direct_children_contributions.items():
                if df.empty:
                    df = pd.DataFrame([[child, parent, contrib]], columns=COLUMNS)
                else:
                    df = pd.concat(
                        [
                            df,
                            pd.DataFrame([[child, parent, contrib]], columns=COLUMNS),
                        ],
                        ignore_index=True,
                    )
                if child in grandchildren_contributions:
                    df = _update_dataframe_recursive(grandchildren_contributions[child], parent=child, df=df)
            return df

        return _update_dataframe_recursive(output_from_parent, self.routine.name, df)

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
        fig = px.treemap(
            self.get_dataframe(resource=resource, scale_to=scale_to),
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
