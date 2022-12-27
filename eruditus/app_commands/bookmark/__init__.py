import discord
from discord import app_commands

from config import BOOKMARK_CHANNEL


class Bookmark(app_commands.ContextMenu):
    def __init__(self) -> None:
        super().__init__(
            name="Bookmark",
            callback=self.callback,
        )

    async def callback(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        """Bookmark a message.

        Args:
            interaction: The interaction that triggered this command.
            message: The message to bookmark.
        """
        bookmark_channel = interaction.guild.get_channel(BOOKMARK_CHANNEL)
        await bookmark_channel.send(
            f"{message.content}\n\n⭐ Added by {interaction.user.mention}"
        )
        await interaction.response.send_message("⭐ Added to bookmarks", ephemeral=True)
