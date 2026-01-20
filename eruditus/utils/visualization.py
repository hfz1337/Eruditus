"""Visualization utilities for scoreboard plotting."""

import io
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt

if TYPE_CHECKING:
    from platforms.base import TeamScoreHistory


def plot_scoreboard(
    data: list["TeamScoreHistory"], fig_size: tuple = (15, 6)
) -> io.BytesIO:
    """Plot scoreboard.

    Args:
        data: A list where each element is a struct containing:
            - The team name (used as the label in the graph).
            - The timestamps of each solve (as datetime objects, these will fill the
                x-axis).
            - The number of points at each instant (these will fill the y-axis).
        fig_size: The figure size.

    Returns:
        A BytesIO buffer containing the saved figure data in bytes.
    """
    # We use an actual color instead of transparent background for visibility
    # in both light and dark themes.
    background_color: str = "#313338"

    # Create a new figure.
    fig: plt.Figure = plt.figure(
        figsize=fig_size, facecolor=background_color, layout="tight"
    )

    # Apply background color to the axes.
    axes = fig.subplots()
    for axe in [axes] if not isinstance(axes, list) else axes:
        axe.set_facecolor(background_color)

    # Obtain current axes and set the figure title.
    gca: plt.Subplot = fig.gca()
    gca.set_title(
        label=f"Top {len(data)} Teams", fontdict={"weight": "bold", "color": "white"}
    )

    for team in data:
        kw = {}
        if team.is_me:
            kw["zorder"] = len(data) + 1  # Bring our team to the front

        # Create a new plot item with the X axis set to time and the Y axis set to
        # score.
        gca.plot(
            [x.time for x in team.history],
            [x.score for x in team.history],
            label=team.name,
            **kw,
        )

    # Apply grid and legend style.
    gca.grid(color="gray", linestyle="dashed", alpha=0.5)
    gca.legend(loc="best")

    # Apply x tick labels styles.
    for label in gca.get_xticklabels(minor=False):
        label.set(rotation=45, color="white")

    # Apply y tick labels style.
    for label in gca.get_yticklabels(minor=False):
        label.set(color="white")

    # Apply spine colors.
    for highlighted_spine in ["bottom", "left"]:
        gca.spines[highlighted_spine].set_color("white")

    # Make the top/right spines invisible.
    for invisible_spine in ["top", "right"]:
        gca.spines[invisible_spine].set_visible(False)

    # Save the result and close the figure object.
    result = io.BytesIO()
    fig.savefig(result, bbox_inches="tight")
    plt.close(fig)

    # Reset buffer position and return it.
    result.seek(0)
    return result
