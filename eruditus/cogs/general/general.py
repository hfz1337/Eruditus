from importlib import import_module
from datetime import datetime
import os

import discord
from discord.ext import commands
from discord.ext.commands import Bot

from discord_slash import SlashContext, cog_ext
from discord_slash.utils.manage_commands import create_option

import aiohttp
import pymongo

from cogs.general.help import cog_help

from config import (
    MONGODB_URI,
    DBNAME_PREFIX,
    CONFIG_COLLECTION,
    MINIMUM_PLAYER_COUNT,
    VOTING_STARTS_COUNTDOWN,
    VOTING_VERDICT_COUNTDOWN,
    DATE_FORMAT,
    DEVELOPER_USER_ID,
    WRITEUP_INDEX_API,
)

# MongoDB handle
mongo = pymongo.MongoClient(MONGODB_URI)


class General(commands.Cog):
    """This cog contains general commands."""

    def __init__(self, bot: Bot, extensions: list) -> None:
        self._bot = bot
        self._bot_extensions = extensions

    @cog_ext.cog_slash(
        name=cog_help["commands"]["help"]["name"],
        description=cog_help["commands"]["help"]["description"],
        options=[
            create_option(**option)
            for option in cog_help["commands"]["help"]["options"]
        ],
    )
    async def _help(self, ctx: SlashContext) -> None:
        """Show help about the bot usage."""
        embed = (
            discord.Embed(
                title="Eruditus - CTF helper bot",
                url="https://github.com/hfz1337/Eruditus",
                description=(
                    "Eruditus is dedicated to CTF teams who communicate via Discord "
                    "during CTF competitions."
                ),
                colour=discord.Colour.blue(),
            )
            .set_thumbnail(url=self._bot.user.avatar_url)
            .set_footer(
                text=(
                    "“I never desire to converse with a man who has written more than "
                    "he has read.”\n"
                    "― Samuel Johnson, Johnsonian Miscellanies - Vol II"
                )
            )
        )

        for extension in self._bot_extensions:
            if "commands" in self._bot_extensions[extension]:
                for command in self._bot_extensions[extension]["commands"]:
                    embed.add_field(
                        name=f"/{command}",
                        value=self._bot_extensions[extension]["commands"][command][
                            "description"
                        ],
                        inline=False,
                    )
            else:
                embed.add_field(
                    name=f"/{extension}",
                    value=self._bot_extensions[extension]["description"],
                    inline=False,
                )
        await ctx.send(embed=embed)

    @commands.has_permissions(manage_channels=True)
    @commands.guild_only()
    @cog_ext.cog_slash(
        name=cog_help["commands"]["config"]["name"],
        description=cog_help["commands"]["config"]["description"],
        options=[
            create_option(**option)
            for option in cog_help["commands"]["config"]["options"]
        ],
    )
    async def _config(
        self,
        ctx: SlashContext,
        minimum_player_count: int = None,
        voting_starts_countdown: int = None,
        voting_verdict_countdown: int = None,
    ) -> None:
        """Change the guild's configuration."""
        # Get guild config from the database
        config = mongo[f"{DBNAME_PREFIX}-{ctx.guild.id}"][CONFIG_COLLECTION].find_one()

        if (
            minimum_player_count is None
            and voting_starts_countdown is None
            and voting_verdict_countdown is None
        ):
            current_configuration = "\n".join(
                f"{var}: {config[var]}"
                for var in [
                    "minimum_player_count",
                    "voting_starts_countdown",
                    "voting_verdict_countdown",
                ]
            )
            await ctx.send(
                f"⚙️ Current configuration\n```yaml\n{current_configuration}\n```"
            )
            return

        minimum_player_count = minimum_player_count or MINIMUM_PLAYER_COUNT
        voting_starts_countdown = voting_starts_countdown or VOTING_STARTS_COUNTDOWN
        voting_verdict_countdown = voting_verdict_countdown or VOTING_VERDICT_COUNTDOWN

        mongo[f"{DBNAME_PREFIX}-{ctx.guild.id}"][CONFIG_COLLECTION].update_one(
            {"_id": config["_id"]},
            {
                "$set": {
                    "minimum_player_count": minimum_player_count,
                    "voting_starts_countdown": voting_starts_countdown,
                    "voting_verdict_countdown": voting_verdict_countdown,
                }
            },
        )
        await ctx.send("⚙️ Configuration updated")

    @cog_ext.cog_slash(
        name=cog_help["commands"]["request"]["name"],
        description=cog_help["commands"]["request"]["description"],
        options=[
            create_option(**option)
            for option in cog_help["commands"]["request"]["options"]
        ],
    )
    async def _request(self, ctx: SlashContext, feature: str) -> None:
        """Send a feature request to the developer."""
        developer = await self._bot.fetch_user(DEVELOPER_USER_ID)
        embed = (
            discord.Embed(
                title="💡 **Feature request**",
                description=feature,
                colour=discord.Colour.green(),
            )
            .set_thumbnail(url=ctx.author.avatar_url)
            .set_author(name=ctx.author.name)
            .set_footer(text=datetime.now().strftime(DATE_FORMAT).strip())
        )
        message = await developer.send(embed=embed)
        await message.pin()
        await ctx.send(
            "✅ Your suggestion has been sent to the developer, thanks for your help!",
            hidden=True,
        )

    @cog_ext.cog_slash(
        name=cog_help["commands"]["report"]["name"],
        description=cog_help["commands"]["report"]["description"],
        options=[
            create_option(**option)
            for option in cog_help["commands"]["report"]["options"]
        ],
    )
    async def _report(self, ctx: SlashContext, bug: str) -> None:
        """Send a bug report to the developer."""
        developer = await self._bot.fetch_user(DEVELOPER_USER_ID)
        embed = (
            discord.Embed(
                title="🐛 **Bug report**",
                description=bug,
                colour=discord.Colour.green(),
            )
            .set_thumbnail(url=ctx.author.avatar_url)
            .set_author(name=ctx.author.name)
            .set_footer(text=datetime.now().strftime(DATE_FORMAT).strip())
        )
        message = await developer.send(embed=embed)
        await message.pin()
        await ctx.send(
            "✅ Your bug report has been sent to the developer, thanks for your help!",
            hidden=True,
        )

    @cog_ext.cog_slash(
        name=cog_help["commands"]["search"]["name"],
        description=cog_help["commands"]["search"]["description"],
        options=[
            create_option(**option)
            for option in cog_help["commands"]["search"]["options"]
        ],
    )
    async def _search(self, ctx: SlashContext, query: str, limit: int = 3) -> None:
        """Search for a topic in the CTF write-ups index.

        Args:
            ctx: The context in which the command is being invoked under.
            query: The search query.
            limit: Number of results to show.
        """
        await ctx.defer()

        limit = limit if 0 < limit < 25 else 3
        params = {"q": query, "limit": limit}
        async with aiohttp.request(
            method="get", url=WRITEUP_INDEX_API, params=params
        ) as response:
            if response.status != 200:
                await ctx.send(f"Received a {response.status} HTTP response code.")
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
            await ctx.send(embed=embed)


def setup(bot: Bot) -> None:
    extensions = {
        ext: import_module(f"cogs.{ext}.help").cog_help for ext in os.listdir("cogs")
    }
    bot.add_cog(General(bot, extensions))
