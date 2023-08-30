import discord
from config import BOOKMARK_CHANNEL
from discord import app_commands


class Bookmark(app_commands.ContextMenu):
    def __init__(self) -> None:
        super().__init__(
            name="⭐ Bookmark",
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
            f"> _Author: {message.author.display_name}_\n"
            f"> _Added by: {interaction.user.display_name}_\n\n"
            f"{message.content}",
            files=[await attachment.to_file() for attachment in message.attachments],
        )
        await interaction.response.send_message(
            f"⭐ Added to {bookmark_channel.mention}", ephemeral=True
        )
