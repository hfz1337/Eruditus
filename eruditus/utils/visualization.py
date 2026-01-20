"""Visualization utilities for scoreboard plotting."""

import io
from typing import TYPE_CHECKING, Optional

import matplotlib.pyplot as plt
import numpy as np

if TYPE_CHECKING:
    from platforms.base import TeamCategoryStats, TeamScoreHistory


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


def plot_category_radar(
    teams_stats: list["TeamCategoryStats"], fig_size: tuple = (8, 8)
) -> Optional[io.BytesIO]:
    """Plot a radar/spider chart showing category solve percentage for multiple teams.

    Args:
        teams_stats: A list of TeamCategoryStats objects, each containing a team's
            category performance data. The first team with is_me=True is highlighted.
        fig_size: The figure size.

    Returns:
        A BytesIO buffer containing the saved figure data in bytes, or None if
        teams_stats is empty or has no categories.
    """
    if not teams_stats:
        return None

    # Get categories from the first team (all teams should have same categories)
    base_stats = teams_stats[0].stats
    if not base_stats:
        return None

    # Discord dark theme background
    background_color: str = "#313338"
    # Discord blurple for our team
    blurple: str = "#5865F2"
    # Orange for comparison team
    comparison_color: str = "#F0A020"

    # Pad to minimum 3 categories for proper radar shape
    from platforms.base import CategoryStats

    working_stats = list(base_stats)
    while len(working_stats) < 3:
        working_stats.append(CategoryStats(category="", total=1, solved=0))

    # Extract category data
    categories = [s.category for s in working_stats]
    totals = [s.total for s in working_stats]

    # Number of categories
    num_cats = len(categories)

    # Calculate angles for each category (evenly spaced)
    angles = np.linspace(0, 2 * np.pi, num_cats, endpoint=False).tolist()
    # Close the polygon
    angles += angles[:1]

    # Create figure with polar projection
    fig = plt.figure(figsize=fig_size, facecolor=background_color)
    ax = fig.add_subplot(111, polar=True)
    ax.set_facecolor(background_color)

    # Plot each team's solve percentage
    for team_stats in teams_stats:
        # Build solve percentage values aligned with working_stats categories
        solved_map = {s.category: s.solved for s in team_stats.stats}
        total_map = {s.category: s.total for s in team_stats.stats}

        percentages = []
        for cat, total in zip(categories, totals):
            solved = solved_map.get(cat, 0)
            cat_total = total_map.get(cat, total)
            # Calculate percentage, avoid division by zero
            pct = (solved / cat_total * 100) if cat_total > 0 else 0
            percentages.append(pct)

        percentages_closed = percentages + percentages[:1]

        # Determine color and style based on whether this is our team
        if team_stats.is_me:
            color = blurple
            alpha = 0.4
            linewidth = 2
            zorder = 10  # Bring our team to front
        else:
            color = comparison_color
            alpha = 0.2
            linewidth = 2
            zorder = 5

        ax.plot(
            angles,
            percentages_closed,
            color=color,
            linewidth=linewidth,
            label=team_stats.team_name,
            zorder=zorder,
        )
        ax.fill(angles, percentages_closed, color=color, alpha=alpha, zorder=zorder)

    # Set category labels
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, color="white", fontsize=10)

    # Scale is 0-100%
    ax.set_ylim(0, 100)
    ax.set_yticks([25, 50, 75, 100])
    ax.set_yticklabels([])

    # Style the gridlines
    ax.yaxis.grid(color="gray", linestyle="dashed", alpha=0.5)
    ax.xaxis.grid(color="gray", linestyle="dashed", alpha=0.5)

    # Add legend
    ax.legend(loc="upper right", bbox_to_anchor=(1.2, 1.1), facecolor=background_color)
    legend = ax.get_legend()
    for text in legend.get_texts():
        text.set_color("white")

    # Add title
    ax.set_title(
        "Category Performance", fontdict={"weight": "bold", "color": "white"}, pad=20
    )

    # Save the result and close the figure object
    result = io.BytesIO()
    fig.savefig(result, bbox_inches="tight", facecolor=background_color)
    plt.close(fig)

    # Reset buffer position and return it
    result.seek(0)
    return result
