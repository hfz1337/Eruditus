import openai
import logging
import textwrap
from config import MONGO, DBNAME, OPENAI_COLLECTION, OPENAI_API_KEY, OPENAI_LANGUAGE_MODEL
from discord import Interaction, app_commands

_log = logging.getLogger(__name__)


class OpenAI(app_commands.Command):

    client = openai.AsyncClient(api_key=OPENAI_API_KEY)
    max_body_size = 2000

    def __init__(self) -> None:
        super().__init__(
            name="openai",
            description="Start chatting with OpenAI.",
            callback=self.cmd_callback,
        )

    def get_previous_messages(self, user: str) -> list:
        return MONGO[DBNAME][OPENAI_COLLECTION].find({"user": user}).sort({"_id": -1}).limit(2)

    def insert_message(self, user: str, message: str, response: str) -> None:
        MONGO[DBNAME][OPENAI_COLLECTION].insert_one(
            dict([("user", user), ("message", message), ("response", response)]))

    async def cmd_callback(self, interaction: Interaction, message: str) -> None:
        """Send a message to OpenAI

        Args:
            interaction: The interaction that triggered this command.
            message: The message to send to openai.
        """

        await interaction.response.defer()

        try:
            user = str(interaction.user)

            previous_messages = self.get_previous_messages(
                user=user)

            messages = [
                dict(
                    [
                        ("role", "system"),
                        ("content", "You are a Discord bot that helps CTF players solve CTF challenges during a CTF competition in challenges including forensics, cryptography, web exploitation, reverse engineering, binary exploitation.")
                    ]
                )
            ]

            for previous_message in previous_messages:
                messages.append(
                    dict([("role", "user"), ("content", previous_message["message"])]))
                messages.append(
                    dict([("role", "assistant"), ("content", previous_message["response"])]))

            messages.append(
                dict([("role", "assistant"), ("content", message)]))

            chat_completion = await self.client.chat.completions.create(
                user=user,
                # frequency_penalty=0.6,
                # temperature=0,
                model=OPENAI_LANGUAGE_MODEL,
                messages=messages,
                # max_tokens=1500,
            )

            response = chat_completion.choices[0].message.content

            self.insert_message(user=user,
                                message=message, response=response)

            if len(response) <= self.max_body_size:
                await interaction.followup.send(response)
            else:
                wrapped_response = textwrap.wrap(
                    text=response, width=self.max_body_size)
                for r in wrapped_response:
                    await interaction.followup.send(r)
        except Exception as e:
            _log.exception(msg=e)
            await interaction.followup.send("The request was unsuccessful :confused:")
