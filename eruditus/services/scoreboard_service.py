"""Service for scoreboard-related business logic."""

import logging
from collections import defaultdict
from datetime import datetime
from typing import Optional

import aiohttp
import discord
from config import MAX_CONTENT_SIZE, TEAM_NAME
from constants import ErrorMessages
from platforms import PlatformCTX, match_platform
from platforms.base import CategoryStats, Challenge, Team, TeamCategoryStats
from utils.visualization import plot_category_radar, plot_scoreboard

_log = logging.getLogger(__name__)


class ScoreboardService:
    """Service for managing CTF scoreboards."""

    async def send_scoreboard(
        self,
        ctf: dict,
        interaction: Optional[discord.Interaction] = None,
        guild: Optional[discord.Guild] = None,
    ) -> None:
        """Send or update the scoreboard in the scoreboard channel.

        Args:
            ctf: The CTF document.
            interaction: The Discord interaction (optional).
            guild: The Discord guild object (optional).

        Raises:
            AssertionError: if both guild and interaction are not provided.
        """
        assert interaction or guild
        guild = guild or interaction.guild

        async def followup(content: str, ephemeral=True, **kwargs) -> None:
            if not interaction:
                return
            await interaction.followup.send(content, ephemeral=ephemeral, **kwargs)

        if ctf["credentials"]["url"] is None:
            await followup(ErrorMessages.NO_CREDENTIALS)
            return

        ctx = PlatformCTX.from_credentials(ctf["credentials"])
        platform = await match_platform(ctx)
        if not platform:
            await followup("Invalid URL set for this CTF, or platform isn't supported.")
            return

        try:
            teams = [x async for x in platform.impl.pull_scoreboard(ctx)]
        except aiohttp.InvalidURL:
            await followup("Invalid URL set for this CTF.")
            return
        except aiohttp.ClientError:
            await followup(
                "Could not communicate with the CTF platform, please try again."
            )
            return

        if not teams:
            await followup("Failed to fetch the scoreboard.")
            return

        me = await platform.impl.get_me(ctx)
        our_team_name = me.name if me is not None else TEAM_NAME

        name_field_width = max(len(team.name) for team in teams) + 10
        message = (
            f"**Scoreboard as of "
            f"<t:{datetime.now().timestamp():.0f}>**"
            "```diff\n"
            f"  {'Rank':<10}{'Team':<{name_field_width}}{'Score'}\n"
            "{}"
            "```"
        )
        scoreboard = ""
        for rank, team in enumerate(teams, start=1):
            line = (
                f"{['-', '+'][team.name == our_team_name]} "
                f"{rank:<10}{team.name:<{name_field_width}}"
                f"{round(team.score or 0, 4)}\n"
            )
            if len(message) + len(scoreboard) + len(line) - 2 > MAX_CONTENT_SIZE:
                break
            scoreboard += line

        if scoreboard:
            message = message.format(scoreboard)
        else:
            message = "No solves yet, or platform isn't supported."

        graph_data = await platform.impl.pull_scoreboard_datapoints(ctx)
        graph = (
            None
            if graph_data is None
            else discord.File(plot_scoreboard(graph_data), filename="scoreboard.png")
        )

        # Generate category radar chart with comparison team
        radar = await self._generate_category_radar(ctx, platform, teams)

        scoreboard_channel = discord.utils.get(
            guild.text_channels, id=ctf["guild_channels"]["scoreboard"]
        )
        await self.update_scoreboard(scoreboard_channel, message, graph, radar)

        # Send followup messages separately for full-size display
        if graph:
            await followup(message, ephemeral=False, file=graph)
            graph.fp.seek(0)
        else:
            await followup(message, ephemeral=False)

        if radar:
            await followup("", ephemeral=False, file=radar)
            radar.fp.seek(0)

    async def _generate_category_radar(
        self, ctx: PlatformCTX, platform, teams: list[Team]
    ) -> Optional[discord.File]:
        """Generate category performance radar chart comparing teams.

        Args:
            ctx: The platform context.
            platform: The matched platform.
            teams: List of teams from the scoreboard.

        Returns:
            A discord.File containing the radar chart, or None if generation fails.
        """
        try:
            # Get our team info
            me = await platform.impl.get_me(ctx)
            our_team_name = me.name if me is not None else TEAM_NAME

            # Find our rank and determine comparison team
            our_rank = None
            for rank, team in enumerate(teams, start=1):
                if team.name == our_team_name:
                    our_rank = rank
                    break

            # Determine comparison team: #1 if we're not #1, #2 if we are #1
            comparison_team: Optional[Team] = None
            if our_rank == 1 and len(teams) > 1:
                comparison_team = teams[1]  # #2 team
            elif our_rank != 1 and len(teams) > 0:
                comparison_team = teams[0]  # #1 team

            # Pull all challenges and build category map
            challenges: list[Challenge] = []
            category_totals: dict[str, int] = defaultdict(int)
            our_category_solved: dict[str, int] = defaultdict(int)

            async for challenge in platform.impl.pull_challenges(ctx):
                challenges.append(challenge)
                category = challenge.category or "Uncategorized"
                category_totals[category] += 1
                if challenge.solved_by_me:
                    our_category_solved[category] += 1

            if not category_totals:
                return None

            # Build our team's stats
            sorted_categories = sorted(category_totals.keys())
            our_stats = [
                CategoryStats(
                    category=cat,
                    total=category_totals[cat],
                    solved=our_category_solved.get(cat, 0),
                )
                for cat in sorted_categories
            ]

            teams_stats: list[TeamCategoryStats] = [
                TeamCategoryStats(
                    team_name=our_team_name,
                    is_me=True,
                    stats=our_stats,
                )
            ]

            # Build comparison team's stats if available
            if comparison_team:
                comp_category_solved: dict[str, int] = defaultdict(int)

                # Check each challenge's solvers for the comparison team
                for challenge in challenges:
                    category = challenge.category or "Uncategorized"
                    try:
                        async for solver in platform.impl.pull_challenge_solvers(
                            ctx, challenge.id, limit=0  # 0 = no limit
                        ):
                            # Match by ID or name (names may have slight differences)
                            if (
                                solver.team.id == comparison_team.id
                                or solver.team.name == comparison_team.name
                            ):
                                comp_category_solved[category] += 1
                                break
                    except Exception as e:
                        _log.debug(
                            "Error checking solvers for challenge %s: %s",
                            challenge.id,
                            e,
                        )

                comp_stats = [
                    CategoryStats(
                        category=cat,
                        total=category_totals[cat],
                        solved=comp_category_solved.get(cat, 0),
                    )
                    for cat in sorted_categories
                ]

                teams_stats.append(
                    TeamCategoryStats(
                        team_name=comparison_team.name,
                        is_me=False,
                        stats=comp_stats,
                    )
                )

            chart_buffer = plot_category_radar(teams_stats)
            if chart_buffer is None:
                return None

            return discord.File(chart_buffer, filename="category_radar.png")

        except aiohttp.ClientError as e:
            _log.warning("Failed to generate category radar: %s", e)
            return None
        except Exception as e:
            _log.error("Unexpected error generating category radar: %s", e)
            return None

    async def update_scoreboard(
        self,
        scoreboard_channel: discord.TextChannel,
        message: str,
        graph: Optional[discord.File] = None,
        radar: Optional[discord.File] = None,
    ) -> None:
        """Update scoreboard in the scoreboard channel.

        Sends images as separate messages for full-size display on Discord.

        Args:
            scoreboard_channel: The Discord scoreboard channel.
            message: The scoreboard message.
            graph: The score graph to send as an attachment.
            radar: The category radar chart to send as an attachment.
        """
        # Clear previous messages (up to 3: text, graph, radar)
        await scoreboard_channel.purge(limit=3)

        # Send scoreboard text with graph (silent to avoid notifications)
        if graph:
            await scoreboard_channel.send(message, file=graph, silent=True)
            graph.fp.seek(0)
        else:
            await scoreboard_channel.send(message, silent=True)

        # Send radar chart separately for full-size display
        if radar:
            await scoreboard_channel.send(file=radar, silent=True)
            radar.fp.seek(0)
