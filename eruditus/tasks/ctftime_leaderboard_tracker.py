"""Background task for tracking CTFtime leaderboard."""

from typing import TYPE_CHECKING

from config import (
    CTFTIME_LEADERBOARD_CHANNEL,
    CTFTIME_TEAM_ID,
    GUILD_ID,
    MAX_CONTENT_SIZE,
)
from constants import Emojis
from discord.ext import tasks
from integrations.ctftime import get_ctftime_leaderboard
from utils.countries import country_name

if TYPE_CHECKING:
    from eruditus import Eruditus


def create_ctftime_leaderboard_tracker(client: "Eruditus") -> tasks.Loop:
    """Create the CTFtime leaderboard tracking task.

    Args:
        client: The Discord bot client.

    Returns:
        The configured task loop.
    """

    @tasks.loop(minutes=15, reconnect=True)
    async def ctftime_leaderboard_tracking() -> None:
        """Track CTFtime leaderboard changes and post updates."""
        await client.wait_until_ready()

        if not CTFTIME_LEADERBOARD_CHANNEL:
            ctftime_leaderboard_tracking.stop()
            return

        guild = client.get_guild(GUILD_ID)
        channel = guild.get_channel(CTFTIME_LEADERBOARD_CHANNEL) if guild else None
        if not channel:
            return

        leaderboard = await get_ctftime_leaderboard(n=50)
        if not leaderboard:
            return

        first_run = False
        if not client.previous_leaderboard:
            first_run = True
            client.previous_leaderboard = leaderboard

        head = (
            f"  {Emojis.BAR_CHART} {'Rank':<10} {'Country':<53} "
            f"{'Points':<15} {'Events':<10} Name\n\n"
        )
        team_ids = list(client.previous_leaderboard.keys())
        chunks, chunk, update = [], head, False

        for index, (team_id, row) in enumerate(leaderboard.items()):
            if team_id not in client.previous_leaderboard or index < team_ids.index(
                team_id
            ):
                emoji = Emojis.UP
                update = True
            elif index == team_ids.index(team_id):
                emoji = Emojis.NEUTRAL
            else:
                emoji = Emojis.DOWN
                update = True

            diff = (
                {Emojis.UP: "+", Emojis.DOWN: "-", Emojis.NEUTRAL: "+"}[emoji]
                if team_id == CTFTIME_TEAM_ID
                else " "
            )
            country = country_name(row.country_code or "") or ""
            line = (
                f"{diff} {emoji} {row.position:>4}       {country:<45} "
                f"{row.points:>17.4f} {row.events:>12}     {row.team_name}\n"
            )
            if len(chunk) + len(line) < MAX_CONTENT_SIZE - 11:
                chunk += line
            else:
                chunks.append(chunk)
                chunk = head + line

        chunks.append(chunk)

        client.previous_leaderboard = leaderboard
        if not update and not first_run:
            return

        await channel.purge()
        for msg in chunks:
            await channel.send(f"```diff\n{msg}```", silent=True)

    return ctftime_leaderboard_tracking
