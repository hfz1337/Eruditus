import discord
from discord import app_commands

from lib.util import get_ctf_info


class TakeNote(app_commands.ContextMenu):
    def __init__(self) -> None:
        super().__init__(
            name="📝 Take note",
            callback=self.context_callback,
        )

    async def context_callback(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        """Copy a message into the current CTF's note channel.

        Args:
            interaction: The interaction that triggered this command.
            message: The message to copy.
        """
        ctf = get_ctf_info(guild_category=interaction.channel.category_id)
        if ctf is None:
            await interaction.response.send_message(
                "This command can only be used from within a CTF channel.",
                ephemeral=True,
            )
            return None

        notes_channel = discord.utils.get(
            interaction.guild.text_channels, id=ctf["guild_channels"]["notes"]
        )
        await notes_channel.send(
            f"> _Author: {message.author.display_name}_\n"
            f"> _Added by: {interaction.user.display_name}_\n\n"
            f"{message.content}",
            files=[await attachment.to_file() for attachment in message.attachments],
        )
        await interaction.response.send_message(
            f"📝 Added to {notes_channel.mention}", ephemeral=True
        )
