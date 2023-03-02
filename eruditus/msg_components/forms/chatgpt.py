import aiohttp
from io import BytesIO

import discord

from config import OPENAI_URL, OPENAI_API_KEY, MAX_CONTENT_SIZE, OPENAI_GPT_MODEL


class ChatGPTForm(discord.ui.Modal, title="ChatGPT"):
    prompt = discord.ui.TextInput(
        label="Prompt",
        style=discord.TextStyle.long,
        placeholder="Ask ChatGPT a question...",
        required=True,
        max_length=4000,
    )

    def __init__(self, private: int, temperature: float) -> None:
        super().__init__()
        self.ephemeral = bool(private)
        self.temperature = temperature

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()

        async with aiohttp.request(
            method="post",
            url=f"{OPENAI_URL}/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json={
                "model": OPENAI_GPT_MODEL,
                "messages": [
                    {"role": "user", "content": self.prompt.value},
                ],
                "temperature": self.temperature,
                "max_tokens": 2048,
            },
        ) as response:
            if response.status != 200:
                await interaction.followup.send(
                    f"Received a {response.status} HTTP response code."
                )
                return None

            try:
                response = (await response.json())["choices"][0]["text"]
            except Exception:
                await interaction.followup.send("Something went wrong")
                return None

            message = f"> {response}"
            if len(message) > MAX_CONTENT_SIZE:
                buffer = BytesIO(message.encode())
                file = discord.File(buffer, filename="answer.txt")
                await interaction.followup.send(file=file, ephemeral=self.ephemeral)
            else:
                await interaction.followup.send(message, ephemeral=self.ephemeral)
