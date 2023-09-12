from discord import app_commands

from lib.discord_util import Interaction
from msg_components.forms.contact import FeatureRequestForm


# noinspection PyMethodMayBeStatic
class Request(app_commands.Command):
    def __init__(self) -> None:
        super().__init__(
            name="request",
            description="Request a new feature from the developer.",
            callback=self.cmd_callback,  # type: ignore
        )

    async def cmd_callback(self, interaction: Interaction) -> None:
        """Send a feature request to the developer.

        Args:
            interaction: The interaction that triggered this command.
        """
        await interaction.response.send_modal(FeatureRequestForm())
