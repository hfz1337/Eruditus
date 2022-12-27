import discord
from discord import app_commands

from forms.contact import BugReportForm


class Report(app_commands.Command):
    def __init__(self) -> None:
        super().__init__(
            name="report",
            description="Report a bug to the developer.",
            callback=self.callback,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        """Report a bug to the developer.

        Args:
            interaction: The interaction that triggered this command.
        """
        await interaction.response.send_modal(BugReportForm())
