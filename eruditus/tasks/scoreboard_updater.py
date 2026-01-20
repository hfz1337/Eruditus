"""Background task for updating scoreboards."""

from typing import TYPE_CHECKING

from config import GUILD_ID
from db.ctf_repository import CTFRepository
from discord.ext import tasks
from services.scoreboard_service import ScoreboardService

_ctf_repo = CTFRepository()

if TYPE_CHECKING:
    from eruditus import Eruditus


def create_scoreboard_updater(client: "Eruditus") -> tasks.Loop:
    """Create the scoreboard updater task.

    Args:
        client: The Discord bot client.

    Returns:
        The configured task loop.
    """
    scoreboard_service = ScoreboardService()

    @tasks.loop(minutes=1, reconnect=True)
    async def scoreboard_updater() -> None:
        """Periodically update the scoreboard for all running CTFs."""
        await client.wait_until_ready()

        guild = client.get_guild(GUILD_ID)
        if not guild:
            return

        for ctf in _ctf_repo.find_not_ended():
            await scoreboard_service.send_scoreboard(ctf, guild=guild)

    return scoreboard_updater
