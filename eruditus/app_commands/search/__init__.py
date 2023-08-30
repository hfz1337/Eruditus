from typing import Optional

import aiohttp
import discord
from discord import app_commands

from config import WRITEUP_INDEX_API


class Search(app_commands.Command):
    def __init__(self) -> None:
        super().__init__(
            name="search",
            description="Search for a topic in the CTF write-ups index.",
            callback=self.cmd_callback,  # type: ignore
        )

    async def cmd_callback(
        self, interaction: discord.Interaction, query: str, limit: Optional[int] = 3
    ) -> None:
        """Search for a topic in the CTF write-ups index.

        Args:
            interaction: The interaction that triggered this command.
            query: The search query. Use double quotes for exact matches, and
                prepend a term with a "-" to exclude it.
            limit: Number of results to display (default: 3).
        """
        await interaction.response.defer()

        limit = limit if 0 < limit < 25 else 3
        params = {"q": query, "limit": limit}
        async with aiohttp.request(
            method="get", url=WRITEUP_INDEX_API, params=params
        ) as response:
            if response.status != 200:
                await interaction.followup.send(
                    f"Received a {response.status} HTTP response code."
                )
                return None

            writeups = (await response.json())[:limit]
            embed = discord.Embed(
                title="🕸️ CTF Write-ups Search Index",
                colour=discord.Colour.blue(),
                description=(
                    "No results found, want some cookies instead? 🍪"
                    if len(writeups) == 0
                    else f"🔍 Search results for: {query}"
                ),
            )
            for writeup in writeups:
                embed.add_field(
                    name=f"🚩 {writeup['ctf']}",
                    value="\n".join(
                        filter(
                            None,
                            [
                                "```yaml",
                                f"Search score: {writeup['score']:.2f}",
                                f"Challenge: {writeup['name']}",
                                f"Tags: {writeup['tags']}" if writeup["tags"] else "",
                                f"Author: {writeup['author']}"
                                if writeup["author"]
                                else "",
                                f"Team: {writeup['team']}",
                                "```",
                                f"{writeup['ctftime']}",
                                f"{writeup['url']}" if writeup["url"] else "",
                            ],
                        )
                    ),
                    inline=False,
                )
            await interaction.followup.send(embed=embed)
