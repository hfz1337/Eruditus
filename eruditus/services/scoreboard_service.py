"""Service for scoreboard-related business logic."""

from datetime import datetime
from typing import Optional

import aiohttp
import discord
from config import MAX_CONTENT_SIZE, TEAM_NAME
from constants import ErrorMessages
from platforms import PlatformCTX, match_platform
from utils.visualization import plot_scoreboard


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

        scoreboard_channel = discord.utils.get(
            guild.text_channels, id=ctf["guild_channels"]["scoreboard"]
        )
        await self.update_scoreboard(scoreboard_channel, message, graph)
        await followup(message, ephemeral=False, file=graph)

    async def update_scoreboard(
        self,
        scoreboard_channel: discord.TextChannel,
        message: str,
        graph: Optional[discord.File] = None,
    ) -> None:
        """Update scoreboard in the scoreboard channel.

        Args:
            scoreboard_channel: The Discord scoreboard channel.
            message: The scoreboard message.
            graph: The score graph to send as an attachment.
        """
        async for last_message in scoreboard_channel.history(limit=1):
            kwargs = {"attachments": [graph]} if graph else {}
            await last_message.edit(content=message, **kwargs)
            break
        else:
            kwargs = {"file": graph} if graph else {}
            await scoreboard_channel.send(message, **kwargs)

        if graph:
            graph.fp.seek(0)
