import os

from datetime import datetime, timezone

import discord
from discord import app_commands

DEVELOPER_USER_ID = int(os.getenv("DEVELOPER_USER_ID"))
DATE_FORMAT = os.getenv("DATE_FORMAT")


class Report(app_commands.Command):
    def __init__(self) -> None:
        super().__init__(
            name="report",
            description="Report a bug to the developer.",
            callback=self.callback,
        )

    async def callback(self, interaction: discord.Interaction, bug: str) -> None:
        """Report a bug to the developer.

        Args:
            interaction: The interaction that triggered this command.
            bug: Description of the bug you encountered.
        """
        developer = await interaction.client.fetch_user(DEVELOPER_USER_ID)
        embed = (
            discord.Embed(
                title="🐛 **Bug report**",
                description=bug,
                colour=discord.Colour.dark_orange(),
            )
            .set_thumbnail(url=interaction.user.display_avatar.url)
            .set_author(name=interaction.user.display_name)
            .set_footer(
                text=datetime.now(tz=timezone.utc).strftime(DATE_FORMAT).strip()
            )
        )
        message = await developer.send(embed=embed)
        await message.pin()
        await interaction.response.send_message(
            "✅ Your bug report has been sent to the developer, thanks for your help!",
            ephemeral=True,
        )
