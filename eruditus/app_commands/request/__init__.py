import discord
from discord import app_commands

from msg_components.forms.contact import FeatureRequestForm


class Request(app_commands.Command):
    def __init__(self) -> None:
        super().__init__(
            name="request",
            description="Request a new feature from the developer.",
            callback=self.callback,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        """Send a feature request to the developer.

        Args:
            interaction: The interaction that triggered this command.
        """
        await interaction.response.send_modal(FeatureRequestForm())
