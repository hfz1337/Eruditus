import discord
from constants import Emojis, ErrorMessages
from db.ctf_repository import CTFRepository
from discord import app_commands
from utils.responses import send_error, send_response

_ctf_repo = CTFRepository()


class TakeNote(app_commands.ContextMenu):
    def __init__(self) -> None:
        super().__init__(
            name=f"{Emojis.CLIPBOARD} Take note",
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
        ctf = _ctf_repo.get_ctf_info(guild_category=interaction.channel.category_id)
        if ctf is None:
            await send_error(interaction, ErrorMessages.NOT_IN_CTF_CHANNEL)
            return

        notes_channel = discord.utils.get(
            interaction.guild.text_channels, id=ctf["guild_channels"]["notes"]
        )
        await notes_channel.send(
            f"> _Author: {message.author.display_name}_\n"
            f"> _Added by: {interaction.user.display_name}_\n\n"
            f"{message.content}",
            files=[await attachment.to_file() for attachment in message.attachments],
        )
        await send_response(
            interaction, f"{Emojis.CLIPBOARD} Added to {notes_channel.mention}"
        )
