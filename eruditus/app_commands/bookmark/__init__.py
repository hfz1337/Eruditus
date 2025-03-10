import discord
from discord import HTTPException, app_commands

from config import BOOKMARK_CHANNEL


class Bookmark(app_commands.ContextMenu):
    def __init__(self) -> None:
        super().__init__(
            name="⭐ Bookmark",
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
        bookmark_channel = interaction.guild.get_channel(BOOKMARK_CHANNEL)
        try:
            await message.forward(destination=bookmark_channel)
            status = f"⭐ Added to {bookmark_channel.mention}"
        except HTTPException:
            status = "❌ Failed to bookmark the message, was it deleted?"
        finally:
            await interaction.response.send_message(status, ephemeral=True)
