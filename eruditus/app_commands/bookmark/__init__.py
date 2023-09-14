import discord
from discord import app_commands

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
        await bookmark_channel.send(
            f"> _Author: {message.author.display_name}_\n"
            f"> _Added by: {interaction.user.display_name}_\n\n"
            f"{message.content}",
            files=[await attachment.to_file() for attachment in message.attachments],
        )
        await interaction.response.send_message(
            f"⭐ Added to {bookmark_channel.mention}", ephemeral=True
        )
