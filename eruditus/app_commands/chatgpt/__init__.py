from typing import Optional

import discord
from discord import app_commands

from lib.types import PromptPrivacy
from msg_components.forms.chatgpt import ChatGPTForm


class ChatGPT(app_commands.Command):
    def __init__(self) -> None:
        super().__init__(
            name="chatgpt",
            description="Ask ChatGPT a question.",
            callback=self.cmd_callback,  # type: ignore
        )

    async def cmd_callback(
        self,
        interaction: discord.Interaction,
        privacy: Optional[PromptPrivacy] = PromptPrivacy.public,
        temperature: Optional[float] = 0.9,
    ) -> None:
        """Ask ChatGPT a question.

        Args:
            interaction: The interaction that triggered this command.
            privacy: Set the prompt's privacy (defaults to public).
            temperature: Defaults to 0.9, use lower values for applications with a
                well-defined answer (e.g., 0).
        """
        await interaction.response.send_modal(
            ChatGPTForm(private=privacy.value, temperature=temperature)  # type: ignore
        )
