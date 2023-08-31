from datetime import datetime

import discord

from config import DEVELOPER_USER_ID


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
                title="💡 **Feature request**",
                description=self.feature_request.value,
                colour=discord.Colour.green(),
                timestamp=datetime.now(),
            )
            .set_thumbnail(url=interaction.user.display_avatar.url)
            .set_author(name=interaction.user.display_name)
        )
        message = await developer.send(embed=embed)
        await message.pin()
        await interaction.response.send_message(
            "✅ Your suggestion has been sent to the developer, thank you!",
            ephemeral=True,
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
                title="🐛 **Bug report**",
                description=self.bug_report.value,
                colour=discord.Colour.dark_orange(),
                timestamp=datetime.now(),
            )
            .set_thumbnail(url=interaction.user.display_avatar.url)
            .set_author(name=interaction.user.display_name)
        )
        message = await developer.send(embed=embed)
        await message.pin()
        await interaction.response.send_message(
            "✅ Your bug report has been sent to the developer, thank you!",
            ephemeral=True,
        )
