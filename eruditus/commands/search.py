from typing import Optional

import aiohttp
import discord
from config import WRITEUP_INDEX_API
from constants import EmbedColours, Emojis
from discord import app_commands
from utils.responses import send_response


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

        if not WRITEUP_INDEX_API:
            await send_response(
                interaction,
                f"{Emojis.ERROR} Write-up search index is not configured.",
            )
            return

        limit = limit if 0 < limit < 25 else 3
        params = {"q": query, "limit": limit}

        try:
            async with aiohttp.request(
                method="get",
                url=WRITEUP_INDEX_API,
                params=params,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status != 200:
                    await send_response(
                        interaction,
                        f"{Emojis.ERROR} Received HTTP {response.status} from the API.",
                    )
                    return

                writeups = (await response.json())[:limit]
        except aiohttp.ClientError as e:
            await send_response(
                interaction,
                f"{Emojis.ERROR} Failed to reach the write-up search API: "
                f"{type(e).__name__}",
            )
            return

        embed = discord.Embed(
            title=f"{Emojis.WEB} CTF Write-ups Search Index",
            colour=EmbedColours.INFO,
            description=(
                f"No results found, want some cookies instead? {Emojis.COOKIE}"
                if len(writeups) == 0
                else f"{Emojis.SEARCH} Search results for: {query}"
            ),
        )
        for writeup in writeups:
            embed.add_field(
                name=f"{Emojis.FLAG} {writeup['ctf']}",
                value="\n".join(
                    filter(
                        None,
                        [
                            "```yaml",
                            f"Search score: {writeup['score']:.2f}",
                            f"Challenge: {writeup['name']}",
                            f"Tags: {writeup['tags']}" if writeup["tags"] else "",
                            (
                                f"Author: {writeup['author']}"
                                if writeup["author"]
                                else ""
                            ),
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
