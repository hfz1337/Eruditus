from typing import Optional

import discord
from discord import app_commands

from forms.chatgpt import ChatGPTForm

from lib.types import PromptPrivacy


class ChatGPT(app_commands.Command):
    def __init__(self) -> None:
        super().__init__(
            name="chatgpt",
            description="Ask ChatGPT a question.",
            callback=self.callback,
        )

    async def callback(
        self,
        interaction: discord.Interaction,
        privacy: Optional[PromptPrivacy] = PromptPrivacy.public,
    ) -> None:
        """Ask ChatGPT a question.

        Args:
            interaction: The interaction that triggered this command.
            privacy: Set the prompt's privacy (defaults to public).
        """
        await interaction.response.send_modal(ChatGPTForm(private=privacy.value))
