"""Background task for creating Discord events from CTFtime."""

from typing import TYPE_CHECKING

from config import GUILD_ID
from discord.ext import tasks
from integrations.ctftime import create_discord_events

if TYPE_CHECKING:
    from eruditus import Eruditus


def create_event_creator_task(client: "Eruditus") -> tasks.Loop:
    """Create the event creator task.

    Args:
        client: The Discord bot client.

    Returns:
        The configured task loop.
    """

    @tasks.loop(hours=3, reconnect=True)
    async def create_upcoming_events() -> None:
        """Create a Discord Scheduled Event for each upcoming CTF competition."""
        await client.wait_until_ready()

        guild = client.get_guild(GUILD_ID)
        if not guild:
            return

        await create_discord_events(
            guild=guild,
            current_loop=create_upcoming_events.current_loop,
        )

    return create_upcoming_events
