import discord
from config import BOOKMARK_CHANNEL
from constants import Emojis
from discord import HTTPException, app_commands
from utils.responses import send_response


class Bookmark(app_commands.ContextMenu):
    def __init__(self) -> None:
        super().__init__(
            name=f"{Emojis.STAR} Bookmark",
            callback=self.context_callback,
        )

    async def context_callback(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        """Bookmark a message.

        Args:
            interaction: The interaction that triggered this command.
            message: The message to bookmark.
        """
        if not BOOKMARK_CHANNEL:
            await send_response(
                interaction, f"{Emojis.ERROR} Bookmark channel is not configured."
            )
            return

        bookmark_channel = interaction.guild.get_channel(BOOKMARK_CHANNEL)
        if bookmark_channel is None:
            await send_response(
                interaction, f"{Emojis.ERROR} Bookmark channel not found."
            )
            return

        try:
            await message.forward(destination=bookmark_channel)
            await send_response(
                interaction, f"{Emojis.STAR} Added to {bookmark_channel.mention}"
            )
        except HTTPException:
            await send_response(
                interaction,
                f"{Emojis.ERROR} Failed to bookmark the message, was it deleted?",
            )
