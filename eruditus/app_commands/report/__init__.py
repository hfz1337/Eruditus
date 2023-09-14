from discord import Interaction, app_commands

from msg_components.forms.contact import BugReportForm


class Report(app_commands.Command):
    def __init__(self) -> None:
        super().__init__(
            name="report",
            description="Report a bug to the developer.",
            callback=self.cmd_callback,  # type: ignore
        )

    async def cmd_callback(self, interaction: Interaction) -> None:
        """Report a bug to the developer.

        Args:
            interaction: The interaction that triggered this command.
        """
        await interaction.response.send_modal(BugReportForm())
