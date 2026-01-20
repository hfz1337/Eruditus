from datetime import datetime

import discord
from config import DEVELOPER_USER_ID
from constants import EmbedColours, Emojis
from utils.responses import send_response


class FeatureRequestForm(discord.ui.Modal, title="Contact form"):
    feature_request = discord.ui.TextInput(
        label="Feature request",
        style=discord.TextStyle.long,
        placeholder="Describe the feature you want to suggest...",
        required=True,
        max_length=1000,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        developer = await interaction.client.fetch_user(DEVELOPER_USER_ID)
        embed = (
            discord.Embed(
                title=f"{Emojis.LIGHTBULB} **Feature request**",
                description=self.feature_request.value,
                colour=EmbedColours.GREEN,
                timestamp=datetime.now(),
            )
            .set_thumbnail(url=interaction.user.display_avatar.url)
            .set_author(name=interaction.user.display_name)
        )
        message = await developer.send(embed=embed)
        await message.pin()
        await send_response(
            interaction,
            f"{Emojis.SUCCESS} Your suggestion has been sent to the developer, "
            "thank you!",
        )


class BugReportForm(discord.ui.Modal, title="Contact form"):
    bug_report = discord.ui.TextInput(
        label="Bug report",
        style=discord.TextStyle.long,
        placeholder="Describe the bug you encountered...",
        required=True,
        max_length=1000,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        developer = await interaction.client.fetch_user(DEVELOPER_USER_ID)
        embed = (
            discord.Embed(
                title=f"{Emojis.BUG} **Bug report**",
                description=self.bug_report.value,
                colour=EmbedColours.WARNING,
                timestamp=datetime.now(),
            )
            .set_thumbnail(url=interaction.user.display_avatar.url)
            .set_author(name=interaction.user.display_name)
        )
        message = await developer.send(embed=embed)
        await message.pin()
        await send_response(
            interaction,
            f"{Emojis.SUCCESS} Your bug report has been sent to the developer, "
            "thank you!",
        )
